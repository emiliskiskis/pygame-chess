"""
ml_ai.py — ML-based AI move selection and online training.

Manages two independent ChessResNet models (one per colour), providing:
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
_model_white = None
_optimizer_white = None
_model_black = None
_optimizer_black = None

# ── Persistent stats (loaded from / saved to black model checkpoint) ──────────
# Stats track the black AI's performance in human-vs-AI (MODE_ML_AI) games.
_elo = 800
_games_played = 0
_wins = 0    # AI wins  (black wins)
_losses = 0  # AI losses (white / human wins)
_draws = 0

# Last value-head estimate produced by the last ml_ai_move/ml_ai_move_for call.
_last_value_estimate: float = 0.0

# Positions collected during the current game:
#   list of (tensor, move_index, turn_color)
_game_positions: list = []


# ── Model lifecycle ────────────────────────────────────────────────────────────


def _get_model_path_for(color: str):
    """Return the checkpoint path for the given colour's model."""
    base = _get_model_path()
    return base.parent / f"model_{color}.pt"


def _load_one_model(color: str):
    """
    Load or create the model + optimizer for one colour.
    Falls back to the legacy single-model checkpoint (model.pt) if the
    colour-specific file doesn't exist yet.
    Returns (model, optimizer, extra_stats_dict).
    extra_stats_dict is non-empty only for the black model (which carries ELO).
    """
    m = ChessResNet()
    opt = torch.optim.Adam(m.parameters(), lr=1e-4)
    stats = {}

    colour_path = _get_model_path_for(color)
    if colour_path.exists():
        ckpt = torch.load(str(colour_path), map_location="cpu", weights_only=False)
        m.load_state_dict(ckpt["model"])
        opt.load_state_dict(ckpt["optimizer"])
        stats = {k: ckpt[k] for k in ("elo", "games_played", "wins", "losses", "draws") if k in ckpt}
    else:
        # Backward compat: try the old single-model file
        old_path = _get_model_path()
        if old_path.exists():
            ckpt = torch.load(str(old_path), map_location="cpu", weights_only=False)
            m.load_state_dict(ckpt["model"])
            try:
                opt.load_state_dict(ckpt["optimizer"])
            except Exception:
                pass
            stats = {k: ckpt[k] for k in ("elo", "games_played", "wins", "losses", "draws") if k in ckpt}

    m.eval()
    return m, opt, stats


def _ensure_models():
    """Load or create both models + optimizers, loading saved stats."""
    global _model_white, _optimizer_white, _model_black, _optimizer_black
    global _elo, _games_played, _wins, _losses, _draws

    if _model_white is None:
        _model_white, _optimizer_white, _ = _load_one_model("white")

    if _model_black is None:
        _model_black, _optimizer_black, stats = _load_one_model("black")
        _elo = stats.get("elo", 800)
        _games_played = stats.get("games_played", 0)
        _wins = stats.get("wins", 0)
        _losses = stats.get("losses", 0)
        _draws = stats.get("draws", 0)


def _save_models():
    """Persist both models to disk."""
    # White model
    white_path = _get_model_path_for("white")
    white_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model": _model_white.state_dict(),
            "optimizer": _optimizer_white.state_dict(),
        },
        str(white_path),
    )

    # Black model carries the ELO / game stats
    black_path = _get_model_path_for("black")
    torch.save(
        {
            "model": _model_black.state_dict(),
            "optimizer": _optimizer_black.state_dict(),
            "elo": _elo,
            "games_played": _games_played,
            "wins": _wins,
            "losses": _losses,
            "draws": _draws,
        },
        str(black_path),
    )


def unload_model() -> None:
    """
    Reset all in-memory model state.

    Call this when switching the active profile so that the next call to
    _ensure_models() loads the new profile's checkpoints from disk.
    """
    global _model_white, _optimizer_white, _model_black, _optimizer_black
    global _elo, _games_played, _wins, _losses, _draws
    global _last_value_estimate, _game_positions
    _model_white = None
    _optimizer_white = None
    _model_black = None
    _optimizer_black = None
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
    _ensure_models()
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

    _ensure_models()

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


def _pick_move(model, board, color, last_move, castling_rights):
    """
    Core move-picking logic shared by ml_ai_move and ml_ai_move_for.
    Returns (chosen_idx, move_map, value_estimate).
    """
    moves = all_legal_moves(board, color, last_move, castling_rights)
    if not moves:
        return None, {}, 0.0

    tensor = board_to_tensor(board, color, castling_rights, last_move)

    with torch.no_grad():
        policy_logits, value = model(tensor)

    value_estimate = float(value.item())

    mask = torch.full((4096,), float("-inf"))
    move_map = {}
    for fr, fc, tr, tc in moves:
        idx = move_to_index(fr, fc, tr, tc)
        mask[idx] = 0.0
        move_map[idx] = (fr, fc, tr, tc)

    masked = policy_logits.squeeze(0) + mask
    probs = torch.softmax(masked, dim=0)
    chosen_idx = int(torch.multinomial(probs, 1).item())

    return chosen_idx, move_map, value_estimate


def ml_ai_move(board, last_move, castling_rights, progress=None):
    """
    Pick a move for black using the black model.  Returns (fr, fc, tr, tc) or None.
    Also updates _last_value_estimate with the model's confidence.
    """
    global _last_value_estimate

    _ensure_models()
    chosen_idx, move_map, value_estimate = _pick_move(
        _model_black, board, "black", last_move, castling_rights
    )
    if chosen_idx is None:
        return None

    _last_value_estimate = value_estimate

    # Record this position for training
    tensor = board_to_tensor(board, "black", castling_rights, last_move)
    _game_positions.append((tensor.squeeze(0), chosen_idx, "black"))

    if progress is not None:
        progress[0] = 1
        progress[1] = 1

    return move_map[chosen_idx]


def ml_ai_move_for(board, color, last_move, castling_rights, progress=None):
    """
    Pick a move for *any* colour using that colour's dedicated model.

    Unlike ml_ai_move(), this function does NOT append to _game_positions.
    Position recording is handled entirely by do_move() so that self-play
    games don't double-record moves.

    Updates _last_value_estimate with the model's evaluation from `color`'s
    perspective (positive = good for `color`).

    Returns (fr, fc, tr, tc) or None.
    """
    global _last_value_estimate

    _ensure_models()
    model = _model_white if color == "white" else _model_black
    chosen_idx, move_map, value_estimate = _pick_move(
        model, board, color, last_move, castling_rights
    )
    if chosen_idx is None:
        return None

    _last_value_estimate = value_estimate

    if progress is not None:
        progress[0] = 1
        progress[1] = 1

    return move_map[chosen_idx]


# ── Training ───────────────────────────────────────────────────────────────────


def _train_one_model(model, optimizer, positions, result, color, progress, offset):
    """
    Run one REINFORCE-style gradient step per position for a single model.
    `color` determines the sign of the target value.
    `offset` is added to progress[0] so both models share one progress counter.
    """
    model.train()
    for i, (tensor, move_idx, _) in enumerate(positions):
        target_val = result if color == "white" else -result

        inp = tensor.unsqueeze(0)
        policy_logits, value = model(inp)

        value_target = torch.tensor([[target_val]], dtype=torch.float32)
        value_loss = nn.MSELoss()(value, value_target)

        move_target = torch.tensor([move_idx], dtype=torch.long)
        policy_loss = nn.CrossEntropyLoss()(policy_logits, move_target)

        weight = max(target_val, 0.1)
        loss = value_loss + policy_loss * weight

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if progress is not None:
            progress[0] = offset + i + 1

    model.eval()


def _train_both_models(white_positions, black_positions, result, progress):
    """
    Train white and black models on their respective positions.
    Designed to be called from a background thread.
    """
    if _model_white is None or _model_black is None:
        if progress is not None:
            progress[0] = progress[1]
        return

    _train_one_model(
        _model_white, _optimizer_white,
        white_positions, result, "white",
        progress, offset=0,
    )
    _train_one_model(
        _model_black, _optimizer_black,
        black_positions, result, "black",
        progress, offset=len(white_positions),
    )

    _save_models()


def start_training_async(result: float, progress: list) -> threading.Thread:
    """
    Snapshot the current game positions, split them by colour, initialise the
    progress counters, and spawn a daemon thread that trains both models and
    saves them when done.

    Call record_game_result() *before* this so that ELO is already updated in
    memory before the thread starts writing to the checkpoint.

    Returns the Thread object (already started).
    """
    global _game_positions

    positions = list(_game_positions)
    _game_positions = []

    white_positions = [(t, m, c) for t, m, c in positions if c == "white"]
    black_positions = [(t, m, c) for t, m, c in positions if c == "black"]

    total = max(1, len(positions))
    if progress is not None:
        progress[0] = 0
        progress[1] = total

    thread = threading.Thread(
        target=_train_both_models,
        args=(white_positions, black_positions, result, progress),
        daemon=True,
    )
    thread.start()
    return thread
