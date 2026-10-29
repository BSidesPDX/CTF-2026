#!/usr/bin/env python3
"""
Solver for challenge-island.py using simple DFS exploration with backtracking.
"""

import os
import re
import sys
from pwn import *

# Direction mappings
OPPOSITE = {'n': 's', 's': 'n', 'e': 'w', 'w': 'e'}
DIR_TO_DELTA = {'n': (-1, 0), 's': (1, 0), 'e': (0, 1), 'w': (0, -1)}
SEED_RE = re.compile(r'maze seed: (\d+)')

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

class MazeSolver:
    def __init__(self, challenge_script='challenge-island.py', fast=False, seed=None):
        self.fast = fast
        self.seed = seed          # replaced by what the challenge reports, if it does
        self.challenge_script = challenge_script
        self.proc = None
        self.visited = set()
        self.current_pos = (0, 0)
        self.path_stack = []  # Stack of directions taken to get here
        self.has_key = False
        self.door_unlocked = False
        self.room_connections = {}  # Maps (row, col) -> set of available directions
        self.key_path = []  # Path taken to reach the key

    def start_game(self):
        """Start the challenge process."""
        # Check if challenge_script is a host:port or a file
        if ':' in self.challenge_script:
            # Network connection
            host, port = self.challenge_script.split(':', 1)
            port = int(port)
            log.info(f"Connecting to {host}:{port}")
            self.proc = remote(host, port)
        else:
            # Local file. sys.executable is already the venv interpreter running this
            # solver, so the challenge gets the same one wherever we were invoked from.
            # --verify drops the game's per-move sleep, --seed pins the maze so a
            # failure can be reproduced. Local runs only.
            argv = [sys.executable, resolve_challenge(self.challenge_script)]
            argv += ['--verify'] if self.fast else []
            argv += ['--seed', str(self.seed)] if self.seed is not None else []
            self.proc = process(argv)
            log.info(f"Game started: {self.challenge_script}")

        # Under --verify the challenge announces the maze it built. pwntools merges the
        # child's stderr into this stream, so it arrives here and would otherwise be
        # consumed silently as protocol. Report it: an intermittent failure is only
        # debuggable if the run says which maze it was on.
        intro = self.proc.recvuntil(b'> ').decode('utf-8', 'replace')
        found = SEED_RE.search(intro)
        if found:
            self.seed = int(found.group(1))
            log.info(f"maze seed {self.seed}  (replay with --seed {self.seed})")

        self.proc.sendline(b'look')
        output = self.proc.recvuntil(b'> ').decode()
        return self.parse_output(output)

    def parse_output(self, output):
        """Parse game output to extract available directions and items."""
        available_dirs = []
        has_key = False
        found_flag = False
        flag_text = None

        # Debug: show the raw output
        log.debug(f"Raw output:\n{output}")

        if 'pdx{' in output:
            found_flag = True
            match = re.search(r'pdx\{[^}]+\}', output)
            if match:
                flag_text = match.group(0)

        paths_match = re.search(r'[Tt]here (?:is a path|are paths) leading away to the (.+?)\.', output)
        if paths_match:
            dirs_text = paths_match.group(1)
            log.debug(f"Parsed directions text: '{dirs_text}'")
            # Handle both ", and " and " and "
            dirs_text = dirs_text.replace(', and ', ', ')
            dirs_text = dirs_text.replace(' and ', ', ')
            for direction in dirs_text.split(', '):
                direction = direction.strip()
                if direction in ['north', 'south', 'east', 'west']:
                    available_dirs.append(direction[0])
                else:
                    log.warning(f"Unrecognized direction: '{direction}'")

        log.debug(f"Available directions: {available_dirs}")

        if 'key' in output.lower():
            has_key = True

        return {
            'directions': available_dirs,
            'has_key': has_key,
            'found_flag': found_flag,
            'flag': flag_text
        }

    def move(self, direction):
        """Move in a direction and return the new state."""
        log.info(f">>> {direction}")
        self.proc.sendline(direction.encode())
        output = self.proc.recvuntil(b'> ').decode()
        state = self.parse_output(output)

        if "can't go" in output.lower():
            return False, state

        # Update position and path
        dr, dc = DIR_TO_DELTA[direction]
        self.current_pos = (self.current_pos[0] + dr, self.current_pos[1] + dc)
        self.path_stack.append(direction)

        return True, state

    def backtrack(self):
        """Move back one step."""
        if not self.path_stack:
            return False

        last_move = self.path_stack.pop()
        opposite_dir = OPPOSITE[last_move]

        log.info(f">>> {opposite_dir} (backtracking)")
        self.proc.sendline(opposite_dir.encode())
        self.proc.recvuntil(b'> ')

        # Update position
        dr, dc = DIR_TO_DELTA[opposite_dir]
        self.current_pos = (self.current_pos[0] + dr, self.current_pos[1] + dc)

        return True

    def print_map(self):
        """Print the explored map with walls."""
        if not self.visited:
            return

        import numpy as np

        # Find bounds of rooms
        rows = [pos[0] for pos in self.visited]
        cols = [pos[1] for pos in self.visited]
        min_row, max_row = min(rows), max(rows)
        min_col, max_col = min(cols), max(cols)

        # Build grid: each room at (r,c) becomes cell (2*r+1, 2*c+1) in grid
        # Walls are at even coordinates
        height = 2 * (max_row - min_row + 1) + 1
        width = 2 * (max_col - min_col + 1) + 1
        grid = np.ones((height, width), dtype=np.int8)
        unexplored_markers = {}  # Track unexplored passage entrances

        # Place rooms and connections
        for room_pos in self.visited:
            r, c = room_pos
            gr = 2 * (r - min_row) + 1
            gc = 2 * (c - min_col) + 1
            grid[gr][gc] = 0  # Room is a passage

            # Add passages to connected rooms
            if room_pos in self.room_connections:
                for direction in self.room_connections[room_pos]:
                    dr, dc = DIR_TO_DELTA[direction]
                    next_room = (r + dr, c + dc)
                    if next_room in self.visited:
                        # Open wall between rooms
                        wall_r = gr + (1 if direction == 's' else -1 if direction == 'n' else 0)
                        wall_c = gc + (1 if direction == 'e' else -1 if direction == 'w' else 0)
                        grid[wall_r][wall_c] = 0
                    else:
                        # Mark unexplored passage entrance
                        wall_r = gr + (1 if direction == 's' else -1 if direction == 'n' else 0)
                        wall_c = gc + (1 if direction == 'e' else -1 if direction == 'w' else 0)
                        unexplored_markers[(wall_r, wall_c)] = "?"

        # Build path positions using saved key path
        path_positions = set()
        pos = (0, 0)
        path_to_use = self.key_path if self.key_path else self.path_stack
        for direction in path_to_use:
            dr, dc = DIR_TO_DELTA[direction]
            pos = (pos[0] + dr, pos[1] + dc)
            path_positions.add(pos)

        # Build markers
        markers = {}
        # Find key position (end of key_path)
        key_pos = None
        if self.key_path:
            pos = (0, 0)
            for direction in self.key_path:
                dr, dc = DIR_TO_DELTA[direction]
                pos = (pos[0] + dr, pos[1] + dc)
            key_pos = pos

        for room_pos in self.visited:
            r, c = room_pos
            gr = 2 * (r - min_row) + 1
            gc = 2 * (c - min_col) + 1
            if room_pos == key_pos:
                markers[(gr, gc)] = "K"
            elif room_pos == self.current_pos:
                markers[(gr, gc)] = "@"
            elif room_pos == (0, 0):
                markers[(gr, gc)] = "S"
            elif room_pos in path_positions:
                markers[(gr, gc)] = "*"

        # Print grid with box-drawing characters
        BOX_CHARS = [
            "█", "─", "─", "─", "│", "┐", "┌", "┬",
            "│", "┘", "└", "┴", "│", "┤", "├", "┼",
        ]

        log.info("\n=== Explored Map ===")
        for row in range(grid.shape[0]):
            line = ""
            for col in range(grid.shape[1]):
                pos = (row, col)
                if pos in markers:
                    line += markers[pos]
                elif pos in unexplored_markers:
                    line += unexplored_markers[pos]
                elif grid[row][col] == 1:
                    # Wall - use box-drawing character
                    north = (row > 0 and grid[row-1][col] == 1)
                    south = (row < grid.shape[0]-1 and grid[row+1][col] == 1)
                    east = (col < grid.shape[1]-1 and grid[row][col+1] == 1)
                    west = (col > 0 and grid[row][col-1] == 1)
                    bitfield = (north << 3) | (south << 2) | (east << 1) | west
                    line += BOX_CHARS[bitfield]
                else:
                    line += " "
            log.info(line)
        log.info("")

    def explore(self):
        """Explore the maze using depth-first search."""
        state = self.start_game()
        self.visited.add(self.current_pos)
        self.room_connections[self.current_pos] = set(state['directions'])

        moves = 0
        max_moves = 5000

        while moves < max_moves:
            # Check if we found the flag
            if state['found_flag']:
                log.success("="*50)
                log.success("FLAG FOUND!")
                log.success("="*50)
                if state['flag']:
                    log.success(f"FLAG: {state['flag']}")
                return True

            # Check if we found the key and haven't picked it up yet
            if state['has_key'] and not self.has_key:
                log.info(f"Found key at {self.current_pos}!")
                # Try to take the key
                log.info(">>> take key")
                self.proc.sendline(b'take key')
                output = self.proc.recvuntil(b'> ').decode()
                log.info(f"Took key")
                self.has_key = True

                # Save the path to the key before backtracking
                self.key_path = self.path_stack.copy()
                log.info(f"Path to key has {len(self.key_path)} steps")

                # Update state after taking key
                self.proc.sendline(b'look')
                output = self.proc.recvuntil(b'> ').decode()
                state = self.parse_output(output)

                # Now backtrack to the start (0, 0) where the door is
                log.info(f"Backtracking to start (0, 0) with the key...")
                while self.current_pos != (0, 0):
                    if not self.backtrack():
                        log.error("Failed to backtrack to start!")
                        break
                    moves += 1

                # Get state at the door
                self.proc.sendline(b'look')
                output = self.proc.recvuntil(b'> ').decode()
                state = self.parse_output(output)

                # Use the key with the door
                log.info(">>> use key with door")
                self.proc.sendline(b'use key with door')
                try:
                    # The game might exit after this, so use recvall with timeout
                    output = self.proc.recvall(timeout=2).decode()
                except:
                    output = self.proc.recvrepeat(timeout=2).decode()

                log.info(f"Output after using key:\n{output}")
                state = self.parse_output(output)
                self.door_unlocked = True

                # Check if this revealed the flag
                if state['found_flag']:
                    self.print_map()
                    log.success("="*50)
                    log.success("FLAG FOUND after using key!")
                    log.success("="*50)
                    if state['flag']:
                        log.success(f"FLAG: {state['flag']}")
                    return True

                # If flag in output but not parsed, show output
                if 'pdx{' in output:
                    self.print_map()
                    log.success("="*50)
                    log.success("FLAG FOUND in output!")
                    log.success("="*50)
                    match = re.search(r'pdx\{[^}]+\}', output)
                    if match:
                        log.success(f"FLAG: {match.group(0)}")
                        return True

            # Find unvisited directions
            unvisited_dirs = []
            for d in state['directions']:
                dr, dc = DIR_TO_DELTA[d]
                next_pos = (self.current_pos[0] + dr, self.current_pos[1] + dc)
                if next_pos not in self.visited:
                    unvisited_dirs.append(d)

            if unvisited_dirs:
                # Try first unvisited direction
                direction = unvisited_dirs[0]
                success, new_state = self.move(direction)

                if success:
                    self.visited.add(self.current_pos)
                    self.room_connections[self.current_pos] = set(new_state['directions'])
                    log.debug(f"At {self.current_pos}, connections: {new_state['directions']}")
                    state = new_state
                    moves += 1

                    if moves % 50 == 0:
                        log.info(f"Explored {moves} moves, visited {len(self.visited)} rooms, depth {len(self.path_stack)}")
            else:
                # No unvisited directions - backtrack
                if not self.backtrack():
                    log.info("Fully explored - cannot backtrack further")
                    break
                moves += 1

                # Get state after backtracking
                self.proc.sendline(b'look')
                output = self.proc.recvuntil(b'> ').decode()
                state = self.parse_output(output)

        log.warning(f"Exploration ended after {moves} moves, visited {len(self.visited)} rooms")
        self.print_map()
        return False

    def cleanup(self):
        """Clean up the game process."""
        if self.proc:
            try:
                self.proc.sendline(b'quit')
                self.proc.close()
            except:
                try:
                    self.proc.kill()
                except:
                    pass

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Solve hedge maze challenges')
    parser.add_argument('challenge', nargs='?', default='challenge-island.py',
                        help='Challenge script to solve or host:port to connect to (default: challenge-island.py)')
    parser.add_argument('--fast', action='store_true',
                        help='pass --verify to a locally spawned challenge, '
                             'removing its per-move delay')
    parser.add_argument('--seed', type=int,
                        help='pass --seed to a locally spawned challenge, pinning the '
                             'maze so a failure can be reproduced')
    args = parser.parse_args()

    context.log_level = 'info'
    # The challenge picks and announces its own seed under --verify, which --fast turns
    # on; --seed here is for replaying one it reported.
    solver = MazeSolver(args.challenge, fast=args.fast, seed=args.seed)
    try:
        success = solver.explore()
        if not success:
            log.warning("Failed to find the flag in this maze.")
            solver.print_map()
    finally:
        solver.cleanup()

if __name__ == '__main__':
    main()
