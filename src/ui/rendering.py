import pygame

from ..constants import (
    FILES,
    RANKS,
    WHITE_TILE,
    BLACK_TILE,
    HIGHLIGHT_COLOR,
    SELECT_COLOR,
    LAST_MOVE_COLOR,
    CURSOR_COLOR,
    PREVIEW_COLOR,
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
from ..strings import S
from ..engine.pieces import FLAG_W, FLAG_H


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


def _best_font(candidates, size, bold=False):
    """Return the first available SysFont from candidates; fall back to pygame default."""
    for name in candidates:
        if pygame.font.match_font(name):
            return pygame.font.SysFont(name, size, bold=bold)
    return pygame.font.Font(None, size)

# Fonts with broad Unicode / chess-symbol coverage (tried in order)
_SYMBOL = [
    "segoeuisymbol",      # Windows
    "notosanssymbols2",   # Linux (Noto)
    "notosanssymbols",
    "symbola",            # comprehensive Unicode font
    "dejavusans",
    "freesans",
]
# Fonts for emoji (color emoji preferred, then symbol fallbacks)
_EMOJI = [
    "notocoloremoji",     # Linux
    "seguiemj",           # Windows (Segoe UI Emoji)
] + _SYMBOL
# Plain Latin text fonts
_TEXT = ["arial", "liberationsans", "dejavusans", "freesans"]


def make_fonts(L):
    return {
        "coord":  _best_font(_TEXT,   L.fs_coord,  bold=True),
        "status": _best_font(_TEXT,   L.fs_status, bold=True),
        "piece":  _best_font(_SYMBOL, L.fs_piece),
        "panel":  _best_font(_TEXT,   L.fs_panel),
        "header": _best_font(_TEXT,   L.fs_header, bold=True),
        "tip":    _best_font(_TEXT,   L.fs_tip),
        "title":  _best_font(_TEXT,   L.fs_title,  bold=True),
        "btn":    _best_font(_TEXT,   L.fs_btn,    bold=True),
        "icon":   _best_font(_SYMBOL, L.fs_btn),
        "sub":    _best_font(_TEXT,   L.fs_sub),
        "over":   _best_font(_TEXT,   L.fs_over,   bold=True),
        "bar":    _best_font(_TEXT,   L.fs_bar),
    }


def _blit_icon_btn(screen, rect, icon_font, icon, icon_color, text_font, text, text_color):
    """Render a colored chess-piece icon and UTF-8 text side-by-side, centered in rect."""
    icon_s = icon_font.render(icon, True, icon_color)
    text_s = text_font.render(text, True, text_color)
    gap = 8
    total_w = icon_s.get_width() + gap + text_s.get_width()
    row_h = max(icon_s.get_height(), text_s.get_height())
    x = rect.centerx - total_w // 2
    y = rect.centery - row_h // 2
    screen.blit(icon_s, (x, y + (row_h - icon_s.get_height()) // 2))
    screen.blit(text_s, (x + icon_s.get_width() + gap, y + (row_h - text_s.get_height()) // 2))


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
            L.coord_bottom_y,
        ]:
            s = f.render(letter, True, COORD_COLOR)
            screen.blit(s, s.get_rect(center=(x, y)))
    for row, number in enumerate(ranks):
        y = L.border_top + row * L.tile + L.tile // 2
        for x in [L.border_side // 2, L.border_side + 8 * L.tile + L.border_side // 2]:
            s = f.render(number, True, COORD_COLOR)
            screen.blit(s, s.get_rect(center=(x, y)))


def draw_highlights(screen, selected, moves, last_move_coords, cursor, flipped, L, preview_move=None):
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
    if preview_move:
        from_sq, to_sq = preview_move
        ov.fill(PREVIEW_COLOR)
        for r, c in [from_sq, to_sq]:
            vr, vc = board_to_view(r, c, flipped)
            screen.blit(ov, (L.border_side + vc * L.tile, L.border_top + vr * L.tile))
        # Draw a border around the destination square
        vr, vc = board_to_view(to_sq[0], to_sq[1], flipped)
        pygame.draw.rect(
            screen,
            (220, 140, 20),
            (L.border_side + vc * L.tile, L.border_top + vr * L.tile, L.tile, L.tile),
            3,
        )
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


def draw_ai_progress(screen, progress, L):
    done, total = progress[0], max(progress[1], 1)
    ratio = min(done / total, 1.0)
    bar_w = L.board_px * 2 // 3
    bar_h = max(4, L.tile // 16)
    x = (L.board_w - bar_w) // 2
    y = L.border_top - bar_h - 4
    pygame.draw.rect(screen, (60, 60, 80), (x, y, bar_w, bar_h), border_radius=bar_h)
    if ratio > 0:
        pygame.draw.rect(screen, (100, 180, 255), (x, y, int(bar_w * ratio), bar_h), border_radius=bar_h)


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

    label = f.render(S.NOTATION_LABEL, True, (140, 140, 160))
    screen.blit(label, (bx + pad, by + (bh - label.get_height()) // 2))

    text_x = bx + pad + label.get_width()
    disp = bar_text + ("|" if (pygame.time.get_ticks() // 500) % 2 == 0 else "")
    txt_s = f.render(disp, True, (220, 220, 255) if not bar_error else (255, 120, 120))
    screen.blit(txt_s, (text_x, by + (bh - txt_s.get_height()) // 2))

    hint = f.render(S.NOTATION_HINT, True, (70, 70, 90))
    screen.blit(hint, hint.get_rect(midright=(bx + bw - pad, by + bh // 2)))


def draw_move_panel(screen, fonts, move_history, L):
    panel_rect = pygame.Rect(L.board_w, 0, L.panel_w, L.window_h)
    header_rect = pygame.Rect(L.board_w, 0, L.panel_w, L.border_top)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)
    pygame.draw.rect(screen, PANEL_HEADER, header_rect)
    title = fonts["header"].render(S.PANEL_HEADER, True, (255, 220, 50))
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
    screen.blit(fp.render(S.PANEL_COL_NUMBER, True, (140, 140, 140)), (col_num, y_hdr))
    screen.blit(fp.render(S.PANEL_COL_WHITE,  True, PANEL_TEXT_W),   (col_w,   y_hdr))
    screen.blit(fp.render(S.PANEL_COL_BLACK,  True, PANEL_TEXT_B),   (col_b,   y_hdr))
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


def _draw_gradient(screen, w, h, top_col, bottom_col):
    """Fill screen with a smooth vertical gradient between two RGB colours."""
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top_col[0] + (bottom_col[0] - top_col[0]) * t)
        g = int(top_col[1] + (bottom_col[1] - top_col[1]) * t)
        b = int(top_col[2] + (bottom_col[2] - top_col[2]) * t)
        pygame.draw.line(screen, (r, g, b), (0, y), (w, y))


def draw_menu(screen, fonts, hovered, L):
    _draw_gradient(screen, screen.get_width(), screen.get_height(), (91, 44, 111), (247, 220, 111))
    cy = L.window_h // 2
    title = fonts["title"].render(S.MENU_TITLE, True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(L.window_w // 2, cy - 180)))
    sub = fonts["sub"].render(S.MENU_SUBTITLE, True, (180, 180, 180))
    screen.blit(sub, sub.get_rect(center=(L.window_w // 2, cy - 115)))

    buttons = [
        (MODE_PVP,      S.MENU_PVP_LABEL,      S.MENU_PVP_DESC,      "♙", (255, 215,  50)),
        (MODE_AI,       S.MENU_AI_LABEL,       S.MENU_AI_DESC,       "♟", (255,  90,  90)),
        (MODE_LEARNING, S.MENU_LEARNING_LABEL, S.MENU_LEARNING_DESC, "♗", ( 80, 200, 255)),
    ]
    bw = min(460, L.window_w - 80)
    bh = max(50, L.tile - 10)
    gap = bh + 18
    rects = {}
    for i, (m, label, desc, icon, icon_col) in enumerate(buttons):
        bx = L.window_w // 2 - bw // 2
        by = cy - 60 + i * gap
        rect = pygame.Rect(bx, by, bw, bh)
        rects[m] = rect
        col = (70, 70, 90) if hovered == m else (45, 45, 60)
        border = (255, 220, 50) if hovered == m else (80, 80, 100)
        pygame.draw.rect(screen, col, rect, border_radius=12)
        pygame.draw.rect(screen, border, rect, 2, border_radius=12)
        icon_s = fonts["icon"].render(icon, True, icon_col)
        ls = fonts["btn"].render(label, True, (240, 240, 240))
        screen.blit(icon_s, icon_s.get_rect(midleft=(bx + 16, by + bh // 3)))
        screen.blit(ls, ls.get_rect(midleft=(bx + 16 + icon_s.get_width() + 8, by + bh // 3)))
        ds = fonts["sub"].render(desc, True, (160, 160, 160))
        screen.blit(ds, ds.get_rect(midleft=(bx + 16, by + 2 * bh // 3)))

    hint = fonts["sub"].render(S.MENU_HINT, True, (80, 80, 80))
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

    title = fonts["over"].render(S.PAUSE_TITLE, True, (255, 220, 50))
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
        ("resume",     S.PAUSE_RESUME,     "♙", ( 80, 220, 100)),
        ("restart",    S.PAUSE_RESTART,    "♞", (255, 200,  50)),
        ("menu",       S.PAUSE_MENU,       "♝", (130, 160, 255)),
        ("fullscreen", S.PAUSE_FULLSCREEN, "♜", ( 80, 210, 210)),
        ("quit",       S.PAUSE_QUIT,       "♛", (255,  90,  90)),
    ]
    rects = {}
    total_h = len(actions) * gap - (gap - bh)
    start_y = cy - total_h // 2
    for i, (key, label, icon, icon_col) in enumerate(actions):
        bx = cx - bw // 2
        by = start_y + i * gap
        rect = pygame.Rect(bx, by, bw, bh)
        rects[key] = rect
        col = (80, 80, 110) if hovered == key else (45, 45, 65)
        border = (255, 220, 50) if hovered == key else (70, 70, 95)
        pygame.draw.rect(screen, col, rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)
        _blit_icon_btn(screen, rect, fonts["icon"], icon, icon_col,
                       fonts["btn"], label, (230, 230, 230))

    esc_hint = fonts["sub"].render(S.PAUSE_ESC_HINT, True, (90, 90, 90))
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
        ("restart", S.OVER_PLAY_AGAIN, "♞", ( 80, 220, 100)),
        ("menu",    S.OVER_MENU,       "♝", (130, 160, 255)),
        ("quit",    S.OVER_QUIT,       "♛", (255,  90,  90)),
    ]
    bw = min(280, L.window_w - 80)
    bh = max(40, L.tile - 20)
    gap = bh + 12
    cx = L.window_w // 2
    cy = L.window_h // 2
    rects = {}
    total_h = len(actions) * gap - (gap - bh)
    start_y = cy - total_h // 2
    for i, (key, label, icon, icon_col) in enumerate(actions):
        bx = cx - bw // 2
        by = start_y + i * gap
        rect = pygame.Rect(bx, by, bw, bh)
        rects[key] = rect
        col = (80, 80, 110) if over_hovered == key else (45, 45, 65)
        border = (255, 220, 50) if over_hovered == key else (70, 70, 95)
        pygame.draw.rect(screen, col, rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)
        _blit_icon_btn(screen, rect, fonts["icon"], icon, icon_col,
                       fonts["btn"], label, (230, 230, 230))
    return rects


_PAD = 6  # padding inside flag buttons


def draw_lang_picker(screen, fonts, flags, locales, current, open_, hovered, L):
    """
    Flag dropdown in the top-right corner of the menu.

    Returns a dict of pygame.Rects:
      "toggle"       – the always-visible current-flag button
      "<locale_code>" – one rect per locale in the open dropdown
    """
    rects = {}
    item_h = FLAG_H + _PAD * 2

    # Max language-name width (for dropdown sizing)
    name_w = max((fonts["sub"].size(name)[0] for _, name, _ in locales), default=60)
    drop_w = _PAD + FLAG_W + 8 + name_w + _PAD

    # Toggle button: top-right, aligned with dropdown
    tx = L.window_w - drop_w - 8
    ty = 8
    toggle_rect = pygame.Rect(tx, ty, drop_w, item_h)
    rects["toggle"] = toggle_rect

    bg = (80, 80, 110) if hovered == "toggle" else (50, 50, 75)
    pygame.draw.rect(screen, bg, toggle_rect, border_radius=6)
    pygame.draw.rect(screen, (120, 120, 160), toggle_rect, 1, border_radius=6)
    current_name = next((name for code, name, _ in locales if code == current), current)
    _draw_flag_item(screen, fonts, flags, current, current_name,
                    toggle_rect.x, toggle_rect.y, drop_w, item_h)

    if not open_:
        return rects

    # Dropdown list below the toggle
    dy = ty + item_h + 4
    for code, name, _ in locales:
        item_rect = pygame.Rect(tx, dy, drop_w, item_h)
        rects[code] = item_rect
        item_bg = (80, 80, 110) if hovered == code else (40, 40, 60)
        pygame.draw.rect(screen, item_bg, item_rect, border_radius=4)
        border_col = (255, 220, 50) if code == current else (70, 70, 100)
        pygame.draw.rect(screen, border_col, item_rect, 1, border_radius=4)
        _draw_flag_item(screen, fonts, flags, code, name,
                        tx, dy, drop_w, item_h)
        dy += item_h + 2

    return rects


def draw_lang_select(screen, fonts, flags, locales, hovered, L):
    """Full-screen language list shown on first launch (no prefs.dat)."""
    _draw_gradient(screen, screen.get_width(), screen.get_height(), (91, 44, 111), (247, 220, 111))

    default_title = next((t for code, _, t in locales if code == "en"), "Select Language")
    title_text = next((t for code, _, t in locales if code == hovered), default_title)
    title = fonts["title"].render(title_text, True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(screen.get_width() // 2, 70)))

    bw = min(420, screen.get_width() - 80)
    item_h = max(50, FLAG_H + 20)
    gap = item_h + 10
    total_h = len(locales) * gap - 10
    start_y = max(130, screen.get_height() // 2 - total_h // 2)

    cx = screen.get_width() // 2
    rects = {}
    for i, (code, name, _) in enumerate(locales):
        bx = cx - bw // 2
        by = start_y + i * gap
        rect = pygame.Rect(bx, by, bw, item_h)
        rects[code] = rect
        col = (70, 70, 90) if hovered == code else (45, 45, 60)
        border = (255, 220, 50) if hovered == code else (80, 80, 100)
        pygame.draw.rect(screen, col, rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)
        _draw_flag_item(screen, fonts, flags, code, name, bx, by, bw, item_h)

    return rects


def _draw_flag_item(screen, fonts, flags, code, label, x, y, w, h):
    """Blit flag (or code text fallback) + language label inside a row."""
    if code in flags:
        screen.blit(flags[code], (x + _PAD, y + (h - FLAG_H) // 2))
    else:
        code_s = fonts["sub"].render(code.upper(), True, (220, 220, 220))
        screen.blit(code_s, code_s.get_rect(
            midleft=(x + _PAD, y + h // 2)))
    name_s = fonts["sub"].render(label, True, (220, 220, 220))
    screen.blit(name_s, name_s.get_rect(
        midleft=(x + _PAD + FLAG_W + 8, y + h // 2)))
