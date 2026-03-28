import pygame

from constants import (
    FILES,
    RANKS,
    WHITE_TILE,
    BLACK_TILE,
    HIGHLIGHT_COLOR,
    SELECT_COLOR,
    LAST_MOVE_COLOR,
    CURSOR_COLOR,
    BORDER_BG,
    COORD_COLOR,
    PANEL_BG,
    PANEL_HEADER,
    PANEL_TEXT_W,
    PANEL_TEXT_B,
    PIECE_SYMBOLS,
    MODE_PVP,
    MODE_AI,
    MODE_LEARNING,
)


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
