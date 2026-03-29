#!/usr/bin/env python3
"""
train_selfplay.py — Self-play training for the chess ML model.

Usage:
    python train_selfplay.py --games 1000
    python train_selfplay.py --games 5000 --save-every 100 --max-moves 300
"""

import argparse
import copy
import os
import sys
import time

import torch
import torch.nn as nn

# Add project root to path so we can import from src/
sys.path.insert(0, os.path.dirname(__file__))

from src.engine.board import (
    starting_board,
    all_legal_moves,
    execute_move,
    is_in_check,
    opponent,
)
from src.engine.ml_model import ChessResNet, board_to_tensor, move_to_index

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pt")


# ── Dashboard ────────────────────────────────────────────────────────────────

class Dashboard:
    """Terminal dashboard using ANSI escape codes."""

    def __init__(self, total_games):
        self.total_games = total_games
        self.start_time = time.time()
        self.games_done = 0
        self.white_wins = 0
        self.black_wins = 0
        self.draws = 0
        self.game_lengths = []
        self.losses = []
        self.current_move = 0
        self.current_turn = "white"
        self.last_result = ""

    def update_game(self, result, length, loss):
        self.games_done += 1
        self.game_lengths.append(length)
        self.losses.append(loss)
        if result > 0:
            self.white_wins += 1
            self.last_result = "White won"
        elif result < 0:
            self.black_wins += 1
            self.last_result = "Black won"
        else:
            self.draws += 1
            self.last_result = "Draw"

    def set_current(self, move_num, turn):
        self.current_move = move_num
        self.current_turn = turn

    def render(self):
        elapsed = time.time() - self.start_time
        h, m, s = int(elapsed // 3600), int(elapsed % 3600 // 60), int(elapsed % 60)

        avg_len = sum(self.game_lengths) / max(len(self.game_lengths), 1)
        last10 = self.game_lengths[-10:]
        avg_last10 = sum(last10) / max(len(last10), 1)

        last_loss = self.losses[-1] if self.losses else 0.0
        avg_loss = sum(self.losses) / max(len(self.losses), 1)

        games_per_sec = self.games_done / max(elapsed, 0.1)
        eta = (self.total_games - self.games_done) / max(games_per_sec, 0.001)
        eta_h, eta_m, eta_s = int(eta // 3600), int(eta % 3600 // 60), int(eta % 60)

        pct = self.games_done / max(self.total_games, 1)
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "\033[92m" + "█" * filled + "\033[90m" + "░" * (bar_len - filled) + "\033[0m"

        w_pct = self.white_wins / max(self.games_done, 1) * 100
        b_pct = self.black_wins / max(self.games_done, 1) * 100
        d_pct = self.draws / max(self.games_done, 1) * 100

        # Strength indicator: as training progresses, games get longer (smarter play)
        strength_bar_len = 20
        # Use average game length as a rough proxy (longer = smarter, up to ~100 moves)
        strength = min(avg_len / 100.0, 1.0)
        s_filled = int(strength_bar_len * strength)
        s_bar = "\033[95m" + "█" * s_filled + "\033[90m" + "░" * (strength_bar_len - s_filled) + "\033[0m"

        lines = [
            "",
            "\033[1;33m  ╔══════════════════════════════════════════════════╗\033[0m",
            "\033[1;33m  ║     ♚  Chess ML Self-Play Training  ♚          ║\033[0m",
            "\033[1;33m  ╚══════════════════════════════════════════════════╝\033[0m",
            "",
            f"  \033[1mProgress:\033[0m  {bar}  {self.games_done}/{self.total_games} ({pct:.1%})",
            f"  \033[1mElapsed:\033[0m   {h:02d}:{m:02d}:{s:02d}        \033[1mETA:\033[0m {eta_h:02d}:{eta_m:02d}:{eta_s:02d}        \033[1mSpeed:\033[0m {games_per_sec:.1f} games/s",
            "",
            "  \033[90m──────────────────────────────────────────────────\033[0m",
            "",
            f"  \033[1mResults:\033[0m",
            f"    \033[97mWhite wins:\033[0m  {self.white_wins:>5}  ({w_pct:5.1f}%)",
            f"    \033[90mBlack wins:\033[0m  {self.black_wins:>5}  ({b_pct:5.1f}%)",
            f"    \033[93mDraws:     \033[0m  {self.draws:>5}  ({d_pct:5.1f}%)",
            "",
            f"  \033[1mGame Length:\033[0m",
            f"    Average:       {avg_len:6.1f} moves",
            f"    Last 10 avg:   {avg_last10:6.1f} moves",
            "",
            f"  \033[1mTraining Loss:\033[0m",
            f"    Last game:     {last_loss:8.4f}",
            f"    Running avg:   {avg_loss:8.4f}",
            "",
            f"  \033[1mEst. Strength:\033[0m  {s_bar}  ({avg_len:.0f} avg moves)",
            "",
            "  \033[90m──────────────────────────────────────────────────\033[0m",
            "",
            f"  \033[1mCurrent game:\033[0m  move {self.current_move}, {self.current_turn} to play",
            f"  \033[1mLast result:\033[0m   {self.last_result}",
            "",
        ]

        # Clear screen and draw
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

    def final_summary(self):
        elapsed = time.time() - self.start_time
        h, m, s = int(elapsed // 3600), int(elapsed % 3600 // 60), int(elapsed % 60)
        avg_len = sum(self.game_lengths) / max(len(self.game_lengths), 1)
        avg_loss = sum(self.losses) / max(len(self.losses), 1)

        print("\n\033[1;33m  ══════════ Training Complete ══════════\033[0m\n")
        print(f"  Games played:   {self.games_done}")
        print(f"  Total time:     {h:02d}:{m:02d}:{s:02d}")
        print(f"  White wins:     {self.white_wins}")
        print(f"  Black wins:     {self.black_wins}")
        print(f"  Draws:          {self.draws}")
        print(f"  Avg game len:   {avg_len:.1f} moves")
        print(f"  Avg loss:       {avg_loss:.4f}")
        print(f"\n  Model saved to: {MODEL_PATH}\n")


# ── Self-play ────────────────────────────────────────────────────────────────

def play_one_game(model, max_moves, temperature, dashboard):
    """Play a single self-play game. Returns (positions, result, move_count)."""
    board = starting_board()
    turn = "white"
    last_move = None
    castling_rights = {
        "white": {"kingside": True, "queenside": True},
        "black": {"kingside": True, "queenside": True},
    }
    positions = []  # list of (tensor, move_index, turn_color)

    for move_num in range(max_moves):
        dashboard.set_current(move_num + 1, turn)

        moves = all_legal_moves(board, turn, last_move, castling_rights)
        if not moves:
            if is_in_check(board, turn):
                winner = opponent(turn)
                result = 1.0 if winner == "white" else -1.0
            else:
                result = 0.0
            return positions, result, move_num

        tensor = board_to_tensor(board, turn, castling_rights, last_move)

        with torch.no_grad():
            policy_logits, _value = model(tensor)

        # Build legal move mask
        mask = torch.full((4096,), float("-inf"))
        move_map = {}
        for fr, fc, tr, tc in moves:
            idx = move_to_index(fr, fc, tr, tc)
            mask[idx] = 0.0
            move_map[idx] = (fr, fc, tr, tc)

        masked = policy_logits.squeeze(0) + mask
        probs = torch.softmax(masked / temperature, dim=0)

        chosen_idx = torch.multinomial(probs, 1).item()
        chosen_move = move_map[chosen_idx]

        positions.append((tensor.squeeze(0), chosen_idx, turn))

        fr, fc, tr, tc = chosen_move
        last_move, castling_rights, _note = execute_move(
            board, (fr, fc), (tr, tc), last_move, castling_rights, turn
        )
        turn = opponent(turn)

    # Draw by move limit
    return positions, 0.0, max_moves


def train_on_positions(model, optimizer, positions, result):
    """Train model on collected positions from one game. Returns average loss."""
    if not positions:
        return 0.0

    model.train()
    total_loss = 0.0

    for tensor, move_idx, turn_color in positions:
        target_val = result if turn_color == "white" else -result

        inp = tensor.unsqueeze(0)
        policy_logits, value = model(inp)

        # Value loss
        value_target = torch.tensor([[target_val]], dtype=torch.float32)
        value_loss = nn.MSELoss()(value, value_target)

        # Policy loss weighted by outcome
        move_target = torch.tensor([move_idx], dtype=torch.long)
        policy_loss = nn.CrossEntropyLoss()(policy_logits, move_target)

        weight = max(target_val, 0.1)
        loss = value_loss + policy_loss * weight

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    model.eval()
    return total_loss / len(positions)


def load_or_create_model():
    """Load existing model or create a new one."""
    model = ChessResNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    if os.path.exists(MODEL_PATH):
        checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        print(f"  Loaded existing model from {MODEL_PATH}")
    else:
        print("  Starting with a fresh model")

    model.eval()
    return model, optimizer


def save_model(model, optimizer):
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(
        {"model": model.state_dict(), "optimizer": optimizer.state_dict()},
        MODEL_PATH,
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Chess ML self-play training")
    parser.add_argument("--games", type=int, default=1000, help="Number of games to play (default: 1000)")
    parser.add_argument("--save-every", type=int, default=50, help="Save model every N games (default: 50)")
    parser.add_argument("--max-moves", type=int, default=200, help="Max moves per game before draw (default: 200)")
    parser.add_argument("--temperature", type=float, default=1.0, help="Sampling temperature (default: 1.0)")
    args = parser.parse_args()

    print("\n\033[1;33m  ♚  Chess ML Self-Play Training  ♚\033[0m\n")
    model, optimizer = load_or_create_model()
    print(f"  Games to play: {args.games}")
    print(f"  Save every:    {args.save_every} games")
    print(f"  Max moves:     {args.max_moves}")
    print(f"  Temperature:   {args.temperature}")
    print()

    dashboard = Dashboard(args.games)
    time.sleep(1)

    for game_num in range(args.games):
        positions, result, length = play_one_game(
            model, args.max_moves, args.temperature, dashboard
        )

        avg_loss = train_on_positions(model, optimizer, positions, result)
        dashboard.update_game(result, length, avg_loss)
        dashboard.render()

        if (game_num + 1) % args.save_every == 0:
            save_model(model, optimizer)

    # Final save
    save_model(model, optimizer)
    dashboard.final_summary()


if __name__ == "__main__":
    main()
