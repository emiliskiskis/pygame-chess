import os

MIN_TILE = 40
DEFAULT_TILE = 80
FILES = "abcdefgh"
RANKS = "87654321"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(SCRIPT_DIR, "assets")

WHITE_TILE = (240, 217, 181)
BLACK_TILE = (181, 136, 99)
HIGHLIGHT_COLOR = (20, 85, 30, 180)
SELECT_COLOR = (20, 85, 125, 180)
LAST_MOVE_COLOR = (180, 180, 20, 80)
CURSOR_COLOR = (200, 50, 200, 160)
PREVIEW_COLOR = (220, 140, 20, 160)
BORDER_BG = (40, 40, 40)
COORD_COLOR = (220, 220, 220)
PANEL_BG = (28, 28, 28)
PANEL_HEADER = (60, 60, 60)
PANEL_TEXT_W = (240, 240, 240)
PANEL_TEXT_B = (180, 180, 180)

MODE_MENU = "menu"
MODE_PVP = "pvp"
MODE_AI = "ai"
MODE_LEARNING = "learning"


PIECE_SYMBOLS = {
    "white_king": "♔",
    "white_queen": "♕",
    "white_rook": "♖",
    "white_bishop": "♗",
    "white_knight": "♘",
    "white_pawn": "♙",
    "black_king": "♚",
    "black_queen": "♛",
    "black_rook": "♜",
    "black_bishop": "♝",
    "black_knight": "♞",
    "black_pawn": "♟",
}
