import copy
import io
import os
import random
import sys

import cairosvg
import pygame

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TILE_SIZE = 80
BOARD_SIZE = 8
BORDER_SIDE = 40
BORDER_TOP = 85
BORDER = BORDER_SIDE
PANEL_W = 200
BOARD_W = TILE_SIZE * BOARD_SIZE + BORDER_SIDE * 2  # 720
WINDOW_W = BOARD_W + PANEL_W  # 920
WINDOW_H = TILE_SIZE * BOARD_SIZE + BORDER_SIDE + BORDER_TOP  # 765

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
PANEL_LINE_H = 22

FILES = "abcdefgh"
RANKS = "87654321"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(SCRIPT_DIR, "assets")

# ---------------------------------------------------------------------------
# Game modes
# ---------------------------------------------------------------------------
MODE_MENU = "menu"
MODE_PVP = "pvp"
MODE_AI = "ai"
MODE_LEARNING = "learning"


# ---------------------------------------------------------------------------
# SVG / piece loading
# ---------------------------------------------------------------------------
def load_svg(path: str, size: int) -> pygame.Surface:
    png = cairosvg.svg2png(url=path, output_width=size, output_height=size)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def load_pieces(asset_dir: str, size: int) -> dict:
    pieces = {}
    colors = ["white", "black"]
    names = ["king", "queen", "rook", "bishop", "knight", "pawn"]
    print(f"\nLoading pieces from: {asset_dir}")
    if not os.path.isdir(asset_dir):
        print(f"  ERROR: assets folder not found at {asset_dir}")
        return pieces
    for color in colors:
        for name in names:
            filename = f"{name}_{color}.svg"
            path = os.path.join(asset_dir, filename)
            key = f"{color}_{name}"
            if os.path.isfile(path):
                try:
                    pieces[key] = load_svg(path, size)
                    print(f"  OK  {filename}")
                except Exception as e:
                    print(f"  FAIL {filename}: {e}")
            else:
                print(f"  MISSING {filename}")
    print(f"\n  {len(pieces)}/{len(colors) * len(names)} pieces loaded.\n")
    return pieces


# ---------------------------------------------------------------------------
# Board
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


# ---------------------------------------------------------------------------
# Chess logic
# ---------------------------------------------------------------------------
def piece_color(p):
    return p.split("_")[0] if p else None


def piece_type(p):
    return p.split("_")[1] if p else None


def opponent(c):
    return "black" if c == "white" else "white"


def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def raw_moves(board, row, col):
    piece = board[row][col]
    if piece is None:
        return []
    color = piece_color(piece)
    ptype = piece_type(piece)
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
        for dc in [-1, 1]:
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
            if piece_color(board[r][c]) == opponent(color):
                if kp in raw_moves(board, r, c):
                    return True
    return False


def apply_move(board, fr, fc, tr, tc):
    b = copy.deepcopy(board)
    b[tr][tc] = b[fr][fc]
    b[fr][fc] = None
    return b


def legal_moves(board, row, col, last_move, castling_rights):
    piece = board[row][col]
    if piece is None:
        return []
    color = piece_color(piece)
    ptype = piece_type(piece)
    cands = raw_moves(board, row, col)

    # En-passant
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

    # Castling
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
                if (
                    board[rk][3] is None
                    and board[rk][2] is None
                    and board[rk][1] is None
                ):
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
    return len(all_legal_moves(board, color, last_move, castling_rights)) > 0


def promote_pawns(board, color):
    pr = 0 if color == "white" else 7
    for c in range(8):
        if board[pr][c] == f"{color}_pawn":
            board[pr][c] = f"{color}_queen"


# ---------------------------------------------------------------------------
# Notation
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Execute move
# ---------------------------------------------------------------------------
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
# AI  (minimax with alpha-beta, depth 3)
# ---------------------------------------------------------------------------
PIECE_VALUES = {
    "pawn": 100,
    "knight": 320,
    "bishop": 330,
    "rook": 500,
    "queen": 900,
    "king": 20000,
}

# Simple piece-square tables (encourages central control)
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
    table = (
        PST_PAWN
        if ptype == "pawn"
        else PST_KNIGHT
        if ptype == "knight"
        else PST_DEFAULT
    )
    r = row if color == "black" else 7 - row
    return table[r][col]


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
    if maximising:
        best = -999999
        random.shuffle(moves)
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
        random.shuffle(moves)
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
    """Return (fr,fc,tr,tc) for the best AI move as black."""
    _, move = minimax(board, 3, -999999, 999999, False, last_move, castling_rights)
    return move


# ---------------------------------------------------------------------------
# Learning mode: hints
# ---------------------------------------------------------------------------
PIECE_TIPS = {
    "pawn": "Pawns move forward 1 square (2 from start) and capture diagonally.",
    "knight": "Knights move in an L-shape and can jump over pieces.",
    "bishop": "Bishops slide diagonally any number of squares.",
    "rook": "Rooks slide horizontally or vertically any number of squares.",
    "queen": "Queens combine rook and bishop — the most powerful piece.",
    "king": "Kings move 1 square in any direction. Protect yours!",
}


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_board(screen):
    screen.fill(BORDER_BG)
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            color = WHITE_TILE if (row + col) % 2 == 0 else BLACK_TILE
            pygame.draw.rect(
                screen,
                color,
                (
                    BORDER_SIDE + col * TILE_SIZE,
                    BORDER_TOP + row * TILE_SIZE,
                    TILE_SIZE,
                    TILE_SIZE,
                ),
            )


def draw_coordinates(screen, font, flipped):
    files = FILES if not flipped else FILES[::-1]
    ranks = RANKS if not flipped else RANKS[::-1]
    for col, letter in enumerate(files):
        x = BORDER_SIDE + col * TILE_SIZE + TILE_SIZE // 2
        for y in [
            BORDER_TOP // 2 + 20,
            BORDER_TOP + BOARD_SIZE * TILE_SIZE + BORDER_SIDE // 2,
        ]:
            s = font.render(letter, True, COORD_COLOR)
            screen.blit(s, s.get_rect(center=(x, y)))
    for row, number in enumerate(ranks):
        y = BORDER_TOP + row * TILE_SIZE + TILE_SIZE // 2
        for x in [
            BORDER_SIDE // 2,
            BORDER_SIDE + BOARD_SIZE * TILE_SIZE + BORDER_SIDE // 2,
        ]:
            s = font.render(number, True, COORD_COLOR)
            screen.blit(s, s.get_rect(center=(x, y)))


def draw_highlights(screen, selected, moves, last_move_coords, cursor, flipped):
    overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)

    # Last move tint
    if last_move_coords:
        fr, fc, tr, tc = last_move_coords
        for r, c in [(fr, fc), (tr, tc)]:
            vr, vc = board_to_view(r, c, flipped)
            overlay.fill(LAST_MOVE_COLOR)
            screen.blit(
                overlay, (BORDER_SIDE + vc * TILE_SIZE, BORDER_TOP + vr * TILE_SIZE)
            )

    # Selected piece
    if selected:
        vr, vc = board_to_view(selected[0], selected[1], flipped)
        overlay.fill(SELECT_COLOR)
        screen.blit(
            overlay, (BORDER_SIDE + vc * TILE_SIZE, BORDER_TOP + vr * TILE_SIZE)
        )

    # Legal move dots
    overlay.fill(HIGHLIGHT_COLOR)
    for r, c in moves:
        vr, vc = board_to_view(r, c, flipped)
        screen.blit(
            overlay, (BORDER_SIDE + vc * TILE_SIZE, BORDER_TOP + vr * TILE_SIZE)
        )

    # Keyboard cursor
    if cursor:
        vr, vc = board_to_view(cursor[0], cursor[1], flipped)
        overlay.fill(CURSOR_COLOR)
        screen.blit(
            overlay, (BORDER_SIDE + vc * TILE_SIZE, BORDER_TOP + vr * TILE_SIZE)
        )
        pygame.draw.rect(
            screen,
            (200, 50, 200),
            (
                BORDER_SIDE + vc * TILE_SIZE,
                BORDER_TOP + vr * TILE_SIZE,
                TILE_SIZE,
                TILE_SIZE,
            ),
            3,
        )


def draw_pieces(screen, board, pieces, flipped, skip=None):
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            piece = board[row][col]
            if piece and piece in pieces and (row, col) != skip:
                vr, vc = board_to_view(row, col, flipped)
                screen.blit(
                    pieces[piece],
                    (BORDER_SIDE + vc * TILE_SIZE, BORDER_TOP + vr * TILE_SIZE),
                )


def draw_fallback_pieces(screen, board, font_large, flipped, skip=None):
    symbols = {
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
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            piece = board[row][col]
            if piece and (row, col) != skip:
                vr, vc = board_to_view(row, col, flipped)
                sym = symbols.get(piece, "?")
                surf = font_large.render(sym, True, (30, 30, 30))
                rect = surf.get_rect(
                    center=(
                        BORDER_SIDE + vc * TILE_SIZE + TILE_SIZE // 2,
                        BORDER_TOP + vr * TILE_SIZE + TILE_SIZE // 2,
                    )
                )
                screen.blit(surf, rect)


def draw_status(screen, font, message):
    s = font.render(message, True, (255, 220, 50))
    screen.blit(s, s.get_rect(center=(BOARD_W // 2, BORDER_TOP // 2 - 8)))


def draw_tip(screen, font_tip, tip_text):
    """Render a learning-mode tip at the bottom of the board area."""
    if not tip_text:
        return
    max_w = BOARD_W - BORDER_SIDE * 2
    words = tip_text.split()
    lines = []
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if font_tip.size(test)[0] <= max_w:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    y = BORDER_TOP + BOARD_SIZE * TILE_SIZE + 6
    for ln in lines:
        s = font_tip.render(ln, True, (180, 230, 180))
        screen.blit(s, (BORDER_SIDE, y))
        y += font_tip.get_linesize()


def draw_move_panel(screen, font_panel, font_header, move_history, scroll_offset):
    panel_rect = pygame.Rect(BOARD_W, 0, PANEL_W, WINDOW_H)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    header_rect = pygame.Rect(BOARD_W, 0, PANEL_W, BORDER_TOP)
    pygame.draw.rect(screen, PANEL_HEADER, header_rect)
    title = font_header.render("Moves", True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(BOARD_W + PANEL_W // 2, BORDER_TOP // 2)))
    pygame.draw.line(
        screen, (80, 80, 80), (BOARD_W, BORDER_TOP), (WINDOW_W, BORDER_TOP), 1
    )

    col_x_num = BOARD_W + 10
    col_x_w = BOARD_W + 40
    col_x_b = BOARD_W + 120
    y_hdr = BORDER_TOP + 8
    screen.blit(font_panel.render("#", True, (140, 140, 140)), (col_x_num, y_hdr))
    screen.blit(font_panel.render("White", True, PANEL_TEXT_W), (col_x_w, y_hdr))
    screen.blit(font_panel.render("Black", True, PANEL_TEXT_B), (col_x_b, y_hdr))
    pygame.draw.line(
        screen,
        (60, 60, 60),
        (BOARD_W + 5, y_hdr + PANEL_LINE_H - 2),
        (WINDOW_W - 5, y_hdr + PANEL_LINE_H - 2),
        1,
    )

    list_top = BORDER_TOP + PANEL_LINE_H + 14
    visible_h = WINDOW_H - list_top - 10
    max_rows = visible_h // PANEL_LINE_H

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
        y = list_top + idx * PANEL_LINE_H
        if y + PANEL_LINE_H > WINDOW_H - 5:
            break
        mn = scroll_offset + idx + 1
        if scroll_offset + idx == total_rows - 1:
            pygame.draw.rect(
                screen, (50, 50, 60), (BOARD_W + 4, y - 2, PANEL_W - 8, PANEL_LINE_H)
            )
        screen.blit(font_panel.render(f"{mn}.", True, (120, 120, 120)), (col_x_num, y))
        screen.blit(font_panel.render(wm, True, PANEL_TEXT_W), (col_x_w, y))
        if bm:
            screen.blit(font_panel.render(bm, True, PANEL_TEXT_B), (col_x_b, y))
    return scroll_offset


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------
def view_to_board(vr, vc, flipped):
    return (7 - vr, 7 - vc) if flipped else (vr, vc)


def board_to_view(r, c, flipped):
    return (7 - r, 7 - c) if flipped else (r, c)


def pixel_to_cell(mx, my, flipped):
    vc = (mx - BORDER_SIDE) // TILE_SIZE
    vr = (my - BORDER_TOP) // TILE_SIZE
    if 0 <= vr < 8 and 0 <= vc < 8:
        return view_to_board(vr, vc, flipped)
    return None


# ---------------------------------------------------------------------------
# Menu screen
# ---------------------------------------------------------------------------
def draw_menu(screen, fonts, hovered):
    screen.fill((20, 20, 20))
    title_font, btn_font, sub_font = fonts

    # Title
    title = title_font.render("♟ Chess", True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(WINDOW_W // 2, 120)))

    subtitle = sub_font.render("Choose a game mode", True, (180, 180, 180))
    screen.blit(subtitle, subtitle.get_rect(center=(WINDOW_W // 2, 185)))

    buttons = [
        (MODE_PVP, "👥  Player vs Player", "Two humans play on the same computer"),
        (MODE_AI, "🤖  Player vs AI", "Play against the computer (black)"),
        (MODE_LEARNING, "📖  Learning Mode", "Hints, tips and move explanations"),
    ]

    rects = {}
    for i, (mode, label, desc) in enumerate(buttons):
        bw, bh = 420, 70
        bx = WINDOW_W // 2 - bw // 2
        by = 240 + i * 100
        rect = pygame.Rect(bx, by, bw, bh)
        rects[mode] = rect

        col = (70, 70, 90) if hovered == mode else (45, 45, 60)
        border = (255, 220, 50) if hovered == mode else (80, 80, 100)
        pygame.draw.rect(screen, col, rect, border_radius=12)
        pygame.draw.rect(screen, border, rect, 2, border_radius=12)

        ls = btn_font.render(label, True, (240, 240, 240))
        screen.blit(ls, ls.get_rect(midleft=(bx + 20, by + 22)))
        ds = sub_font.render(desc, True, (160, 160, 160))
        screen.blit(ds, ds.get_rect(midleft=(bx + 20, by + 50)))

    # Keyboard hint
    hint = sub_font.render(
        "Tip: use arrow keys + Enter/Space to move with keyboard during the game",
        True,
        (100, 100, 100),
    )
    screen.blit(hint, hint.get_rect(center=(WINDOW_W // 2, WINDOW_H - 30)))

    return rects


# ---------------------------------------------------------------------------
# After-game screen
# ---------------------------------------------------------------------------
def draw_gameover_overlay(screen, font_large, font_small, message):
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))
    ms = font_large.render(message, True, (255, 220, 50))
    screen.blit(ms, ms.get_rect(center=(BOARD_W // 2, WINDOW_H // 2 - 30)))
    rs = font_small.render(
        "Press R to restart  |  M for menu  |  Q to quit", True, (200, 200, 200)
    )
    screen.blit(rs, rs.get_rect(center=(BOARD_W // 2, WINDOW_H // 2 + 20)))


# ---------------------------------------------------------------------------
# Shared post-move logic
# ---------------------------------------------------------------------------
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
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Chess")
    clock = pygame.time.Clock()

    # Fonts
    font = pygame.font.SysFont("Arial", 24, bold=True)
    font_large = pygame.font.SysFont("Segoe UI Symbol", 52)
    font_panel = pygame.font.SysFont("Arial", 15)
    font_header = pygame.font.SysFont("Arial", 20, bold=True)
    font_tip = pygame.font.SysFont("Arial", 13)
    font_title = pygame.font.SysFont("Arial", 64, bold=True)
    font_btn = pygame.font.SysFont("Arial", 22, bold=True)
    font_sub = pygame.font.SysFont("Arial", 15)
    font_over = pygame.font.SysFont("Arial", 36, bold=True)
    menu_fonts = (font_title, font_btn, font_sub)

    pieces = load_pieces(ASSET_DIR, TILE_SIZE)
    use_svg = bool(pieces)

    # ── State machine ──────────────────────────────────────────────────────
    mode = MODE_MENU
    menu_hovered = None
    menu_rects = {}

    def new_game(new_mode):
        nonlocal board, turn, selected, possible_moves, last_move
        nonlocal castling_rights, status_msg, game_over
        nonlocal move_history, scroll_offset, flipped
        nonlocal cursor, tip_text, ai_thinking
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
        scroll_offset = 0
        flipped = False
        cursor = (7, 4)  # keyboard cursor starts on white king
        tip_text = ""
        ai_thinking = False

    # Initialise game vars (will be properly set by new_game)
    board = None
    turn = None
    selected = None
    possible_moves = []
    last_move = None
    castling_rights = None
    status_msg = ""
    game_over = False
    move_history = []
    scroll_offset = 0
    flipped = False
    cursor = (7, 4)
    tip_text = ""
    ai_thinking = False
    dragging = False
    drag_piece_key = None
    drag_from = None
    drag_pos = (0, 0)

    # ── Main loop ──────────────────────────────────────────────────────────
    while True:
        mx, my = pygame.mouse.get_pos()

        # ── AI move (black's turn in AI mode) ─────────────────────────────
        if mode == MODE_AI and turn == "black" and not game_over and not ai_thinking:
            ai_thinking = True
            move = ai_move(board, last_move, castling_rights)
            if move:
                fr, fc, tr, tc = move
                last_move, castling_rights, notation = execute_move(
                    board, (fr, fc), (tr, tc), last_move, castling_rights, "black"
                )
                move_history.append(notation)
                turn = "white"
                status_msg, game_over = post_move_status(
                    board, turn, last_move, castling_rights
                )
            ai_thinking = False

        # ── Events ────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # ── Global keys ───────────────────────────────────────────────
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_m:
                    mode = MODE_MENU
                    continue
                if event.key == pygame.K_r and mode != MODE_MENU:
                    new_game(mode)
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
                continue  # skip game logic while in menu

            # ── In-game keyboard input ─────────────────────────────────────
            if event.type == pygame.KEYDOWN and not game_over:
                # Block keyboard control during AI turn
                if mode == MODE_AI and turn == "black":
                    pass
                else:
                    if event.key in (
                        pygame.K_UP,
                        pygame.K_DOWN,
                        pygame.K_LEFT,
                        pygame.K_RIGHT,
                    ):
                        dr = {"UP": -1, "DOWN": 1}.get(
                            pygame.key.name(event.key).upper(), 0
                        )
                        dc = {"LEFT": -1, "RIGHT": 1}.get(
                            pygame.key.name(event.key).upper(), 0
                        )
                        # Arrow keys move in visual direction
                        if flipped:
                            dr, dc = -dr, -dc
                        nr = max(0, min(7, cursor[0] + dr))
                        nc = max(0, min(7, cursor[1] + dc))
                        cursor = (nr, nc)
                        # Update tip in learning mode
                        if mode == MODE_LEARNING and board[nr][nc]:
                            tip_text = PIECE_TIPS.get(piece_type(board[nr][nc]), "")
                        else:
                            tip_text = ""

                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        r, c = cursor
                        clicked = board[r][c]
                        if selected:
                            if cursor in possible_moves:
                                last_move, castling_rights, notation = execute_move(
                                    board,
                                    selected,
                                    cursor,
                                    last_move,
                                    castling_rights,
                                    turn,
                                )
                                move_history.append(notation)
                                turn = opponent(turn)
                                selected = None
                                possible_moves = []
                                tip_text = ""
                                status_msg, game_over = post_move_status(
                                    board, turn, last_move, castling_rights
                                )
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

                    elif event.key == pygame.K_ESCAPE:
                        selected = None
                        possible_moves = []
                        tip_text = ""

            # ── Mouse events (game) ────────────────────────────────────────
            if mode != MODE_MENU and not game_over:
                # Block mouse during AI turn
                if mode == MODE_AI and turn == "black":
                    pass
                else:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        cell = pixel_to_cell(mx, my, flipped)
                        if cell is None:
                            continue
                        r, c = cell
                        clicked = board[r][c]
                        cursor = cell  # sync cursor to mouse

                        if selected:
                            if cell in possible_moves:
                                last_move, castling_rights, notation = execute_move(
                                    board,
                                    selected,
                                    cell,
                                    last_move,
                                    castling_rights,
                                    turn,
                                )
                                move_history.append(notation)
                                turn = opponent(turn)
                                selected = None
                                possible_moves = []
                                tip_text = ""
                                status_msg, game_over = post_move_status(
                                    board, turn, last_move, castling_rights
                                )
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
                        # Update learning tip on hover
                        if mode == MODE_LEARNING and not selected:
                            cell = pixel_to_cell(mx, my, flipped)
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
                        cell = pixel_to_cell(mx, my, flipped)
                        if (
                            cell
                            and selected
                            and cell in possible_moves
                            and cell != selected
                        ):
                            last_move, castling_rights, notation = execute_move(
                                board, selected, cell, last_move, castling_rights, turn
                            )
                            move_history.append(notation)
                            turn = opponent(turn)
                            selected = None
                            possible_moves = []
                            tip_text = ""
                            status_msg, game_over = post_move_status(
                                board, turn, last_move, castling_rights
                            )

        # ── Render ────────────────────────────────────────────────────────
        if mode == MODE_MENU:
            menu_rects = draw_menu(screen, menu_fonts, menu_hovered)
        else:
            draw_board(screen)
            draw_highlights(
                screen, selected, possible_moves, last_move, cursor, flipped
            )
            draw_coordinates(screen, font, flipped)

            skip = drag_from if dragging else None
            if use_svg:
                draw_pieces(screen, board, pieces, flipped, skip=skip)
            else:
                draw_fallback_pieces(screen, board, font_large, flipped, skip=skip)

            # Dragged piece under cursor
            if dragging and drag_piece_key:
                if use_svg and drag_piece_key in pieces:
                    img = pieces[drag_piece_key]
                    screen.blit(img, img.get_rect(center=drag_pos))
                elif not use_svg:
                    syms = {
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
                    surf = font_large.render(
                        syms.get(drag_piece_key, "?"), True, (30, 30, 30)
                    )
                    screen.blit(surf, surf.get_rect(center=drag_pos))

            # Mode badge
            badges = {MODE_PVP: "PvP", MODE_AI: "vs AI", MODE_LEARNING: "Learning"}
            badge = font_sub.render(badges.get(mode, ""), True, (120, 120, 120))
            screen.blit(badge, (BOARD_W - badge.get_width() - 8, 6))

            draw_status(screen, font, status_msg)

            if mode == MODE_LEARNING:
                draw_tip(screen, font_tip, tip_text)

            scroll_offset = draw_move_panel(
                screen, font_panel, font_header, move_history, scroll_offset
            )

            if game_over:
                draw_gameover_overlay(screen, font_over, font_sub, status_msg)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
