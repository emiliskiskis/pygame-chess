#!/usr/bin/env python3
"""
train_selfplay.py — Self-play training for the chess ML model.

Usage:
    python train_selfplay.py --games 1000
    python train_selfplay.py --games 5000 --save-every 100 --max-moves 300
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

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pt")

# torch.cuda.is_available() returns True for both NVIDIA (CUDA) and AMD (ROCm)
# because PyTorch's ROCm builds expose the same torch.cuda API via HIP.
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── Dashboard ────────────────────────────────────────────────────────────────


class Dashboard:
    """Logs training metrics to TensorBoard; prints a minimal status line."""

    def __init__(self, total_games, num_simulations, log_dir, games_completed=0):
        self.total_games = total_games
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
        self, result, length, total_loss, policy_loss, value_loss, buffer_size
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

        # ── Terminal line ─────────────────────────────────────────────────────
        elapsed = time.time() - self.start_time
        self.avg_spg = elapsed / self.games_done
        pct = self.games_done / self.total_games
        avg_len = sum(self.game_lengths) / self.games_done
        eta_secs = (self.total_games - self.games_done) * self.avg_spg
        eta_h = int(eta_secs // 3600)
        eta_m = int(eta_secs % 3600 // 60)
        eta_s = int(eta_secs % 60)
        print(
            f"\r  [{self.games_done:>{len(str(self.total_games))}}/{self.total_games}]"
            f"  {pct:5.1%}"
            f"  loss={total_loss:.4f}"
            f"  len={length:>3}"
            f"  avg_len={avg_len:5.1f}"
            f"  result={result_str:<5}"
            f"  {self.avg_spg:.1f}s/game"
            f"  ETA {eta_h:02d}:{eta_m:02d}:{eta_s:02d}" + " " * 4,
            flush=True,
        )

    def set_current(self, move_num, turn):
        """Overwrite the current terminal line with live move progress."""
        if self.avg_spg > 0:
            eta_secs = (self.total_games - self.games_done) * self.avg_spg
            eta_h = int(eta_secs // 3600)
            eta_m = int(eta_secs % 3600 // 60)
            eta_s = int(eta_secs % 60)
            eta_str = f"  ETA {eta_h:02d}:{eta_m:02d}:{eta_s:02d}"
        else:
            eta_str = ""
        print(
            f"\r  [{self.games_done:>{len(str(self.total_games))}}/{self.total_games}]"
            f"  move {move_num:>3} ({turn:<5}){eta_str}",
            end="",
            flush=True,
        )

    def close(self):
        self.writer.close()

    def final_summary(self):
        elapsed = time.time() - self.start_time
        h, m, s = int(elapsed // 3600), int(elapsed % 3600 // 60), int(elapsed % 60)
        avg_len = sum(self.game_lengths) / max(len(self.game_lengths), 1)
        avg_loss = sum(self.losses) / max(len(self.losses), 1)

        print("\n")
        print("  ══════════ Training Complete ══════════")
        print(f"  Games played:   {self.games_done}")
        print(f"  Total time:     {h:02d}:{m:02d}:{s:02d}")
        print(f"  White wins:     {self.white_wins}")
        print(f"  Black wins:     {self.black_wins}")
        print(f"  Draws:          {self.draws}")
        print(f"  Avg game len:   {avg_len:.1f} moves")
        print(f"  Avg loss:       {avg_loss:.4f}")
        print(f"\n  Model saved to: {MODEL_PATH}")


# ── Self-play ────────────────────────────────────────────────────────────────


def play_one_game(model, max_moves, temperature, num_simulations, c_puct, dashboard):
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
                result = 1.0 if winner == "white" else -1.0
            else:
                result = 0.0
            return positions, result, move_num

        dashboard.set_current(move_num + 1, turn)

        policy_dict, chosen_move, board_tensor = mcts_search(
            model,
            board,
            turn,
            last_move,
            castling_rights,
            num_simulations,
            c_puct=c_puct,
            device=DEVICE,
            temperature=temperature,
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

    # Policy loss: full weight on winning positions, reduced weight on draws,
    # zero on losing positions (don't reinforce bad moves).
    tv = target_vals.squeeze(1)
    winner_mask = tv > 0
    draw_mask = tv == 0
    policy_terms = []
    if winner_mask.any():
        lp = torch.log_softmax(policy_logits[winner_mask], dim=1)
        policy_terms.append(-(policy_targets[winner_mask] * lp).sum(dim=1).mean())
    if draw_mask.any():
        lp = torch.log_softmax(policy_logits[draw_mask], dim=1)
        policy_terms.append(0.3 * -(policy_targets[draw_mask] * lp).sum(dim=1).mean())
    if policy_terms:
        policy_loss = sum(policy_terms) / len(policy_terms)
        total_loss = value_loss + policy_loss
    else:
        policy_loss = torch.tensor(0.0, device=DEVICE)
        total_loss = value_loss

    optimizer.zero_grad()
    total_loss.backward()
    optimizer.step()
    model.eval()

    return total_loss.item(), policy_loss.item(), value_loss.item()


def load_or_create_model():
    model = ChessResNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)
    games_completed = 0

    if os.path.exists(MODEL_PATH):
        checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        games_completed = checkpoint.get("games_completed", 0)
        print(f"  Loaded existing model from {MODEL_PATH}")
        if games_completed:
            print(f"  Resuming from game {games_completed}")
    else:
        print("  Starting with a fresh model")

    model.to(DEVICE)
    model.eval()
    return model, optimizer, games_completed


def save_model(model, optimizer, games_completed):
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "games_completed": games_completed,
        },
        MODEL_PATH,
    )


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Chess ML self-play training")
    parser.add_argument(
        "--games",
        type=int,
        default=1000,
        help="Number of games to play (default: 1000)",
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
        default=50,
        help="MCTS simulations per move (default: 50). "
        "More = stronger data, slower games. Try 200+ for best quality.",
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

    run_name = time.strftime("%Y%m%d_%H%M%S")
    log_dir = args.log_dir or os.path.join("runs", run_name)

    print("\n\033[1;33m  ♚  Chess ML Self-Play Training  ♚\033[0m\n")
    model, optimizer, games_completed = load_or_create_model()
    print(f"  Device:      {DEVICE}{' (' + torch.cuda.get_device_name(0) + ')' if DEVICE.type == 'cuda' else ''}")
    print(f"  Games:       {args.games}")
    print(f"  Simulations: {args.simulations} per move  (MCTS)")
    print(f"  Max moves:   {args.max_moves}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Buffer size: {args.buffer_size}")
    print(f"  Batch size:  {args.batch_size}")
    print(f"  c_puct:      {args.c_puct}")
    print()

    if games_completed >= args.games:
        print(f"  Already completed {games_completed}/{args.games} games. Nothing to do.")
        print(f"  Pass a larger --games value to continue training.\n")
        return

    replay_buffer = deque(maxlen=args.buffer_size)
    dashboard = Dashboard(args.games, args.simulations, log_dir, games_completed)

    interrupted = False
    try:
        for game_num in range(games_completed, args.games):
            positions, result, length = play_one_game(
                model,
                args.max_moves,
                args.temperature,
                args.simulations,
                args.c_puct,
                dashboard,
            )

            for tensor, policy_dict, turn_color in positions:
                replay_buffer.append((tensor, policy_dict, turn_color, result))

            total_loss, policy_loss, value_loss = train_on_batch(
                model, optimizer, replay_buffer, args.batch_size
            )
            dashboard.update_game(
                result, length, total_loss, policy_loss, value_loss, len(replay_buffer)
            )

            if (game_num + 1) % args.save_every == 0:
                save_model(model, optimizer, game_num + 1)

    except KeyboardInterrupt:
        interrupted = True
        print("\n\n  Interrupted — saving model...")
        save_model(model, optimizer, dashboard.games_done)
        print(f"  Saved at game {dashboard.games_done}/{args.games}.")
        print(f"  Resume with: python train_selfplay.py --games {args.games}\n")
    else:
        save_model(model, optimizer, args.games)
    finally:
        dashboard.close()

    if not interrupted:
        dashboard.final_summary()


if __name__ == "__main__":
    main()
