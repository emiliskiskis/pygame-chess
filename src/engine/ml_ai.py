"""
ml_ai.py — ML-based AI move selection and online training.

Manages a single global ChessResNet model, providing:
  - ml_ai_move()       : pick a move during gameplay
  - record_position()  : record board state after each move
  - train_on_game()    : REINFORCE update from the completed game
  - clear_game_history(): reset recorded positions for a new game
"""

import os
import copy

import torch
import torch.nn as nn

from .ml_model import ChessResNet, board_to_tensor, move_to_index
from .board import all_legal_moves

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(_SCRIPT_DIR, "..", "..", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pt")

_model = None
_optimizer = None

# Positions collected during the current game:
#   list of (tensor, move_index, turn_color)
_game_positions = []


def _ensure_model():
    """Load or create the global model + optimizer."""
    global _model, _optimizer
    if _model is not None:
        return _model

    _model = ChessResNet()
    _optimizer = torch.optim.Adam(_model.parameters(), lr=1e-4)

    if os.path.exists(MODEL_PATH):
        checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
        _model.load_state_dict(checkpoint["model"])
        _optimizer.load_state_dict(checkpoint["optimizer"])

    _model.eval()
    return _model


def _save_model():
    """Persist model + optimizer state to disk."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(
        {"model": _model.state_dict(), "optimizer": _optimizer.state_dict()},
        MODEL_PATH,
    )


def record_position(board, turn, castling_rights, last_move, move_fr, move_to):
    """Record a (state, action, turn) tuple for later training."""
    tensor = board_to_tensor(board, turn, castling_rights, last_move)
    fr, fc = move_fr
    tr, tc = move_to
    idx = move_to_index(fr, fc, tr, tc)
    _game_positions.append((tensor.squeeze(0), idx, turn))


def clear_game_history():
    """Reset recorded positions for a new game."""
    global _game_positions
    _game_positions = []


def ml_ai_move(board, last_move, castling_rights, progress=None):
    """Pick a move using the ML model. Returns (fr, fc, tr, tc) or None."""
    model = _ensure_model()
    moves = all_legal_moves(board, "black", last_move, castling_rights)
    if not moves:
        return None

    tensor = board_to_tensor(board, "black", castling_rights, last_move)

    with torch.no_grad():
        policy_logits, _value = model(tensor)

    # Mask illegal moves
    mask = torch.full((4096,), float("-inf"))
    move_map = {}
    for fr, fc, tr, tc in moves:
        idx = move_to_index(fr, fc, tr, tc)
        mask[idx] = 0.0
        move_map[idx] = (fr, fc, tr, tc)

    masked = policy_logits.squeeze(0) + mask
    probs = torch.softmax(masked, dim=0)

    # Small temperature for slight exploration during play
    chosen_idx = torch.multinomial(probs, 1).item()
    chosen_move = move_map[chosen_idx]

    # Record this position for training
    _game_positions.append((tensor.squeeze(0), chosen_idx, "black"))

    if progress is not None:
        progress[0] = 1
        progress[1] = 1

    return chosen_move


def train_on_game(result):
    """
    Train the model on positions collected during this game.

    result: +1.0 if white won, -1.0 if black won, 0.0 for draw.
    """
    global _game_positions
    if not _game_positions or _model is None:
        _game_positions = []
        return

    _model.train()

    for tensor, move_idx, turn_color in _game_positions:
        # Target value from this player's perspective
        target_val = result if turn_color == "white" else -result

        inp = tensor.unsqueeze(0)
        policy_logits, value = _model(inp)

        # Value loss: predict the game outcome
        value_target = torch.tensor([[target_val]], dtype=torch.float32)
        value_loss = nn.MSELoss()(value, value_target)

        # Policy loss: reinforce moves that led to wins, discourage losses
        move_target = torch.tensor([move_idx], dtype=torch.long)
        policy_loss = nn.CrossEntropyLoss()(policy_logits, move_target)

        # Weight policy gradient by outcome sign
        # Always learn a little (0.1 floor) even from draws
        sign = target_val
        weight = max(sign, 0.1)
        loss = value_loss + policy_loss * weight

        _optimizer.zero_grad()
        loss.backward()
        _optimizer.step()

    _model.eval()
    _save_model()
    _game_positions = []
