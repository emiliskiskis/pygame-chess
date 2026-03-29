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
import threading

import pygame

from .constants import (
    ASSET_DIR,
    MODE_LANG_SELECT,
    MODE_MENU,
    MODE_AI,
    MODE_LEARNING,
)
from . import strings
from .strings import S, reload as reload_strings, available_locales, prefs_exist
from .ui.layout import Layout
from .engine.pieces import load_pieces, reload_pieces, load_flags
from .engine.board import (
    starting_board,
    piece_color,
    piece_type,
    opponent,
    legal_moves,
    execute_move,
    post_move_status,
)
from .engine.ai import ai_move
from .engine.notation import parse_algebraic
from .ui.rendering import (
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
    draw_lang_picker,
    draw_lang_select,
    draw_ai_progress,
    PIECE_SYMBOLS,
)


def main():
    pygame.init()

    INIT_W, INIT_H = 960, 780
    screen = pygame.display.set_mode((INIT_W, INIT_H), pygame.RESIZABLE)
    pygame.display.set_caption(S.WINDOW_TITLE)
    clock = pygame.time.Clock()

    fullscreen = False
    L = Layout(INIT_W, INIT_H)
    fonts = make_fonts(L)
    pieces = load_pieces(ASSET_DIR, L.tile)
    use_svg = bool(pieces)
    last_tile = L.tile

    locales = available_locales()
    flags = load_flags(ASSET_DIR, locales)
    lang_open = False
    lang_hovered = None
    lang_rects = {}

    # Resize debounce: apply layout only after the user stops dragging
    pending_size = None  # (w,h) waiting to be applied
    resize_timer = 0  # ticks when we will apply it
    RESIZE_DELAY = 100  # ms quiet period before re-layout

    mode = MODE_MENU if prefs_exist() else MODE_LANG_SELECT
    lang_select_hovered = None
    lang_select_rects = {}
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
    ai_thread = None
    ai_result = [None]
    ai_progress = [0, 1]
    dragging = False
    drag_piece_key = drag_from = None
    drag_pos = (0, 0)

    def new_game(new_mode):
        nonlocal board, turn, selected, possible_moves, last_move
        nonlocal castling_rights, status_msg, game_over, move_history
        nonlocal flipped, cursor, tip_text, ai_thinking, ai_thread, ai_result, ai_progress
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
        status_msg = S.STATUS_YOUR_TURN if new_mode == MODE_AI else S.STATUS_WHITE_TURN
        game_over = False
        move_history = []
        flipped = False
        cursor = (7, 4)
        tip_text = ""
        ai_thinking = False
        ai_thread = None
        ai_result = [None]
        ai_progress = [0, 1]
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
            board, turn, last_move, castling_rights, mode
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
            ai_progress[0] = 0
            ai_progress[1] = 1
            ai_result[0] = None
            _board_snap = board
            _lm_snap = last_move
            _cr_snap = castling_rights
            def _run_ai():
                ai_result[0] = ai_move(_board_snap, _lm_snap, _cr_snap, ai_progress)
            ai_thread = threading.Thread(target=_run_ai, daemon=True)
            ai_thread.start()
            ai_thinking = True

        if ai_thinking and ai_thread is not None and not ai_thread.is_alive():
            ai_thinking = False
            ai_thread = None
            move = ai_result[0]
            if move:
                do_move((move[0], move[1]), (move[2], move[3]))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # ── Resize: buffer the latest size, defer application ──────────
            if event.type == pygame.VIDEORESIZE:
                w = max(event.w, 400)
                h = max(event.h, 400)
                pending_size = (w, h)
                resize_timer = now + RESIZE_DELAY
                continue  # skip all other processing this frame

            # ── F11 always works ──────────────────────────────────────────
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                toggle_fullscreen()
                continue

            # ── Language selection (first launch) ─────────────────────────
            if mode == MODE_LANG_SELECT:
                if event.type == pygame.MOUSEMOTION:
                    lang_select_hovered = None
                    for k, rect in lang_select_rects.items():
                        if rect.collidepoint(mx, my):
                            lang_select_hovered = k
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for k, rect in lang_select_rects.items():
                        if rect.collidepoint(mx, my):
                            reload_strings(k)
                            pygame.display.set_caption(S.WINDOW_TITLE)
                            mode = MODE_MENU
                            lang_select_hovered = None
                            break
                continue

            # ── Menu ──────────────────────────────────────────────────────
            if mode == MODE_MENU:
                if event.type == pygame.MOUSEMOTION:
                    menu_hovered = None
                    lang_hovered = None
                    for m, rect in menu_rects.items():
                        if rect.collidepoint(mx, my):
                            menu_hovered = m
                    for k, rect in lang_rects.items():
                        if rect.collidepoint(mx, my):
                            lang_hovered = k
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Lang picker has priority
                    picked_lang = False
                    for k, rect in lang_rects.items():
                        if rect.collidepoint(mx, my):
                            if k == "toggle":
                                lang_open = not lang_open
                            else:
                                reload_strings(k)
                                pygame.display.set_caption(S.WINDOW_TITLE)
                                if board is not None:
                                    status_msg, game_over = post_move_status(
                                        board, turn, last_move, castling_rights, mode
                                    )
                                lang_open = False
                            picked_lang = True
                            break
                    if not picked_lang:
                        lang_open = False
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
                    lang_hovered = None
                    for k, rect in pause_rects.items():
                        if rect.collidepoint(mx, my):
                            pause_hovered = k
                    for k, rect in lang_rects.items():
                        if rect.collidepoint(mx, my):
                            lang_hovered = k
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    picked_lang = False
                    for k, rect in lang_rects.items():
                        if rect.collidepoint(mx, my):
                            if k == "toggle":
                                lang_open = not lang_open
                            else:
                                reload_strings(k)
                                pygame.display.set_caption(S.WINDOW_TITLE)
                                status_msg, game_over = post_move_status(
                                    board, turn, last_move, castling_rights, mode
                                )
                                lang_open = False
                            picked_lang = True
                            break
                    if not picked_lang:
                        lang_open = False
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
                    lang_open = False
                    lang_hovered = None
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
                        lang_open = False
                        lang_hovered = None
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
                        tip_text = S.TIPS.get(piece_type(board[nr][nc]), "")
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
                                tip_text = S.TIPS.get(piece_type(clicked), "")
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
                                tip_text = S.TIPS.get(piece_type(clicked), "")

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
                                tip_text = S.TIPS.get(piece_type(clicked), "")
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
                                tip_text = S.TIPS.get(piece_type(clicked), "")

                if event.type == pygame.MOUSEMOTION:
                    drag_pos = (mx, my)
                    if mode == MODE_LEARNING and not selected:
                        cell = pixel_to_cell(mx, my, flipped, L)
                        if cell and board[cell[0]][cell[1]]:
                            tip_text = S.TIPS.get(
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
        if mode == MODE_LANG_SELECT:
            lang_select_rects = draw_lang_select(
                screen, fonts, flags, locales, lang_select_hovered, L
            )
        elif mode == MODE_MENU:
            menu_rects = draw_menu(screen, fonts, menu_hovered, L)
            lang_rects = draw_lang_picker(
                screen, fonts, flags, locales,
                strings.CURRENT_LOCALE, lang_open, lang_hovered, L
            )
        else:
            draw_board(screen, L)
            if board:
                bar_preview = None
                if bar_text and not game_over and not paused:
                    bar_preview = parse_algebraic(
                        bar_text, board, turn, last_move, castling_rights
                    )
                draw_highlights(
                    screen, selected, possible_moves, last_move, cursor, flipped, L,
                    preview_move=bar_preview,
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

            badges = {"pvp": S.BADGE_PVP, "ai": S.BADGE_AI, "learning": S.BADGE_LEARNING}
            badge = fonts["sub"].render(badges.get(mode, ""), True, (120, 120, 120))
            screen.blit(badge, (L.board_w - badge.get_width() - 8, 6))

            if status_msg:
                draw_status(screen, fonts, status_msg, L)

            if mode == MODE_AI and ai_thinking:
                draw_ai_progress(screen, ai_progress, L)

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
                lang_rects = draw_lang_picker(
                    screen, fonts, flags, locales,
                    strings.CURRENT_LOCALE, lang_open, lang_hovered, L
                )

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
