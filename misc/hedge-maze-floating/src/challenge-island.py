#!/usr/bin/env python3
"""
Hedge Maze CTF Challenge: Medium
Navigate through a procedurally generated maze to find the flag!
"""
# Shared with the other tiers; see hedgemaze.py. This import MUST come before
# adventurelib: it pins the terminal size to 80 columns, and adventurelib binds
# get_terminal_size at its own import time.
import hedgemaze

from adventurelib import *

# Maze configuration
# A placeholder: the real flag lives in medium.flag under HEDGEMAZE_FLAG_DIR, never in
# git. See hedgemaze.load_flag.
FLAG = hedgemaze.load_flag("pdx{Place_Holder}", "medium")

# MAZE_WIDTH is the width of each of the eight outer mazes.
MAZE_WIDTH = 8

# No provided map, generated maze has loops: medium tier.
state = hedgemaze.GameState(FLAG, MAZE_WIDTH)

if __name__ == "__main__":
    hedgemaze.show_intro()
    start(help=False)  # Start the adventurelib game loop (disable default help)
