"""
state.py — Dataclasses for all mutable game state.

Grouping state into named objects replaces the ~60 nonlocal variables that
lived in the original monolithic main() function.
"""

import time as _time
from collections import deque
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
class SelfPlayState:
    """State for the ML vs ML MCTS self-play mode.

    replay_buffer items: (board_tensor, policy_dict, turn_color, result)
    mcts_result is written by the background MCTS thread:
      [policy_dict, move, board_tensor]  (None until the thread finishes)
    loss_result is written by the batch-training thread:
      [total_loss, policy_loss, value_loss]
    """

    replay_buffer: object = field(
        default_factory=lambda: deque(maxlen=50_000)
    )
    games_done: int = 0
    white_wins: int = 0
    black_wins: int = 0
    draws: int = 0
    game_lengths: list = field(default_factory=list)
    losses: list = field(default_factory=list)       # total_loss per completed game
    current_positions: list = field(default_factory=list)

    # Background training
    training_active: bool = False
    training_thread: object = None                   # threading.Thread | None
    loss_result: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    progress: list = field(default_factory=lambda: [0, 0])

    # Background MCTS thread communication
    mcts_result: list = field(default_factory=lambda: [None, None, None])

    # Timing (seconds per game)
    game_start_time: float = field(default_factory=_time.time)
    avg_spg: float = 0.0   # updated each time a game completes


@dataclass
class ProfilesDialogState:
    """State for the profiles-screen text-input and confirm dialogs."""

    editing_id: str | None = None
    edit_text: str = ""
    creating: bool = False
    create_text: str = ""
    deleting_id: str | None = None
    dialog_hovered: str | None = None
