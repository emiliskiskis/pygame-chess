"""
ml_model.py — Chess ResNet for policy + value prediction.

Input : 18-channel 8x8 tensor
Output: policy logits (4096 = 64*64 from-to pairs), value scalar (-1..+1)
"""

import torch
import torch.nn as nn
import numpy as np


PIECE_CHANNEL = {
    "white_pawn": 0, "white_knight": 1, "white_bishop": 2,
    "white_rook": 3, "white_queen": 4, "white_king": 5,
    "black_pawn": 6, "black_knight": 7, "black_bishop": 8,
    "black_rook": 9, "black_queen": 10, "black_king": 11,
}

# 18 input channels:
#  0-11  piece planes (one-hot per piece type)
#  12    turn (1.0 = white, 0.0 = black)
#  13    white kingside castling
#  14    white queenside castling
#  15    black kingside castling
#  16    black queenside castling
#  17    en passant target square
N_CHANNELS = 18


class ResidualBlock(nn.Module):
    def __init__(self, n_filters):
        super().__init__()
        self.conv1 = nn.Conv2d(n_filters, n_filters, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(n_filters)
        self.conv2 = nn.Conv2d(n_filters, n_filters, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(n_filters)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        residual = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual
        return self.relu(out)


class ChessResNet(nn.Module):
    def __init__(self, n_blocks=10, n_filters=128):
        super().__init__()
        # Input convolution
        self.conv_in = nn.Conv2d(N_CHANNELS, n_filters, 3, padding=1, bias=False)
        self.bn_in = nn.BatchNorm2d(n_filters)
        self.relu = nn.ReLU(inplace=True)

        # Residual tower
        self.res_blocks = nn.ModuleList(
            [ResidualBlock(n_filters) for _ in range(n_blocks)]
        )

        # Policy head: from-square x to-square = 64*64 = 4096
        self.policy_conv = nn.Conv2d(n_filters, 2, 1, bias=False)
        self.policy_bn = nn.BatchNorm2d(2)
        self.policy_fc = nn.Linear(2 * 64, 64 * 64)

        # Value head: single scalar in [-1, 1]
        self.value_conv = nn.Conv2d(n_filters, 1, 1, bias=False)
        self.value_bn = nn.BatchNorm2d(1)
        self.value_fc1 = nn.Linear(64, 128)
        self.value_fc2 = nn.Linear(128, 1)

    def forward(self, x):
        # Shared trunk
        out = self.relu(self.bn_in(self.conv_in(x)))
        for block in self.res_blocks:
            out = block(out)

        # Policy head
        p = self.relu(self.policy_bn(self.policy_conv(out)))
        p = p.view(p.size(0), -1)  # (B, 2*64)
        p = self.policy_fc(p)      # (B, 4096)

        # Value head
        v = self.relu(self.value_bn(self.value_conv(out)))
        v = v.view(v.size(0), -1)  # (B, 64)
        v = self.relu(self.value_fc1(v))
        v = torch.tanh(self.value_fc2(v))  # (B, 1)

        return p, v


def board_to_tensor(board, turn, castling_rights, last_move):
    """Convert board state to an (18, 8, 8) numpy array, then to a (1, 18, 8, 8) tensor."""
    planes = np.zeros((N_CHANNELS, 8, 8), dtype=np.float32)

    # Piece planes (0-11)
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece and piece in PIECE_CHANNEL:
                planes[PIECE_CHANNEL[piece], r, c] = 1.0

    # Turn plane (12)
    if turn == "white":
        planes[12, :, :] = 1.0

    # Castling planes (13-16)
    if castling_rights["white"]["kingside"]:
        planes[13, :, :] = 1.0
    if castling_rights["white"]["queenside"]:
        planes[14, :, :] = 1.0
    if castling_rights["black"]["kingside"]:
        planes[15, :, :] = 1.0
    if castling_rights["black"]["queenside"]:
        planes[16, :, :] = 1.0

    # En passant plane (17)
    if last_move:
        fr, fc, tr, tc = last_move
        if board[tr][tc] and "pawn" in board[tr][tc] and abs(fr - tr) == 2:
            ep_row = (fr + tr) // 2
            planes[17, ep_row, tc] = 1.0

    return torch.from_numpy(planes).unsqueeze(0)  # (1, 18, 8, 8)


def move_to_index(fr, fc, tr, tc):
    """Convert a move (from_row, from_col, to_row, to_col) to a flat index in [0, 4096)."""
    return (fr * 8 + fc) * 64 + (tr * 8 + tc)


def index_to_move(idx):
    """Convert a flat index back to (from_row, from_col, to_row, to_col)."""
    from_sq = idx // 64
    to_sq = idx % 64
    return from_sq // 8, from_sq % 8, to_sq // 8, to_sq % 8
