"""
ml_ai.py — ML-based AI move selection and online training.

Manages a single global ChessResNet model, providing:
  - ml_ai_move()            : pick a move for black during human-vs-AI gameplay
  - ml_ai_move_for()        : pick a move for any colour (used by self-play);
                              does NOT self-record — do_move handles recording
  - record_position()       : record board state after any move
  - record_game_result()    : update ELO + game record immediately on game end
                              (call this on the main thread before training starts;
                              do NOT call for self-play games — no human opponent)
  - start_training_async()  : snapshot positions, spawn background training thread
                              and return it; progress is reported via a shared list
  - get_stats()             : return current ELO and game record (always safe to call)
  - clear_game_history()    : reset recorded positions for a new game
"""

import threading

import torch
import torch.nn as nn

from .board import all_legal_moves
from .ml_model import ChessResNet, board_to_tensor, move_to_index
from ..profiles import get_model_path as _get_model_path

# ── Global model state ─────────────────────────────────────────────────────────
_model = None
_optimizer = None

# ── Persistent stats (loaded from / saved to checkpoint) ──────────────────────
_elo = 800
_games_played = 0
_wins = 0  # AI wins  (black wins)
_losses = 0  # AI losses (white / human wins)
_draws = 0

# Last value-head estimate produced by ml_ai_move(), from black's perspective.
# Updated every AI move; read after game ends for the "confidence" stat.
_last_value_estimate: float = 0.0

# Positions collected during the current game:
#   list of (tensor, move_index, turn_color)
_game_positions: list = []


# ── Model lifecycle ────────────────────────────────────────────────────────────


def _ensure_model():
    """Load or create the global model + optimizer, loading saved stats."""
    global _model, _optimizer
    global _elo, _games_played, _wins, _losses, _draws

    if _model is not None:
        return _model

    _model = ChessResNet()
    _optimizer = torch.optim.Adam(_model.parameters(), lr=1e-4)

    model_path = _get_model_path()
    if model_path.exists():
        checkpoint = torch.load(str(model_path), map_location="cpu", weights_only=False)
        _model.load_state_dict(checkpoint["model"])
        _optimizer.load_state_dict(checkpoint["optimizer"])
        _elo = checkpoint.get("elo", 800)
        _games_played = checkpoint.get("games_played", 0)
        _wins = checkpoint.get("wins", 0)
        _losses = checkpoint.get("losses", 0)
        _draws = checkpoint.get("draws", 0)

    _model.eval()
    return _model


def _save_model():
    """Persist model weights, optimizer state, and stats to disk."""
    model_path = _get_model_path()
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model": _model.state_dict(),
            "optimizer": _optimizer.state_dict(),
            "elo": _elo,
            "games_played": _games_played,
            "wins": _wins,
            "losses": _losses,
            "draws": _draws,
        },
        str(model_path),
    )


def unload_model() -> None:
    """
    Reset all in-memory model state.

    Call this when switching the active profile so that the next call to
    _ensure_model() loads the new profile's checkpoint from disk.
    """
    global _model, _optimizer
    global _elo, _games_played, _wins, _losses, _draws
    global _last_value_estimate, _game_positions
    _model = None
    _optimizer = None
    _elo = 800
    _games_played = 0
    _wins = 0
    _losses = 0
    _draws = 0
    _last_value_estimate = 0.0
    _game_positions = []


# ── Public stats API ───────────────────────────────────────────────────────────


def get_stats() -> dict:
    """
    Return current AI stats.  Safe to call at any time, including while a
    training thread is running (stats in memory are updated before the thread
    starts, so no lock is needed).
    """
    _ensure_model()
    return {
        "elo": _elo,
        "games": _games_played,
        "wins": _wins,
        "losses": _losses,
        "draws": _draws,
        "last_value": _last_value_estimate,
    }


def record_game_result(result: float) -> None:
    """
    Update ELO and win/loss/draw record immediately when a game ends.

    Call this on the **main thread** before starting the training thread so
    that get_stats() returns up-to-date figures while training is in progress.

    result:  +1.0 = white (human) won,  -1.0 = black (AI) won,  0.0 = draw.
    """
    global _games_played, _wins, _losses, _draws, _elo

    _ensure_model()

    _games_played += 1
    if result < 0.0:  # AI (black) won
        _wins += 1
        ai_score = 1.0
    elif result > 0.0:  # Human (white) won
        _losses += 1
        ai_score = 0.0
    else:  # Draw
        _draws += 1
        ai_score = 0.5

    # Standard Elo: K = 32 for the first 30 games, 16 thereafter.
    human_elo = 1200  # fixed reference rating for the human opponent
    k = 32 if _games_played <= 30 else 16
    expected = 1.0 / (1.0 + 10.0 ** ((human_elo - _elo) / 400.0))
    _elo = max(100, round(_elo + k * (ai_score - expected)))


# ── Position recording ─────────────────────────────────────────────────────────


def record_position(board, turn, castling_rights, last_move, move_fr, move_to):
    """Record a (state, action, turn) tuple for the current game."""
    tensor = board_to_tensor(board, turn, castling_rights, last_move)
    fr, fc = move_fr
    tr, tc = move_to
    idx = move_to_index(fr, fc, tr, tc)
    _game_positions.append((tensor.squeeze(0), idx, turn))


def clear_game_history():
    """Reset recorded positions ready for a new game."""
    global _game_positions
    _game_positions = []


# ── Move selection ─────────────────────────────────────────────────────────────


def ml_ai_move(board, last_move, castling_rights, progress=None):
    """
    Pick a move using the ML model.  Returns (fr, fc, tr, tc) or None.
    Also updates _last_value_estimate with the model's confidence.
    """
    global _last_value_estimate

    model = _ensure_model()
    moves = all_legal_moves(board, "black", last_move, castling_rights)
    if not moves:
        return None

    tensor = board_to_tensor(board, "black", castling_rights, last_move)

    with torch.no_grad():
        policy_logits, value = model(tensor)

    _last_value_estimate = float(value.item())

    # Mask illegal moves
    mask = torch.full((4096,), float("-inf"))
    move_map = {}
    for fr, fc, tr, tc in moves:
        idx = move_to_index(fr, fc, tr, tc)
        mask[idx] = 0.0
        move_map[idx] = (fr, fc, tr, tc)

    masked = policy_logits.squeeze(0) + mask
    probs = torch.softmax(masked, dim=0)

    chosen_idx = int(torch.multinomial(probs, 1).item())
    chosen_move = move_map[chosen_idx]

    # Record this position for training
    _game_positions.append((tensor.squeeze(0), chosen_idx, "black"))

    if progress is not None:
        progress[0] = 1
        progress[1] = 1

    return chosen_move


def ml_ai_move_for(board, color, last_move, castling_rights, progress=None):
    """
    Pick a move for *any* colour using the ML model.

    Unlike ml_ai_move(), this function does NOT append to _game_positions.
    Position recording is handled entirely by do_move() so that self-play
    games don't double-record moves.

    Updates _last_value_estimate with the model's evaluation from `color`'s
    perspective (positive = good for `color`).

    Returns (fr, fc, tr, tc) or None.
    """
    global _last_value_estimate

    model = _ensure_model()
    moves = all_legal_moves(board, color, last_move, castling_rights)
    if not moves:
        return None

    tensor = board_to_tensor(board, color, castling_rights, last_move)

    with torch.no_grad():
        policy_logits, value = model(tensor)

    _last_value_estimate = float(value.item())

    # Mask illegal moves
    mask = torch.full((4096,), float("-inf"))
    move_map = {}
    for fr, fc, tr, tc in moves:
        idx = move_to_index(fr, fc, tr, tc)
        mask[idx] = 0.0
        move_map[idx] = (fr, fc, tr, tc)

    masked = policy_logits.squeeze(0) + mask
    probs = torch.softmax(masked, dim=0)

    chosen_idx = int(torch.multinomial(probs, 1).item())

    if progress is not None:
        progress[0] = 1
        progress[1] = 1

    return move_map[chosen_idx]


# ── Training ───────────────────────────────────────────────────────────────────


def _train_on_positions(positions: list, result: float, progress: list) -> None:
    """
    Run one REINFORCE-style gradient step per recorded position.
    Designed to be called from a background thread.

    progress: a two-element list [steps_done, total_steps] updated in place
              after each step so the main thread can read it without a lock
              (integer writes are atomic on CPython).
    """
    if not positions or _model is None:
        if progress is not None:
            progress[0] = progress[1]
        return

    total = len(positions)
    if progress is not None:
        progress[0] = 0
        progress[1] = total

    _model.train()

    for i, (tensor, move_idx, turn_color) in enumerate(positions):
        # Target value from this player's perspective
        target_val = result if turn_color == "white" else -result

        inp = tensor.unsqueeze(0)
        policy_logits, value = _model(inp)

        value_target = torch.tensor([[target_val]], dtype=torch.float32)
        value_loss = nn.MSELoss()(value, value_target)

        move_target = torch.tensor([move_idx], dtype=torch.long)
        policy_loss = nn.CrossEntropyLoss()(policy_logits, move_target)

        # Weight policy gradient by outcome; always learn a little (0.1 floor)
        sign = target_val
        weight = max(sign, 0.1)
        loss = value_loss + policy_loss * weight

        _optimizer.zero_grad()
        loss.backward()
        _optimizer.step()

        if progress is not None:
            progress[0] = i + 1

    _model.eval()
    # Save model (including already-updated ELO/stats from record_game_result)
    _save_model()


def start_training_async(result: float, progress: list) -> threading.Thread:
    """
    Snapshot the current game positions, initialise the progress counters, and
    spawn a daemon thread that trains the model and saves it when done.

    Call record_game_result() *before* this so that ELO is already updated in
    memory before the thread starts writing to the checkpoint.

    Returns the Thread object (already started).
    """
    global _game_positions

    # Take a snapshot and clear immediately so a new game can start recording
    # positions without interfering with the training run.
    positions = list(_game_positions)
    _game_positions = []

    total = max(1, len(positions))
    if progress is not None:
        progress[0] = 0
        progress[1] = total

    thread = threading.Thread(
        target=_train_on_positions,
        args=(positions, result, progress),
        daemon=True,
    )
    thread.start()
    return thread
