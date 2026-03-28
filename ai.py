import copy
import random

from board import (
    all_legal_moves,
    execute_move,
    piece_color,
    piece_type,
)


PIECE_VALUES = {
    "pawn": 100,
    "knight": 320,
    "bishop": 330,
    "rook": 500,
    "queen": 900,
    "king": 20000,
}
PST_PAWN = [
    [0, 0, 0, 0, 0, 0, 0, 0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5, 5, 10, 25, 25, 10, 5, 5],
    [0, 0, 0, 20, 20, 0, 0, 0],
    [5, -5, -10, 0, 0, -10, -5, 5],
    [5, 10, 10, -20, -20, 10, 10, 5],
    [0, 0, 0, 0, 0, 0, 0, 0],
]
PST_KNIGHT = [
    [-50, -40, -30, -30, -30, -30, -40, -50],
    [-40, -20, 0, 0, 0, 0, -20, -40],
    [-30, 0, 10, 15, 15, 10, 0, -30],
    [-30, 5, 15, 20, 20, 15, 5, -30],
    [-30, 0, 15, 20, 20, 15, 0, -30],
    [-30, 5, 10, 15, 15, 10, 5, -30],
    [-40, -20, 0, 5, 5, 0, -20, -40],
    [-50, -40, -30, -30, -30, -30, -40, -50],
]
PST_DEFAULT = [[0] * 8 for _ in range(8)]


def pst_score(ptype, row, col, color):
    t = (
        PST_PAWN
        if ptype == "pawn"
        else PST_KNIGHT
        if ptype == "knight"
        else PST_DEFAULT
    )
    r = row if color == "black" else 7 - row
    return t[r][col]


def evaluate(board):
    score = 0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p:
                v = PIECE_VALUES.get(piece_type(p), 0) + pst_score(
                    piece_type(p), r, c, piece_color(p)
                )
                score += v if piece_color(p) == "white" else -v
    return score


def minimax(board, depth, alpha, beta, maximising, last_move, castling_rights):
    color = "white" if maximising else "black"
    moves = all_legal_moves(board, color, last_move, castling_rights)
    if depth == 0 or not moves:
        return evaluate(board), None
    best_move = None
    random.shuffle(moves)
    if maximising:
        best = -999999
        for fr, fc, tr, tc in moves:
            b2 = copy.deepcopy(board)
            cr2 = copy.deepcopy(castling_rights)
            lm2, cr2, _ = execute_move(b2, (fr, fc), (tr, tc), last_move, cr2, "white")
            score, _ = minimax(b2, depth - 1, alpha, beta, False, lm2, cr2)
            if score > best:
                best = score
                best_move = (fr, fc, tr, tc)
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best, best_move
    else:
        best = 999999
        for fr, fc, tr, tc in moves:
            b2 = copy.deepcopy(board)
            cr2 = copy.deepcopy(castling_rights)
            lm2, cr2, _ = execute_move(b2, (fr, fc), (tr, tc), last_move, cr2, "black")
            score, _ = minimax(b2, depth - 1, alpha, beta, True, lm2, cr2)
            if score < best:
                best = score
                best_move = (fr, fc, tr, tc)
            beta = min(beta, best)
            if beta <= alpha:
                break
        return best, best_move


def ai_move(board, last_move, castling_rights):
    _, move = minimax(board, 3, -999999, 999999, False, last_move, castling_rights)
    return move
