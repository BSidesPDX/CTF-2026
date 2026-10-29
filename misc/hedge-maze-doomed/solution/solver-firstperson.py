#!/usr/bin/env python3
"""Solver for the first-person hedge maze (challenge-doomed.py).

Driven entirely by what the game draws on screen. It knows nothing about how the maze
is generated, where the goal sits, or how big the grid is; it reads frames, builds its
own map by dead reckoning, and explores until it finds the key.

How the screen is read
----------------------
Each frame is 25 rows of 77 columns: a border, then three 25-column panes showing what
is to the left, ahead, and to the right. Braille characters are drifting clouds and are
stripped as decoration. The hedge texture uses only '%', '#', '*', '|' and space, which
makes the two objects in the game trivially separable from it.

  ahead is open   the corridor recedes to a vanishing point, so the middle band of the
                  centre pane is mostly empty (ink 0.427) rather than a flat wall face
                  (ink >= 0.800).
  side is open    a hedge wall recedes as a wedge that fills the top and bottom corners
                  of its pane; an opening leaves them blank. The bottom band is
                  cloud-free, so it is the reliable test: ink 0.000 vs 0.520.
  an object       scenery is drawn from five characters and nothing else: ' #%*|'. Add
                  '<>', which mark the vanishing point of an open corridor, and any
                  other character on screen must belong to something the maze put
                  there. The solver never learns what the key or the door look like --
                  it sees "that is not hedge", presses 'e', and reads what the game
                  says back.

Every threshold was measured against ground truth taken from the game's own behaviour,
never from its source: a blocked move prints no new frame, which labels the view ahead,
and a character's share of frames separates scenery from objects. See
agentic/derive_view_rules.py, derive_side_rules.py and derive_alphabet.py.

Wire protocol note
------------------
The prompt is '> ', but the open-corridor art contains '> <', so reading until '> '
stops halfway through a frame. A reply is complete when it ends at a prompt and holds a
whole number of 25-line frames.
"""
import argparse
import os
import re
import sys
from collections import deque

from pwn import context, log, process, remote

HERE = os.path.dirname(os.path.abspath(__file__))


def resolve_challenge(path):
    """Find a challenge script whether named from the cwd or from beside this solver.

    Lets the solver be run by absolute path from anywhere, rather than only from the
    challenge directory.
    """
    if os.path.exists(path):
        return os.path.abspath(path)
    beside = os.path.join(HERE, path)
    if os.path.exists(beside):
        return beside
    raise SystemExit(f"challenge script not found: {path}")

FRAME_H = 25
FRAME_RE = re.compile(r'^\|.{75}\|$')
BRAILLE = re.compile(r'[⠀-⣿]')
PANES = ((1, 26), (26, 51), (51, 76))          # left, centre, right

FORWARD_INK_MAX = 0.60      # centre rows 9-17:  passage 0.427 | hedge >= 0.800
SIDE_INK_MAX = 0.26         # side rows 18-24:   passage 0.000 | hedge 0.520
SCENERY = set(' #%*|<>')    # hedges, borders, and the corridor vanishing point

# Headings are relative to wherever we started; north is simply "the way we first faced".
NORTH, EAST, SOUTH, WEST = range(4)
DELTA = {NORTH: (0, -1), EAST: (1, 0), SOUTH: (0, 1), WEST: (-1, 0)}
FLAG_RE = re.compile(r'[A-Za-z0-9_]+\{[^}]+\}')
SEED_RE = re.compile(r'maze seed: (\d+)')


def step_from(pos, direction):
    dx, dy = DELTA[direction]
    return (pos[0] + dx, pos[1] + dy)


class Screen:
    """One rendered frame, and the questions worth asking of it."""

    def __init__(self, rows):
        self.rows = rows
        self.panes = [[BRAILLE.sub(' ', r[lo:hi]) for r in rows] for lo, hi in PANES]

    @staticmethod
    def ink(pane, r0, r1):
        cells = ''.join(pane[r0:r1])
        return sum(c != ' ' for c in cells) / max(1, len(cells))

    @property
    def forward_open(self):
        return self.ink(self.panes[1], 9, 18) < FORWARD_INK_MAX

    @property
    def left_open(self):
        return self.ink(self.panes[0], 18, 25) < SIDE_INK_MAX

    @property
    def right_open(self):
        return self.ink(self.panes[2], 18, 25) < SIDE_INK_MAX

    @property
    def has_object(self):
        """Something is on screen that hedges cannot draw."""
        for pane in self.panes:
            for row in pane:
                if any(ch not in SCENERY for ch in row):
                    return True
        return False


class Game:
    """Keystrokes in, screens out."""

    def __init__(self, target, python=None, fast=False, seed=None):
        if ':' in target:
            host, port = target.rsplit(':', 1)
            self.io = remote(host, int(port))
        else:
            # sys.executable is already the venv interpreter running this solver, so
            # the challenge gets the same one wherever we were invoked from.
            # --verify drops the game's per-move sleep, which otherwise dominates
            # the wall clock of a full exploration. --seed pins the maze so a failure
            # can be reproduced. Local runs only: a deployed instance offers neither.
            argv = [python or sys.executable, '-u', resolve_challenge(target)]
            argv += ['--verify'] if fast else []
            argv += ['--seed', str(seed)] if seed is not None else []
            self.io = process(argv)
        self.alive = True
        self.commands = 0
        self.last_text = self._read()

        # Under --verify the challenge announces the maze it built. pwntools merges the
        # child's stderr into this stream, so it arrives here and would otherwise be
        # consumed silently as protocol. Report it: an intermittent failure is only
        # debuggable if the run says which maze it was on.
        self.seed = None
        found = SEED_RE.search(self.last_text)
        if found:
            self.seed = int(found.group(1))
            log.info(f'maze seed {self.seed}  (replay with --seed {self.seed})')

    def _read(self, timeout=60):
        """Read one reply.

        A reply ends at a prompt holding a whole number of frames. The awkward case is
        an empty reply: a refused move prints nothing at all, which looks exactly like
        a frame that has not finished arriving. Before believing in a frameless reply,
        wait briefly to see whether one is still on the way -- mistaking a successful
        move for a refused one desyncs the map for good.
        """
        buf = ''
        while True:
            try:
                chunk = self.io.recv(timeout=timeout)
            except EOFError:
                self.alive = False
                break
            if not chunk:
                break
            buf += chunk.decode('utf-8', 'replace')
            frames = sum(1 for l in buf.splitlines() if FRAME_RE.match(l))
            if not (buf.endswith('> ') and frames % FRAME_H == 0):
                continue
            if frames == 0:
                try:
                    trailing = self.io.recv(timeout=0.3)
                except EOFError:
                    trailing = b''
                    self.alive = False
                if trailing:
                    buf += trailing.decode('utf-8', 'replace')
                    continue
            break
        return buf

    def send(self, cmd):
        if not self.alive:
            return ''
        self.commands += 1
        try:
            self.io.sendline(cmd.encode())
        except EOFError:
            self.alive = False
            return ''
        self.last_text = self._read()
        return self.last_text

    def close(self):
        try:
            self.io.close()
        except Exception:
            pass


def screen_of(text):
    rows = [l for l in text.splitlines() if FRAME_RE.match(l)]
    return Screen(rows[-FRAME_H:]) if len(rows) >= FRAME_H else None


class Solver:
    def __init__(self, target, fast=False, seed=None):
        self.game = Game(target, fast=fast, seed=seed)
        self.pos = (0, 0)
        self.heading = NORTH
        self.exits = {}          # pos -> set of open headings
        self.visited = set()
        self.key_taken = False
        self.door_heading = None
        self.flag = None

    # -- reading the world -------------------------------------------------

    def record(self, screen):
        """Fold what a frame shows into the map, in absolute headings."""
        open_dirs = self.exits.setdefault(self.pos, set())
        if screen.forward_open:
            open_dirs.add(self.heading)
        if screen.left_open:
            open_dirs.add((self.heading - 1) % 4)
        if screen.right_open:
            open_dirs.add((self.heading + 1) % 4)
        self.visited.add(self.pos)

    def look(self):
        screen = screen_of(self.game.send('l'))
        if screen:
            self.record(screen)
        return screen

    # -- moving ------------------------------------------------------------

    def turn_to(self, direction):
        while self.heading != direction:
            delta = (direction - self.heading) % 4
            cmd = 'd' if delta in (1, 2) else 'a'
            self.game.send(cmd)
            self.heading = (self.heading + (1 if cmd == 'd' else -1)) % 4

    def walk(self, direction):
        """Move one room, turning first unless reversing into somewhere already mapped.

        's' reverses without turning, which saves two commands but leaves a blind spot:
        arriving still faces the way we came, so the frame shows left/forward/right of
        *that* facing and the direction we were travelling ends up behind us, unseen.
        record() only ever adds exits, so an unseen exit is indistinguishable from a
        wall -- the room looks like a dead end in exactly the direction we were headed,
        and everything beyond it becomes unreachable.

        So 's' is only safe into a room already mapped. Anywhere new, turn and walk
        forward, which shows three sides and gets the fourth from arriving.
        """
        reversing = direction == (self.heading + 2) % 4
        if reversing and step_from(self.pos, direction) in self.visited:
            text, moved_dir = self.game.send('s'), direction
        else:
            self.turn_to(direction)
            text, moved_dir = self.game.send('w'), direction
        screen = screen_of(text)
        if self.check_flag(text):
            return None
        if screen is None:
            # No frame drawn means the move was refused: that way is a hedge.
            self.exits.setdefault(self.pos, set()).discard(direction)
            return None
        self.pos = step_from(self.pos, moved_dir)
        self.exits.setdefault(self.pos, set()).add((moved_dir + 2) % 4)
        self.record(screen)
        return screen

    def route(self, goal):
        """Shortest path of headings through rooms we have already stood in."""
        if self.pos == goal:
            return []
        prev = {self.pos: None}
        queue = deque([self.pos])
        while queue:
            cur = queue.popleft()
            for d in self.exits.get(cur, ()):
                nxt = step_from(cur, d)
                if nxt in prev or (nxt not in self.visited and nxt != goal):
                    continue
                prev[nxt] = (cur, d)
                if nxt == goal:
                    path = []
                    while prev[nxt] is not None:
                        cur, d = prev[nxt]
                        path.append(d)
                        nxt = cur
                    return path[::-1]
                queue.append(nxt)
        return None

    def travel(self, goal):
        path = self.route(goal)
        if path is None:
            return False
        for direction in path:
            if self.walk(direction) is None and self.flag is None:
                return False
        return True

    # -- objectives --------------------------------------------------------

    def check_flag(self, text):
        if 'pdx{' in text or 'hackers{' in text:
            match = FLAG_RE.search(text)
            if match:
                self.flag = match.group(0)
                return True
        return False

    def interact(self):
        """Press 'e' and let the game say what we were looking at."""
        text = self.game.send('e')
        self.check_flag(text)
        low = text.lower()
        if 'take' in low:
            return 'key'
        if 'missing the key' in low:
            return 'door'
        return None

    def find_door(self):
        """Spin on the spot. Whatever answers 'e' with a complaint is the door.

        Always completes the full turn rather than stopping at the door: the sweep is
        also how the starting room learns its fourth wall, since a single view only
        ever shows three, and we have not arrived from anywhere yet.
        """
        for _ in range(4):
            screen = screen_of(self.game.last_text) or self.look()
            if screen and screen.has_object:
                what = self.interact()
                if what == 'door':
                    self.door_heading = self.heading
                elif what == 'key':
                    self.key_taken = True
            self.game.send('a')
            self.heading = (self.heading - 1) % 4
            self.look()

    def frontier(self):
        """Nearest room with an unexplored exit: returns (room, heading) or None."""
        prev = {self.pos: None}
        queue = deque([self.pos])
        while queue:
            cur = queue.popleft()
            for d in sorted(self.exits.get(cur, ())):
                nxt = step_from(cur, d)
                if nxt not in self.visited:
                    return cur, d
                if nxt not in prev:
                    prev[nxt] = cur
                    queue.append(nxt)
        return None

    def solve(self, max_commands=200000):
        screen = screen_of(self.game.last_text) or self.look()
        if screen is None:
            log.error('no frame from the game; is this the first-person tier?')
            return False
        self.record(screen)
        self.find_door()
        start = self.pos
        log.info(f'door lies to heading {self.door_heading} from the start')

        while self.game.commands < max_commands and self.game.alive:
            screen = screen_of(self.game.last_text)
            if screen and screen.has_object and not self.key_taken:
                if self.interact() == 'key':
                    self.key_taken = True
                    log.success(f'key found at {self.pos} '
                                f'after {self.game.commands} commands, '
                                f'{len(self.visited)} rooms seen')
                    break
                self.look()

            target = self.frontier()
            if target is None:
                log.warning('explored everything reachable without finding the key')
                return False
            room, direction = target
            if room != self.pos and not self.travel(room):
                # Do not blame the frontier edge: whichever step actually failed has
                # already been struck from the map by walk(). Discarding this one too
                # would delete a real passage, which on a small maze can strand the
                # search with rooms still unexplored.
                continue
            if self.walk(direction) is None:
                continue
            if len(self.visited) % 200 == 0:
                log.info(f'{len(self.visited)} rooms, {self.game.commands} commands')

        if not self.key_taken:
            return False

        log.info(f'walking the key back to the door at {start}')
        if not self.travel(start):
            log.error('lost the way back to the door')
            return False
        self.turn_to(self.door_heading)
        text = self.game.send('e')
        self.check_flag(text)
        return self.flag is not None


def main():
    parser = argparse.ArgumentParser(
        description='Solve the first-person hedge maze from its rendered view alone')
    parser.add_argument('challenge', nargs='?', default='challenge-doomed.py',
                        help='challenge script, or host:port (default: challenge-doomed.py)')
    parser.add_argument('--max-commands', type=int, default=200000)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--fast', action='store_true',
                        help="pass --verify to a locally spawned challenge, "
                             "removing its per-move delay")
    parser.add_argument('--seed', type=int,
                        help="pass --seed to a locally spawned challenge, pinning the "
                             "maze so a failure can be reproduced")
    args = parser.parse_args()

    context.log_level = 'debug' if args.verbose else 'info'
    # The challenge picks and announces its own seed under --verify, which --fast turns
    # on; --seed here is for replaying one it reported.
    solver = Solver(args.challenge, fast=args.fast, seed=args.seed)
    try:
        if solver.solve(args.max_commands):
            log.success('=' * 46)
            log.success(f'FLAG: {solver.flag}')
            log.success('=' * 46)
            return 0
        log.failure(f'no flag. {len(solver.visited)} rooms, '
                    f'{solver.game.commands} commands')
        return 1
    finally:
        solver.game.close()


if __name__ == '__main__':
    sys.exit(main())
