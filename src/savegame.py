"""
savegame.py — Per-mode, per-profile game state persistence.

Each saveable game mode gets its own JSON file stored under
saves/<profile_id>/ in the project root.
The file name is saves/<profile_id>/save_<mode>.json.

Saveable modes: pvp, ai, learning, ml_ai
NOT saved: ml_self (spectator-only automated mode)
"""

import json
from pathlib import Path

from .profiles import get_save_dir

SAVEABLE_MODES = {"pvp", "ai", "learning", "ml_ai"}

_SAVE_NAMES = {
    "pvp": "save_pvp.json",
    "ai": "save_ai.json",
    "learning": "save_learning.json",
    "ml_ai": "save_ml_ai.json",
}


def _save_path(mode: str) -> Path:
    return get_save_dir() / _SAVE_NAMES[mode]


def save_game(mode, board, turn, last_move, castling_rights, move_history, flipped):
    """Persist the current game state for *mode* to disk.

    Silently ignores unsaveable modes or I/O errors so callers never crash.
    """
    if mode not in _SAVE_NAMES:
        return
    data = {
        "mode": mode,
        "board": board,
        "turn": turn,
        "last_move": list(last_move) if last_move is not None else None,
        "castling_rights": castling_rights,
        "move_history": move_history,
        "flipped": flipped,
    }
    try:
        save_dir = get_save_dir()
        save_dir.mkdir(parents=True, exist_ok=True)
        _save_path(mode).write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_game(mode):
    """Load the saved game state for *mode*.

    Returns a dict with keys: board, turn, last_move (tuple or None),
    castling_rights, move_history, flipped.

    Raises ValueError if no save exists or if the file is corrupt / incomplete.
    """
    if mode not in _SAVE_NAMES:
        raise ValueError(f"No save slot for mode {mode!r}")
    path = _save_path(mode)
    if not path.exists():
        raise ValueError("No save file found")
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read save file: {exc}") from exc

    # Validate required keys
    required = ("board", "turn", "last_move", "castling_rights", "move_history")
    for key in required:
        if key not in data:
            raise ValueError(f"Save file missing key: {key!r}")

    # Sanity-check board shape
    board = data["board"]
    if not (
        isinstance(board, list)
        and len(board) == 8
        and all(isinstance(row, list) and len(row) == 8 for row in board)
    ):
        raise ValueError("Board data has wrong shape")

    # Convert last_move list → tuple (or keep None)
    lm = data["last_move"]
    if lm is not None:
        if not (isinstance(lm, list) and len(lm) == 4):
            raise ValueError("last_move has wrong format")
        data["last_move"] = tuple(lm)

    # Ensure flipped key exists (older saves may omit it)
    data.setdefault("flipped", False)

    return data


def delete_save(mode):
    """Delete the save file for *mode*. Silent on missing file or errors."""
    if mode not in _SAVE_NAMES:
        return
    try:
        _save_path(mode).unlink(missing_ok=True)
    except OSError:
        pass


def save_exists(mode):
    """Return True if a non-empty save file exists for *mode*."""
    if mode not in _SAVE_NAMES:
        return False
    p = _save_path(mode)
    return p.exists() and p.stat().st_size > 0
