#!/usr/bin/env python3
"""
Hedge Maze CTF Challenge: Easy
Navigate through a procedurally generated maze to find the flag!
"""
# This import MUST come before adventurelib: it pins the terminal size to 80
# columns, and adventurelib binds get_terminal_size at its own import time.
import hedgemaze
from adventurelib import *

# Maze configuration
MAZE_WIDTH = 10  # one plain 10x10 maze
# A placeholder: the real flag lives in easy.flag under HEDGEMAZE_FLAG_DIR, never in
# git. See hedgemaze.load_flag.
FLAG = hedgemaze.load_flag("pdx{Place_Holder}", "easy")

# Map provided, maze has no loops: easy tier.
state = hedgemaze.GameState(FLAG, MAZE_WIDTH, loops=False, provide_map=True)

if __name__ == "__main__":
    hedgemaze.show_intro()
    start(help=False)  # Start the adventurelib game loop (disable default help)
