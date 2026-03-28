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

import sys

import pygame

from constants import (
    ASSET_DIR,
    PIECE_TIPS,
    MODE_MENU,
    MODE_AI,
    MODE_LEARNING,
)
from layout import Layout
from pieces import load_pieces, reload_pieces
from board import (
    starting_board,
    piece_color,
    piece_type,
    opponent,
    legal_moves,
    execute_move,
    post_move_status,
)
from ai import ai_move
from notation import parse_algebraic
from rendering import (
    pixel_to_cell,
    make_fonts,
    draw_board,
    draw_coordinates,
    draw_highlights,
    draw_pieces,
    draw_fallback_pieces,
    draw_status,
    draw_tip,
    draw_notation_bar,
    draw_move_panel,
    draw_menu,
    draw_pause_menu,
    draw_gameover_overlay,
    PIECE_SYMBOLS,
)


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

            badges = {"pvp": "PvP", "ai": "vs AI", "learning": "Learning"}
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
