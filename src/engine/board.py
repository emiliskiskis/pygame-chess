import copy

from ..constants import FILES
from ..strings import S


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
            if col != tc and tc == ltc and tr != ltr and board[ltr][ltc] == f"{opponent(color)}_pawn":
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
        if fc != tc and tc == ltc and tr != ltr and board[ltr][ltc] == f"{opponent(mcolor)}_pawn":
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


def post_move_status(board, turn, last_move, castling_rights, mode=None):
    if not has_any_legal_move(board, turn, last_move, castling_rights):
        if is_in_check(board, turn):
            winner_name = S.PANEL_COL_WHITE if opponent(turn) == "white" else S.PANEL_COL_BLACK
            return S.STATUS_CHECKMATE.format(winner=winner_name), True
        return S.STATUS_STALEMATE, True
    if is_in_check(board, turn):
        player_name = S.PANEL_COL_WHITE if turn == "white" else S.PANEL_COL_BLACK
        return S.STATUS_CHECK.format(player=player_name), False
    if mode in ("ai", "ml_ai"):
        return (S.STATUS_YOUR_TURN if turn == "white" else S.STATUS_AI_TURN), False
    player_name = S.PANEL_COL_WHITE if turn == "white" else S.PANEL_COL_BLACK
    return S.STATUS_TURN.format(player=player_name), False
