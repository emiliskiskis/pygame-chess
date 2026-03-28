"""
Chess – main.py
Controls
--------
Mouse           : click / drag pieces
Notation box    : always-visible bar at the bottom; type e.g. "e4", "Nf3", "O-O" + Enter
Arrow keys      : move board cursor
Space / Enter   : confirm cursor selection (when notation bar is empty)
Escape          : open / close pause menu  (clears notation bar if text is present)
F11             : toggle fullscreen
"""

import copy
import io
import os
import random
import re
import sys

import pygame

try:
    import cairosvg

    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_TILE = 40
DEFAULT_TILE = 80
FILES = "abcdefgh"
RANKS = "87654321"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(SCRIPT_DIR, "assets")

WHITE_TILE = (240, 217, 181)
BLACK_TILE = (181, 136, 99)
HIGHLIGHT_COLOR = (20, 85, 30, 180)
SELECT_COLOR = (20, 85, 125, 180)
LAST_MOVE_COLOR = (180, 180, 20, 80)
CURSOR_COLOR = (200, 50, 200, 160)
BORDER_BG = (40, 40, 40)
COORD_COLOR = (220, 220, 220)
PANEL_BG = (28, 28, 28)
PANEL_HEADER = (60, 60, 60)
PANEL_TEXT_W = (240, 240, 240)
PANEL_TEXT_B = (180, 180, 180)

MODE_MENU = "menu"
MODE_PVP = "pvp"
MODE_AI = "ai"
MODE_LEARNING = "learning"


# ---------------------------------------------------------------------------
# Layout  - recomputed on every resize / fullscreen toggle
# ---------------------------------------------------------------------------
class Layout:
    PANEL_MIN = 160

    def __init__(self, win_w, win_h):
        self.update(win_w, win_h)

    def update(self, win_w, win_h):
        self.win_w = win_w
        self.win_h = win_h

        # Reserve fixed fractions for borders, then fit 8 tiles
        bt_est = max(50, win_h // 9)
        bb_est = max(40, win_h // 11)
        bs_est = max(20, win_w // 24)

        tile_h = (win_h - bt_est - bb_est) // 8
        tile_w = (win_w - bs_est * 2 - self.PANEL_MIN) // 8
        tile = max(MIN_TILE, min(tile_h, tile_w))

        self.tile = tile
        self.border_side = max(20, tile // 2)
        self.border_top = max(50, tile + 5)
        self.border_bottom = max(40, tile // 2)

        self.board_px = tile * 8
        self.board_w = self.board_px + self.border_side * 2
        self.panel_w = max(self.PANEL_MIN, win_w - self.board_w)
        self.window_w = self.board_w + self.panel_w
        self.window_h = self.board_px + self.border_top + self.border_bottom

        # Notation bar inside the bottom border
        bar_h = max(24, tile // 3)
        self.bar_h = bar_h
        self.bar_y = self.board_px + self.border_top + (self.border_bottom - bar_h) // 2
        self.bar_x = self.border_side
        self.bar_w = self.board_px

        # Font sizes scale with tile
        s = tile / DEFAULT_TILE
        self.fs_coord = max(10, int(16 * s))
        self.fs_status = max(12, int(18 * s))
        self.fs_piece = max(24, int(52 * s))
        self.fs_panel = max(10, int(14 * s))
        self.fs_header = max(11, int(17 * s))
        self.fs_tip = max(9, int(13 * s))
        self.fs_title = max(28, int(56 * s))
        self.fs_btn = max(14, int(20 * s))
        self.fs_sub = max(10, int(14 * s))
        self.fs_over = max(20, int(34 * s))
        self.fs_bar = max(11, int(15 * s))
        self.panel_line = max(16, int(22 * s))


# ---------------------------------------------------------------------------
# SVG piece loading
# ---------------------------------------------------------------------------
def load_svg(path, size):
    png = cairosvg.svg2png(url=path, output_width=size, output_height=size)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def load_pieces(asset_dir, size):
    pieces = {}
    if not HAS_CAIRO or not os.path.isdir(asset_dir):
        return pieces
    for color in ("white", "black"):
        for name in ("king", "queen", "rook", "bishop", "knight", "pawn"):
            path = os.path.join(asset_dir, f"{name}_{color}.svg")
            key = f"{color}_{name}"
            if os.path.isfile(path):
                try:
                    pieces[key] = load_svg(path, size)
                except Exception:
                    pass
    return pieces


def reload_pieces(asset_dir, size, existing):
    if not HAS_CAIRO or not existing:
        return existing
    return load_pieces(asset_dir, size)


# ---------------------------------------------------------------------------
# Board helpers
# ---------------------------------------------------------------------------
def starting_board():
    back = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]
    board = [[None] * 8 for _ in range(8)]
    for col in range(8):
        board[0][col] = f"black_{back[col]}"
        board[1][col] = "black_pawn"
        board[6][col] = "white_pawn"
        board[7][col] = f"white_{back[col]}"
    return board


def piece_color(p):
    return p.split("_")[0] if p else None


def piece_type(p):
    return p.split("_")[1] if p else None


def opponent(c):
    return "black" if c == "white" else "white"


def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


# ---------------------------------------------------------------------------
# Chess logic
# ---------------------------------------------------------------------------
def raw_moves(board, row, col):
    piece = board[row][col]
    if not piece:
        return []
    color, ptype = piece_color(piece), piece_type(piece)
    moves = []

    def slide(dirs):
        for dr, dc in dirs:
            r, c = row + dr, col + dc
            while in_bounds(r, c):
                if board[r][c] is None:
                    moves.append((r, c))
                elif piece_color(board[r][c]) != color:
                    moves.append((r, c))
                    break
                else:
                    break
                r += dr
                c += dc

    def jump(offs):
        for dr, dc in offs:
            r, c = row + dr, col + dc
            if in_bounds(r, c) and piece_color(board[r][c]) != color:
                moves.append((r, c))

    if ptype == "rook":
        slide([(1, 0), (-1, 0), (0, 1), (0, -1)])
    elif ptype == "bishop":
        slide([(1, 1), (1, -1), (-1, 1), (-1, -1)])
    elif ptype == "queen":
        slide([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)])
    elif ptype == "knight":
        jump([(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)])
    elif ptype == "king":
        jump([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)])
    elif ptype == "pawn":
        d = -1 if color == "white" else 1
        sr = 6 if color == "white" else 1
        r = row + d
        if in_bounds(r, col) and board[r][col] is None:
            moves.append((r, col))
            if row == sr and board[r + d][col] is None:
                moves.append((r + d, col))
        for dc in (-1, 1):
            r, c = row + d, col + dc
            if in_bounds(r, c) and piece_color(board[r][c]) == opponent(color):
                moves.append((r, c))
    return moves


def find_king(board, color):
    for r in range(8):
        for c in range(8):
            if board[r][c] == f"{color}_king":
                return r, c
    return None


def is_in_check(board, color):
    kp = find_king(board, color)
    if kp is None:
        return False
    for r in range(8):
        for c in range(8):
            if piece_color(board[r][c]) == opponent(color) and kp in raw_moves(
                board, r, c
            ):
                return True
    return False


def apply_move(board, fr, fc, tr, tc):
    b = copy.deepcopy(board)
    b[tr][tc] = b[fr][fc]
    b[fr][fc] = None
    return b


def legal_moves(board, row, col, last_move, castling_rights):
    piece = board[row][col]
    if not piece:
        return []
    color, ptype = piece_color(piece), piece_type(piece)
    cands = raw_moves(board, row, col)

    if ptype == "pawn" and last_move:
        fr, fc, tr, tc = last_move
        if (
            board[tr][tc] == f"{opponent(color)}_pawn"
            and abs(fr - tr) == 2
            and tr == row
            and abs(tc - col) == 1
        ):
            d = -1 if color == "white" else 1
            cands.append((row + d, tc))

    legal = []
    for tr, tc in cands:
        b2 = apply_move(board, row, col, tr, tc)
        if ptype == "pawn" and last_move:
            lfr, lfc, ltr, ltc = last_move
            if tc == ltc and tr != ltr and board[ltr][ltc] == f"{opponent(color)}_pawn":
                b2[ltr][ltc] = None
        if not is_in_check(b2, color):
            legal.append((tr, tc))

    if ptype == "king" and not is_in_check(board, color):
        rk = 7 if color == "white" else 0
        if row == rk and col == 4:
            if castling_rights[color]["kingside"]:
                if board[rk][5] is None and board[rk][6] is None:
                    m = apply_move(board, rk, 4, rk, 5)
                    d = apply_move(m, rk, 4, rk, 6)
                    if not is_in_check(m, color) and not is_in_check(d, color):
                        legal.append((rk, 6))
            if castling_rights[color]["queenside"]:
                if all(board[rk][c] is None for c in (1, 2, 3)):
                    m = apply_move(board, rk, 4, rk, 3)
                    d = apply_move(m, rk, 4, rk, 2)
                    if not is_in_check(m, color) and not is_in_check(d, color):
                        legal.append((rk, 2))
    return legal


def all_legal_moves(board, color, last_move, castling_rights):
    moves = []
    for r in range(8):
        for c in range(8):
            if piece_color(board[r][c]) == color:
                for dest in legal_moves(board, r, c, last_move, castling_rights):
                    moves.append((r, c, dest[0], dest[1]))
    return moves


def has_any_legal_move(board, color, last_move, castling_rights):
    return bool(all_legal_moves(board, color, last_move, castling_rights))


def promote_pawns(board, color):
    pr = 0 if color == "white" else 7
    for c in range(8):
        if board[pr][c] == f"{color}_pawn":
            board[pr][c] = f"{color}_queen"


def move_to_notation(
    fr, fc, tr, tc, moving, captured, ck, cq, ep, gives_check, gives_mate
):
    if ck:
        return "O-O" + ("#" if gives_mate else "+" if gives_check else "")
    if cq:
        return "O-O-O" + ("#" if gives_mate else "+" if gives_check else "")
    pt = piece_type(moving)
    sym = {
        "king": "K",
        "queen": "Q",
        "rook": "R",
        "bishop": "B",
        "knight": "N",
        "pawn": "",
    }[pt]
    df = FILES[tc]
    dr = str(8 - tr)
    if pt == "pawn":
        note = f"{FILES[fc]}x{df}{dr}" if (captured or ep) else f"{df}{dr}"
    else:
        note = f"{sym}{'x' if captured else ''}{df}{dr}"
    return note + ("#" if gives_mate else "+" if gives_check else "")


def execute_move(board, selected, dest, last_move, castling_rights, turn):
    fr, fc = selected
    tr, tc = dest
    moving = board[fr][fc]
    mtype = piece_type(moving)
    mcolor = piece_color(moving)
    captured = board[tr][tc]
    ck = mtype == "king" and fc == 4 and tc == 6
    cq = mtype == "king" and fc == 4 and tc == 2
    ep = False

    if mtype == "pawn" and last_move:
        lfr, lfc, ltr, ltc = last_move
        if tc == ltc and tr != ltr and board[ltr][ltc] == f"{opponent(mcolor)}_pawn":
            board[ltr][ltc] = None
            ep = True

    board[tr][tc] = moving
    board[fr][fc] = None

    if mtype == "king":
        rk = 7 if mcolor == "white" else 0
        if fc == 4 and tc == 6:
            board[rk][5] = board[rk][7]
            board[rk][7] = None
        if fc == 4 and tc == 2:
            board[rk][3] = board[rk][0]
            board[rk][0] = None
        castling_rights[mcolor]["kingside"] = False
        castling_rights[mcolor]["queenside"] = False
    if mtype == "rook":
        if fc == 7:
            castling_rights[mcolor]["kingside"] = False
        if fc == 0:
            castling_rights[mcolor]["queenside"] = False

    last_move = (fr, fc, tr, tc)
    promote_pawns(board, mcolor)
    opp = opponent(mcolor)
    gcheck = is_in_check(board, opp)
    gmate = gcheck and not has_any_legal_move(board, opp, last_move, castling_rights)
    note = move_to_notation(fr, fc, tr, tc, moving, captured, ck, cq, ep, gcheck, gmate)
    return last_move, castling_rights, note


# ---------------------------------------------------------------------------
# Algebraic notation parser
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# AI (minimax alpha-beta depth 3)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Learning tips
# ---------------------------------------------------------------------------
PIECE_TIPS = {
    "pawn": "Pawns move forward 1 square (2 from start) and capture diagonally.",
    "knight": "Knights move in an L-shape and can jump over pieces.",
    "bishop": "Bishops slide diagonally any number of squares.",
    "rook": "Rooks slide horizontally or vertically any number of squares.",
    "queen": "Queens combine rook and bishop - the most powerful piece.",
    "king": "Kings move 1 square in any direction. Protect yours!",
}


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------
def view_to_board(vr, vc, flipped):
    return (7 - vr, 7 - vc) if flipped else (vr, vc)


def board_to_view(r, c, flipped):
    return (7 - r, 7 - c) if flipped else (r, c)


def pixel_to_cell(mx, my, flipped, L):
    vc = (mx - L.border_side) // L.tile
    vr = (my - L.border_top) // L.tile
    if 0 <= vr < 8 and 0 <= vc < 8:
        return view_to_board(vr, vc, flipped)
    return None


# ---------------------------------------------------------------------------
# Font factory
# ---------------------------------------------------------------------------
def make_fonts(L):
    return {
        "coord": pygame.font.SysFont("Arial", L.fs_coord, bold=True),
        "status": pygame.font.SysFont("Arial", L.fs_status, bold=True),
        "piece": pygame.font.SysFont("Segoe UI Symbol", L.fs_piece),
        "panel": pygame.font.SysFont("Arial", L.fs_panel),
        "header": pygame.font.SysFont("Arial", L.fs_header, bold=True),
        "tip": pygame.font.SysFont("Arial", L.fs_tip),
        "title": pygame.font.SysFont("Arial", L.fs_title, bold=True),
        "btn": pygame.font.SysFont("Arial", L.fs_btn, bold=True),
        "sub": pygame.font.SysFont("Arial", L.fs_sub),
        "over": pygame.font.SysFont("Arial", L.fs_over, bold=True),
        "bar": pygame.font.SysFont("Arial", L.fs_bar),
    }


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_board(screen, L):
    screen.fill(BORDER_BG)
    for row in range(8):
        for col in range(8):
            color = WHITE_TILE if (row + col) % 2 == 0 else BLACK_TILE
            pygame.draw.rect(
                screen,
                color,
                (
                    L.border_side + col * L.tile,
                    L.border_top + row * L.tile,
                    L.tile,
                    L.tile,
                ),
            )


def draw_coordinates(screen, fonts, flipped, L):
    f = fonts["coord"]
    files = FILES if not flipped else FILES[::-1]
    ranks = RANKS if not flipped else RANKS[::-1]
    for col, letter in enumerate(files):
        x = L.border_side + col * L.tile + L.tile // 2
        for y in [
            L.border_top // 2 + L.border_top // 4,
            L.border_top + 8 * L.tile + L.border_bottom // 2,
        ]:
            s = f.render(letter, True, COORD_COLOR)
            screen.blit(s, s.get_rect(center=(x, y)))
    for row, number in enumerate(ranks):
        y = L.border_top + row * L.tile + L.tile // 2
        for x in [L.border_side // 2, L.border_side + 8 * L.tile + L.border_side // 2]:
            s = f.render(number, True, COORD_COLOR)
            screen.blit(s, s.get_rect(center=(x, y)))


def draw_highlights(screen, selected, moves, last_move_coords, cursor, flipped, L):
    ov = pygame.Surface((L.tile, L.tile), pygame.SRCALPHA)
    if last_move_coords:
        fr, fc, tr, tc = last_move_coords
        for r, c in [(fr, fc), (tr, tc)]:
            vr, vc = board_to_view(r, c, flipped)
            ov.fill(LAST_MOVE_COLOR)
            screen.blit(ov, (L.border_side + vc * L.tile, L.border_top + vr * L.tile))
    if selected:
        vr, vc = board_to_view(selected[0], selected[1], flipped)
        ov.fill(SELECT_COLOR)
        screen.blit(ov, (L.border_side + vc * L.tile, L.border_top + vr * L.tile))
    ov.fill(HIGHLIGHT_COLOR)
    for r, c in moves:
        vr, vc = board_to_view(r, c, flipped)
        screen.blit(ov, (L.border_side + vc * L.tile, L.border_top + vr * L.tile))
    if cursor:
        vr, vc = board_to_view(cursor[0], cursor[1], flipped)
        ov.fill(CURSOR_COLOR)
        screen.blit(ov, (L.border_side + vc * L.tile, L.border_top + vr * L.tile))
        pygame.draw.rect(
            screen,
            (200, 50, 200),
            (L.border_side + vc * L.tile, L.border_top + vr * L.tile, L.tile, L.tile),
            3,
        )


PIECE_SYMBOLS = {
    "white_king": "♔",
    "white_queen": "♕",
    "white_rook": "♖",
    "white_bishop": "♗",
    "white_knight": "♘",
    "white_pawn": "♙",
    "black_king": "♚",
    "black_queen": "♛",
    "black_rook": "♜",
    "black_bishop": "♝",
    "black_knight": "♞",
    "black_pawn": "♟",
}


def draw_pieces(screen, board, pieces, flipped, L, skip=None):
    for row in range(8):
        for col in range(8):
            p = board[row][col]
            if p and p in pieces and (row, col) != skip:
                vr, vc = board_to_view(row, col, flipped)
                screen.blit(
                    pieces[p], (L.border_side + vc * L.tile, L.border_top + vr * L.tile)
                )


def draw_fallback_pieces(screen, board, fonts, flipped, L, skip=None):
    f = fonts["piece"]
    for row in range(8):
        for col in range(8):
            p = board[row][col]
            if p and (row, col) != skip:
                vr, vc = board_to_view(row, col, flipped)
                surf = f.render(PIECE_SYMBOLS.get(p, "?"), True, (30, 30, 30))
                rect = surf.get_rect(
                    center=(
                        L.border_side + vc * L.tile + L.tile // 2,
                        L.border_top + vr * L.tile + L.tile // 2,
                    )
                )
                screen.blit(surf, rect)


def draw_status(screen, fonts, message, L):
    s = fonts["status"].render(message, True, (255, 220, 50))
    screen.blit(s, s.get_rect(center=(L.board_w // 2, L.border_top // 2)))


def draw_tip(screen, fonts, tip_text, L):
    if not tip_text:
        return
    f = fonts["tip"]
    max_w = L.board_px
    words = tip_text.split()
    lines = []
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if f.size(test)[0] <= max_w:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    total_h = f.get_linesize() * len(lines)
    y = L.border_top + 8 * L.tile + (L.border_bottom - total_h) // 2
    for ln in lines:
        s = f.render(ln, True, (180, 230, 180))
        screen.blit(s, (L.border_side, y))
        y += f.get_linesize()


def draw_notation_bar(screen, fonts, bar_text, bar_error, L):
    """Always-visible algebraic notation input bar."""
    f = fonts["bar"]
    bx, by = L.bar_x, L.bar_y
    bw, bh = L.bar_w, L.bar_h
    pad = max(4, bh // 5)

    pygame.draw.rect(screen, (20, 20, 20), (bx, by, bw, bh), border_radius=4)
    border_col = (200, 60, 60) if bar_error else (100, 100, 120)
    pygame.draw.rect(screen, border_col, (bx, by, bw, bh), 1, border_radius=4)

    label = f.render("Move: ", True, (140, 140, 160))
    screen.blit(label, (bx + pad, by + (bh - label.get_height()) // 2))

    text_x = bx + pad + label.get_width()
    disp = bar_text + ("|" if (pygame.time.get_ticks() // 500) % 2 == 0 else "")
    txt_s = f.render(disp, True, (220, 220, 255) if not bar_error else (255, 120, 120))
    screen.blit(txt_s, (text_x, by + (bh - txt_s.get_height()) // 2))

    hint = f.render("Enter to submit  |  Esc clears", True, (70, 70, 90))
    screen.blit(hint, hint.get_rect(midright=(bx + bw - pad, by + bh // 2)))


def draw_move_panel(screen, fonts, move_history, L):
    panel_rect = pygame.Rect(L.board_w, 0, L.panel_w, L.window_h)
    header_rect = pygame.Rect(L.board_w, 0, L.panel_w, L.border_top)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    pygame.draw.rect(screen, PANEL_HEADER, header_rect)
    title = fonts["header"].render("Moves", True, (255, 220, 50))
    screen.blit(
        title, title.get_rect(center=(L.board_w + L.panel_w // 2, L.border_top // 2))
    )
    pygame.draw.line(
        screen,
        (80, 80, 80),
        (L.board_w, L.border_top),
        (L.board_w + L.panel_w, L.border_top),
        1,
    )

    fp = fonts["panel"]
    col_num = L.board_w + 8
    col_w = L.board_w + 32
    col_b = L.board_w + L.panel_w // 2 + 8
    y_hdr = L.border_top + 6
    screen.blit(fp.render("#", True, (140, 140, 140)), (col_num, y_hdr))
    screen.blit(fp.render("White", True, PANEL_TEXT_W), (col_w, y_hdr))
    screen.blit(fp.render("Black", True, PANEL_TEXT_B), (col_b, y_hdr))
    pygame.draw.line(
        screen,
        (60, 60, 60),
        (L.board_w + 4, y_hdr + L.panel_line - 2),
        (L.board_w + L.panel_w - 4, y_hdr + L.panel_line - 2),
        1,
    )

    list_top = L.border_top + L.panel_line + 12
    visible_h = L.window_h - list_top - 10
    max_rows = max(1, visible_h // L.panel_line)

    pairs = []
    for i in range(0, len(move_history), 2):
        pairs.append(
            (
                move_history[i],
                move_history[i + 1] if i + 1 < len(move_history) else None,
            )
        )
    total_rows = len(pairs)
    scroll_offset = max(0, total_rows - max_rows)

    for idx, (wm, bm) in enumerate(pairs[scroll_offset:]):
        y = list_top + idx * L.panel_line
        if y + L.panel_line > L.window_h - 5:
            break
        mn = scroll_offset + idx + 1
        if scroll_offset + idx == total_rows - 1:
            pygame.draw.rect(
                screen,
                (50, 50, 60),
                (L.board_w + 4, y - 2, L.panel_w - 8, L.panel_line),
            )
        screen.blit(fp.render(f"{mn}.", True, (120, 120, 120)), (col_num, y))
        screen.blit(fp.render(wm, True, PANEL_TEXT_W), (col_w, y))
        if bm:
            screen.blit(fp.render(bm, True, PANEL_TEXT_B), (col_b, y))


def draw_menu(screen, fonts, hovered, L):
    screen.fill((20, 20, 20))
    cy = L.window_h // 2
    title = fonts["title"].render("♟ Chess", True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(L.window_w // 2, cy - 180)))
    sub = fonts["sub"].render("Choose a game mode", True, (180, 180, 180))
    screen.blit(sub, sub.get_rect(center=(L.window_w // 2, cy - 115)))

    buttons = [
        (MODE_PVP, "👥  Player vs Player", "Two humans play on the same computer"),
        (MODE_AI, "🤖  Player vs AI", "Play against the computer (black)"),
        (MODE_LEARNING, "📖  Learning Mode", "Hints, tips and move explanations"),
    ]
    bw = min(460, L.window_w - 80)
    bh = max(50, L.tile - 10)
    gap = bh + 18
    rects = {}
    for i, (m, label, desc) in enumerate(buttons):
        bx = L.window_w // 2 - bw // 2
        by = cy - 60 + i * gap
        rect = pygame.Rect(bx, by, bw, bh)
        rects[m] = rect
        col = (70, 70, 90) if hovered == m else (45, 45, 60)
        border = (255, 220, 50) if hovered == m else (80, 80, 100)
        pygame.draw.rect(screen, col, rect, border_radius=12)
        pygame.draw.rect(screen, border, rect, 2, border_radius=12)
        ls = fonts["btn"].render(label, True, (240, 240, 240))
        screen.blit(ls, ls.get_rect(midleft=(bx + 16, by + bh // 3)))
        ds = fonts["sub"].render(desc, True, (160, 160, 160))
        screen.blit(ds, ds.get_rect(midleft=(bx + 16, by + 2 * bh // 3)))

    hint = fonts["sub"].render(
        "F11 fullscreen   |   Arrow keys + Space: cursor   |   Type notation in bar below board",
        True,
        (80, 80, 80),
    )
    screen.blit(hint, hint.get_rect(center=(L.window_w // 2, L.window_h - 22)))
    return rects


def draw_pause_menu(screen, fonts, hovered, L):
    """Semi-transparent pause overlay with action buttons."""
    ov = pygame.Surface((L.window_w, L.window_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 185))
    screen.blit(ov, (0, 0))

    bw = min(320, L.window_w - 80)
    bh = max(44, L.tile - 16)
    gap = bh + 14
    cx = L.window_w // 2
    cy = L.window_h // 2

    title = fonts["over"].render("Paused", True, (255, 220, 50))
    screen.blit(
        title,
        title.get_rect(
            center=(
                cx,
                cy
                - len(["resume", "restart", "menu", "fullscreen", "quit"]) * gap // 2
                - bh,
            )
        ),
    )

    actions = [
        ("resume", "▶  Resume"),
        ("restart", "↺  Restart"),
        ("menu", "⌂  Main Menu"),
        ("fullscreen", "⛶  Toggle Fullscreen"),
        ("quit", "✕  Quit"),
    ]
    rects = {}
    total_h = len(actions) * gap - (gap - bh)
    start_y = cy - total_h // 2
    for i, (key, label) in enumerate(actions):
        bx = cx - bw // 2
        by = start_y + i * gap
        rect = pygame.Rect(bx, by, bw, bh)
        rects[key] = rect
        col = (80, 80, 110) if hovered == key else (45, 45, 65)
        border = (255, 220, 50) if hovered == key else (70, 70, 95)
        pygame.draw.rect(screen, col, rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)
        ls = fonts["btn"].render(label, True, (230, 230, 230))
        screen.blit(ls, ls.get_rect(center=rect.center))

    esc_hint = fonts["sub"].render("Escape to resume", True, (90, 90, 90))
    screen.blit(
        esc_hint, esc_hint.get_rect(center=(cx, start_y + len(actions) * gap + 10))
    )
    return rects


def draw_gameover_overlay(screen, fonts, message, over_hovered, L):
    ov = pygame.Surface((L.window_w, L.window_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 175))
    screen.blit(ov, (0, 0))
    ms = fonts["over"].render(message, True, (255, 220, 50))
    screen.blit(ms, ms.get_rect(center=(L.window_w // 2, L.window_h // 2 - 90)))

    actions = [
        ("restart", "↺  Play Again"),
        ("menu", "⌂  Main Menu"),
        ("quit", "✕  Quit"),
    ]
    bw = min(280, L.window_w - 80)
    bh = max(40, L.tile - 20)
    gap = bh + 12
    cx = L.window_w // 2
    cy = L.window_h // 2
    rects = {}
    total_h = len(actions) * gap - (gap - bh)
    start_y = cy - total_h // 2
    for i, (key, label) in enumerate(actions):
        bx = cx - bw // 2
        by = start_y + i * gap
        rect = pygame.Rect(bx, by, bw, bh)
        rects[key] = rect
        col = (80, 80, 110) if over_hovered == key else (45, 45, 65)
        border = (255, 220, 50) if over_hovered == key else (70, 70, 95)
        pygame.draw.rect(screen, col, rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)
        ls = fonts["btn"].render(label, True, (230, 230, 230))
        screen.blit(ls, ls.get_rect(center=rect.center))
    return rects


def post_move_status(board, turn, last_move, castling_rights):
    if not has_any_legal_move(board, turn, last_move, castling_rights):
        if is_in_check(board, turn):
            return f"Checkmate! {opponent(turn).capitalize()} wins!", True
        return "Stalemate! It's a draw.", True
    if is_in_check(board, turn):
        return f"{turn.capitalize()} is in check!", False
    return f"{turn.capitalize()}'s turn", False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    pygame.init()

    INIT_W, INIT_H = 960, 780
    screen = pygame.display.set_mode((INIT_W, INIT_H), pygame.RESIZABLE)
    pygame.display.set_caption("Chess")
    clock = pygame.time.Clock()

    fullscreen = False
    L = Layout(INIT_W, INIT_H)
    fonts = make_fonts(L)
    pieces = load_pieces(ASSET_DIR, L.tile)
    use_svg = bool(pieces)
    last_tile = L.tile

    # Resize debounce: apply layout only after the user stops dragging
    pending_size = None  # (w,h) waiting to be applied
    resize_timer = 0  # ticks when we will apply it
    RESIZE_DELAY = 100  # ms quiet period before re-layout

    mode = MODE_MENU
    menu_hovered = None
    menu_rects = {}
    paused = False
    pause_hovered = None
    pause_rects = {}
    over_hovered = None
    over_rects = {}

    bar_text = ""
    bar_error = False

    # Game state
    board = turn = selected = possible_moves = last_move = None
    castling_rights = status_msg = game_over = move_history = None
    flipped = cursor = tip_text = ai_thinking = None
    dragging = False
    drag_piece_key = drag_from = None
    drag_pos = (0, 0)

    def new_game(new_mode):
        nonlocal board, turn, selected, possible_moves, last_move
        nonlocal castling_rights, status_msg, game_over, move_history
        nonlocal flipped, cursor, tip_text, ai_thinking
        nonlocal bar_text, bar_error, paused, over_hovered, over_rects
        nonlocal pause_hovered, pause_rects
        board = starting_board()
        turn = "white"
        selected = None
        possible_moves = []
        last_move = None
        castling_rights = {
            "white": {"kingside": True, "queenside": True},
            "black": {"kingside": True, "queenside": True},
        }
        status_msg = "White's turn"
        game_over = False
        move_history = []
        flipped = False
        cursor = (7, 4)
        tip_text = ""
        ai_thinking = False
        bar_text = ""
        bar_error = False
        paused = False
        over_hovered = None
        over_rects = {}
        pause_hovered = None
        pause_rects = {}

    def apply_new_size(w, h):
        nonlocal L, fonts, pieces, use_svg, last_tile
        L = Layout(w, h)
        fonts = make_fonts(L)
        if L.tile != last_tile:
            pieces = reload_pieces(ASSET_DIR, L.tile, pieces)
            use_svg = bool(pieces)
            last_tile = L.tile

    def toggle_fullscreen():
        nonlocal fullscreen, screen
        fullscreen = not fullscreen
        if fullscreen:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode((INIT_W, INIT_H), pygame.RESIZABLE)
        apply_new_size(*screen.get_size())

    def do_move(from_sq, to_sq):
        nonlocal last_move, castling_rights, turn, selected, possible_moves
        nonlocal status_msg, game_over, tip_text, bar_text, bar_error
        last_move, castling_rights, notation = execute_move(
            board, from_sq, to_sq, last_move, castling_rights, turn
        )
        move_history.append(notation)
        turn = opponent(turn)
        selected = None
        possible_moves = []
        tip_text = ""
        bar_text = ""
        bar_error = False
        status_msg, game_over = post_move_status(
            board, turn, last_move, castling_rights
        )

    # ── Main loop ──────────────────────────────────────────────────────────
    while True:
        now = pygame.time.get_ticks()
        mx, my = pygame.mouse.get_pos()

        # Apply deferred resize once quiet
        if pending_size and now >= resize_timer:
            apply_new_size(*pending_size)
            pending_size = None

        # AI turn
        if (
            mode == MODE_AI
            and board
            and turn == "black"
            and not game_over
            and not ai_thinking
            and not paused
        ):
            ai_thinking = True
            move = ai_move(board, last_move, castling_rights)
            if move:
                do_move((move[0], move[1]), (move[2], move[3]))
            ai_thinking = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # ── Resize: buffer the latest size, defer application ──────────
            if event.type == pygame.VIDEORESIZE:
                w = max(event.w, 400)
                h = max(event.h, 400)
                # Update the window surface immediately so it doesn't look blank,
                # but only re-layout after the quiet period.
                screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                pending_size = (w, h)
                resize_timer = now + RESIZE_DELAY
                continue  # skip all other processing this frame

            # ── F11 always works ──────────────────────────────────────────
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                toggle_fullscreen()
                continue

            # ── Menu ──────────────────────────────────────────────────────
            if mode == MODE_MENU:
                if event.type == pygame.MOUSEMOTION:
                    menu_hovered = None
                    for m, rect in menu_rects.items():
                        if rect.collidepoint(mx, my):
                            menu_hovered = m
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for m, rect in menu_rects.items():
                        if rect.collidepoint(mx, my):
                            mode = m
                            new_game(m)
                            break
                continue

            # ── Pause menu ────────────────────────────────────────────────
            if paused and not game_over:
                if event.type == pygame.MOUSEMOTION:
                    pause_hovered = None
                    for k, rect in pause_rects.items():
                        if rect.collidepoint(mx, my):
                            pause_hovered = k
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for k, rect in pause_rects.items():
                        if rect.collidepoint(mx, my):
                            if k == "resume":
                                paused = False
                            elif k == "restart":
                                new_game(mode)
                            elif k == "menu":
                                mode = MODE_MENU
                            elif k == "fullscreen":
                                toggle_fullscreen()
                            elif k == "quit":
                                pygame.quit()
                                sys.exit()
                            break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    paused = False
                continue

            # ── Game-over overlay ─────────────────────────────────────────
            if game_over:
                if event.type == pygame.MOUSEMOTION:
                    over_hovered = None
                    for k, rect in over_rects.items():
                        if rect.collidepoint(mx, my):
                            over_hovered = k
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for k, rect in over_rects.items():
                        if rect.collidepoint(mx, my):
                            if k == "restart":
                                new_game(mode)
                            elif k == "menu":
                                mode = MODE_MENU
                            elif k == "quit":
                                pygame.quit()
                                sys.exit()
                            break
                continue

            # ── In-game ───────────────────────────────────────────────────
            block = mode == MODE_AI and turn == "black"

            if event.type == pygame.KEYDOWN and not block:
                # Escape: clear bar first, then pause
                if event.key == pygame.K_ESCAPE:
                    if bar_text:
                        bar_text = ""
                        bar_error = False
                    else:
                        paused = True
                        pause_hovered = None
                    continue

                # ── Notation bar ──────────────────────────────────────────
                if event.key == pygame.K_RETURN:
                    if bar_text.strip():
                        result = parse_algebraic(
                            bar_text, board, turn, last_move, castling_rights
                        )
                        if result:
                            do_move(*result)
                        else:
                            bar_error = True
                    # Enter with empty bar = confirm cursor move (see below)
                    elif selected and cursor in possible_moves:
                        do_move(selected, cursor)
                    continue

                if event.key == pygame.K_BACKSPACE:
                    bar_text = bar_text[:-1]
                    bar_error = False
                    continue

                # Characters valid in algebraic notation feed into the bar
                NOTATION_CHARS = set("abcdefghABCDEFGH12345678KQRBNkqrbnxXoO0-+#")
                if (
                    event.unicode
                    and event.unicode.isprintable()
                    and event.unicode in NOTATION_CHARS
                    and len(bar_text) < 12
                ):
                    bar_text += event.unicode
                    bar_error = False
                    continue

                # ── Arrow keys move cursor ────────────────────────────────
                kn = pygame.key.name(event.key).upper()
                if event.key in (
                    pygame.K_UP,
                    pygame.K_DOWN,
                    pygame.K_LEFT,
                    pygame.K_RIGHT,
                ):
                    dr = {"UP": -1, "DOWN": 1}.get(kn, 0)
                    dc = {"LEFT": -1, "RIGHT": 1}.get(kn, 0)
                    if flipped:
                        dr, dc = -dr, -dc
                    nr = max(0, min(7, cursor[0] + dr))
                    nc = max(0, min(7, cursor[1] + dc))
                    cursor = (nr, nc)
                    if mode == MODE_LEARNING and board[nr][nc]:
                        tip_text = PIECE_TIPS.get(piece_type(board[nr][nc]), "")
                    else:
                        tip_text = ""
                    continue

                # Space confirms cursor selection (Enter handled above)
                if event.key == pygame.K_SPACE:
                    r, c = cursor
                    clicked = board[r][c]
                    if selected:
                        if cursor in possible_moves:
                            do_move(selected, cursor)
                        elif clicked and piece_color(clicked) == turn:
                            selected = cursor
                            possible_moves = legal_moves(
                                board, r, c, last_move, castling_rights
                            )
                            if mode == MODE_LEARNING:
                                tip_text = PIECE_TIPS.get(piece_type(clicked), "")
                        else:
                            selected = None
                            possible_moves = []
                    else:
                        if clicked and piece_color(clicked) == turn:
                            selected = cursor
                            possible_moves = legal_moves(
                                board, r, c, last_move, castling_rights
                            )
                            if mode == MODE_LEARNING:
                                tip_text = PIECE_TIPS.get(piece_type(clicked), "")

            # ── Mouse ─────────────────────────────────────────────────────
            if not block:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    cell = pixel_to_cell(mx, my, flipped, L)
                    if cell is None:
                        continue
                    r, c = cell
                    clicked = board[r][c]
                    cursor = cell
                    if selected:
                        if cell in possible_moves:
                            do_move(selected, cell)
                        elif clicked and piece_color(clicked) == turn:
                            selected = cell
                            possible_moves = legal_moves(
                                board, r, c, last_move, castling_rights
                            )
                            dragging = True
                            drag_piece_key = clicked
                            drag_from = cell
                            drag_pos = (mx, my)
                            if mode == MODE_LEARNING:
                                tip_text = PIECE_TIPS.get(piece_type(clicked), "")
                        else:
                            selected = None
                            possible_moves = []
                            tip_text = ""
                    else:
                        if clicked and piece_color(clicked) == turn:
                            selected = cell
                            possible_moves = legal_moves(
                                board, r, c, last_move, castling_rights
                            )
                            dragging = True
                            drag_piece_key = clicked
                            drag_from = cell
                            drag_pos = (mx, my)
                            if mode == MODE_LEARNING:
                                tip_text = PIECE_TIPS.get(piece_type(clicked), "")

                if event.type == pygame.MOUSEMOTION:
                    drag_pos = (mx, my)
                    if mode == MODE_LEARNING and not selected:
                        cell = pixel_to_cell(mx, my, flipped, L)
                        if cell and board[cell[0]][cell[1]]:
                            tip_text = PIECE_TIPS.get(
                                piece_type(board[cell[0]][cell[1]]), ""
                            )
                        else:
                            tip_text = ""

                if (
                    event.type == pygame.MOUSEBUTTONUP
                    and event.button == 1
                    and dragging
                ):
                    dragging = False
                    cell = pixel_to_cell(mx, my, flipped, L)
                    if (
                        cell
                        and selected
                        and cell in possible_moves
                        and cell != selected
                    ):
                        do_move(selected, cell)

        # ── Render ────────────────────────────────────────────────────────
        if mode == MODE_MENU:
            menu_rects = draw_menu(screen, fonts, menu_hovered, L)
        else:
            draw_board(screen, L)
            if board:
                draw_highlights(
                    screen, selected, possible_moves, last_move, cursor, flipped, L
                )
            draw_coordinates(screen, fonts, flipped, L)

            skip = drag_from if dragging else None
            if board:
                if use_svg:
                    draw_pieces(screen, board, pieces, flipped, L, skip=skip)
                else:
                    draw_fallback_pieces(screen, board, fonts, flipped, L, skip=skip)

            if dragging and drag_piece_key:
                if use_svg and drag_piece_key in pieces:
                    img = pieces[drag_piece_key]
                    screen.blit(img, img.get_rect(center=drag_pos))
                else:
                    surf = fonts["piece"].render(
                        PIECE_SYMBOLS.get(drag_piece_key, "?"), True, (30, 30, 30)
                    )
                    screen.blit(surf, surf.get_rect(center=drag_pos))

            badges = {MODE_PVP: "PvP", MODE_AI: "vs AI", MODE_LEARNING: "Learning"}
            badge = fonts["sub"].render(badges.get(mode, ""), True, (120, 120, 120))
            screen.blit(badge, (L.board_w - badge.get_width() - 8, 6))

            if status_msg:
                draw_status(screen, fonts, status_msg, L)

            if mode == MODE_LEARNING and tip_text:
                draw_tip(screen, fonts, tip_text, L)
            else:
                draw_notation_bar(screen, fonts, bar_text, bar_error, L)

            draw_move_panel(screen, fonts, move_history or [], L)

            if game_over:
                over_rects = draw_gameover_overlay(
                    screen, fonts, status_msg, over_hovered, L
                )
            elif paused:
                pause_rects = draw_pause_menu(screen, fonts, pause_hovered, L)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
