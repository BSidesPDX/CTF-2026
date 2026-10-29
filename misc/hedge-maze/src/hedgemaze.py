#!/usr/bin/env python3
"""Shared pieces of the hedge maze challenges.

Lives beside the challenge scripts. Python puts a script's own directory at the front of
sys.path, so `import hedgemaze` resolves under inetd, run by absolute path, from any
working directory -- deployment stays "ship the directory", which it already was.

This module holds no game state and registers no commands. Command registration has to
stay in the challenge scripts, because @when registers globally at import time and the
tiers use different verb sets. Nor does any flag string live here: unlock_door reads the
flag off the door object it is handed, so each tier keeps its own.

IMPORT THIS FIRST, before adventurelib. Importing it pins the terminal size to 80x24 and
only then imports adventurelib, whose say() wraps to whatever width it sees at import.
A network player has no tty, so without the pin every line would wrap at the fallback
width and the ASCII art would be shredded.
"""
import argparse
import atexit
import json
import os
import random
import signal
import socket
import stat
import sys
import time
import uuid
from collections import deque

if 'adventurelib' in sys.modules:
    raise ImportError(
        "import hedgemaze BEFORE adventurelib. adventurelib binds get_terminal_size at "
        "its own import time, so pinning the size afterwards has no effect and every "
        "line of ASCII art wraps at the real terminal width instead of 80.")

# Pin the terminal size before adventurelib is imported anywhere.
from os import terminal_size


def _patched_get_terminal_size(fallback=(80, 24)):
    return terminal_size((80, 24))


import shutil                                                        # noqa: E402

shutil.get_terminal_size = _patched_get_terminal_size
sys.modules['shutil'].get_terminal_size = _patched_get_terminal_size

import adventurelib                                                  # noqa: E402
import numpy as np                                                   # noqa: E402
from adventurelib import Bag, Item, Room, say, when                  # noqa: E402,F401
from mazelib import Maze                                             # noqa: E402
from mazelib.generate.Prims import Prims                             # noqa: E402

# adventurelib seeds its command table with (Pattern('quit'), sys.exit) at import time,
# and @when *appends*. _handle_command stops at the first pattern that matches and
# _available_commands sorts stably by context depth, so the built-in is always reached
# first and a tier's own @when("quit") can never run -- 'quit' would kill the process
# outright while its documented siblings ('exit' in the cardinal tiers, 'q' in the
# first-person one) said goodbye first. The table is a plain module-level list, so
# dropping that one entry is all it takes to hand 'quit' back to the tiers. Identified
# by the function rather than the word: no handler of ours is sys.exit.
# agentic/check_quit.py is what catches this silently regressing.
adventurelib.commands[:] = [entry for entry in adventurelib.commands
                            if entry[1] is not sys.exit]

# Room flavour text, shared by every tier.
ROOM_TEMPLATES = [
    "Tall hedges tower above you, their leaves rustling softly.",
    "The maze walls are thick with greenery and small flowers.",
    "You stand at a junction in the hedge maze.",
    "The path here is narrow, hemmed in by dense foliage.",
    "Sunlight filters through gaps in the hedge above.",
    "A cool breeze whispers through the corridor of hedges.",
    "The scent of earth and growing things fills the air.",
    "Shadows from the towering hedges stretch across your path.",
    "Birds chirp unseen somewhere beyond the green walls.",
    "The hedges here are meticulously trimmed and maintained.",
    "Dappled light plays across the ground at your feet.",
    "The maze seems to stretch endlessly in every direction.",
]


class MazeRoom(Room):
    """A Room that remembers where it sits in the grid, for map drawing."""

    items = Bag()  # Class attribute that gets copied to instances

    def __init__(self, description, row, col):
        super().__init__(description)
        self.row = row
        self.col = col


class Object(Item):
    """Item subclass with examine behavior."""

    carriable = True

    def __init__(self, name, *aliases, description=None):
        super().__init__(name, *aliases)
        self.description = description
        self.activated_by = {}  # Hash mapping items to activation functions

    def examine(self):
        """Default examine behavior - say the description."""
        if self.description:
            say(self.description)
        else:
            say(f"There is nothing notable about the {self.name}.")

    def use_with(self, item):
        """Try to use an item with this object. Returns True if successful, False otherwise."""
        if item in self.activated_by:
            # Call the activation function for this item
            self.activated_by[item](self, item)
            return
        say(f"You don't know how to do that.")


def say_list(the_list, singular_prefix="", plural_prefix=None, empty_message=None):
    """Format a list with proper grammar using 'and' before the last item.

    Args:
        items: List of items to format
        singular_prefix: Text to prepend when there's exactly one item
        plural_prefix: Text to prepend when there are multiple items
        empty_message: Message to return when the list is empty

    Returns:
        Formatted string with proper grammar
    """
    # Convert list to strings.
    items = [str(i) for i in the_list]

    if not plural_prefix:
        plural_prefix = singular_prefix

    if len(items) == 0:
        if empty_message:
            say(empty_message)
    elif len(items) == 1:
        say(f"{singular_prefix}{items[0]}" + ".")
    elif len(items) == 2:
        say(f"{plural_prefix}{items[0]} and {items[1]}" + ".")
    else:
        # 3+ items: use Oxford comma
        item_list = ", ".join(items[:-1]) + f", and {items[-1]}"
        say(f"{plural_prefix}{item_list}" + ".")


def show_intro():
    """Print the opening narration, identical in every tier.

    Deliberately stops short of start(): the tiers do not all begin the same way -- the
    first-person one draws its opening view first -- and burying adventurelib's game
    loop in here would hide where each challenge actually starts running.
    """
    say("""
You find yourself in a lush hedge maze.
Legend says that those who can exit the maze will be rewarded
with a great treasure...
""")
    print()
    seconds = idle_seconds()
    if seconds:
        print(f"(You will be disconnected after {idle_text(seconds)} without input.)")
        print()


FLAG_FILE_ENV = 'HEDGEMAZE_FLAG_FILE'
FLAG_DIR_ENV = 'HEDGEMAZE_FLAG_DIR'


def load_flag(default, tier):
    """The flag this tier hands out, read from a file when one is configured.

    HEDGEMAZE_FLAG_FILE names one file outright and wins; HEDGEMAZE_FLAG_DIR names a
    directory holding easy.flag, medium.flag and hard.flag. With neither set the string
    compiled into the challenge is used, which is what local play and every check
    harness rely on.

    Keeping the real flags in files means they never enter git. A configured path that
    cannot be read is fatal rather than falling back: the built-in strings are
    placeholders, so quietly serving one would hand every winner a useless flag for the
    whole event.
    """
    path = os.environ.get(FLAG_FILE_ENV)
    if not path:
        directory = os.environ.get(FLAG_DIR_ENV)
        path = os.path.join(directory, f'{tier}.flag') if directory else None
    if not path:
        return default

    try:
        with open(path) as handle:
            flag = handle.read().strip()
    except OSError as err:
        raise SystemExit(f"cannot read the {tier} flag from {path}: {err}")
    if not flag:
        raise SystemExit(f"the {tier} flag file is empty: {path}")
    if '\n' in flag:
        # Two lines means somebody appended instead of overwriting. Guessing which one
        # is wanted would hand out the wrong flag for the length of the event.
        raise SystemExit(f"the {tier} flag file has more than one line: {path}")
    return flag


IDLE_ENV = 'HEDGEMAZE_IDLE_SECONDS'
IDLE_SECONDS = 300


def idle_seconds():
    """How long a player may sit at the prompt before being dropped; 0 means never.

    HEDGEMAZE_IDLE_SECONDS overrides the default. A bad value is fatal: a typo here would
    otherwise either never drop anyone or drop everyone at once.
    """
    raw = os.environ.get(IDLE_ENV)
    if raw is None:
        return IDLE_SECONDS
    try:
        seconds = int(raw)
    except ValueError:
        seconds = -1
    if seconds < 0:
        raise SystemExit(f"{IDLE_ENV} must be a whole number of seconds, not {raw!r}")
    return seconds


def idle_text(seconds):
    """The idle limit as the player is told it: '5 minutes', '1 minute', '90 seconds'."""
    if seconds % 60:
        return f'{seconds} seconds'
    minutes = seconds // 60
    return f'{minutes} minute' if minutes == 1 else f'{minutes} minutes'


def quit_game():
    """Exit the game."""
    say("Thanks for playing!")
    sys.exit(0)


# Seconds paused after each move. This is the one knob that separates a bot's cost from
# a player's: a solver pays it thousands of times over a full exploration, a human a
# couple of hundred over a whole session. Enlarging the maze does not have that property,
# it scales both alike. Challenges zero this under --verify so automated checks do not
# burn minutes on it; never deploy with it disabled.
MOVE_DELAY = 0.1


def pause_after_move():
    """Pause briefly after a move, unless the delay has been turned off."""
    if MOVE_DELAY:
        time.sleep(MOVE_DELAY)


def adjust_entrances(maze):
    """Move start and end off the boundary wall onto the passage just inside.

    mazelib's generate_entrances() puts entrances *on* the outer wall, at an even
    coordinate. Rooms live at odd coordinates, so an unadjusted entrance is not a room
    and anything stepping by 2 from it walks along the wall instead of the corridor.

    The wall-following harness needs exactly this adjustment before it can judge a maze,
    which is why it lives here rather than being spelled out in both the challenge and
    the test. Mutates and returns the maze.

    **Only mazelib-generated mazes need this.** generate_composite_maze() places its
    start and goal at odd coordinates by construction and never on the boundary, so this
    is a verified no-op there (0 changes in 200 composite mazes) and the composite tiers
    do not call it. The shared requirement is the invariant, not this function: start and
    end must be odd-coordinate room cells, or anything stepping by 2 -- movement,
    wall_follow_solver, the solvers -- walks along walls instead of corridors.
    """
    rows, cols = maze.grid.shape

    for attr in ('start', 'end'):
        r, c = getattr(maze, attr)
        if maze.grid[r][c] == 1:
            if r == 0:
                r = 1
            elif r == rows - 1:
                r = rows - 2
            if maze.grid[r][c] == 1:
                if c == 0:
                    c = 1
                elif c == cols - 1:
                    c = cols - 2
        setattr(maze, attr, (r, c))

    return maze


def build_prims_maze(size):
    """One plain Prims maze, entrances on opposite outer walls.

    mazelib puts the entrances *on* the boundary wall, so adjust_entrances nudges them
    to the passage just inside; see its docstring for why that matters.
    """
    maze = Maze()
    maze.generator = Prims(size, size)
    maze.generate()
    maze.generate_entrances()
    return adjust_entrances(maze)


def build_rooms(maze):
    """Build a MazeRoom for every passable cell and wire them into a graph.

    Identical in all three tiers, because it depends on nothing but the grid. Rooms sit
    at odd coordinates with a wall cell between them, so two rooms are linked by testing
    that cell -- which is what lets movement afterwards be plain room.exit(direction)
    and never grid arithmetic.

    Returns {(row, col): MazeRoom}. Descriptions are drawn with random.choice in grid
    order, so a seeded run reproduces the same rooms.
    """
    grid = maze.grid
    rows, cols = grid.shape

    rooms = {}
    for row in range(rows):
        for col in range(cols):
            if grid[row][col] == 0:            # passable cell
                rooms[(row, col)] = MazeRoom(random.choice(ROOM_TEMPLATES), row, col)

    for (row, col), room in rooms.items():
        if row >= 2 and grid[row - 1][col] == 0 and (row - 2, col) in rooms:
            room.north = rooms[(row - 2, col)]
        if row < rows - 2 and grid[row + 1][col] == 0 and (row + 2, col) in rooms:
            room.south = rooms[(row + 2, col)]
        if col < cols - 2 and grid[row][col + 1] == 0 and (row, col + 2) in rooms:
            room.east = rooms[(row, col + 2)]
        if col >= 2 and grid[row][col - 1] == 0 and (row, col - 2) in rooms:
            room.west = rooms[(row, col - 2)]

    return rooms


FACING_CHARS = {'north': '^', 'east': '>', 'south': 'v', 'west': '<'}

STEPS = ((-2, 0), (2, 0), (0, -2), (0, 2))   # rooms are two cells apart


def shortest_path(maze):
    """The shortest route from start to goal, as a set of grid cells to mark.

    Breadth-first over the room graph: O(rooms), so it is instant even on the hard
    tier's 121x121 grid, and the result is cached on the maze, which never changes
    during a game. Revealing the map repeatedly therefore costs nothing.

    mazelib's own ShortestPaths is not used because it enumerates *every* shortest
    path, forking a full copy of the route at each junction with no shared visited set.
    On a maze with loops -- which these deliberately have, to defeat wall-following --
    that is about 14s at 576 rooms and does not finish at all at 3,600.

    Rooms are two cells apart, so the wall cell between each pair is included too and
    the drawn line comes out continuous rather than dotted.
    """
    cached = getattr(maze, '_shortest_path', None)
    if cached is not None:
        return cached

    grid = maze.grid
    start, goal = tuple(maze.start), tuple(maze.end)
    came_from = {start: None}
    queue = deque([start])

    while queue:
        pos = queue.popleft()
        if pos == goal:
            break
        for dr, dc in STEPS:
            nxt = (pos[0] + dr, pos[1] + dc)
            if not (0 <= nxt[0] < grid.shape[0] and 0 <= nxt[1] < grid.shape[1]):
                continue
            if grid[pos[0] + dr // 2][pos[1] + dc // 2] or grid[nxt[0]][nxt[1]]:
                continue
            if nxt not in came_from:
                came_from[nxt] = pos
                queue.append(nxt)

    path = set()
    pos = goal if goal in came_from else None
    while pos is not None:
        path.add(pos)
        parent = came_from[pos]
        if parent is not None:
            path.add(((pos[0] + parent[0]) // 2, (pos[1] + parent[1]) // 2))
        pos = parent

    maze._shortest_path = path
    return path


def render_map(maze, visited, current_room, test_mode=False, facing=None):
    """Draw the magic map, either as fog-of-war or as the full solved maze.

    Kept out of the tiers because all three drew it identically bar one detail, passed
    in here: whether the player has a facing to show.

    Args:
        maze: the Maze, for .grid, .start and .end
        visited: set of (row, col) the player has stood in
        current_room: where they are now, for .row / .col
        test_mode: reveal the whole maze and the solution instead of fog-of-war
        facing: 'north'/'east'/'south'/'west' to draw the player as an arrow, or None
            to draw '@'. Only the first-person tier has a facing.
    """
    here = (current_room.row, current_room.col)
    player_char = FACING_CHARS.get(facing, '@') if facing else '@'

    if test_mode:
        print("The surface of the parchment shimmers into view.")
        print("Map legend: @ = you, X = door, K = key, * = shortest route\n")

        # Order matters: later entries override earlier ones.
        markers = {pos: "*" for pos in shortest_path(maze)}
        markers[maze.end] = "K"
        markers[maze.start] = "X"
        markers[here] = player_char        # the player outranks everything

        print_maze_grid(maze.grid, markers)
        print()
        return

    # Fog of war: every visited cell plus the ring of walls and openings around it.
    display = {}
    all_visited = visited | {here}
    rows_n, cols_n = maze.grid.shape

    for (cell_row, cell_col) in all_visited:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                r, c = cell_row + dr, cell_col + dc
                if (r, c) in display:
                    continue
                if not (0 <= r < rows_n and 0 <= c < cols_n):
                    display[(r, c)] = 'wall'          # off-grid reads as wall
                elif dr == 0 and dc == 0:
                    display[(r, c)] = 'cell'
                elif dr == 0 or dc == 0:              # orthogonal neighbour
                    if maze.grid[r][c] == 1:
                        display[(r, c)] = 'wall'
                    else:
                        # An opening: note the room beyond if we have not been there.
                        beyond = (cell_row + dr * 2, cell_col + dc * 2)
                        if (beyond not in all_visited
                                and 0 <= beyond[0] < rows_n and 0 <= beyond[1] < cols_n
                                and beyond not in display):
                            display[beyond] = 'unvisited'
                        display[(r, c)] = 'passage'
                else:                                  # diagonal corner
                    display[(r, c)] = 'wall' if maze.grid[r][c] == 1 else 'corner'

    if not display:
        print("The surface of the parchment sputters briefly.")
        return

    print("The surface of the parchment shimmers into view.")
    print("Map legend: @ = you, # = wall, ? = unknown\n")

    glyphs = {'wall': '#', 'corner': '#', 'passage': ' ', 'unvisited': '?'}
    for row in sorted({pos[0] for pos in display}):
        line = ""
        for col in sorted({pos[1] for pos in display}):
            pos = (row, col)
            if pos == here:
                line += player_char
            elif pos == maze.start and pos in visited:
                line += "X"                            # the door, once discovered
            elif pos in visited:
                line += " "
            else:
                line += glyphs.get(display.get(pos), ' ')
        print(line)
    print()


def peer_address():
    """Who is on the far end of stdin, or None when this is not a network game.

    inetd, xinetd and systemd socket activation with Accept=yes all hand the challenge a
    connected socket as fd 0, so the contestant's address is simply its peer. Played from
    a shell, fd 0 is a tty or a pipe instead and there is nobody to name; the web tool
    shows those as "local".
    """
    try:
        if not stat.S_ISSOCK(os.fstat(0).st_mode):
            return None
        # socket.socket(fileno=...) takes ownership of the fd and closes it with the
        # object, which for fd 0 would take the game's own stdin down with it. Wrap a
        # duplicate so only the duplicate is ever closed.
        fd = os.dup(0)
    except OSError:
        return None

    try:
        sock = socket.socket(fileno=fd)     # family and type are detected from the fd
    except OSError:
        os.close(fd)
        return None
    try:
        with sock:
            return _format_address(sock.family, sock.getpeername())
    except OSError:
        # An unconnected or already-shutdown socket has no peer to report.
        return None


def _format_address(family, addr):
    """A sockaddr as something readable, or None if it names nobody."""
    if family == socket.AF_INET6:
        host, port = addr[0], addr[1]
        # inetd on a dual-stack listener reports IPv4 clients as ::ffff:198.51.100.7;
        # showing the v4 address they actually used is far more use to an organiser.
        if host.startswith('::ffff:') and '.' in host:
            return f'{host[7:]}:{port}'
        return f'[{host}]:{port}'
    if family == socket.AF_INET:
        return f'{addr[0]}:{addr[1]}'
    if family == getattr(socket, 'AF_UNIX', None):
        if isinstance(addr, bytes):
            addr = addr.decode('utf-8', 'replace')
        if addr.startswith('\0'):
            addr = '@' + addr[1:]       # abstract namespace, written the way ss(8) does
        # An unnamed peer is a socketpair, which is how plenty of supervisors and test
        # harnesses hand over stdin. It names nobody, so this is not a network game and
        # reporting a bare "unix" would look like a connection that is not there.
        return f'unix:{addr}' if addr else None
    return str(addr)


class Telemetry:
    """Records a run to disk so organisers can watch it, and never gets in the way.

    Enabled by setting HEDGEMAZE_TELEMETRY to a directory; unset means this does
    nothing at all, so local play and the solver harnesses are unaffected.

    Writes three files under <dir>/active/<uuid>/ and renames that directory into
    <dir>/ended/ when the game finishes. See agentic/TELEMETRY.md for the data model.

    Every operation is wrapped: on the first failure the whole thing switches off for
    the life of the process and the game plays on. A challenge that dies because a disk
    filled would be far worse than one nobody can watch.
    """

    ENV_VAR = 'HEDGEMAZE_TELEMETRY'

    @classmethod
    def start(cls, state):
        """Build a recorder, or None when telemetry is not configured."""
        root = os.environ.get(cls.ENV_VAR)
        if not root:
            return None
        try:
            return cls(root, state)
        except Exception:
            return None

    def __init__(self, root, state):
        self.uuid = str(uuid.uuid4())
        self.live = True
        self.count = 0
        # How the run ended, once it does. Set by won(); otherwise finish() says why.
        self.outcome = None
        self.dir = os.path.join(root, 'active', self.uuid)
        self.ended_dir = os.path.join(root, 'ended', self.uuid)
        os.makedirs(self.dir, exist_ok=True)
        os.makedirs(os.path.join(root, 'ended'), exist_ok=True)

        maze = state.maze
        self._write_json('meta.json', {
            'uuid': self.uuid,
            'tier': os.path.basename(sys.argv[0]),
            'pid': os.getpid(),
            'started': time.time(),
            # The contestant's address when this run came in over the network, and None
            # when it did not -- the web tool renders that as "local".
            'peer': peer_address(),
            # Every run seeds explicitly, so this replays the exact maze a contestant
            # saw: challenge-doomed.py --seed <this>.
            'seed': state.args.seed,
            'height': int(maze.grid.shape[0]),
            'width': int(maze.grid.shape[1]),
            # Rooms the player can actually reach, so the overview can show progress as
            # visited/total without re-counting the grid on every poll. Not
            # len(state.rooms): build_rooms also makes a MazeRoom for each wall-gap cell
            # at even coordinates, and movement steps by 2 from an odd start, so those
            # are never reachable.
            'rooms': sum(1 for r, c in state.rooms if r % 2 and c % 2),
            # One string per row, '1' = wall. Compact and trivially readable in JS.
            'grid': [''.join('1' if cell else '0' for cell in row)
                     for row in maze.grid],
            'start': list(map(int, maze.start)),
            'goal': list(map(int, maze.end)),
            'shortest': sorted(list(p) for p in shortest_path(maze)),
            # Where everything lies before the player touches it. status.json carries
            # only the *current* layout, so replaying a finished run from the event log
            # needs this as the starting point -- otherwise the scrubber shows the key
            # already in hand at step one.
            'items': self._item_positions(state),
        })
        self._events = open(os.path.join(self.dir, 'events.jsonl'), 'a', buffering=1)
        self.record(state, 'begin')

    # -- the game calls these -------------------------------------------------------

    def moved(self, state):
        self.record(state, 'move')

    def turned(self, state):
        self.record(state, 'turn')

    def item_taken(self, state, item):
        self.record(state, 'take', item=item.tkey)

    def item_dropped(self, state, item):
        self.record(state, 'drop', item=item.tkey)

    def won(self, state):
        # Remembered so the final status says 'won' rather than a bare 'ended': the
        # index view wants to tell a solved run from an abandoned one at a glance.
        self.outcome = 'won'
        self.record(state, 'win')

    def record(self, state, event, **extra):
        """Append one event and refresh the status summary."""
        if not self.live:
            return
        try:
            self.count += 1
            line = {'t': round(time.time(), 3), 'e': event,
                    'pos': list(state.here), 'step': state.step_count}
            if state.player_facing:
                line['facing'] = state.player_facing
            line.update(extra)
            # A short line written in one call under O_APPEND is atomic, so a reader
            # tailing this file never sees half of one.
            self._events.write(json.dumps(line, separators=(',', ':')) + '\n')
            self._write_json('status.json', self._status(state, 'active'))
        except Exception:
            self.disable()

    def finish(self, state, status='ended'):
        """Mark the run over and move it out of active/. Safe to call more than once.

        A win recorded earlier takes precedence over the caller's guess, since the
        process exits through the same path either way.
        """
        if not self.live:
            return
        try:
            self._write_json('status.json',
                             self._status(state, self.outcome or status))
            self._events.close()
            os.rename(self.dir, self.ended_dir)
        except Exception:
            pass
        self.live = False

    @staticmethod
    def _item_positions(state):
        """item -> [row, col], or 'inventory'. JSON wants lists, not tuples."""
        return {k: (v if v == 'inventory' else list(v))
                for k, v in state.item_at.items()}

    def _status(self, state, status):
        """The summary the index view reads, so it never has to parse the event log."""
        return {
            'status': status,
            'pos': list(state.here),
            'facing': state.player_facing,
            'step': state.step_count,
            'visited': len(state.visited),
            'items': self._item_positions(state),
            'last_seen': round(time.time(), 3),
            'events': self.count,
        }

    def disable(self):
        """Give up on telemetry for the rest of this process."""
        self.live = False
        try:
            self._events.close()
        except Exception:
            pass

    def _write_json(self, name, payload):
        """Write a whole file atomically, so a reader never catches it half-written."""
        path = os.path.join(self.dir, name)
        tmp = path + '.tmp'
        with open(tmp, 'w') as handle:
            json.dump(payload, handle, separators=(',', ':'))
        os.replace(tmp, path)


class GameState:
    """Everything that changes while the game is played.

    Holding this on an object rather than in module globals is what lets the shared
    command handlers live here: they mutate `state.current_room` instead of declaring
    `global current_room`, so they no longer have to be defined in the same module as
    the variables they touch.
    """

    def __init__(self, flag, width, loops=True, provide_map=False,
                 custom_movement=False):
        """Build a tier.

        loops is the difficulty lever. A maze without them is perfect, so the
        right-hand rule walks straight to the goal; adding them is what forces a player
        to actually search. It selects the generator, and so also what width means:
        with loops it is the width of each of the eight outer mazes tiled around the
        island (see generate_composite_maze), without them the side of one plain NxN
        Prims maze.

        custom_movement=True suppresses the shared cardinal verb set, for a tier that
        registers its own controls instead -- the first-person one does.
        """
        # Options are parsed here rather than by the caller because --seed has to take
        # effect before the maze is generated, and the maze is generated below.
        self.args = parse_args()
        self.test_mode = self.args.test

        self.maze = (generate_composite_maze(width, self.test_mode) if loops
                     else build_prims_maze(width))

        # Refuse to hand out a maze whose key cannot be reached from the door. Nothing
        # checked this before, so an unwinnable maze would have looked to the player
        # exactly like a hard one -- they would simply never find the key. The BFS is
        # O(rooms) and its result is cached on the maze, so --test and telemetry reuse
        # it and this costs nothing.
        if not shortest_path(self.maze):
            raise RuntimeError(
                f"generated an unsolvable maze: no route from {tuple(self.maze.start)} "
                f"to {tuple(self.maze.end)}. This is a generation bug, not bad luck; "
                f"reproduce it with --seed {self.args.seed}.")

        self.rooms = build_rooms(self.maze)
        self.current_room = self.start_room
        self.inventory = Bag()
        self.visited = {tuple(self.maze.start)}
        self.step_count = 0
        # Only the first-person tier tracks a heading, and it sets one after
        # construction because the value derives from the maze. None means render_map
        # draws the player as @ rather than an arrow.
        self._player_facing = None
        # Where each item is: a room coordinate, or 'inventory' once picked up. Kept up
        # to date by place/take/drop so telemetry never has to search the rooms for one.
        self.item_at = {}

        self.magic_map, self.skeleton_key, self.door = make_items(self, flag)

        # Where things start. The door always guards the way out. The map is a feature
        # of the easy tier (provide_map) and a debug aid everywhere else. The key waits
        # at the goal unless --test brings it within reach.
        self.place(self.door, self.start_room)
        if provide_map or self.test_mode:
            self.place(self.magic_map, self.start_room)
        self.place(self.skeleton_key,
                   self.start_room if self.test_mode else self.goal_room)

        self.telemetry = Telemetry.start(self)
        if self.telemetry:
            self._arm_exit_hooks()
        self._arm_idle_timer()

        if not custom_movement:
            register_cardinal_commands(self)

    def _arm_exit_hooks(self):
        """Make sure the session leaves active/ however the process ends.

        atexit covers quitting, winning and the client disconnecting -- EOF returns from
        adventurelib's loop and the process exits normally. SIGTERM and SIGHUP are what
        a container stop or a dropped connection look like. SIGKILL cannot be caught, so
        some sessions will be left behind in active/; the web tool spots those by
        checking whether the recorded pid is still alive.
        """
        atexit.register(lambda: self.telemetry.finish(self))

        def bail(signum, frame):
            self.telemetry.finish(self, status='disconnected')
            sys.exit(0)

        for sig in (signal.SIGTERM, signal.SIGHUP):
            try:
                signal.signal(sig, bail)
            except (ValueError, OSError):
                pass        # not the main thread, or the platform disagrees

    def _arm_idle_timer(self):
        """Drop a player who sits at the prompt for idle_seconds() without typing.

        Every connection is a process holding a maze, so an abandoned one fills a game
        slot until something ends it. adventurelib calls prompt() just before every
        input(), so wrapping it restarts the clock each time the player is asked for a
        command. Telemetry records the run as 'idle'.
        """
        seconds = idle_seconds()
        if not seconds:
            return

        def expire(signum, frame):
            print(f"\n\nYou stand still so long that the hedges grow over the path.\n"
                  f"(No input for {idle_text(seconds)}: disconnecting.)")
            if self.telemetry:
                self.telemetry.finish(self, status='idle')
            sys.exit(0)

        try:
            signal.signal(signal.SIGALRM, expire)
        except (ValueError, OSError):
            return          # not the main thread, or the platform disagrees
        ask = adventurelib.prompt

        def prompt():
            signal.alarm(seconds)
            return ask()
        adventurelib.prompt = prompt

    # -- things that change, each routed through one place so telemetry sees them ----

    @property
    def player_facing(self):
        return self._player_facing

    @player_facing.setter
    def player_facing(self, facing):
        self._player_facing = facing
        # Guarded because the hard tier sets an initial facing before Telemetry exists.
        if getattr(self, 'telemetry', None):
            self.telemetry.turned(self)

    def enter(self, room):
        """Move the player into a room and record the visit."""
        self.current_room = room
        self.step_count += 1
        self.visited.add((room.row, room.col))
        if self.telemetry:
            self.telemetry.moved(self)

    def place(self, item, room):
        """Put an item in a room, at setup."""
        room.items.add(item)
        self.item_at[item.tkey] = (room.row, room.col)

    def take(self, item):
        """Move an item from the current room into the player's hands.

        Takes the object rather than its name: Bag.take() matches on a name string, and
        the callers have already resolved one to an object.
        """
        self.current_room.items.remove(item)      # Bag is a set; remove by identity
        self.inventory.add(item)
        self.item_at[item.tkey] = 'inventory'
        if self.telemetry:
            self.telemetry.item_taken(self, item)

    def drop(self, item):
        """Put a carried item down in the current room."""
        self.inventory.remove(item)
        self.current_room.items.add(item)
        self.item_at[item.tkey] = self.here
        if self.telemetry:
            self.telemetry.item_dropped(self, item)

    @property
    def here(self):
        """Where the player is, as a grid coordinate."""
        return (self.current_room.row, self.current_room.col)

    @property
    def start_room(self):
        """Where the player begins, and where the locked door stands."""
        return self.rooms[tuple(self.maze.start)]

    @property
    def goal_room(self):
        """Where the key waits, unless --test moved it within reach."""
        return self.rooms[tuple(self.maze.end)]

    @property
    def at_start(self):
        return self.here == tuple(self.maze.start)


class Map(Object):
    """The magic map.

    Reads the player's position from the GameState it was built for rather than from
    module globals, because current_room and player_facing are rebound as the game runs
    -- a value captured at construction would go stale after the first step. That is
    what lets one Map serve every tier.
    """

    def __init__(self, *aliases, state=None, **kwargs):
        super().__init__(*aliases, **kwargs)
        self.state = state

    def examine(self):
        render_map(self.state.maze, self.state.visited, self.state.current_room,
                   test_mode=self.state.test_mode,
                   facing=self.state.player_facing)


def make_items(state, flag):
    """Create the three objects every tier uses, wired together.

    Called by GameState, which then places them. Keeping the wiring here means a tier
    cannot forget the parts that are not cosmetic: the door being uncarriable, its flag,
    and the unlock handler.

    Returns (magic_map, skeleton_key, door).
    """
    magic_map = Map('a glowing parchment', 'parchment', 'map', state=state)
    skeleton_key = Object(
        'a shiny skeleton key', 'key', 'skeleton key',
        description="A beautiful skeleton key made of tarnished silver.")
    door = Object(
        'an ornate wood door', 'door', 'lock',
        description="A huge ornately carved door. Glowing crystal shards ring a "
                    "deep-set key hole.")
    door.carriable = False

    # unlock_door is handed the door, and reads both off it, so no flag lives here and
    # it needs no globals.
    door.flag = flag
    door.state = state
    door.activated_by[skeleton_key] = unlock_door

    # Short stable names for telemetry. Item.name is the player-facing text, which is
    # long and could be reworded; these are what the web view keys on.
    magic_map.tkey, skeleton_key.tkey, door.tkey = 'map', 'key', 'door'

    return magic_map, skeleton_key, door


def register_cardinal_commands(state):
    """Register the verb set the two cardinal tiers share.

    Called by GameState unless custom_movement=True, never on import: @when writes into
    adventurelib's global command table, so merely importing this module must not hand
    `north` and `take` to the first-person tier, which has its own controls.

    The handlers close over `state`, which is why they can live here at all -- they
    rebind attributes on it rather than module globals.
    """

    @when("look")
    @when("l")
    def look_around():
        """Look at your surroundings."""
        say(state.current_room.description)

        say_list(state.current_room.items, singular_prefix="Here you see ")

        exits = state.current_room.exits()
        say_list(
            exits,
            singular_prefix="There is a path leading away to the ",
            plural_prefix="There are paths leading away to the ",
            empty_message="You seem to be trapped! (This shouldn't happen. Please hang up and call back later.)"
        )
        if not exits:
            raise RuntimeError(f"No available exits from position {state.here}")

    @when("go DIRECTION")
    @when("north", direction='north')
    @when("n", direction='north')
    @when("south", direction='south')
    @when("s", direction='south')
    @when("east", direction='east')
    @when("e", direction='east')
    @when("west", direction='west')
    @when("w", direction='west')
    def go(direction):
        """Move in a given direction."""
        next_room = state.current_room.exit(direction)

        if next_room:
            state.enter(next_room)
            say(f"You move {direction}...\n")
            look_around()
        else:
            say(f"You can't go {direction} - there's a hedge wall blocking the way.")
        pause_after_move()

    @when("take ITEM")
    @when("get ITEM")
    def take_item(item):
        """Take an item from the current room."""
        obj = state.current_room.items.find(item)
        if obj:
            if not obj.carriable:
                say(f"You can't pick up {obj}.")
                return
            state.take(obj)
            say(f"You take {obj}.")
        else:
            say(f"There's no {item} here.")

    @when("drop ITEM")
    def drop_item(item):
        """Drop an item in the current room."""
        obj = state.inventory.find(item)
        if obj:
            state.drop(obj)
            say(f"You drop {obj}.")
        else:
            say(f"You don't have that.")

    @when("inventory")
    @when("i")
    def show_inventory():
        """Show what you're carrying."""
        say_list(state.inventory,
            singular_prefix="You are carrying ",
            plural_prefix="You are carrying ",
            empty_message="You aren't carrying anything."
        )

    @when("examine ITEM")
    @when("look at ITEM")
    @when("look ITEM")
    @when("l ITEM")
    @when("read ITEM")
    def examine_item(item):
        """Examine an item in your inventory."""
        # You can look at what you're holding.
        obj = state.inventory.find(item)
        if not obj:
            obj = state.current_room.items.find(item)
            # You can look at objects in the room that don't need to be carried.
            if not obj or obj.carriable:
                say(f"You don't have that.")
                return

        obj.examine()

    @when("use SRC with DST")
    def use(src, dst):
        item = state.inventory.find(src)
        if not item:
            say(f"You don't have that.")
            return
        target = state.inventory.find(dst)
        if not target:
            target = state.current_room.items.find(dst)
            if not target:
                say(f"You can't find that.")
                return
            if target.carriable:
                say(f"You're not carrying {target}.")
                return
        if item == target:
            say(f"That seems difficult.")
            return

        target.use_with(item)

    @when("help")
    def show_help_custom():
        """Show available commands."""
        print("""
Available commands:
  north, south, east, west - Move in that direction
  look - Look around the room
  take/get <item> - Pick up an item
  drop <item> - Drop an item
  inventory - Show what you're carrying
  examine/look/read <item> - Examine an item in your inventory
  use <item> with <item> - Use an item
  help - Show this help
  exit - Exit the game
""")

    @when("exit")
    @when("quit")
    def quit_command():
        """Exit the game."""
        quit_game()


def parse_args(description='Hedge Maze CTF Challenge'):
    """Parse the options every tier shares, and apply the process-wide ones.

    Seeding and the move delay take effect here because they are global; GameState
    reads `.test` back off the result.

    None of these options belong on a deployed instance. --test hands the player the
    key and the solution, --seed makes every connection generate the same maze, and
    --verify removes the delay that is the main brake on automated solving.
    """
    global MOVE_DELAY

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        '--test', action='store_true',
        help='Enable test mode: grants the magic map (revealing the full solved '
             'maze), places the key in the starting room, and prints maze details '
             'at generation. Never deploy with this.')
    parser.add_argument('--seed', type=int,
                        help='Replay a specific maze. Every run already picks and '
                             'records a seed, so pass one from a session you want back.')
    parser.add_argument('--verify', action='store_true',
                        help='Remove the per-move delay, so automated solver checks do '
                             'not spend minutes sleeping. Never deploy with this.')
    args = parser.parse_args()

    if args.seed is None:
        # Always seed explicitly, even when nobody asked for a particular maze. Drawing
        # the seed and recording it makes every run reproducible after the fact, which
        # turns "a solve failed and I cannot repeat it" into passing one number back.
        # It costs a little entropy -- 2**32 possible mazes rather than the full RNG
        # state space -- which is an easy trade for four billion distinct mazes.
        args.seed = random.randrange(2 ** 32)

    # Maze.set_seed seeds both random and numpy.random. Seeding only the stdlib module
    # is not enough: mazelib's generators shuffle with numpy.random, so --seed used to
    # leave maze generation genuinely random and reproduced nothing.
    Maze.set_seed(args.seed)

    if args.verify:
        MOVE_DELAY = 0
        # Announce the seed so an intermittent solver failure can be replayed. Only
        # under --verify, which is local automation and never deployed, and only on
        # stderr, because stdout is the game protocol the solvers parse.
        #
        # A deployed challenge stays silent on both streams: under inetd all three
        # descriptors are the same socket, so anything written to either reaches the
        # player, and a player holding the seed can regenerate the maze offline and
        # walk the solution. Deployed runs record it in telemetry instead, which is
        # organiser-side and already holds the full grid.
        print(f"maze seed: {args.seed}  (replay with --seed {args.seed})",
              file=sys.stderr, flush=True)

    return args


def unlock_door(lock, key):
    """Unlock the door when activated with the correct key.

    The flag and the state both ride on the door itself (make_items sets them) rather
    than being read from module globals, which is what lets this stay a plain shared
    function: activated_by hands us the door as `lock`, so the tier's own flag arrives
    with it and no flag string is ever stored in this module.
    """
    flag = getattr(lock, 'flag', None)
    if flag is None:
        raise RuntimeError(
            f"{lock} has no .flag - set door.flag = FLAG in the challenge script")

    # Record the win before printing, so a session that ends here is not filed as a
    # plain quit. The flag itself is never written to telemetry.
    state = getattr(lock, 'state', None)
    if state is not None and state.telemetry:
        state.telemetry.won(state)

    say("You slide the key into the lock and turn. It clicks, and the door slowly swings open revealing a sign that reads:")
    print()
    print(f"          {flag}")
    print()
    quit_game()


def print_maze_grid(grid, markers={}):
    """
    Print a maze grid with Unicode box-drawing characters.

    Args:
        grid: numpy array representing the maze (1=wall, 0=passage)
        markers: dict of (row, col) -> character to display special positions
    """

    # Box-drawing characters indexed by bitfield: [N=8, S=4, E=2, W=1]
    BOX_CHARS = [
        "·",  # 0000: no connections
        "─",  # 0001: west
        "─",  # 0010: east
        "─",  # 0011: east-west
        "│",  # 0100: south
        "┐",  # 0101: south-west
        "┌",  # 0110: south-east
        "┬",  # 0111: south-east-west
        "│",  # 1000: north
        "┘",  # 1001: north-west
        "└",  # 1010: north-east
        "┴",  # 1011: north-east-west
        "│",  # 1100: north-south
        "┤",  # 1101: north-south-west
        "├",  # 1110: north-south-east
        "┼",  # 1111: north-south-east-west
    ]

    for row in range(grid.shape[0]):
        line = ""
        for col in range(grid.shape[1]):
            pos = (row, col)
            if pos in markers:
                line += markers[pos]
            elif grid[row][col] == 1:
                # Build bitfield for wall connections
                north = (row > 0 and grid[row-1][col] == 1)
                south = (row < grid.shape[0]-1 and grid[row+1][col] == 1)
                east = (col < grid.shape[1]-1 and grid[row][col+1] == 1)
                west = (col > 0 and grid[row][col-1] == 1)

                bitfield = (north << 3) | (south << 2) | (east << 1) | west
                line += BOX_CHARS[bitfield]
            else:
                line += " "
        print(line)

def open_passage_horizontal(grid, boundary_col, row_start, row_end):
    """
    Open a horizontal passage through a vertical wall at boundary_col.
    The wall is at an even column coordinate (boundary_col).
    We need passages on odd row coordinates, with passages at boundary_col-1 and boundary_col+1.
    """
    valid_rows = []
    for passage_row in range(row_start, row_end, 2):
        # passage_row must be odd (a passage coordinate)
        # Check that cells on both sides of the wall are passages
        left_col = boundary_col - 1  # Should be odd (passage)
        right_col = boundary_col + 1  # Should be odd (passage)

        if (grid[passage_row][left_col] == 0 and
            grid[passage_row][right_col] == 0):
            valid_rows.append(passage_row)

    if len(valid_rows) == 0:
        print("\nERROR: No available hallways - printing full map:")
        markers = {(r, boundary_col): ("!" if grid[r][boundary_col] == 1 else "?")
                   for r in range(row_start, row_end + 1)}
        print_maze_grid(grid, markers)
        print()
        raise RuntimeError(f"No available hallways along column {boundary_col} rows {row_start}..{row_end}")
    passage_row = random.choice(valid_rows)
    grid[passage_row][boundary_col] = 0

def open_passage_vertical(grid, boundary_row, col_start, col_end):
    """
    Open a vertical passage through a horizontal wall at boundary_row.
    The wall is at an even row coordinate (boundary_row).
    We need passages on odd column coordinates, with passages at boundary_row-1 and boundary_row+1.
    """
    valid_cols = []
    for passage_col in range(col_start, col_end, 2):
        # passage_col must be odd (a passage coordinate)
        # Check that cells on both sides of the wall are passages
        top_row = boundary_row - 1  # Should be odd (passage)
        bottom_row = boundary_row + 1  # Should be odd (passage)

        if (grid[top_row][passage_col] == 0 and
            grid[bottom_row][passage_col] == 0):
            valid_cols.append(passage_col)

    if len(valid_cols) == 0:
        print("\nERROR: No available hallways - printing full map:")
        markers = {(boundary_row, c): ("!" if grid[boundary_row][c] == 1 else "?")
                   for c in range(col_start, col_end + 1)}
        print_maze_grid(grid, markers)
        print()
        raise RuntimeError(f"No available hallways along row {boundary_row} columns {col_start}..{col_end}")
    passage_col = random.choice(valid_cols)
    grid[boundary_row][passage_col] = 0


def generate_composite_maze(mini_maze_width, test_mode=False):
    """
    Generate a composite maze with 8 outer mazes around a central island.
    The island is surrounded by a hallway and has one entrance on each side.
    This defeats wall-following algorithms.

    mini_maze_width sets the width of each outer maze; everything else derives from it.
    The medium tier uses 8, the hard tier 20. See agentic/sweep_hard_width.py for how
    that scales rooms, solution length and solver cost.

    **Start and goal come out odd-coordinate and off the boundary already**, so callers
    do not need adjust_entrances() the way mazelib-generated mazes do. The goal forces
    parity (`if island_center % 2 == 0: island_center += 1`, and the +/-2 offsets keep
    it); the start uses 1 or grid_size - 2 on one axis -- both odd, since grid_size is
    odd -- and randrange(..., 2) from an odd base on the other. Preserve that if you
    change placement: anything stepping by 2 walks along walls otherwise.
    """
    island_maze_width = mini_maze_width - 2  # Island is 2 cells smaller

    # Generate 8 outer mazes and 1 island maze (no entrances)
    outer_mazes = []
    for i in range(8):
        m = Maze()
        m.generator = Prims(mini_maze_width, mini_maze_width)
        m.generate()
        outer_mazes.append(m)

    island_maze = Maze()
    island_maze.generator = Prims(island_maze_width, island_maze_width)
    island_maze.generate()

    # Calculate grid dimensions
    # An NxN maze becomes (2N+1)x(2N+1) cells in the grid
    mini_cell_size = 2 * mini_maze_width + 1  # 8x8 -> 17x17
    island_cell_size = 2 * island_maze_width + 1  # 6x6 -> 13x13

    # Layout: 3x3 grid of mazes with overlapping walls
    # Total size: 3 mazes - 2 overlapping walls
    grid_size = mini_cell_size * 3 - 2
    composite_grid = np.ones((grid_size, grid_size), dtype=np.int8)

    # Place the 8 outer mazes in a 3x3 grid (skipping center)
    # Positions: (row, col) in 3x3 grid
    positions = [(0,0), (0,1), (0,2), (1,0), (1,2), (2,0), (2,1), (2,2)]
    maze_stride = mini_cell_size - 1  # Overlap by 1 cell

    for idx, (grid_row, grid_col) in enumerate(positions):
        maze = outer_mazes[idx]
        # Calculate offset with overlapping walls
        row_offset = grid_row * maze_stride
        col_offset = grid_col * maze_stride

        # Copy maze into composite grid
        for r in range(mini_cell_size):
            for c in range(mini_cell_size):
                composite_grid[row_offset + r][col_offset + c] = maze.grid[r][c]

    # Create hallway around center and place island
    center_start = maze_stride  # Start of center section
    center_size = mini_cell_size  # Size of center section

    # Hallway passages are 1 cell in from the edges
    hallway_outer = center_start + 1
    hallway_inner = center_start + center_size - 2

    # Create hallway by clearing a rectangle
    for r in range(hallway_outer, hallway_inner + 1):
        composite_grid[r][hallway_outer] = 0  # Left hallway
        composite_grid[r][hallway_inner] = 0  # Right hallway
    for c in range(hallway_outer, hallway_inner + 1):
        composite_grid[hallway_outer][c] = 0  # Top hallway
        composite_grid[hallway_inner][c] = 0  # Bottom hallway

    # Place island in center
    island_offset = center_start + 2
    for r in range(island_cell_size):
        for c in range(island_cell_size):
            composite_grid[island_offset + r][island_offset + c] = island_maze.grid[r][c]

    # Connect adjacent outer mazes by opening random passages
    # Horizontal connections in top and bottom rows
    h_connections = [((0,0), (0,1)), ((0,1), (0,2)), ((2,0), (2,1)), ((2,1), (2,2))]
    for (r1, c1), (r2, c2) in h_connections:
        boundary_col = (c1 + 1) * maze_stride
        row_start = r1 * maze_stride + 1
        row_end = r1 * maze_stride + mini_cell_size - 2
        open_passage_horizontal(composite_grid, boundary_col, row_start, row_end)

    # Vertical connections in left and right columns
    v_connections = [((0,0), (1,0)), ((0,2), (1,2)), ((1,0), (2,0)), ((1,2), (2,2))]
    for (r1, c1), (r2, c2) in v_connections:
        boundary_row = (r1 + 1) * maze_stride
        col_start = c1 * maze_stride + 1
        col_end = c1 * maze_stride + mini_cell_size - 2
        open_passage_vertical(composite_grid, boundary_row, col_start, col_end)

    # Connect middle row mazes to center hallway
    # The walls are BETWEEN the maze and hallway
    open_passage_vertical(composite_grid, hallway_outer - 1, hallway_outer + 2, hallway_inner - 1)  # Top
    open_passage_vertical(composite_grid, hallway_inner + 1, hallway_outer + 2, hallway_inner - 1)  # Bottom
    open_passage_horizontal(composite_grid, hallway_outer - 1, hallway_outer + 2, hallway_inner - 1)  # Left
    open_passage_horizontal(composite_grid, hallway_inner + 1, hallway_outer + 2, hallway_inner - 1)  # Right

    # Open passages from island to hallway (one on each of 4 sides)
    island_wall_start = island_offset
    island_wall_end = island_offset + island_cell_size - 1
    # Passages are at odd coordinates, so start searching from island_wall_start + 1 (first passage inside)
    passage_start = island_wall_start + 1
    passage_end = island_wall_end - 1
    open_passage_vertical(composite_grid, island_wall_start, passage_start, passage_end)  # North
    open_passage_vertical(composite_grid, island_wall_end, passage_start, passage_end)  # South
    open_passage_horizontal(composite_grid, island_wall_start, passage_start, passage_end)  # West
    open_passage_horizontal(composite_grid, island_wall_end, passage_start, passage_end)  # East

    # Place goal in center 3x3 of island (using odd coordinates for passages)
    # Island interior passages span from island_offset+1 to island_offset+island_cell_size-2
    # Center of island passages
    island_center = island_offset + island_cell_size // 2
    if island_center % 2 == 0:
        island_center += 1  # Make sure center is odd (a passage)
    goal_row = random.choice([island_center - 2, island_center, island_center + 2])
    goal_col = random.choice([island_center - 2, island_center, island_center + 2])

    # Place start on random edge of one of the corner 8x8 mazes
    # 8 possible outer edges: NW-top, NW-left, NE-top, NE-right, SW-bottom, SW-left, SE-bottom, SE-right
    outer_edges = [
        ('NW', 'north'),  # (0,0) top edge
        ('NW', 'west'),   # (0,0) left edge
        ('NE', 'north'),  # (0,2) top edge
        ('NE', 'east'),   # (0,2) right edge
        ('SW', 'south'),  # (2,0) bottom edge
        ('SW', 'west'),   # (2,0) left edge
        ('SE', 'south'),  # (2,2) bottom edge
        ('SE', 'east'),   # (2,2) right edge
    ]
    corner_name, edge_side = random.choice(outer_edges)

    # Map corner names to grid positions
    corner_positions = {
        'NW': (0, 0),
        'NE': (0, 2),
        'SW': (2, 0),
        'SE': (2, 2),
    }
    corner_row, corner_col = corner_positions[corner_name]

    # Calculate the bounds of this corner maze
    maze_row_start = corner_row * maze_stride + 1
    maze_row_end = corner_row * maze_stride + mini_cell_size - 2
    maze_col_start = corner_col * maze_stride + 1
    maze_col_end = corner_col * maze_stride + mini_cell_size - 2

    # Place start on the selected outer edge
    if edge_side == 'north':
        start_row = 1
        start_col = random.randrange(maze_col_start, maze_col_end, 2)
    elif edge_side == 'south':
        start_row = grid_size - 2
        start_col = random.randrange(maze_col_start, maze_col_end, 2)
    elif edge_side == 'east':
        start_row = random.randrange(maze_row_start, maze_row_end, 2)
        start_col = grid_size - 2
    else:  # west
        start_row = random.randrange(maze_row_start, maze_row_end, 2)
        start_col = 1

    # Create maze object to return
    result = Maze()
    result.grid = composite_grid
    result.start = (start_row, start_col)
    result.end = (goal_row, goal_col)
    result.start_edge = edge_side  # Store which edge the start is on

    if test_mode:
        print(f"Generated composite maze: {grid_size}x{grid_size}")
        print(f"Start: {result.start}, Goal: {result.end}, Edge: {edge_side}")

    return result
