"""
strings.py — locale loader.

Add a language by placing locale/<code>.json (copy en.json and translate values)
and a matching flag at assets/flags/<code>.svg.
The picker in the main menu will pick it up automatically.
"""

import json
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent.parent / "locale"
_PREFS_FILE = Path(__file__).parent.parent / "prefs.dat"

CURRENT_LOCALE = "en"


def _save_locale(locale):
    try:
        _PREFS_FILE.write_text(locale, encoding="utf-8")
    except OSError:
        pass


def _load_locale():
    try:
        return _PREFS_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "en"


def prefs_exist():
    """Return True if a saved locale preference file exists."""
    return _PREFS_FILE.exists()


def available_locales():
    """Return [(code, language_name, lang_select_title)] for every locale that has a JSON file."""
    result = []
    for path in sorted(_LOCALE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append(
                (
                    path.stem,
                    data.get("_language", path.stem),
                    data.get("_lang_select_title", "Select Language"),
                )
            )
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
    MENU_ML_AI_LABEL = ""
    MENU_ML_AI_DESC = ""

    # Badges
    BADGE_PVP = ""
    BADGE_AI = ""
    BADGE_LEARNING = ""
    BADGE_ML_AI = ""

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
    STATUS_YOUR_TURN = ""
    STATUS_AI_TURN = ""

    # Piece tips
    TIPS: dict = {}

    # Save / continue popup
    SAVE_CONTINUE_TITLE = ""
    SAVE_YES = ""
    SAVE_NO = ""
    SAVE_CANCEL = ""
    SAVE_CORRUPT_TITLE = ""
    SAVE_CORRUPT_MSG = ""
    SAVE_CORRUPT_CONTINUE = ""

    # ML vs ML self-play
    MENU_ML_SELF_LABEL = ""
    MENU_ML_SELF_DESC = ""
    BADGE_ML_SELF = ""
    ML_SELF_DELAY = ""
    ML_SELF_SPEED_HINT = ""

    # ML AI game-over overlay
    ML_OVER_TRAINING = ""
    ML_OVER_TRAINING_DONE = ""
    ML_OVER_ELO = ""
    ML_OVER_RECORD = ""
    ML_OVER_GAMES = ""
    ML_OVER_GAME_LENGTH = ""
    ML_OVER_CONFIDENCE = ""


def reload(locale="en", save=True):
    """Load locale/<locale>.json into S. Falls back to en if missing."""
    global CURRENT_LOCALE
    path = _LOCALE_DIR / f"{locale}.json"
    if not path.exists():
        path = _LOCALE_DIR / "en.json"
        locale = "en"
    d = json.loads(path.read_text(encoding="utf-8"))
    CURRENT_LOCALE = locale
    if save:
        _save_locale(locale)

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
    S.MENU_ML_AI_LABEL = d.get("menu_ml_ai_label", "Player vs ML AI")
    S.MENU_ML_AI_DESC = d.get(
        "menu_ml_ai_desc", "Play against a learning neural network"
    )
    S.BADGE_PVP = d["badge_pvp"]
    S.BADGE_AI = d["badge_ai"]
    S.BADGE_LEARNING = d["badge_learning"]
    S.BADGE_ML_AI = d.get("badge_ml_ai", "vs ML AI")
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
    S.STATUS_YOUR_TURN = d["status_your_turn"]
    S.STATUS_AI_TURN = d["status_ai_turn"]
    S.MENU_ML_SELF_LABEL = d.get("menu_ml_self_label", "ML vs ML")
    S.MENU_ML_SELF_DESC = d.get(
        "menu_ml_self_desc", "Watch the model play against itself"
    )
    S.BADGE_ML_SELF = d.get("badge_ml_self", "ML vs ML")
    S.ML_SELF_DELAY = d.get("ml_self_delay", "Delay: {ms}ms")
    S.ML_SELF_SPEED_HINT = d.get("ml_self_speed_hint", "+/- to change speed")
    S.ML_OVER_TRAINING = d.get("ml_over_training", "Training\u2026")
    S.ML_OVER_TRAINING_DONE = d.get("ml_over_training_done", "Training complete")
    S.ML_OVER_ELO = d.get("ml_over_elo", "ELO: {elo}")
    S.ML_OVER_RECORD = d.get("ml_over_record", "{wins}W  {draws}D  {losses}L")
    S.ML_OVER_GAMES = d.get("ml_over_games", "Games: {games}")
    S.ML_OVER_GAME_LENGTH = d.get("ml_over_game_length", "Moves: {moves}")
    S.ML_OVER_CONFIDENCE = d.get("ml_over_confidence", "Last eval: {val:+.2f}")
    S.TIPS = {
        "pawn": d["tip_pawn"],
        "knight": d["tip_knight"],
        "bishop": d["tip_bishop"],
        "rook": d["tip_rook"],
        "queen": d["tip_queen"],
        "king": d["tip_king"],
    }
    S.SAVE_CONTINUE_TITLE = d.get("save_continue_title", "Continue your saved game?")
    S.SAVE_YES = d.get("save_yes", "Yes, continue")
    S.SAVE_NO = d.get("save_no", "No, start fresh")
    S.SAVE_CANCEL = d.get("save_cancel", "Cancel")
    S.SAVE_CORRUPT_TITLE = d.get("save_corrupt_title", "Save Error")
    S.SAVE_CORRUPT_MSG = d.get(
        "save_corrupt_msg", "The saved game could not be loaded."
    )
    S.SAVE_CORRUPT_CONTINUE = d.get("save_corrupt_continue", "Continue")


# Load default on import — don't create prefs.dat if it doesn't exist yet
reload(_load_locale(), save=_PREFS_FILE.exists())
