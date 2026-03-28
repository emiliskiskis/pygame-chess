import io
import os
import sys

import cairosvg
import pygame

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TILE_SIZE = 80
BOARD_SIZE = 8
BORDER_SIDE = 40  # left / right / bottom padding
BORDER_TOP = 85  # extra top padding to fit the status label
BORDER = BORDER_SIDE  # kept for coordinate helpers that use BORDER
PANEL_W = 200  # width of the move history panel on the right
BOARD_W = TILE_SIZE * BOARD_SIZE + BORDER_SIDE * 2  # 720  (board area)
WINDOW_W = BOARD_W + PANEL_W  # 920
WINDOW_H = TILE_SIZE * BOARD_SIZE + BORDER_SIDE + BORDER_TOP  # 765

PANEL_BG = (28, 28, 28)
PANEL_HEADER = (60, 60, 60)
PANEL_TEXT_W = (240, 240, 240)  # white move text
PANEL_TEXT_B = (180, 180, 180)  # black move text
PANEL_LINE_H = 22  # pixels per move row

WHITE_TILE = (240, 217, 181)
BLACK_TILE = (181, 136, 99)
HIGHLIGHT_COLOR = (20, 85, 30, 180)  # semi-transparent green  (legal moves)
SELECT_COLOR = (20, 85, 125, 180)  # semi-transparent blue   (selected piece)
BORDER_BG = (40, 40, 40)
COORD_COLOR = (220, 220, 220)

FILES = "abcdefgh"
RANKS = "87654321"

# Asset folder is resolved relative to THIS script file so it always works
# regardless of which directory you launch python from.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(SCRIPT_DIR, "assets")


# ---------------------------------------------------------------------------
# SVG loader
# ---------------------------------------------------------------------------
def load_svg(path: str, size: int) -> pygame.Surface:
    png = cairosvg.svg2png(url=path, output_width=size, output_height=size)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def load_pieces(asset_dir: str, size: int) -> dict:
    """
    Loads piece images from  <asset_dir>/<name>_<color>.svg
    e.g.  king_white.svg   pawn_black.svg   rook_white.svg …

    Returns a dict keyed as  '<color>_<name>'
    e.g.  { 'white_king': Surface, 'black_pawn': Surface, … }
    """
    pieces = {}
    colors = ["white", "black"]
    names = ["king", "queen", "rook", "bishop", "knight", "pawn"]

    print(f"\nLoading pieces from: {asset_dir}")
    if not os.path.isdir(asset_dir):
        print(f"  ERROR: assets folder not found at {asset_dir}")
        print("  Create an 'assets' folder next to chess.py and put your SVGs inside.")
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
                print(f"  MISSING {filename}  (expected at {path})")

    loaded = len(pieces)
    total = len(colors) * len(names)
    print(f"\n  {loaded}/{total} pieces loaded.\n")
    return pieces


# ---------------------------------------------------------------------------
# Board initialisation
# ---------------------------------------------------------------------------
def starting_board():
    """
    Returns an 8×8 list. Each cell is a piece key string or None.
    Row 0 = rank 8 (black back rank), Row 7 = rank 1 (white back rank).
    White pieces are at the bottom; white moves first.
    """
    back = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]
    board = [[None] * 8 for _ in range(8)]
    for col in range(8):
        board[0][col] = f"black_{back[col]}"
        board[1][col] = "black_pawn"
        board[6][col] = "white_pawn"
        board[7][col] = f"white_{back[col]}"
    return board


# ---------------------------------------------------------------------------
# Chess logic helpers
# ---------------------------------------------------------------------------
def piece_color(piece):
    return piece.split("_")[0] if piece else None


def piece_type(piece):
    return piece.split("_")[1] if piece else None


def opponent(color):
    return "black" if color == "white" else "white"


def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


# ---------------------------------------------------------------------------
# Raw move generation  (ignores leaving own king in check)
# ---------------------------------------------------------------------------
def raw_moves(board, row, col):
    piece = board[row][col]
    if piece is None:
        return []
    color = piece_color(piece)
    ptype = piece_type(piece)
    moves = []

    def slide(directions):
        for dr, dc in directions:
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

    def jump(offsets):
        for dr, dc in offsets:
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
        direction = -1 if color == "white" else 1
        start_row = 6 if color == "white" else 1
        r = row + direction
        if in_bounds(r, col) and board[r][col] is None:
            moves.append((r, col))
            if row == start_row and board[r + direction][col] is None:
                moves.append((r + direction, col))
        for dc in [-1, 1]:
            r, c = row + direction, col + dc
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
    king_pos = find_king(board, color)
    if king_pos is None:
        return False
    opp = opponent(color)
    for r in range(8):
        for c in range(8):
            if piece_color(board[r][c]) == opp:
                if king_pos in raw_moves(board, r, c):
                    return True
    return False


def apply_move(board, fr, fc, tr, tc):
    import copy

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
    candidates = raw_moves(board, row, col)

    # En-passant candidate
    if ptype == "pawn" and last_move:
        fr, fc, tr, tc = last_move
        moved = board[tr][tc]
        if (
            moved == f"{opponent(color)}_pawn"
            and abs(fr - tr) == 2
            and tr == row
            and abs(tc - col) == 1
        ):
            direction = -1 if color == "white" else 1
            candidates.append((row + direction, tc))

    # Filter: must not leave own king in check
    legal = []
    for tr, tc in candidates:
        b2 = apply_move(board, row, col, tr, tc)
        # Remove en-passant captured pawn from the copy
        if ptype == "pawn" and last_move:
            lfr, lfc, ltr, ltc = last_move
            if tc == ltc and tr != ltr and board[ltr][ltc] == f"{opponent(color)}_pawn":
                b2[ltr][ltc] = None
        if not is_in_check(b2, color):
            legal.append((tr, tc))

    # Castling
    if ptype == "king" and not is_in_check(board, color):
        row_k = 7 if color == "white" else 0
        if row == row_k and col == 4:
            if castling_rights[color]["kingside"]:
                if board[row_k][5] is None and board[row_k][6] is None:
                    mid = apply_move(board, row_k, 4, row_k, 5)
                    dest = apply_move(mid, row_k, 4, row_k, 6)
                    if not is_in_check(mid, color) and not is_in_check(dest, color):
                        legal.append((row_k, 6))
            if castling_rights[color]["queenside"]:
                if (
                    board[row_k][3] is None
                    and board[row_k][2] is None
                    and board[row_k][1] is None
                ):
                    mid = apply_move(board, row_k, 4, row_k, 3)
                    dest = apply_move(mid, row_k, 4, row_k, 2)
                    if not is_in_check(mid, color) and not is_in_check(dest, color):
                        legal.append((row_k, 2))

    return legal


def has_any_legal_move(board, color, last_move, castling_rights):
    for r in range(8):
        for c in range(8):
            if piece_color(board[r][c]) == color:
                if legal_moves(board, r, c, last_move, castling_rights):
                    return True
    return False


def promote_pawns(board, color):
    promo_row = 0 if color == "white" else 7
    for c in range(8):
        if board[promo_row][c] == f"{color}_pawn":
            board[promo_row][c] = f"{color}_queen"


# ---------------------------------------------------------------------------
# Execute a move (shared by click and drag)
# ---------------------------------------------------------------------------
def execute_move(board, selected, dest, last_move, castling_rights, turn):
    """
    Applies the move to board in-place.
    Returns (last_move, castling_rights, notation_str).
    """
    fr, fc = selected
    tr, tc = dest
    moving = board[fr][fc]
    mtype = piece_type(moving)
    mcolor = piece_color(moving)
    captured = board[tr][tc]

    is_castling_kingside = mtype == "king" and fc == 4 and tc == 6
    is_castling_queenside = mtype == "king" and fc == 4 and tc == 2
    is_en_passant = False

    # En-passant capture
    if mtype == "pawn" and last_move:
        lfr, lfc, ltr, ltc = last_move
        if tc == ltc and tr != ltr and board[ltr][ltc] == f"{opponent(mcolor)}_pawn":
            board[ltr][ltc] = None
            is_en_passant = True

    board[tr][tc] = moving
    board[fr][fc] = None

    # Castling: move the rook too
    if mtype == "king":
        row_k = 7 if mcolor == "white" else 0
        if fc == 4 and tc == 6:  # kingside
            board[row_k][5] = board[row_k][7]
            board[row_k][7] = None
        if fc == 4 and tc == 2:  # queenside
            board[row_k][3] = board[row_k][0]
            board[row_k][0] = None
        castling_rights[mcolor]["kingside"] = False
        castling_rights[mcolor]["queenside"] = False

    if mtype == "rook":
        if fc == 7:
            castling_rights[mcolor]["kingside"] = False
        if fc == 0:
            castling_rights[mcolor]["queenside"] = False

    last_move = (fr, fc, tr, tc)
    promote_pawns(board, mcolor)

    # Determine check / checkmate for notation suffix
    opp = opponent(mcolor)
    gives_check = is_in_check(board, opp)
    gives_checkmate = gives_check and not has_any_legal_move(
        board, opp, last_move, castling_rights
    )

    notation = move_to_notation(
        board,
        fr,
        fc,
        tr,
        tc,
        moving,
        captured,
        is_castling_kingside,
        is_castling_queenside,
        is_en_passant,
        gives_check,
        gives_checkmate,
    )

    return last_move, castling_rights, notation


# ---------------------------------------------------------------------------
# Drawing
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


def draw_highlights(screen, selected, moves, flipped):
    overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    if selected:
        overlay.fill(SELECT_COLOR)
        vr, vc = board_to_view(selected[0], selected[1], flipped)
        screen.blit(
            overlay, (BORDER_SIDE + vc * TILE_SIZE, BORDER_TOP + vr * TILE_SIZE)
        )
    overlay.fill(HIGHLIGHT_COLOR)
    for r, c in moves:
        vr, vc = board_to_view(r, c, flipped)
        screen.blit(
            overlay, (BORDER_SIDE + vc * TILE_SIZE, BORDER_TOP + vr * TILE_SIZE)
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


def draw_status(screen, font, message):
    s = font.render(message, True, (255, 220, 50))
    screen.blit(s, s.get_rect(center=(BOARD_W // 2, BORDER_TOP // 2 - 8)))


def draw_fallback_pieces(screen, board, font_large, flipped, skip=None):
    """Render Unicode chess symbols when SVGs are missing."""
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


def move_to_notation(
    board_before,
    fr,
    fc,
    tr,
    tc,
    moving,
    captured,
    is_castling_kingside,
    is_castling_queenside,
    is_en_passant,
    gives_check,
    gives_checkmate,
):
    """Convert a move to standard algebraic notation."""
    if is_castling_kingside:
        note = "O-O"
    elif is_castling_queenside:
        note = "O-O-O"
    else:
        ptype = piece_type(moving)
        piece_sym = {
            "king": "K",
            "queen": "Q",
            "rook": "R",
            "bishop": "B",
            "knight": "N",
            "pawn": "",
        }[ptype]
        dest_file = FILES[tc]
        dest_rank = str(8 - tr)
        if ptype == "pawn":
            if captured or is_en_passant:
                note = f"{FILES[fc]}x{dest_file}{dest_rank}"
            else:
                note = f"{dest_file}{dest_rank}"
        else:
            capture = "x" if captured else ""
            note = f"{piece_sym}{capture}{dest_file}{dest_rank}"

    if gives_checkmate:
        note += "#"
    elif gives_check:
        note += "+"
    return note


def draw_move_panel(screen, font_panel, font_header, move_history, scroll_offset):
    """Draw the move history panel on the right side of the window."""
    panel_rect = pygame.Rect(BOARD_W, 0, PANEL_W, WINDOW_H)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)

    # Header
    header_rect = pygame.Rect(BOARD_W, 0, PANEL_W, BORDER_TOP)
    pygame.draw.rect(screen, PANEL_HEADER, header_rect)
    title = font_header.render("Moves", True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(BOARD_W + PANEL_W // 2, BORDER_TOP // 2)))

    # Divider line
    pygame.draw.line(
        screen, (80, 80, 80), (BOARD_W, BORDER_TOP), (WINDOW_W, BORDER_TOP), 1
    )

    # Column headers
    col_w = font_panel.render("W", True, PANEL_TEXT_W)
    col_b = font_panel.render("B", True, PANEL_TEXT_B)
    col_x_num = BOARD_W + 10
    col_x_w = BOARD_W + 40
    col_x_b = BOARD_W + 120
    y_header = BORDER_TOP + 8
    screen.blit(font_panel.render("#", True, (140, 140, 140)), (col_x_num, y_header))
    screen.blit(font_panel.render("White", True, PANEL_TEXT_W), (col_x_w, y_header))
    screen.blit(font_panel.render("Black", True, PANEL_TEXT_B), (col_x_b, y_header))
    pygame.draw.line(
        screen,
        (60, 60, 60),
        (BOARD_W + 5, y_header + PANEL_LINE_H - 2),
        (WINDOW_W - 5, y_header + PANEL_LINE_H - 2),
        1,
    )

    # Move rows  (pair white + black per line)
    list_top = BORDER_TOP + PANEL_LINE_H + 14
    visible_h = WINDOW_H - list_top - 10
    max_rows = visible_h // PANEL_LINE_H

    # Group flat move list into pairs  [(white, black_or_None), …]
    pairs = []
    for i in range(0, len(move_history), 2):
        w = move_history[i]
        b = move_history[i + 1] if i + 1 < len(move_history) else None
        pairs.append((w, b))

    # Auto-scroll to keep latest move visible
    total_rows = len(pairs)
    scroll_offset = max(0, total_rows - max_rows)

    visible_pairs = pairs[scroll_offset:]
    for idx, (w_move, b_move) in enumerate(visible_pairs):
        y = list_top + idx * PANEL_LINE_H
        if y + PANEL_LINE_H > WINDOW_H - 5:
            break
        move_num = scroll_offset + idx + 1
        # Highlight the last move row
        is_last = scroll_offset + idx == total_rows - 1
        if is_last:
            pygame.draw.rect(
                screen, (50, 50, 60), (BOARD_W + 4, y - 2, PANEL_W - 8, PANEL_LINE_H)
            )

        screen.blit(
            font_panel.render(f"{move_num}.", True, (120, 120, 120)), (col_x_num, y)
        )
        screen.blit(font_panel.render(w_move, True, PANEL_TEXT_W), (col_x_w, y))
        if b_move:
            screen.blit(font_panel.render(b_move, True, PANEL_TEXT_B), (col_x_b, y))

    return scroll_offset


def view_to_board(vrow, vcol, flipped):
    """Convert a visual grid position to a logical board position."""
    if flipped:
        return 7 - vrow, 7 - vcol
    return vrow, vcol


def board_to_view(row, col, flipped):
    """Convert a logical board position to a visual grid position."""
    if flipped:
        return 7 - row, 7 - col
    return row, col


def pixel_to_cell(mx, my, flipped):
    """Return logical board (row, col) for a mouse position, or None."""
    vcol = (mx - BORDER_SIDE) // TILE_SIZE
    vrow = (my - BORDER_TOP) // TILE_SIZE
    if 0 <= vrow < 8 and 0 <= vcol < 8:
        return view_to_board(vrow, vcol, flipped)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Chess")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 24, bold=True)
    font_large = pygame.font.SysFont("Segoe UI Symbol", 52)
    font_panel = pygame.font.SysFont("Arial", 15)
    font_header = pygame.font.SysFont("Arial", 20, bold=True)

    pieces = load_pieces(ASSET_DIR, TILE_SIZE)
    use_svg = bool(pieces)  # fall back to Unicode symbols if nothing loaded

    board = starting_board()

    # Game state
    turn = "white"  # white always moves first
    selected = None  # (row, col) of the selected piece
    possible_moves = []  # legal destinations for selected piece
    last_move = None  # (fr, fc, tr, tc)
    castling_rights = {
        "white": {"kingside": True, "queenside": True},
        "black": {"kingside": True, "queenside": True},
    }
    status_msg = "White's turn"
    game_over = False
    flipped = False  # False = white at bottom, True = black at bottom
    move_history = []  # flat list of notation strings [w1, b1, w2, b2, …]
    scroll_offset = 0

    # Drag state
    dragging = False
    drag_piece_key = None
    drag_from = None
    drag_pos = (0, 0)

    while True:
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # ----------------------------------------------------------------
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and not game_over
            ):
                cell = pixel_to_cell(mx, my, flipped)
                if cell is None:
                    continue
                r, c = cell
                clicked = board[r][c]

                if selected:
                    if cell in possible_moves:
                        last_move, castling_rights, notation = execute_move(
                            board, selected, cell, last_move, castling_rights, turn
                        )
                        move_history.append(notation)
                        turn = opponent(turn)
                        selected = None
                        possible_moves = []
                        if not has_any_legal_move(
                            board, turn, last_move, castling_rights
                        ):
                            status_msg = (
                                f"Checkmate! {opponent(turn).capitalize()} wins!"
                                if is_in_check(board, turn)
                                else "Stalemate! It's a draw."
                            )
                            game_over = True
                        elif is_in_check(board, turn):
                            status_msg = f"{turn.capitalize()} is in check!"
                        else:
                            status_msg = f"{turn.capitalize()}'s turn"
                    elif clicked and piece_color(clicked) == turn:
                        selected = cell
                        possible_moves = legal_moves(
                            board, r, c, last_move, castling_rights
                        )
                        dragging = True
                        drag_piece_key = clicked
                        drag_from = cell
                        drag_pos = (mx, my)
                    else:
                        selected = None
                        possible_moves = []
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

            # ----------------------------------------------------------------
            if event.type == pygame.MOUSEMOTION:
                drag_pos = (mx, my)

            # ----------------------------------------------------------------
            if (
                event.type == pygame.MOUSEBUTTONUP
                and event.button == 1
                and dragging
                and not game_over
            ):
                dragging = False
                cell = pixel_to_cell(mx, my, flipped)
                if cell and selected and cell in possible_moves and cell != selected:
                    last_move, castling_rights, notation = execute_move(
                        board, selected, cell, last_move, castling_rights, turn
                    )
                    move_history.append(notation)
                    turn = opponent(turn)
                    selected = None
                    possible_moves = []
                    if not has_any_legal_move(board, turn, last_move, castling_rights):
                        status_msg = (
                            f"Checkmate! {opponent(turn).capitalize()} wins!"
                            if is_in_check(board, turn)
                            else "Stalemate! It's a draw."
                        )
                        game_over = True
                    elif is_in_check(board, turn):
                        status_msg = f"{turn.capitalize()} is in check!"
                    else:
                        status_msg = f"{turn.capitalize()}'s turn"
                # If dropped on invalid square, piece stays selected for click-mode

        # --------------------------------------------------------------------
        # Render
        # --------------------------------------------------------------------
        draw_board(screen)
        draw_highlights(screen, selected, possible_moves, flipped)
        draw_coordinates(screen, font, flipped)

        skip_cell = drag_from if dragging else None
        if use_svg:
            draw_pieces(screen, board, pieces, flipped, skip=skip_cell)
        else:
            draw_fallback_pieces(screen, board, font_large, flipped, skip=skip_cell)

        # Dragged piece follows cursor
        if dragging and drag_piece_key:
            if use_svg and drag_piece_key in pieces:
                img = pieces[drag_piece_key]
                rect = img.get_rect(center=drag_pos)
                screen.blit(img, rect)
            elif not use_svg:
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
                sym = symbols.get(drag_piece_key, "?")
                surf = font_large.render(sym, True, (30, 30, 30))
                screen.blit(surf, surf.get_rect(center=drag_pos))

        draw_status(screen, font, status_msg)
        scroll_offset = draw_move_panel(
            screen, font_panel, font_header, move_history, scroll_offset
        )
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
