"""
strings.py — locale loader.

Add a language by placing locale/<code>.json (copy en.json and translate values)
and a matching flag at assets/flags/<code>.svg.
The picker in the main menu will pick it up automatically.
"""

import json
import os
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locale"

CURRENT_LOCALE = "en"


def available_locales():
    """Return [(code, language_name)] for every locale that has a JSON file."""
    result = []
    for path in sorted(_LOCALE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append((path.stem, data.get("_language", path.stem)))
        except Exception:
            pass
    return result


class S:
    """All user-visible strings. Attributes are updated in-place by reload()."""

    # Window
    WINDOW_TITLE = ""

    # Main menu
    MENU_TITLE = ""
    MENU_SUBTITLE = ""
    MENU_HINT = ""
    MENU_PVP_LABEL = ""
    MENU_PVP_DESC = ""
    MENU_AI_LABEL = ""
    MENU_AI_DESC = ""
    MENU_LEARNING_LABEL = ""
    MENU_LEARNING_DESC = ""

    # Badges
    BADGE_PVP = ""
    BADGE_AI = ""
    BADGE_LEARNING = ""

    # Move panel
    PANEL_HEADER = ""
    PANEL_COL_NUMBER = ""
    PANEL_COL_WHITE = ""
    PANEL_COL_BLACK = ""

    # Notation bar
    NOTATION_LABEL = ""
    NOTATION_HINT = ""

    # Pause menu
    PAUSE_TITLE = ""
    PAUSE_RESUME = ""
    PAUSE_RESTART = ""
    PAUSE_MENU = ""
    PAUSE_FULLSCREEN = ""
    PAUSE_QUIT = ""
    PAUSE_ESC_HINT = ""

    # Game-over overlay
    OVER_PLAY_AGAIN = ""
    OVER_MENU = ""
    OVER_QUIT = ""

    # Game status (use .format() to fill {player} / {winner})
    STATUS_TURN = ""
    STATUS_CHECK = ""
    STATUS_CHECKMATE = ""
    STATUS_STALEMATE = ""
    STATUS_WHITE_TURN = ""

    # Piece tips
    TIPS: dict = {}


def reload(locale="en"):
    """Load locale/<locale>.json into S. Falls back to en if missing."""
    global CURRENT_LOCALE
    path = _LOCALE_DIR / f"{locale}.json"
    if not path.exists():
        path = _LOCALE_DIR / "en.json"
        locale = "en"
    d = json.loads(path.read_text(encoding="utf-8"))
    CURRENT_LOCALE = locale

    S.WINDOW_TITLE = d["window_title"]
    S.MENU_TITLE = d["menu_title"]
    S.MENU_SUBTITLE = d["menu_subtitle"]
    S.MENU_HINT = d["menu_hint"]
    S.MENU_PVP_LABEL = d["menu_pvp_label"]
    S.MENU_PVP_DESC = d["menu_pvp_desc"]
    S.MENU_AI_LABEL = d["menu_ai_label"]
    S.MENU_AI_DESC = d["menu_ai_desc"]
    S.MENU_LEARNING_LABEL = d["menu_learning_label"]
    S.MENU_LEARNING_DESC = d["menu_learning_desc"]
    S.BADGE_PVP = d["badge_pvp"]
    S.BADGE_AI = d["badge_ai"]
    S.BADGE_LEARNING = d["badge_learning"]
    S.PANEL_HEADER = d["panel_header"]
    S.PANEL_COL_NUMBER = d["panel_col_number"]
    S.PANEL_COL_WHITE = d["panel_col_white"]
    S.PANEL_COL_BLACK = d["panel_col_black"]
    S.NOTATION_LABEL = d["notation_label"]
    S.NOTATION_HINT = d["notation_hint"]
    S.PAUSE_TITLE = d["pause_title"]
    S.PAUSE_RESUME = d["pause_resume"]
    S.PAUSE_RESTART = d["pause_restart"]
    S.PAUSE_MENU = d["pause_menu"]
    S.PAUSE_FULLSCREEN = d["pause_fullscreen"]
    S.PAUSE_QUIT = d["pause_quit"]
    S.PAUSE_ESC_HINT = d["pause_esc_hint"]
    S.OVER_PLAY_AGAIN = d["over_play_again"]
    S.OVER_MENU = d["over_menu"]
    S.OVER_QUIT = d["over_quit"]
    S.STATUS_TURN = d["status_turn"]
    S.STATUS_CHECK = d["status_check"]
    S.STATUS_CHECKMATE = d["status_checkmate"]
    S.STATUS_STALEMATE = d["status_stalemate"]
    S.STATUS_WHITE_TURN = d["status_white_turn"]
    S.TIPS = {
        "pawn":   d["tip_pawn"],
        "knight": d["tip_knight"],
        "bishop": d["tip_bishop"],
        "rook":   d["tip_rook"],
        "queen":  d["tip_queen"],
        "king":   d["tip_king"],
    }


# Load default on import
reload(os.environ.get("CHESS_LOCALE", "en"))
