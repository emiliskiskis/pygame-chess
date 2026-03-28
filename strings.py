"""
strings.py — locale loader.

To add a language, copy locale/en.json to locale/<code>.json, translate the
values, and change LOCALE below (or set the CHESS_LOCALE environment variable).
"""

import json
import os
from pathlib import Path

LOCALE = os.environ.get("CHESS_LOCALE", "en")

_path = Path(__file__).parent / "locale" / f"{LOCALE}.json"
if not _path.exists():
    _path = Path(__file__).parent / "locale" / "en.json"

_s = json.loads(_path.read_text(encoding="utf-8"))

# ── Window ────────────────────────────────────────────────────────────────────
WINDOW_TITLE = _s["window_title"]

# ── Main menu ─────────────────────────────────────────────────────────────────
MENU_TITLE          = _s["menu_title"]
MENU_SUBTITLE       = _s["menu_subtitle"]
MENU_HINT           = _s["menu_hint"]
MENU_PVP_LABEL      = _s["menu_pvp_label"]
MENU_PVP_DESC       = _s["menu_pvp_desc"]
MENU_AI_LABEL       = _s["menu_ai_label"]
MENU_AI_DESC        = _s["menu_ai_desc"]
MENU_LEARNING_LABEL = _s["menu_learning_label"]
MENU_LEARNING_DESC  = _s["menu_learning_desc"]

# ── In-game badges ────────────────────────────────────────────────────────────
BADGE_PVP      = _s["badge_pvp"]
BADGE_AI       = _s["badge_ai"]
BADGE_LEARNING = _s["badge_learning"]

# ── Move panel ────────────────────────────────────────────────────────────────
PANEL_HEADER     = _s["panel_header"]
PANEL_COL_NUMBER = _s["panel_col_number"]
PANEL_COL_WHITE  = _s["panel_col_white"]
PANEL_COL_BLACK  = _s["panel_col_black"]

# ── Notation bar ──────────────────────────────────────────────────────────────
NOTATION_LABEL = _s["notation_label"]
NOTATION_HINT  = _s["notation_hint"]

# ── Pause menu ────────────────────────────────────────────────────────────────
PAUSE_TITLE      = _s["pause_title"]
PAUSE_RESUME     = _s["pause_resume"]
PAUSE_RESTART    = _s["pause_restart"]
PAUSE_MENU       = _s["pause_menu"]
PAUSE_FULLSCREEN = _s["pause_fullscreen"]
PAUSE_QUIT       = _s["pause_quit"]
PAUSE_ESC_HINT   = _s["pause_esc_hint"]

# ── Game-over overlay ─────────────────────────────────────────────────────────
OVER_PLAY_AGAIN = _s["over_play_again"]
OVER_MENU       = _s["over_menu"]
OVER_QUIT       = _s["over_quit"]

# ── Game status messages ──────────────────────────────────────────────────────
STATUS_TURN       = _s["status_turn"]
STATUS_CHECK      = _s["status_check"]
STATUS_CHECKMATE  = _s["status_checkmate"]
STATUS_STALEMATE  = _s["status_stalemate"]
STATUS_WHITE_TURN = _s["status_white_turn"]

# ── Piece tips (Learning mode) ────────────────────────────────────────────────
TIPS = {
    "pawn":   _s["tip_pawn"],
    "knight": _s["tip_knight"],
    "bishop": _s["tip_bishop"],
    "rook":   _s["tip_rook"],
    "queen":  _s["tip_queen"],
    "king":   _s["tip_king"],
}
