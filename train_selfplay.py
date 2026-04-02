#!/usr/bin/env python3
"""
train_selfplay.py — Self-play training for the chess ML model.

Usage:
    python train_selfplay.py
    python train_selfplay.py --path models/my_model.pt
    python train_selfplay.py --simulations 50  # MCTS simulations per move (default: 50)

View training progress:
    tensorboard --logdir runs/
"""

import argparse
import os
import random
import sys
import time
from collections import deque

import torch
import torch.nn as nn

try:
    from torch.utils.tensorboard import SummaryWriter
except ImportError:
    print("TensorBoard not found. Install it with: pip install tensorboard")
    sys.exit(1)

# Add project root to path so we can import from src/
sys.path.insert(0, os.path.dirname(__file__))

from src.engine.board import (
    all_legal_moves,
    execute_move,
    is_in_check,
    opponent,
    starting_board,
)
from src.engine.mcts import MCTSNode, mcts_search
from src.engine.ml_model import ChessResNet

_DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "model.pt")

# torch.cuda.is_available() returns True for both NVIDIA (CUDA) and AMD (ROCm)
# because PyTorch's ROCm builds expose the same torch.cuda API via HIP.
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── Dashboard ────────────────────────────────────────────────────────────────


class Dashboard:
    """Logs training metrics to TensorBoard; prints a minimal status line."""

    def __init__(self, num_simulations, log_dir, games_completed=0):
        self.num_simulations = num_simulations
        self.start_time = time.time()
        self.games_done = games_completed  # offset so step numbers continue from checkpoint
        self.white_wins = 0
        self.black_wins = 0
        self.draws = 0
        self.game_lengths = []
        self.losses = []
        self.avg_spg = 0.0  # seconds per game, updated only when a game completes
        self.writer = SummaryWriter(log_dir=log_dir)
        print(f"  TensorBoard logs → {log_dir}")
        print(f"  Run: tensorboard --logdir {os.path.dirname(log_dir)}\n")

    def update_game(
        self, result, length, total_loss, policy_loss, value_loss, buffer_size, lr=None
    ):
        self.games_done += 1
        self.game_lengths.append(length)
        self.losses.append(total_loss)
        step = self.games_done

        if result > 0:
            self.white_wins += 1
            result_str = "white"
        elif result < 0:
            self.black_wins += 1
            result_str = "black"
        else:
            self.draws += 1
            result_str = "draw"

        # ── Scalar logging ────────────────────────────────────────────────────
        w = self.writer
        w.add_scalar("loss/total", total_loss, step)
        w.add_scalar("loss/policy", policy_loss, step)
        w.add_scalar("loss/value", value_loss, step)
        w.add_scalar("game/length", length, step)

        # Rolling averages (last 10 games)
        last10 = self.game_lengths[-10:]
        w.add_scalar("game/length_avg10", sum(last10) / len(last10), step)

        # Win rates (cumulative)
        w.add_scalar("rates/white_win", self.white_wins / step, step)
        w.add_scalar("rates/black_win", self.black_wins / step, step)
        w.add_scalar("rates/draw", self.draws / step, step)

        w.add_scalar("train/buffer_size", buffer_size, step)
        w.add_scalar(
            "train/loss_avg10", sum(self.losses[-10:]) / len(self.losses[-10:]), step
        )
        if lr is not None:
            w.add_scalar("train/lr", lr, step)

        # ── Terminal line ─────────────────────────────────────────────────────
        elapsed = time.time() - self.start_time
        self.avg_spg = elapsed / self.games_done
        avg_len = sum(self.game_lengths) / self.games_done
        print(
            f"\r  [game {self.games_done}]"
            f"  loss={total_loss:.4f}"
            f"  len={length:>3}"
            f"  avg_len={avg_len:5.1f}"
            f"  result={result_str:<5}"
            f"  {self.avg_spg:.1f}s/game" + " " * 4,
            flush=True,
        )

    def set_current(self, move_num, turn):
        """Overwrite the current terminal line with live move progress."""
        spg_str = f"  {self.avg_spg:.1f}s/game" if self.avg_spg > 0 else ""
        print(
            f"\r  [game {self.games_done + 1}]"
            f"  move {move_num:>3} ({turn:<5}){spg_str}",
            end="",
            flush=True,
        )

    def close(self):
        self.writer.close()

    def final_summary(self, model_path):
        elapsed = time.time() - self.start_time
        h, m, s = int(elapsed // 3600), int(elapsed % 3600 // 60), int(elapsed % 60)
        avg_len = sum(self.game_lengths) / max(len(self.game_lengths), 1)
        avg_loss = sum(self.losses) / max(len(self.losses), 1)

        print("\n")
        print("  ══════════ Training Stopped ══════════")
        print(f"  Games played:   {self.games_done}")
        print(f"  Total time:     {h:02d}:{m:02d}:{s:02d}")
        print(f"  White wins:     {self.white_wins}")
        print(f"  Black wins:     {self.black_wins}")
        print(f"  Draws:          {self.draws}")
        print(f"  Avg game len:   {avg_len:.1f} moves")
        print(f"  Avg loss:       {avg_loss:.4f}")
        print(f"\n  Model saved to: {model_path}")


# ── Self-play ────────────────────────────────────────────────────────────────


def play_one_game(model, max_moves, temperature, num_simulations, c_puct, dashboard, games_completed=0):
    """Play a single MCTS-guided self-play game.

    Returns (positions, result, move_count) where each position is
    (board_tensor, policy_dict, turn_color).  policy_dict maps move_idx to its
    normalised MCTS visit-count fraction — this is the training target for the
    policy head, much stronger than a single sampled move.
    """
    board = starting_board()
    turn = "white"
    last_move = None
    castling_rights = {
        "white": {"kingside": True, "queenside": True},
        "black": {"kingside": True, "queenside": True},
    }
    positions = []  # list of (tensor, policy_dict, turn_color)

    for move_num in range(max_moves):
        moves = all_legal_moves(board, turn, last_move, castling_rights)
        if not moves:
            if is_in_check(board, turn):
                winner = opponent(turn)
                base = 1.0 if winner == "white" else -1.0
                # Reward finishing faster: scale from 1.0 (move 0) down to 0.5 (move max_moves).
                brevity = 1.0 - 0.5 * (move_num / max_moves)
                result = base * brevity
            else:
                result = 0.0
            return positions, result, move_num

        dashboard.set_current(move_num + 1, turn)

        # Anneal temperature: stay high for early training; drop after move 30
        # once the model has seen enough games to have meaningful priors.
        if games_completed < 200 or move_num < 30:
            effective_temp = temperature
        else:
            effective_temp = max(0.1, temperature * 0.1)

        policy_dict, chosen_move, board_tensor = mcts_search(
            model,
            board,
            turn,
            last_move,
            castling_rights,
            num_simulations,
            c_puct=c_puct,
            device=DEVICE,
            temperature=effective_temp,
        )

        if chosen_move is None:
            return positions, 0.0, move_num

        positions.append((board_tensor, policy_dict, turn))

        fr, fc, tr, tc = chosen_move
        last_move, castling_rights, _note = execute_move(
            board, (fr, fc), (tr, tc), last_move, castling_rights, turn
        )
        turn = opponent(turn)

    return positions, 0.0, max_moves


def train_on_batch(model, optimizer, replay_buffer, batch_size):
    """Sample a random batch from the replay buffer and train.

    Returns (total_loss, policy_loss, value_loss).
    Policy loss uses soft cross-entropy against the MCTS visit-count distribution,
    applied only to positions where this side won.
    """
    n = len(replay_buffer)
    if n < 32:
        return 0.0, 0.0, 0.0

    actual_batch = min(batch_size, n)
    batch = random.sample(list(replay_buffer), actual_batch)
    B = len(batch)

    tensors = torch.stack([t for t, _, _, _ in batch]).to(DEVICE)  # (B, 18, 8, 8)

    policy_targets = torch.zeros(B, 4096, device=DEVICE)
    for i, (_, pd, _, _) in enumerate(batch):
        for idx, val in pd.items():
            policy_targets[i, idx] = val

    target_vals = torch.tensor(
        [r if c == "white" else -r for _, _, c, r in batch],
        dtype=torch.float32,
        device=DEVICE,
    ).unsqueeze(1)  # (B, 1)

    model.train()
    policy_logits, values = model(tensors)  # (B, 4096), (B, 1)

    value_loss = nn.MSELoss()(values, target_vals)

    # Policy loss: soft cross-entropy against MCTS visit distribution.
    # All positions (wins, draws, losses) contribute equally — the value head
    # already learns to discount bad positions; the policy head should still
    # learn which moves MCTS preferred regardless of the game outcome.
    lp = torch.log_softmax(policy_logits, dim=1)
    policy_loss = -(policy_targets * lp).sum(dim=1).mean()
    total_loss = value_loss + policy_loss

    optimizer.zero_grad()
    total_loss.backward()
    optimizer.step()
    model.eval()

    return total_loss.item(), policy_loss.item(), value_loss.item()


def load_or_create_model(model_path):
    model = ChessResNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)
    # Halve the learning rate every 500 games to stabilise late training.
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=500, gamma=0.5)
    games_completed = 0

    if os.path.exists(model_path):
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        if "scheduler" in checkpoint:
            scheduler.load_state_dict(checkpoint["scheduler"])
        games_completed = checkpoint.get("games_completed", 0)
        print(f"  Loaded existing model from {model_path}")
        if games_completed:
            print(f"  Resuming from game {games_completed}")
    else:
        print(f"  No model found at {model_path} — starting fresh")

    model.to(DEVICE)
    model.eval()
    return model, optimizer, scheduler, games_completed


def save_model(model, optimizer, scheduler, games_completed, model_path):
    os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "games_completed": games_completed,
        },
        model_path,
    )


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Chess ML self-play training (runs indefinitely; Ctrl-C to stop)"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=_DEFAULT_MODEL_PATH,
        help="Path to model checkpoint (default: models/model.pt)",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=50,
        help="Save model every N games (default: 50)",
    )
    parser.add_argument(
        "--max-moves",
        type=int,
        default=200,
        help="Max moves per game before draw (default: 200)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="Sampling temperature (default: 1.0)",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=50_000,
        help="Replay buffer capacity (default: 50000)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=256, help="Training batch size (default: 256)"
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=400,
        help="MCTS simulations per move (default: 400). "
        "More = stronger data, slower games.",
    )
    parser.add_argument(
        "--train-steps",
        type=int,
        default=10,
        help="Training batches per game (default: 10).",
    )
    parser.add_argument(
        "--c-puct",
        type=float,
        default=1.5,
        help="PUCT exploration constant (default: 1.5).",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="TensorBoard log directory (default: runs/<timestamp>)",
    )
    args = parser.parse_args()

    model_path = os.path.abspath(args.path)
    run_name = time.strftime("%Y%m%d_%H%M%S")
    log_dir = args.log_dir or os.path.join("runs", run_name)

    print("\n\033[1;33m  ♚  Chess ML Self-Play Training  ♚\033[0m\n")
    model, optimizer, scheduler, games_completed = load_or_create_model(model_path)
    print(f"  Model:       {model_path}")
    print(f"  Device:      {DEVICE}{' (' + torch.cuda.get_device_name(0) + ')' if DEVICE.type == 'cuda' else ''}")
    print(f"  Simulations: {args.simulations} per move  (MCTS)")
    print(f"  Max moves:   {args.max_moves}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Buffer size: {args.buffer_size}")
    print(f"  Batch size:  {args.batch_size}")
    print(f"  c_puct:      {args.c_puct}")
    print(f"  Ctrl-C to stop and save.\n")

    replay_buffer = deque(maxlen=args.buffer_size)
    dashboard = Dashboard(args.simulations, log_dir, games_completed)

    game_num = games_completed
    try:
        while True:
            positions, result, length = play_one_game(
                model,
                args.max_moves,
                args.temperature,
                args.simulations,
                args.c_puct,
                dashboard,
                games_completed=game_num,
            )

            for tensor, policy_dict, turn_color in positions:
                replay_buffer.append((tensor, policy_dict, turn_color, result))

            for _ in range(args.train_steps - 1):
                train_on_batch(model, optimizer, replay_buffer, args.batch_size)
            total_loss, policy_loss, value_loss = train_on_batch(
                model, optimizer, replay_buffer, args.batch_size
            )
            dashboard.update_game(
                result, length, total_loss, policy_loss, value_loss, len(replay_buffer),
                lr=scheduler.get_last_lr()[0],
            )

            game_num += 1
            scheduler.step()
            if game_num % args.save_every == 0:
                save_model(model, optimizer, scheduler, game_num, model_path)

    except KeyboardInterrupt:
        print("\n\n  Interrupted — saving model...")
        save_model(model, optimizer, scheduler, dashboard.games_done, model_path)
        print(f"  Saved at game {dashboard.games_done}.")
        print(f"  Resume with: python train_selfplay.py --path \"{model_path}\"\n")
    finally:
        dashboard.close()

    dashboard.final_summary(model_path)


if __name__ == "__main__":
    main()
