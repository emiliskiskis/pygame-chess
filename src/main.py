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

from . import strings
from .constants import (
    ASSET_DIR,
    MODE_AI,
    MODE_LANG_SELECT,
    MODE_LEARNING,
    MODE_MENU,
    MODE_ML_AI,
    MODE_ML_SELF,
)
from .engine.ai import ai_move
from .engine.board import (
    execute_move,
    legal_moves,
    opponent,
    piece_color,
    piece_type,
    post_move_status,
    starting_board,
)
from .engine.ml_ai import (
    clear_game_history,
    get_stats,
    ml_ai_move,
    ml_ai_move_for,
    record_game_result,
    record_position,
    start_training_async,
)
from .engine.notation import parse_algebraic
from .engine.pieces import load_flags, load_pieces, reload_pieces
from .savegame import (
    SAVEABLE_MODES,
    delete_save,
    load_game,
    save_exists,
    save_game,
)
from .strings import S, available_locales, prefs_exist
from .strings import reload as reload_strings
from .ui.layout import Layout
from .ui.rendering import (
    PIECE_SYMBOLS,
    draw_ai_progress,
    draw_board,
    draw_continue_popup,
    draw_coordinates,
    draw_corrupt_popup,
    draw_fallback_pieces,
    draw_gameover_overlay,
    draw_highlights,
    draw_lang_picker,
    draw_lang_select,
    draw_menu,
    draw_move_panel,
    draw_notation_bar,
    draw_pause_menu,
    draw_pieces,
    draw_self_play_speed,
    draw_status,
    draw_tip,
    make_fonts,
    pixel_to_cell,
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

    training = False
    training_thread = None
    training_progress = [0, 0]

    # ML self-play state
    self_play_delay_ms = 500  # ms pause between moves; 0 = as fast as threads allow
    last_move_time = 0  # pygame ticks when the last self-play move finished

    # Save-game popup state
    save_popup_pending_mode = None  # mode key waiting for user's yes/no/cancel
    save_popup_error = False  # True when save file was found but is corrupt
    save_popup_hovered = None  # which popup button is currently hovered
    save_popup_rects = {}  # hit-test rects for the active popup

    def new_game(new_mode):
        nonlocal board, turn, selected, possible_moves, last_move
        nonlocal castling_rights, status_msg, game_over, move_history
        nonlocal \
            flipped, \
            cursor, \
            tip_text, \
            ai_thinking, \
            ai_thread, \
            ai_result, \
            ai_progress
        nonlocal bar_text, bar_error, paused, over_hovered, over_rects
        nonlocal pause_hovered, pause_rects
        nonlocal training, training_thread, training_progress
        nonlocal last_move_time
        board = starting_board()
        turn = "white"
        selected = None
        possible_moves = []
        last_move = None
        castling_rights = {
            "white": {"kingside": True, "queenside": True},
            "black": {"kingside": True, "queenside": True},
        }
        if new_mode in (MODE_ML_AI, MODE_ML_SELF):
            clear_game_history()
        status_msg = (
            S.STATUS_YOUR_TURN
            if new_mode in (MODE_AI, MODE_ML_AI)
            else S.STATUS_WHITE_TURN
        )
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
        training = False
        training_thread = None
        training_progress = [0, 0]
        last_move_time = 0

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
        nonlocal training, training_thread, last_move_time
        # Record position before executing (for ML training)
        if mode in (MODE_ML_AI, MODE_ML_SELF):
            record_position(board, turn, castling_rights, last_move, from_sq, to_sq)
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
        # Update ELO immediately; start background training thread when game ends
        if game_over and mode in (MODE_ML_AI, MODE_ML_SELF):
            if S.STATUS_CHECKMATE.split("{")[0] in status_msg:
                winner = opponent(turn)  # turn is now the loser's turn
                ml_result = 1.0 if winner == "white" else -1.0
            else:
                ml_result = 0.0
            if mode == MODE_ML_AI:
                # Only update ELO for human-vs-AI games
                record_game_result(ml_result)
            training = True
            training_thread = start_training_async(ml_result, training_progress)

        # Track when this move finished so self-play can honour the delay
        if mode == MODE_ML_SELF:
            last_move_time = pygame.time.get_ticks()

    def _save_current_game():
        """Persist the in-progress game state, if applicable."""
        if mode in SAVEABLE_MODES and board is not None and not game_over:
            save_game(
                mode,
                board,
                turn,
                last_move,
                castling_rights,
                move_history or [],
                flipped or False,
            )

    # ── Main loop ──────────────────────────────────────────────────────────
    while True:
        now = pygame.time.get_ticks()
        mx, my = pygame.mouse.get_pos()

        # Apply deferred resize once quiet
        if pending_size and now >= resize_timer:
            apply_new_size(*pending_size)
            pending_size = None

        # ── ML self-play: trigger AI move for whichever colour is to move ──
        if (
            mode == MODE_ML_SELF
            and board
            and not game_over
            and not ai_thinking
            and not paused
            and now - last_move_time >= self_play_delay_ms
        ):
            ai_result[0] = None
            _board_snap = board
            _lm_snap = last_move
            _cr_snap = castling_rights
            _turn_snap = turn

            def _run_self_play():
                ai_result[0] = ml_ai_move_for(
                    _board_snap, _turn_snap, _lm_snap, _cr_snap, ai_progress
                )

            ai_thread = threading.Thread(target=_run_self_play, daemon=True)
            ai_thread.start()
            ai_thinking = True

        # AI turn (minimax)
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

        # AI turn (ML)
        if (
            mode == MODE_ML_AI
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

            def _run_ml_ai():
                ai_result[0] = ml_ai_move(_board_snap, _lm_snap, _cr_snap, ai_progress)

            ai_thread = threading.Thread(target=_run_ml_ai, daemon=True)
            ai_thread.start()
            ai_thinking = True

        if ai_thinking and ai_thread is not None and not ai_thread.is_alive():
            ai_thinking = False
            ai_thread = None
            move = ai_result[0]
            if move:
                do_move((move[0], move[1]), (move[2], move[3]))

        # Training thread — clear flag once the background job finishes
        if training and training_thread is not None and not training_thread.is_alive():
            training = False
            training_thread = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _save_current_game()
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
                # ── Save-game popup (overlays menu while visible) ─────────
                if save_popup_error or save_popup_pending_mode is not None:
                    if event.type == pygame.MOUSEMOTION:
                        save_popup_hovered = None
                        for k, rect in save_popup_rects.items():
                            if rect.collidepoint(mx, my):
                                save_popup_hovered = k
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        for k, rect in save_popup_rects.items():
                            if rect.collidepoint(mx, my):
                                if save_popup_error:
                                    # Corrupt/unreadable save — wipe it and start fresh
                                    if k == "continue":
                                        delete_save(save_popup_pending_mode)
                                        mode = save_popup_pending_mode
                                        new_game(save_popup_pending_mode)
                                        save_popup_pending_mode = None
                                        save_popup_error = False
                                        save_popup_hovered = None
                                else:
                                    if k == "yes":
                                        try:
                                            data = load_game(save_popup_pending_mode)
                                            new_game(save_popup_pending_mode)
                                            mode = save_popup_pending_mode
                                            # Override new_game defaults with saved state
                                            board = data["board"]
                                            turn = data["turn"]
                                            last_move = data["last_move"]
                                            castling_rights = data["castling_rights"]
                                            move_history = data["move_history"]
                                            flipped = data.get("flipped", False)
                                            status_msg, game_over = post_move_status(
                                                board,
                                                turn,
                                                last_move,
                                                castling_rights,
                                                mode,
                                            )
                                            save_popup_pending_mode = None
                                            save_popup_hovered = None
                                        except ValueError:
                                            save_popup_error = True
                                            save_popup_hovered = None
                                    elif k == "no":
                                        delete_save(save_popup_pending_mode)
                                        mode = save_popup_pending_mode
                                        new_game(save_popup_pending_mode)
                                        save_popup_pending_mode = None
                                        save_popup_hovered = None
                                    elif k == "cancel":
                                        save_popup_pending_mode = None
                                        save_popup_error = False
                                        save_popup_hovered = None
                                break
                    continue
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
                                if m in SAVEABLE_MODES and save_exists(m):
                                    # Show continue/new-game popup
                                    save_popup_pending_mode = m
                                    save_popup_hovered = None
                                    save_popup_rects = {}
                                else:
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
                                    _save_current_game()
                                    mode = MODE_MENU
                                elif k == "fullscreen":
                                    toggle_fullscreen()
                                elif k == "quit":
                                    _save_current_game()
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

            # ── ML self-play: spectator controls only ────────────────────
            if mode == MODE_ML_SELF and not game_over and not paused:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        paused = True
                        pause_hovered = None
                        lang_open = False
                        lang_hovered = None
                    elif event.key in (
                        pygame.K_PLUS,
                        pygame.K_EQUALS,
                        pygame.K_KP_PLUS,
                    ):
                        self_play_delay_ms = max(0, self_play_delay_ms - 50)
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self_play_delay_ms = min(2000, self_play_delay_ms + 50)
                continue  # board is view-only in self-play

            # ── In-game ───────────────────────────────────────────────────
            block = mode in (MODE_AI, MODE_ML_AI) and turn == "black"

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
                            dragging = False
                            drag_piece_key = None
                            drag_from = None
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
                screen,
                fonts,
                flags,
                locales,
                strings.CURRENT_LOCALE,
                lang_open,
                lang_hovered,
                L,
            )
            if save_popup_error:
                save_popup_rects = draw_corrupt_popup(
                    screen, fonts, save_popup_hovered, L
                )
            elif save_popup_pending_mode is not None:
                save_popup_rects = draw_continue_popup(
                    screen, fonts, save_popup_hovered, L
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
                    screen,
                    selected,
                    possible_moves,
                    last_move,
                    cursor,
                    flipped,
                    L,
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

            badges = {
                "pvp": S.BADGE_PVP,
                "ai": S.BADGE_AI,
                "learning": S.BADGE_LEARNING,
                "ml_ai": S.BADGE_ML_AI,
                "ml_self": S.BADGE_ML_SELF,
            }
            badge = fonts["sub"].render(badges.get(mode, ""), True, (120, 120, 120))
            screen.blit(badge, (L.board_w - badge.get_width() - 8, 6))

            if status_msg:
                draw_status(screen, fonts, status_msg, L)

            if mode in (MODE_AI, MODE_ML_AI) and ai_thinking:
                draw_ai_progress(screen, ai_progress, L)

            if mode == MODE_ML_SELF:
                draw_self_play_speed(screen, fonts, self_play_delay_ms, L)

            if mode == MODE_LEARNING and tip_text:
                draw_tip(screen, fonts, tip_text, L)
            else:
                draw_notation_bar(screen, fonts, bar_text, bar_error, L)

            draw_move_panel(screen, fonts, move_history or [], L)

            if game_over:
                ml_data = None
                if mode in (MODE_ML_AI, MODE_ML_SELF):
                    ml_data = get_stats()
                    ml_data["game_length"] = len(move_history) if move_history else 0
                over_rects = draw_gameover_overlay(
                    screen,
                    fonts,
                    status_msg,
                    over_hovered,
                    L,
                    ml_stats=ml_data,
                    training_progress=(
                        training_progress
                        if mode in (MODE_ML_AI, MODE_ML_SELF)
                        else None
                    ),
                    training_done=not training,
                    self_play=mode == MODE_ML_SELF,
                )
            elif paused:
                pause_rects = draw_pause_menu(screen, fonts, pause_hovered, L)
                lang_rects = draw_lang_picker(
                    screen,
                    fonts,
                    flags,
                    locales,
                    strings.CURRENT_LOCALE,
                    lang_open,
                    lang_hovered,
                    L,
                )

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
