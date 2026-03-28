import re

from ..constants import FILES
from .board import piece_color, piece_type, legal_moves


PIECE_LETTER = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight"}


def parse_algebraic(text, board, color, last_move, castling_rights):
    """
    Parse standard algebraic notation and return ((fr,fc),(tr,tc)) or None.
    Handles: e4, d5, exd5, Nf3, Bxe5, O-O, O-O-O, with optional disambiguation.
    """
    t = text.strip().rstrip("+#=")

    # Castling
    if t in ("O-O", "0-0", "o-o"):
        rk = 7 if color == "white" else 0
        moves = legal_moves(board, rk, 4, last_move, castling_rights)
        if (rk, 6) in moves:
            return (rk, 4), (rk, 6)
        return None
    if t in ("O-O-O", "0-0-0", "o-o-o"):
        rk = 7 if color == "white" else 0
        moves = legal_moves(board, rk, 4, last_move, castling_rights)
        if (rk, 2) in moves:
            return (rk, 4), (rk, 2)
        return None

    # Match: [piece][disambig][x][dest]
    pat = re.fullmatch(r"([KQRBN]?)([a-h]?[1-8]?)x?([a-h][1-8])", t, re.IGNORECASE)
    if not pat:
        return None

    piece_sym, disambig, dest_str = pat.group(1), pat.group(2), pat.group(3)
    tc = FILES.index(dest_str[0].lower())
    tr = 8 - int(dest_str[1])
    ptype = PIECE_LETTER.get(piece_sym.upper(), "pawn")

    candidates = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if piece_color(p) == color and piece_type(p) == ptype:
                if (tr, tc) in legal_moves(board, r, c, last_move, castling_rights):
                    candidates.append((r, c))

    if not candidates:
        return None

    if disambig:
        d = disambig.lower()
        filtered = []
        for r, c in candidates:
            if d in FILES and FILES[c] == d:
                filtered.append((r, c))
            elif d.isdigit() and (8 - r) == int(d):
                filtered.append((r, c))
        if filtered:
            candidates = filtered

    if len(candidates) == 1:
        return candidates[0], (tr, tc)
    return None
