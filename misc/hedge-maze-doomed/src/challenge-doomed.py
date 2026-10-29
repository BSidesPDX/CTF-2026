#!/usr/bin/env python3
"""
Hedge Maze CTF Challenge: Hard
Navigate through a procedurally generated maze to find the flag!
"""
import sys, os
import random

unbuf_stdin = os.fdopen(sys.stdin.fileno(), 'rb', buffering=0)

# Shared with the other tiers; see hedgemaze.py. This import MUST come before
# adventurelib: it pins the terminal size to 80 columns, and adventurelib binds
# get_terminal_size at its own import time.
import hedgemaze

from adventurelib import *

# Maze configuration
# A placeholder: the real flag lives in hard.flag under HEDGEMAZE_FLAG_DIR, never in
# git. See hedgemaze.load_flag.
FLAG = hedgemaze.load_flag("pdx{Place_Holder}", "hard")

# MAZE_WIDTH is the width of each of the eight outer mazes. 20 gives 3,600 rooms and an
# 84-move solution, about 4x medium. 32 was tried and rejected: it scales the automated
# solve and the human playthrough by the same ~2.5x, so it costs legitimate players as
# much as it costs a bot. Raising the per-move sleep is the knob that changes that ratio.
MAZE_WIDTH = 20

# Direction utilities
DIRECTIONS = ['north', 'east', 'south', 'west']

# No provided map, generated maze has loops. Renders first-person: hard tier.
# custom_movement=True suppresses the shared cardinal verbs; this tier registers its own
# w/a/s/d controls below.
state = hedgemaze.GameState(FLAG, MAZE_WIDTH, custom_movement=True)
TEST_MODE = state.test_mode

# The player starts facing away from the door, which sits on the outer edge behind them.
# Set after construction because it derives from the maze GameState just built.
state.player_facing = DIRECTIONS[(DIRECTIONS.index(state.maze.start_edge) + 2) % 4]

m = state.maze   # the handlers below read m.start_edge when drawing the door

def turn_left(facing):
    """Rotate 90 degrees counter-clockwise."""
    idx = DIRECTIONS.index(facing)
    return DIRECTIONS[(idx - 1) % 4]

def turn_right(facing):
    """Rotate 90 degrees clockwise."""
    idx = DIRECTIONS.index(facing)
    return DIRECTIONS[(idx + 1) % 4]

def get_left_dir(facing):
    """Get the direction to the left."""
    return turn_left(facing)

def get_right_dir(facing):
    """Get the direction to the right."""
    return turn_right(facing)

# ASCII art tiles for perspective first-person view (25x25 each, 75 chars total width)
# Tile system: Left (25 chars) + Center (25 chars) + Right (25 chars)
tile_width = 25
tile_height = 25
screen_width = tile_width * 3
screen_height = tile_height

# Center tile with passage - vanishing point
TILE_CENTER_OPEN = [
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "%%#                   *%#",
    "%%#*%#             %%#*%#",
    "%%#*%#%#*       #%#*%#*%#",
    "%%#*%#%#%%#> <*%%%#*%#*%#",
    "%%#*%#%#%       %%#*%#*%%",
    "%%#*%#             %%#*%#",
    "%%#                   *%#",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
]


# Left tile with wall - hedge receding toward vanishing point (right side)
TILE_LEFT_WALL = [
    "                         ",
    "%                        ",
    "%%#*                     ",
    "%%#*%#%                  ",
    "*%#*%#%%#%               ",
    "%%#*%*%%#%##%            ",
    "%%#*%#%%#%##%*%#         ",
    "%%#*%#%%#%##%*%#%%#      ",
    "%%#*%#%%#%##%*%*%%#*%#   ",
    "%%#*%#%%#%##%*%#%%#*%#*%#",
    "%%#*%#%*#%##%*%#%%#*%#*%%",
    "%%#*%#%%#%##%*%#%%#*%#*%#",
    "%%#*%#%%#%##%*%#%%#*%#*%%",
    "%%#*%#%%#%##%*%#*%#*%#*%#",
    "%%#*%#%%#%##%*%#%%#*%#*%%",
    "%%#*%#%%#%##%*%#%%#*%#*%#",
    "%%#*%#%%#%##%*%#%%#*%#*%%",
    "%%#*%#%%#%##%*%#%%#*%#*%#",
    "%%#*%#%%#%##%*%#%*#*%#   ",
    "%%#*%*%%#%##%*%#%%#      ",
    "%%#*%#%%#%##%*%#         ",
    "%%#*%#%%*%##%            ",
    "*%#*%#%%#%               ",
    "%%#*%#%                  ",
    "%%#*                     ",
]

# Left tile with passage - flat hedge edge
TILE_LEFT_OPEN = [
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "%##*%#%*#%*#%*%#%*#*%#*%%",
    "%%#*%#%*#%*#%*%#%*#*%#*%#",
    "%%#*%#%*#%*#%*%#%*#*%##%%",
    "%%#*%#%*#%*#%*%#%*#*%#*%#",
    "%%#*%*%*#%*#%*%#*%#*%#*%%",
    "%%#*%#%*#%*#%*%#%*#*%#*%#",
    "%%#*##%*#%*#%*%#%*#*%#*%%",
    "%%#*##%*#%*#%*%#%*#*%#*%%",
    "%%#*##%*#%*#%*%#%*#*%#*%%",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
]

# Center tile with wall - flat hedge wall ahead
TILE_CENTER_WALL = [
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "%##*%#%*#%*#%*%#%*#*%#*%%",
    "%%#*%*%*#%*#%*%#%*#*%#*%#",
    "%%#*%#%*#%*#%*%#%*#*%#*%%",
    "%%#*%#%*#%*#%%%#%*#*%#*%#",
    "%%#*%#%*#%*#%*%#%%#*%#*%%",
    "%%#*%#%*#%*#%*%#%*#*%##%#",
    "%%#*##%*#%*#%*%#%*#*%#*%%",
    "%%#*##%*#%*#%*%#%*#*%#*%%",
    "%%#*##%*#%*#%*%#%*#*%#*%%",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
    "                         ",
]

KEY = [
    "    .---.                   ",
    "   /XXXX|\\________________  ",
    "  (X()XX|X________XXX_XXX_) ",
    "   \\XXXX|/        |X| |X|   ",
    "    `---'          \"-\" |_|   ",
]

DOOR = [
    "     ______     ",
    "  ,-'X;XX!X`-.  ",
    " /X:XX!XX:XX.X\\ ",
    "|_X;X_:_XX;X.X|  ",
    ")|X.X:)(.XX!XX| ",
    "|\"XXX(##)XX_XX| ",
    "|XX:XX;`'X(_)X(  ",
    ")|X.XX.X:XX:XX|  ",
    "|__.-_;----.__|",
]

CLOUD = [
    "      ⠠⠠⡰⠐⠕⢀⣄           ",
    "   ⡀⣠⠶⡊⠃XXXX⢈⡁⢀⡀⡀       ",
    "  ⣄⠇⠁XXXXXXX⠠⠎XX⠈⠑⣄     ",
    " ⠂⠋XXXXXXXXXXXXXXX⠠⠟⠕⠦⡀ ",
    "⡁XXXXXXXXXXXXXXXXXXXX⢡⠇ ",
    "⠁⠐⠐⠄XXXX⢀XXXXXXXXX⣀⡀⠖⠛  ",
    "   ⠙⠁⠄⠆⡸⠓⡆⠠XX⢀⡞⠤⠠⠐⠁     ",
    "          ⠈⠉ ⠁          ",
]

# Sky views will be populated at startup
SKY_VIEWS = {
    'north': [],
    'east': [],
    'south': [],
    'west': []
}

# Wind system
wind_direction = 'north'  # Current wind direction

def flip_braille_horizontal(char):
    """Flip a single Braille character horizontally (left-right mirror)."""
    if char == ' ' or char == 'X':
        return char

    # Braille Unicode range: U+2800 to U+28FF
    # Braille pattern: dots are numbered 1-8 in this layout:
    # 1 4
    # 2 5
    # 3 6
    # 7 8
    # Horizontal flip swaps: 1↔4, 2↔5, 3↔6, 7↔8

    code = ord(char)
    if code < 0x2800 or code > 0x28FF:
        return char

    dots = code - 0x2800

    # Extract individual dots (bits 0-7)
    d1 = dots & 0x01
    d2 = dots & 0x02
    d3 = dots & 0x04
    d4 = dots & 0x08
    d5 = dots & 0x10
    d6 = dots & 0x20
    d7 = dots & 0x40
    d8 = dots & 0x80

    # Swap left and right columns
    new_dots = (d4 >> 3) | (d5 >> 3) | (d6 >> 3) | (d1 << 3) | (d2 << 3) | (d3 << 3) | d7 | d8

    return chr(0x2800 + new_dots)

def flip_braille_vertical(char):
    """Flip a single Braille character vertically (top-bottom mirror)."""
    if char == ' ' or char == 'X':
        return char

    # Braille pattern: dots are numbered 1-8 in this layout:
    # 1 4
    # 2 5
    # 3 6
    # 7 8
    # Vertical flip swaps: 1↔3, 2↔7, 4↔6, 5↔8

    code = ord(char)
    if code < 0x2800 or code > 0x28FF:
        return char

    dots = code - 0x2800

    # Extract individual dots
    d1 = dots & 0x01
    d2 = dots & 0x02
    d3 = dots & 0x04
    d4 = dots & 0x08
    d5 = dots & 0x10
    d6 = dots & 0x20
    d7 = dots & 0x40
    d8 = dots & 0x80

    # Swap top and bottom
    new_dots = (d3 >> 2) | (d7 >> 5) | (d1 << 2) | (d6 >> 2) | (d8 >> 3) | (d4 << 2) | (d2 << 5) | (d5 << 3)

    return chr(0x2800 + new_dots)

def flip_cloud_horizontal(cloud):
    """Flip cloud horizontally, remapping Braille characters."""
    flipped = []
    for line in cloud:
        flipped_line = ''.join(flip_braille_horizontal(char) for char in reversed(line))
        flipped.append(flipped_line)
    return flipped

def flip_cloud_vertical(cloud):
    """Flip cloud vertically, remapping Braille characters."""
    flipped = []
    for line in reversed(cloud):
        flipped_line = ''.join(flip_braille_vertical(char) for char in line)
        flipped.append(flipped_line)
    return flipped

def composite_sprite(scene, sprite, x, y, transparent_char=' ', solid_char='X'):
    """
    Composite a sprite onto a scene at position (x, y).

    Args:
        scene: List of strings representing the scene (modified in-place)
        sprite: List of strings representing the sprite to composite
        x: Horizontal offset (can be negative for partial rendering)
        y: Vertical offset (can be negative for partial rendering)
        transparent_char: Character in sprite that is transparent (default ' ')
        solid_char: Character in sprite that gets replaced with transparent_char after compositing (default 'X')
                    Use None to disable this behavior

    The sprite is drawn onto the scene:
    - transparent_char pixels don't modify the scene
    - solid_char pixels (if specified) are drawn, then converted to transparent_char
    - All other characters are drawn as-is
    """
    sprite_height = len(sprite)
    if sprite_height == 0:
        return

    sprite_width = max(len(line) for line in sprite) if sprite else 0

    for row_offset in range(sprite_height):
        scene_row = y + row_offset
        if scene_row < 0 or scene_row >= len(scene):
            continue

        sprite_line = sprite[row_offset]
        scene_line_list = list(scene[scene_row])

        for col_offset in range(len(sprite_line)):
            scene_col = x + col_offset
            if scene_col < 0 or scene_col >= len(scene_line_list):
                continue

            sprite_char = sprite_line[col_offset]

            # Skip transparent characters
            if sprite_char == transparent_char:
                continue

            # Draw the character (convert solid_char to transparent_char if specified)
            if solid_char is not None and sprite_char == solid_char:
                scene_line_list[scene_col] = transparent_char
            else:
                scene_line_list[scene_col] = sprite_char

        scene[scene_row] = ''.join(scene_line_list)

def composite_cloud_on_canvas(canvas, cloud, x, y):
    """
    Composite a cloud onto a canvas at position (x, y).
    Uses 'X' as solid pixels, space as transparent.
    """
    composite_sprite(canvas, cloud, x, y, transparent_char=' ', solid_char='X')

def generate_sky_views():
    """
    Generate 4 random sky views (north, east, south, west).
    Each view has 4-8 randomly placed clouds with random orientations.
    Sky is limited to upper 13 lines (above the horizon/vanishing point).
    """
    sky_depth = 13
    for direction in ['north', 'east', 'south', 'west']:
        # Create empty canvas
        canvas = [' ' * screen_width for _ in range(sky_depth)]

        # Place 4-8 clouds randomly
        num_clouds = random.randint(4, 8)

        for _ in range(num_clouds):
            # Random orientation
            cloud = CLOUD[:]
            if random.choice([True, False]):
                cloud = flip_cloud_horizontal(cloud)
            if random.choice([True, False]):
                cloud = flip_cloud_vertical(cloud)

            # Random position (allow clouds to go partially off-screen)
            # Limit y position to upper 10 lines (above horizon)
            cloud_width = max(len(line) for line in cloud)
            cloud_height = len(cloud)
            x = random.randint(-cloud_width // 2, screen_width - cloud_width // 2)
            y = random.randint(-cloud_height // 2, (sky_depth - 3) - cloud_height // 2)

            # Composite cloud onto canvas
            composite_cloud_on_canvas(canvas, cloud, x, y)

        # Replace all 'X's with spaces (makes overlapping work correctly)
        canvas = [line.replace('X', ' ') for line in canvas]

        SKY_VIEWS[direction] = canvas

def rotate_sky_view_down(sky_view):
    """Rotate sky view down by one line (wind blowing down)."""
    if not sky_view:
        return sky_view
    # Move last line to front
    return [sky_view[-1]] + sky_view[:-1]

def rotate_sky_view_up(sky_view):
    """Rotate sky view up by one line (wind blowing up)."""
    if not sky_view:
        return sky_view
    # Move first line to end
    return sky_view[1:] + [sky_view[0]]

def rotate_sky_view_left(sky_view):
    """Rotate sky view left by one character (wind blowing left)."""
    rotated = []
    for line in sky_view:
        if len(line) > 0:
            # Move first character to end
            rotated.append(line[1:] + line[0])
        else:
            rotated.append(line)
    return rotated

def rotate_sky_view_right(sky_view):
    """Rotate sky view right by one character (wind blowing right)."""
    rotated = []
    for line in sky_view:
        if len(line) > 0:
            # Move last character to front
            rotated.append(line[-1] + line[:-1])
        else:
            rotated.append(line)
    return rotated

def animate_wind():
    """Animate clouds based on wind direction."""
    global wind_direction, SKY_VIEWS

    # Determine which views to animate based on wind direction
    if wind_direction == 'north':
        # Wind blowing north: north view moves down, south view moves up
        SKY_VIEWS['north'] = rotate_sky_view_down(SKY_VIEWS['north'])
        SKY_VIEWS['south'] = rotate_sky_view_up(SKY_VIEWS['south'])
        # East is "right" of north, west is "left"
        SKY_VIEWS['east'] = rotate_sky_view_left(SKY_VIEWS['east'])
        SKY_VIEWS['west'] = rotate_sky_view_right(SKY_VIEWS['west'])
    elif wind_direction == 'south':
        # Wind blowing south: south view moves down, north view moves up
        SKY_VIEWS['south'] = rotate_sky_view_down(SKY_VIEWS['south'])
        SKY_VIEWS['north'] = rotate_sky_view_up(SKY_VIEWS['north'])
        # West is "right" of south, east is "left"
        SKY_VIEWS['west'] = rotate_sky_view_left(SKY_VIEWS['west'])
        SKY_VIEWS['east'] = rotate_sky_view_right(SKY_VIEWS['east'])
    elif wind_direction == 'east':
        # Wind blowing east: east view moves down, west view moves up
        SKY_VIEWS['east'] = rotate_sky_view_down(SKY_VIEWS['east'])
        SKY_VIEWS['west'] = rotate_sky_view_up(SKY_VIEWS['west'])
        # South is "right" of east, north is "left"
        SKY_VIEWS['south'] = rotate_sky_view_left(SKY_VIEWS['south'])
        SKY_VIEWS['north'] = rotate_sky_view_right(SKY_VIEWS['north'])
    elif wind_direction == 'west':
        # Wind blowing west: west view moves down, east view moves up
        SKY_VIEWS['west'] = rotate_sky_view_down(SKY_VIEWS['west'])
        SKY_VIEWS['east'] = rotate_sky_view_up(SKY_VIEWS['east'])
        # North is "right" of west, south is "left"
        SKY_VIEWS['north'] = rotate_sky_view_left(SKY_VIEWS['north'])
        SKY_VIEWS['south'] = rotate_sky_view_right(SKY_VIEWS['south'])

def change_wind_direction():
    """Change wind direction to left or right of current direction."""
    global wind_direction

    directions = ['north', 'east', 'south', 'west']
    current_idx = directions.index(wind_direction)

    # Turn left or right
    if random.choice([True, False]):
        # Turn right
        wind_direction = directions[(current_idx + 1) % 4]
    else:
        # Turn left
        wind_direction = directions[(current_idx - 1) % 4]

def update_wind():
    """Update wind system based on step counter."""
    # Every 10 steps, animate clouds
    if state.step_count % 10 == 0:
        animate_wind()

    # Every 61 steps, change wind direction
    if state.step_count % 61 == 0:
        change_wind_direction()

def mirror_tile(tile):
    """Mirror a tile horizontally (for right side)."""
    return [line[::-1] for line in tile]

def render_view(has_left, has_forward, has_right, facing='north', show_key=False, show_door=False):
    """
    Render a perspective first-person view using 25x25 tiles.

    Args:
        has_left: Boolean - is there a passage to the left?
        has_forward: Boolean - is there a passage forward?
        has_right: Boolean - is there a passage to the right?
        facing: String - cardinal direction player is facing
        show_key: Boolean - is the skeleton key in this room?
        show_door: Boolean - is the door visible at the starting position?

    Returns perspective ASCII art (75 chars wide, 25 lines tall)
    """
    # Select tiles based on what's open
    left_tile = TILE_LEFT_OPEN if has_left else TILE_LEFT_WALL
    center_tile = TILE_CENTER_OPEN if has_forward else TILE_CENTER_WALL
    right_tile = TILE_LEFT_OPEN if has_right else TILE_LEFT_WALL

    # Mirror the right tile
    right_tile = mirror_tile(right_tile)

    # Start with clouds as the background layer
    sky_view = SKY_VIEWS.get(facing, SKY_VIEWS['north'])
    # Pad sky view to full height and add border characters
    lines = []
    for i in range(tile_height):
        if i < len(sky_view):
            lines.append("|" + sky_view[i] + "|")
        else:
            lines.append("|" + " " * screen_width + "|")

    # Compose the hedge tiles on top of the clouds
    hedge_tiles = []
    for i in range(tile_height):
        line = left_tile[i] + center_tile[i] + right_tile[i]
        # Draw corner edges
        if i > 8 and i < 18:
            if (has_forward and has_left) or (not has_forward and not has_left):
                edge = 24
                line = line[:edge] + '|' + line[edge+1:]
            if (has_forward and has_right) or (not has_forward and not has_right):
                edge = 51
                line = line[:edge] + '|' + line[edge+1:]
        hedge_tiles.append(line)

    # Composite hedges onto cloud background (offset by 1 for left border)
    composite_sprite(lines, hedge_tiles, 1, 0, transparent_char=' ', solid_char=None)

    # Composite the key onto the floor if it's in this room
    if show_key:
        # Position key in the center of the floor (lower portion of screen)
        key_width = max(len(key_line) for key_line in KEY)
        # Center horizontally on the screen (screen_width + 2 for borders = 77)
        key_start_x = (screen_width + 2 - key_width) // 2
        # Position vertically in the lower portion (start around line 18)
        key_start_y = 18
        composite_sprite(lines, KEY, key_start_x, key_start_y, transparent_char=' ', solid_char='X')

    # Composite the door if at the starting position
    if show_door:
        # Position door in the center of the view
        door_width = max(len(door_line) for door_line in DOOR)
        # Center horizontally on the screen (screen_width + 2 for borders = 77)
        door_start_x = (screen_width + 2 - door_width) // 2
        # Position vertically in the center area (start around line 9 to fit in 9-line hedge wall)
        door_start_y = 9
        composite_sprite(lines, DOOR, door_start_x, door_start_y, transparent_char=' ', solid_char='X')

    return '\n'.join(lines)


@when("l")
def look_around():
    """Look at your surroundings in first-person view."""
    player_facing = state.player_facing

    # Check what's in each direction relative to facing
    left_dir = get_left_dir(player_facing)
    right_dir = get_right_dir(player_facing)

    # Check if there's a passage in each direction
    has_left = state.current_room.exit(left_dir) is not None
    has_forward = state.current_room.exit(player_facing) is not None
    has_right = state.current_room.exit(right_dir) is not None

    # Check if the skeleton key is in this room
    show_key = state.current_room.items.find('key') is not None

    # Check if we're at the starting position AND facing the outer wall (where the door is)
    show_door = state.at_start and player_facing == m.start_edge

    # Render and display the perspective view
    view = render_view(has_left, has_forward, has_right, player_facing,
                       show_key, show_door)
    print("\n" + view + "\n")

@when("w")
def move_forward():
    """Move forward in the direction you're facing."""
    next_room = state.current_room.exit(state.player_facing)

    if next_room:
        state.enter(next_room)

        # Update wind animation
        update_wind()

        look_around()

    hedgemaze.pause_after_move()

@when("s")
def move_backward():
    """Move backward (opposite of facing direction)."""
    opposite_facing = DIRECTIONS[(DIRECTIONS.index(state.player_facing) + 2) % 4]
    next_room = state.current_room.exit(opposite_facing)

    if next_room:
        state.enter(next_room)

        # Update wind animation
        update_wind()

        look_around()

    hedgemaze.pause_after_move()

@when("a")
def rotate_left():
    """Turn 90 degrees to the left."""
    state.player_facing = turn_left(state.player_facing)
    look_around()

@when("d")
def rotate_right():
    """Turn 90 degrees to the right."""
    state.player_facing = turn_right(state.player_facing)
    look_around()

@when("e")
def use_interact():
    """Use/interact with items - pick up key or use key with door."""
    # Check if key is in the room
    key_obj = state.current_room.items.find('key')
    if key_obj:
        # Pick up the key
        state.take(key_obj)
        say(f"You take {key_obj}.\n")
        look_around()
        return

    # Check if we're at the starting position and facing the door
    facing_door = state.player_facing == m.start_edge
    door_obj = state.current_room.items.find('door')

    if state.at_start and facing_door and door_obj:
        # We're facing the door - check if we have the key
        key_obj = state.inventory.find('key')
        if key_obj:
            # Use key with door
            door_obj.use_with(key_obj)
            return
        else:
            # Don't have the key
            say("You are missing the key to open the door.")
            return

    say("There's nothing to interact with here.")

@when("i")
def show_inventory():
    """Show what you're carrying."""
    hedgemaze.say_list(state.inventory,
        singular_prefix="You are carrying ",
        plural_prefix="You are carrying ",
        empty_message="You aren't carrying anything."
    )

if TEST_MODE:
    # This tier has no take/examine verbs, so Map.examine() is otherwise unreachable.
    # Registered only under --test, leaving the shipped command set untouched.
    @when("map")
    def show_debug_map():
        """Debug only: reveal the whole maze with the solved route."""
        state.magic_map.examine()

@when("h")
@when("help")
def show_help():
    """Show available commands."""
    print("""
Available commands:
  w - Move forward
  s - Move backward
  a - Turn left
  d - Turn right
  l - Look around
  e - Interact with objects
  i - Show inventory
  q - Quit game
  h - Show this help
""")

@when("q")
@when("quit")
def quit_game():
    """Exit the game."""
    hedgemaze.quit_game()

if __name__ == "__main__":
    # Pick random wind direction at startup
    wind_direction = random.choice(['north', 'east', 'south', 'west'])

    # Generate random sky views at startup
    generate_sky_views()

    hedgemaze.show_intro()
    look_around()          # this tier opens on a rendered view, before the game loop
    start(help=False)      # Start the adventurelib game loop (disable default help)
