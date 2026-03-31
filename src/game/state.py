"""
state.py — Dataclasses for all mutable game state.

Grouping state into named objects replaces the ~60 nonlocal variables that
lived in the original monolithic main() function.
"""

from dataclasses import dataclass, field


@dataclass
class ChessState:
    """All chess-specific game state for one active game."""

    board: list = field(default_factory=list)
    turn: str = "white"
    selected: tuple | None = None
    possible_moves: list = field(default_factory=list)
    last_move: tuple | None = None
    castling_rights: dict = field(
        default_factory=lambda: {
            "white": {"kingside": True, "queenside": True},
            "black": {"kingside": True, "queenside": True},
        }
    )
    status_msg: str = ""
    game_over: bool = False
    move_history: list = field(default_factory=list)
    flipped: bool = False
    cursor: tuple = (7, 4)
    tip_text: str = ""


@dataclass
class DragState:
    """Piece drag-and-drop state."""

    active: bool = False
    piece_key: str | None = None
    from_cell: tuple | None = None
    pos: tuple = (0, 0)


@dataclass
class AIState:
    """Background AI thread state.

    result and progress are shared lists so the background thread can write
    without a lock (integer/object writes are atomic on CPython).
    """

    thinking: bool = False
    thread: object = None  # threading.Thread | None
    result: list = field(default_factory=lambda: [None])
    progress: list = field(default_factory=lambda: [0, 1])


@dataclass
class TrainingState:
    """Background ML training thread state."""

    active: bool = False
    thread: object = None  # threading.Thread | None
    progress: list = field(default_factory=lambda: [0, 0])


@dataclass
class SavePopupState:
    """State for the continue / corrupt-save popups."""

    pending_mode: str | None = None
    error: bool = False
    hovered: str | None = None
    rects: dict = field(default_factory=dict)


@dataclass
class ProfilesDialogState:
    """State for the profiles-screen text-input and confirm dialogs."""

    editing_id: str | None = None
    edit_text: str = ""
    creating: bool = False
    create_text: str = ""
    deleting_id: str | None = None
    dialog_hovered: str | None = None
