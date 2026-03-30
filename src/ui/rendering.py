import pygame

from ..constants import (
    BLACK_TILE,
    BORDER_BG,
    COORD_COLOR,
    CURSOR_COLOR,
    FILES,
    HIGHLIGHT_COLOR,
    LAST_MOVE_COLOR,
    MODE_AI,
    MODE_LEARNING,
    MODE_ML_AI,
    MODE_ML_SELF,
    MODE_PROFILES,
    MODE_PVP,
    PANEL_BG,
    PANEL_HEADER,
    PANEL_TEXT_B,
    PANEL_TEXT_W,
    PIECE_SYMBOLS,
    PREVIEW_COLOR,
    RANKS,
    SELECT_COLOR,
    WHITE_TILE,
)
from ..engine.pieces import FLAG_H, FLAG_W
from ..strings import S


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
    "segoeuisymbol",  # Windows
    "notosanssymbols2",  # Linux (Noto)
    "notosanssymbols",
    "symbola",  # comprehensive Unicode font
    "dejavusans",
    "freesans",
]
# Fonts for emoji (color emoji preferred, then symbol fallbacks)
_EMOJI = [
    "notocoloremoji",  # Linux
    "seguiemj",  # Windows (Segoe UI Emoji)
] + _SYMBOL
# Plain Latin text fonts
_TEXT = ["arial", "liberationsans", "dejavusans", "freesans"]


def make_fonts(L):
    return {
        "coord": _best_font(_TEXT, L.fs_coord, bold=True),
        "status": _best_font(_TEXT, L.fs_status, bold=True),
        "piece": _best_font(_SYMBOL, L.fs_piece),
        "panel": _best_font(_TEXT, L.fs_panel),
        "header": _best_font(_TEXT, L.fs_header, bold=True),
        "tip": _best_font(_TEXT, L.fs_tip),
        "title": _best_font(_TEXT, L.fs_title, bold=True),
        "btn": _best_font(_TEXT, L.fs_btn, bold=True),
        "icon": _best_font(_SYMBOL, L.fs_btn),
        "sub": _best_font(_TEXT, L.fs_sub),
        "over": _best_font(_TEXT, L.fs_over, bold=True),
        "bar": _best_font(_TEXT, L.fs_bar),
    }


def _blit_icon_btn(
    screen, rect, icon_font, icon, icon_color, text_font, text, text_color
):
    """Render a colored chess-piece icon and UTF-8 text side-by-side, centered in rect."""
    icon_s = icon_font.render(icon, True, icon_color)
    text_s = text_font.render(text, True, text_color)
    gap = 8
    total_w = icon_s.get_width() + gap + text_s.get_width()
    row_h = max(icon_s.get_height(), text_s.get_height())
    x = rect.centerx - total_w // 2
    y = rect.centery - row_h // 2
    screen.blit(icon_s, (x, y + (row_h - icon_s.get_height()) // 2))
    screen.blit(
        text_s, (x + icon_s.get_width() + gap, y + (row_h - text_s.get_height()) // 2)
    )


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


def draw_highlights(
    screen, selected, moves, last_move_coords, cursor, flipped, L, preview_move=None
):
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
        pygame.draw.rect(
            screen,
            (100, 180, 255),
            (x, y, int(bar_w * ratio), bar_h),
            border_radius=bar_h,
        )


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
    screen.blit(fp.render(S.PANEL_COL_WHITE, True, PANEL_TEXT_W), (col_w, y_hdr))
    screen.blit(fp.render(S.PANEL_COL_BLACK, True, PANEL_TEXT_B), (col_b, y_hdr))
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


def draw_menu(screen, fonts, hovered, L, profile_name=""):
    _draw_gradient(
        screen, screen.get_width(), screen.get_height(), (91, 44, 111), (247, 220, 111)
    )
    cy = L.window_h // 2
    title = fonts["title"].render(S.MENU_TITLE, True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(L.window_w // 2, cy - 180)))
    sub = fonts["sub"].render(S.MENU_SUBTITLE, True, (180, 180, 180))
    screen.blit(sub, sub.get_rect(center=(L.window_w // 2, cy - 115)))

    buttons = [
        (MODE_PVP, S.MENU_PVP_LABEL, S.MENU_PVP_DESC, "♙", (255, 215, 50)),
        (MODE_AI, S.MENU_AI_LABEL, S.MENU_AI_DESC, "♟", (255, 90, 90)),
        (
            MODE_LEARNING,
            S.MENU_LEARNING_LABEL,
            S.MENU_LEARNING_DESC,
            "♗",
            (80, 200, 255),
        ),
        (MODE_ML_AI, S.MENU_ML_AI_LABEL, S.MENU_ML_AI_DESC, "♚", (180, 120, 255)),
        (
            MODE_ML_SELF,
            S.MENU_ML_SELF_LABEL,
            S.MENU_ML_SELF_DESC,
            "♛",
            (100, 220, 180),
        ),
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
        screen.blit(
            ls, ls.get_rect(midleft=(bx + 16 + icon_s.get_width() + 8, by + bh // 3))
        )
        ds = fonts["sub"].render(desc, True, (160, 160, 160))
        screen.blit(ds, ds.get_rect(midleft=(bx + 16, by + 2 * bh // 3)))

    # Profile button — top-left corner
    if profile_name:
        p_label = f"\u25a3  {profile_name}"
        p_surf = fonts["sub"].render(p_label, True, (220, 220, 220))
        pad = 8
        p_w = p_surf.get_width() + pad * 2
        p_h = p_surf.get_height() + pad * 2
        p_rect = pygame.Rect(8, 8, p_w, p_h)
        rects[MODE_PROFILES] = p_rect
        p_bg = (80, 80, 110) if hovered == MODE_PROFILES else (50, 50, 75)
        pygame.draw.rect(screen, p_bg, p_rect, border_radius=6)
        pygame.draw.rect(screen, (120, 120, 160), p_rect, 1, border_radius=6)
        screen.blit(p_surf, (p_rect.x + pad, p_rect.y + pad))

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
        ("resume", S.PAUSE_RESUME, "♙", (80, 220, 100)),
        ("restart", S.PAUSE_RESTART, "♞", (255, 200, 50)),
        ("menu", S.PAUSE_MENU, "♝", (130, 160, 255)),
        ("fullscreen", S.PAUSE_FULLSCREEN, "♜", (80, 210, 210)),
        ("quit", S.PAUSE_QUIT, "♛", (255, 90, 90)),
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
        _blit_icon_btn(
            screen,
            rect,
            fonts["icon"],
            icon,
            icon_col,
            fonts["btn"],
            label,
            (230, 230, 230),
        )

    esc_hint = fonts["sub"].render(S.PAUSE_ESC_HINT, True, (90, 90, 90))
    screen.blit(
        esc_hint, esc_hint.get_rect(center=(cx, start_y + len(actions) * gap + 10))
    )
    return rects


def draw_self_play_speed(screen, fonts, delay_ms, L):
    """
    Draw a small speed-indicator in the top-right corner of the board area
    (just below the mode badge) during ML self-play.
    """
    if delay_ms > 0:
        label = S.ML_SELF_DELAY.format(ms=delay_ms)
    else:
        label = S.ML_SELF_DELAY.format(ms=0)
    hint = S.ML_SELF_SPEED_HINT
    delay_surf = fonts["sub"].render(label, True, (100, 200, 170))
    hint_surf = fonts["sub"].render(hint, True, (80, 80, 80))
    x = L.board_w - max(delay_surf.get_width(), hint_surf.get_width()) - 8
    screen.blit(delay_surf, (x, 6 + fonts["sub"].get_height() + 4))
    screen.blit(hint_surf, (x, 6 + fonts["sub"].get_height() * 2 + 6))


def draw_gameover_overlay(
    screen,
    fonts,
    message,
    over_hovered,
    L,
    ml_stats=None,
    training_progress=None,
    training_done=False,
    self_play=False,
):
    """
    Draw the game-over overlay.

    When ml_stats is provided (ML AI / ML self-play) the overlay is extended
    with a stats block and a live-filling training progress bar.

    ml_stats keys: elo, wins, draws, losses, games, game_length, last_value
    training_progress: [steps_done, total_steps]  (shared list, updated by thread)
    training_done: True once the training thread has finished
    self_play: when True, hides the human W/D/L record (not meaningful for
               self-play) and labels the ELO row accordingly
    """
    ov = pygame.Surface((L.window_w, L.window_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 175))
    screen.blit(ov, (0, 0))

    cx = L.window_w // 2
    bw = min(320, L.window_w - 80)
    bh = max(40, L.tile - 20)
    gap = bh + 12

    actions = [
        ("restart", S.OVER_PLAY_AGAIN, "♞", (80, 220, 100)),
        ("menu", S.OVER_MENU, "♝", (130, 160, 255)),
        ("quit", S.OVER_QUIT, "♛", (255, 90, 90)),
    ]
    btn_total_h = len(actions) * gap - (gap - bh)
    rects = {}

    if ml_stats is not None:
        # ── Extended ML-AI overlay ──────────────────────────────────────────
        sec = max(8, L.tile // 10)  # gap between sections
        msg_fh = fonts["over"].get_height()
        stat_fh = fonts["status"].get_height()
        sub_fh = fonts["sub"].get_height()
        bar_h = max(12, L.tile // 6)

        total_h = (
            msg_fh
            + sec
            + stat_fh
            + 3
            + stat_fh
            + sec  # two stat rows
            + sub_fh
            + 4
            + bar_h
            + sec  # training label + bar
            + btn_total_h
        )

        y = max(8, L.window_h // 2 - total_h // 2)

        # Result message
        ms = fonts["over"].render(message, True, (255, 220, 50))
        screen.blit(ms, ms.get_rect(centerx=cx, top=y))
        y += msg_fh + sec

        # ── Stats rows ──────────────────────────────────────────────────────
        elo = ml_stats.get("elo", 800)
        wins = ml_stats.get("wins", 0)
        draws = ml_stats.get("draws", 0)
        losses = ml_stats.get("losses", 0)
        games = ml_stats.get("games", 0)
        gl = ml_stats.get("game_length", 0)
        val = ml_stats.get("last_value", 0.0)

        stat_col = (190, 190, 205)
        sep = "   ·   "

        if self_play:
            # Self-play: no human W/D/L record — just ELO and game length
            row1 = (
                S.ML_OVER_ELO.format(elo=elo)
                + sep
                + S.ML_OVER_GAME_LENGTH.format(moves=gl)
            )
            row2 = S.ML_OVER_CONFIDENCE.format(val=val)
        else:
            row1 = (
                S.ML_OVER_ELO.format(elo=elo)
                + sep
                + S.ML_OVER_RECORD.format(wins=wins, draws=draws, losses=losses)
                + sep
                + S.ML_OVER_GAMES.format(games=games)
            )
            row2 = (
                S.ML_OVER_GAME_LENGTH.format(moves=gl)
                + sep
                + S.ML_OVER_CONFIDENCE.format(val=val)
            )

        for row_text in (row1, row2):
            s = fonts["status"].render(row_text, True, stat_col)
            screen.blit(s, s.get_rect(centerx=cx, top=y))
            y += stat_fh + 3
        y += sec

        # ── Training label + progress bar ───────────────────────────────────
        done = training_done or (
            training_progress is not None
            and training_progress[1] > 0
            and training_progress[0] >= training_progress[1]
        )
        label = S.ML_OVER_TRAINING_DONE if done else S.ML_OVER_TRAINING
        label_col = (100, 220, 120) if done else (100, 170, 255)
        ls = fonts["sub"].render(label, True, label_col)
        screen.blit(ls, ls.get_rect(centerx=cx, top=y))
        y += sub_fh + 4

        if training_progress is not None and training_progress[1] > 0:
            frac = min(1.0, training_progress[0] / training_progress[1])
        else:
            frac = 1.0 if done else 0.0

        bx = cx - bw // 2
        bar_rect = pygame.Rect(bx, y, bw, bar_h)
        pygame.draw.rect(screen, (45, 45, 65), bar_rect, border_radius=4)
        if frac > 0:
            fill_w = max(bar_h, int(bw * frac))  # keep ends rounded nicely
            fill = pygame.Rect(bx, y, fill_w, bar_h)
            bar_color = (70, 210, 90) if done else (70, 130, 255)
            pygame.draw.rect(screen, bar_color, fill, border_radius=4)
        pygame.draw.rect(screen, (85, 85, 110), bar_rect, 1, border_radius=4)
        y += bar_h + sec

        # ── Buttons ─────────────────────────────────────────────────────────
        for i, (key, label, icon, icon_col) in enumerate(actions):
            bx2 = cx - bw // 2
            by = y + i * gap
            rect = pygame.Rect(bx2, by, bw, bh)
            rects[key] = rect
            col = (80, 80, 110) if over_hovered == key else (45, 45, 65)
            border = (255, 220, 50) if over_hovered == key else (70, 70, 95)
            pygame.draw.rect(screen, col, rect, border_radius=10)
            pygame.draw.rect(screen, border, rect, 2, border_radius=10)
            _blit_icon_btn(
                screen,
                rect,
                fonts["icon"],
                icon,
                icon_col,
                fonts["btn"],
                label,
                (230, 230, 230),
            )

    else:
        # ── Original simple overlay ─────────────────────────────────────────
        ms = fonts["over"].render(message, True, (255, 220, 50))
        screen.blit(ms, ms.get_rect(center=(cx, L.window_h // 2 - 90)))

        total_h = btn_total_h
        start_y = L.window_h // 2 - total_h // 2
        for i, (key, label, icon, icon_col) in enumerate(actions):
            bx = cx - bw // 2
            by = start_y + i * gap
            rect = pygame.Rect(bx, by, bw, bh)
            rects[key] = rect
            col = (80, 80, 110) if over_hovered == key else (45, 45, 65)
            border = (255, 220, 50) if over_hovered == key else (70, 70, 95)
            pygame.draw.rect(screen, col, rect, border_radius=10)
            pygame.draw.rect(screen, border, rect, 2, border_radius=10)
            _blit_icon_btn(
                screen,
                rect,
                fonts["icon"],
                icon,
                icon_col,
                fonts["btn"],
                label,
                (230, 230, 230),
            )

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
    _draw_flag_item(
        screen,
        fonts,
        flags,
        current,
        current_name,
        toggle_rect.x,
        toggle_rect.y,
        drop_w,
        item_h,
    )

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
        _draw_flag_item(screen, fonts, flags, code, name, tx, dy, drop_w, item_h)
        dy += item_h + 2

    return rects


def draw_lang_select(screen, fonts, flags, locales, hovered, L):
    """Full-screen language list shown on first launch (no prefs.dat)."""
    _draw_gradient(
        screen, screen.get_width(), screen.get_height(), (91, 44, 111), (247, 220, 111)
    )

    default_title = next(
        (t for code, _, t in locales if code == "en"), "Select Language"
    )
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
        screen.blit(code_s, code_s.get_rect(midleft=(x + _PAD, y + h // 2)))
    name_s = fonts["sub"].render(label, True, (220, 220, 220))
    screen.blit(name_s, name_s.get_rect(midleft=(x + _PAD + FLAG_W + 8, y + h // 2)))


def draw_continue_popup(screen, fonts, hovered, L):
    """Modal 'Continue your saved game?' popup drawn on top of the main menu."""
    # Full-screen dim
    ov = pygame.Surface((L.window_w, L.window_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 210))
    screen.blit(ov, (0, 0))

    bw = min(360, L.window_w - 80)
    bh = max(44, L.tile - 16)
    gap = bh + 14
    cx = L.window_w // 2
    cy = L.window_h // 2

    # Panel background
    panel_pad_x = 40
    panel_pad_top = 60
    panel_pad_bottom = 24
    num_buttons = 3
    panel_w = bw + panel_pad_x * 2
    panel_h = panel_pad_top + num_buttons * gap - (gap - bh) + panel_pad_bottom
    panel_rect = pygame.Rect(cx - panel_w // 2, cy - panel_h // 2, panel_w, panel_h)
    pygame.draw.rect(screen, (30, 30, 48), panel_rect, border_radius=16)
    pygame.draw.rect(screen, (80, 80, 130), panel_rect, 2, border_radius=16)

    # Title
    title = fonts["over"].render(S.SAVE_CONTINUE_TITLE, True, (255, 220, 50))
    screen.blit(title, title.get_rect(center=(cx, panel_rect.top + 34)))

    # Buttons: Yes (green), No (red), Cancel (blue)
    actions = [
        ("yes", S.SAVE_YES, "♙", (80, 220, 100)),
        ("no", S.SAVE_NO, "♞", (255, 100, 100)),
        ("cancel", S.SAVE_CANCEL, "♝", (130, 160, 255)),
    ]
    rects = {}
    total_h = num_buttons * gap - (gap - bh)
    start_y = panel_rect.top + panel_pad_top
    for i, (key, label, icon, icon_col) in enumerate(actions):
        bx = cx - bw // 2
        by = start_y + i * gap
        rect = pygame.Rect(bx, by, bw, bh)
        rects[key] = rect
        col = (80, 80, 110) if hovered == key else (45, 45, 65)
        border = (255, 220, 50) if hovered == key else (70, 70, 95)
        pygame.draw.rect(screen, col, rect, border_radius=10)
        pygame.draw.rect(screen, border, rect, 2, border_radius=10)
        _blit_icon_btn(
            screen,
            rect,
            fonts["icon"],
            icon,
            icon_col,
            fonts["btn"],
            label,
            (230, 230, 230),
        )
    return rects


def draw_corrupt_popup(screen, fonts, hovered, L):
    """Modal error popup shown when a save file cannot be loaded."""
    # Full-screen dim
    ov = pygame.Surface((L.window_w, L.window_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 210))
    screen.blit(ov, (0, 0))

    bw = min(360, L.window_w - 80)
    bh = max(44, L.tile - 16)
    cx = L.window_w // 2
    cy = L.window_h // 2

    panel_w = bw + 80
    panel_h = bh + 130
    panel_rect = pygame.Rect(cx - panel_w // 2, cy - panel_h // 2, panel_w, panel_h)
    pygame.draw.rect(screen, (48, 20, 20), panel_rect, border_radius=16)
    pygame.draw.rect(screen, (180, 60, 60), panel_rect, 2, border_radius=16)

    # Error title
    title = fonts["over"].render(S.SAVE_CORRUPT_TITLE, True, (255, 90, 90))
    screen.blit(title, title.get_rect(center=(cx, panel_rect.top + 36)))

    # Error message
    msg = fonts["sub"].render(S.SAVE_CORRUPT_MSG, True, (210, 180, 180))
    screen.blit(msg, msg.get_rect(center=(cx, panel_rect.top + 76)))

    # Single "Continue" button
    by = panel_rect.bottom - bh - 18
    rect = pygame.Rect(cx - bw // 2, by, bw, bh)
    col = (110, 50, 50) if hovered == "continue" else (65, 30, 30)
    border = (255, 90, 90) if hovered == "continue" else (120, 60, 60)
    pygame.draw.rect(screen, col, rect, border_radius=10)
    pygame.draw.rect(screen, border, rect, 2, border_radius=10)
    _blit_icon_btn(
        screen,
        rect,
        fonts["icon"],
        "♛",
        (255, 90, 90),
        fonts["btn"],
        S.SAVE_CORRUPT_CONTINUE,
        (230, 230, 230),
    )
    return {"continue": rect}


def draw_profiles_screen(
    screen,
    fonts,
    profiles,
    active_id,
    hovered,
    L,
    editing_id=None,
    edit_text="",
    creating=False,
    create_text="",
    deleting_id=None,
    dialog_hovered=None,
):
    """
    Full profiles management screen.

    Returns a flat dict of pygame.Rects keyed by:
      "back"            – back button
      "new"             – new profile button
      "select_<id>"     – click a profile row to set it active
      "edit_<id>"       – rename button for profile <id>
      "delete_<id>"     – delete button for profile <id> (absent for active)
      "dialog_ok"       – OK / Save button inside the text-input dialog
      "dialog_cancel"   – Cancel button inside the text-input dialog
      "dialog_yes"      – Confirm delete button inside the confirm dialog
      "dialog_no"       – Cancel button inside the confirm dialog
    """
    _draw_gradient(
        screen, screen.get_width(), screen.get_height(), (91, 44, 111), (247, 220, 111)
    )

    cx = L.window_w // 2
    rects = {}

    # ── Title ──────────────────────────────────────────────────────────────────
    title_surf = fonts["over"].render(S.PROFILES_TITLE, True, (255, 220, 50))
    screen.blit(title_surf, title_surf.get_rect(center=(cx, 50)))

    # ── Profile list ───────────────────────────────────────────────────────────
    row_h = max(48, L.tile - 12)
    gap = row_h + 10
    list_w = min(560, L.window_w - 80)
    btn_w = max(60, L.tile - 20)
    btn_gap = 8
    # start y leaves room for title
    list_start_y = 100

    for i, p in enumerate(profiles):
        pid = p["id"]
        is_active = pid == active_id
        ry = list_start_y + i * gap

        # Row background (full width)
        row_rect = pygame.Rect(cx - list_w // 2, ry, list_w, row_h)
        rects[f"select_{pid}"] = row_rect
        row_col = (55, 55, 80) if is_active else (40, 40, 58)
        row_border = (255, 220, 50) if is_active else (80, 80, 100)
        if hovered == f"select_{pid}" and not is_active:
            row_col = (65, 65, 90)
        pygame.draw.rect(screen, row_col, row_rect, border_radius=10)
        pygame.draw.rect(screen, row_border, row_rect, 2, border_radius=10)

        # Active checkmark
        x_cursor = row_rect.x + 14
        if is_active:
            chk = fonts["btn"].render(S.PROFILES_ACTIVE_INDICATOR, True, (100, 220, 100))
            screen.blit(chk, chk.get_rect(midleft=(x_cursor, ry + row_h // 2)))
            x_cursor += chk.get_width() + 8

        # Profile name
        name_col = (240, 240, 240) if is_active else (200, 200, 200)
        name_surf = fonts["btn"].render(p["name"], True, name_col)
        screen.blit(name_surf, name_surf.get_rect(midleft=(x_cursor, ry + row_h // 2)))

        # Action buttons on the right
        buttons_right = row_rect.right - 10
        # Delete (not shown for active profile)
        if not is_active:
            del_rect = pygame.Rect(
                buttons_right - btn_w, ry + (row_h - 30) // 2, btn_w, 30
            )
            rects[f"delete_{pid}"] = del_rect
            del_col = (120, 40, 40) if hovered == f"delete_{pid}" else (80, 30, 30)
            del_border = (220, 80, 80) if hovered == f"delete_{pid}" else (140, 60, 60)
            pygame.draw.rect(screen, del_col, del_rect, border_radius=6)
            pygame.draw.rect(screen, del_border, del_rect, 1, border_radius=6)
            del_s = fonts["sub"].render("✕", True, (255, 120, 120))
            screen.blit(del_s, del_s.get_rect(center=del_rect.center))
            buttons_right = del_rect.x - btn_gap

        # Edit button
        edit_rect = pygame.Rect(
            buttons_right - btn_w, ry + (row_h - 30) // 2, btn_w, 30
        )
        rects[f"edit_{pid}"] = edit_rect
        edit_col = (50, 80, 120) if hovered == f"edit_{pid}" else (35, 55, 85)
        edit_border = (100, 160, 255) if hovered == f"edit_{pid}" else (70, 100, 150)
        pygame.draw.rect(screen, edit_col, edit_rect, border_radius=6)
        pygame.draw.rect(screen, edit_border, edit_rect, 1, border_radius=6)
        edit_s = fonts["sub"].render("✎", True, (160, 200, 255))
        screen.blit(edit_s, edit_s.get_rect(center=edit_rect.center))

    # ── Bottom buttons ─────────────────────────────────────────────────────────
    bottom_y = list_start_y + len(profiles) * gap + 20
    bb_h = max(40, L.tile - 20)
    bb_w = min(200, list_w // 2 - 10)

    back_rect = pygame.Rect(cx - list_w // 2, bottom_y, bb_w, bb_h)
    rects["back"] = back_rect
    back_col = (60, 60, 80) if hovered == "back" else (40, 40, 58)
    back_border = (180, 180, 220) if hovered == "back" else (80, 80, 100)
    pygame.draw.rect(screen, back_col, back_rect, border_radius=10)
    pygame.draw.rect(screen, back_border, back_rect, 2, border_radius=10)
    back_s = fonts["btn"].render(S.PROFILES_BACK, True, (200, 200, 200))
    screen.blit(back_s, back_s.get_rect(center=back_rect.center))

    new_rect = pygame.Rect(cx + list_w // 2 - bb_w, bottom_y, bb_w, bb_h)
    rects["new"] = new_rect
    new_col = (40, 80, 50) if hovered == "new" else (28, 58, 36)
    new_border = (80, 200, 100) if hovered == "new" else (60, 120, 70)
    pygame.draw.rect(screen, new_col, new_rect, border_radius=10)
    pygame.draw.rect(screen, new_border, new_rect, 2, border_radius=10)
    new_s = fonts["btn"].render(S.PROFILES_NEW, True, (150, 230, 160))
    screen.blit(new_s, new_s.get_rect(center=new_rect.center))

    # ── Text-input dialog (edit name or create new) ────────────────────────────
    if editing_id is not None or creating:
        _draw_name_input_dialog(
            screen, fonts, L, cx,
            title=S.PROFILES_CREATE_TITLE if creating else S.PROFILES_EDIT_TITLE,
            text=create_text if creating else edit_text,
            hovered=dialog_hovered,
            rects=rects,
        )

    # ── Delete confirmation dialog ─────────────────────────────────────────────
    elif deleting_id is not None:
        del_profile = next((p for p in profiles if p["id"] == deleting_id), None)
        del_name = del_profile["name"] if del_profile else ""
        _draw_delete_confirm_dialog(
            screen, fonts, L, cx, del_name, dialog_hovered, rects
        )

    return rects


def _draw_name_input_dialog(screen, fonts, L, cx, title, text, hovered, rects):
    """Semi-transparent overlay with a text-input field, Save and Cancel buttons."""
    ov = pygame.Surface((L.window_w, L.window_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 200))
    screen.blit(ov, (0, 0))

    dlg_w = min(400, L.window_w - 80)
    dlg_h = 200
    cy = L.window_h // 2
    dlg_rect = pygame.Rect(cx - dlg_w // 2, cy - dlg_h // 2, dlg_w, dlg_h)
    pygame.draw.rect(screen, (30, 30, 48), dlg_rect, border_radius=14)
    pygame.draw.rect(screen, (80, 80, 130), dlg_rect, 2, border_radius=14)

    title_surf = fonts["over"].render(title, True, (255, 220, 50))
    screen.blit(title_surf, title_surf.get_rect(center=(cx, dlg_rect.top + 30)))

    # Text input field
    field_w = dlg_w - 40
    field_rect = pygame.Rect(cx - field_w // 2, dlg_rect.top + 60, field_w, 36)
    pygame.draw.rect(screen, (50, 50, 70), field_rect, border_radius=6)
    pygame.draw.rect(screen, (120, 120, 180), field_rect, 2, border_radius=6)
    display_text = text if text else S.PROFILES_NAME_PLACEHOLDER
    text_col = (230, 230, 230) if text else (100, 100, 120)
    text_surf = fonts["btn"].render(display_text, True, text_col)
    screen.blit(
        text_surf,
        text_surf.get_rect(midleft=(field_rect.x + 10, field_rect.centery)),
    )
    # Cursor bar when there is input text
    if text:
        cursor_x = field_rect.x + 10 + text_surf.get_width() + 2
        pygame.draw.line(
            screen,
            (200, 200, 220),
            (cursor_x, field_rect.top + 6),
            (cursor_x, field_rect.bottom - 6),
            2,
        )

    # Buttons
    btn_w = (dlg_w - 60) // 2
    btn_h = 36
    btn_y = dlg_rect.bottom - btn_h - 18

    cancel_rect = pygame.Rect(cx - dlg_w // 2 + 20, btn_y, btn_w, btn_h)
    rects["dialog_cancel"] = cancel_rect
    c_bg = (70, 50, 50) if hovered == "dialog_cancel" else (50, 35, 35)
    c_br = (200, 100, 100) if hovered == "dialog_cancel" else (140, 80, 80)
    pygame.draw.rect(screen, c_bg, cancel_rect, border_radius=8)
    pygame.draw.rect(screen, c_br, cancel_rect, 1, border_radius=8)
    cs = fonts["btn"].render(S.PROFILES_CANCEL, True, (220, 160, 160))
    screen.blit(cs, cs.get_rect(center=cancel_rect.center))

    ok_rect = pygame.Rect(cx + dlg_w // 2 - 20 - btn_w, btn_y, btn_w, btn_h)
    rects["dialog_ok"] = ok_rect
    ok_enabled = bool(text.strip())
    ok_bg = (40, 90, 50) if hovered == "dialog_ok" and ok_enabled else (28, 65, 36)
    ok_br = (80, 200, 100) if hovered == "dialog_ok" and ok_enabled else (50, 120, 65)
    if not ok_enabled:
        ok_bg = (30, 40, 30)
        ok_br = (50, 70, 50)
    pygame.draw.rect(screen, ok_bg, ok_rect, border_radius=8)
    pygame.draw.rect(screen, ok_br, ok_rect, 1, border_radius=8)
    ok_col = (150, 230, 160) if ok_enabled else (80, 100, 80)
    ok_s = fonts["btn"].render(S.PROFILES_SAVE, True, ok_col)
    screen.blit(ok_s, ok_s.get_rect(center=ok_rect.center))


def _draw_delete_confirm_dialog(screen, fonts, L, cx, profile_name, hovered, rects):
    """Semi-transparent overlay confirming profile deletion."""
    ov = pygame.Surface((L.window_w, L.window_h), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 210))
    screen.blit(ov, (0, 0))

    dlg_w = min(440, L.window_w - 80)
    dlg_h = 220
    cy = L.window_h // 2
    dlg_rect = pygame.Rect(cx - dlg_w // 2, cy - dlg_h // 2, dlg_w, dlg_h)
    pygame.draw.rect(screen, (48, 20, 20), dlg_rect, border_radius=14)
    pygame.draw.rect(screen, (160, 60, 60), dlg_rect, 2, border_radius=14)

    title_surf = fonts["over"].render(S.PROFILES_DELETE_TITLE, True, (255, 90, 90))
    screen.blit(title_surf, title_surf.get_rect(center=(cx, dlg_rect.top + 34)))

    name_surf = fonts["btn"].render(f'"{profile_name}"', True, (255, 180, 100))
    screen.blit(name_surf, name_surf.get_rect(center=(cx, dlg_rect.top + 72)))

    # Wrap the warning message
    msg_words = S.PROFILES_DELETE_MSG.split()
    lines = []
    line = []
    max_w = dlg_w - 40
    for word in msg_words:
        test = " ".join(line + [word])
        if fonts["sub"].size(test)[0] <= max_w:
            line.append(word)
        else:
            if line:
                lines.append(" ".join(line))
            line = [word]
    if line:
        lines.append(" ".join(line))

    msg_y = dlg_rect.top + 100
    for ln in lines:
        ln_surf = fonts["sub"].render(ln, True, (200, 160, 160))
        screen.blit(ln_surf, ln_surf.get_rect(center=(cx, msg_y)))
        msg_y += fonts["sub"].get_linesize()

    btn_w = (dlg_w - 60) // 2
    btn_h = 36
    btn_y = dlg_rect.bottom - btn_h - 18

    no_rect = pygame.Rect(cx - dlg_w // 2 + 20, btn_y, btn_w, btn_h)
    rects["dialog_no"] = no_rect
    no_bg = (50, 60, 80) if hovered == "dialog_no" else (35, 42, 58)
    no_br = (130, 160, 220) if hovered == "dialog_no" else (80, 100, 140)
    pygame.draw.rect(screen, no_bg, no_rect, border_radius=8)
    pygame.draw.rect(screen, no_br, no_rect, 1, border_radius=8)
    no_s = fonts["btn"].render(S.PROFILES_CANCEL, True, (180, 200, 240))
    screen.blit(no_s, no_s.get_rect(center=no_rect.center))

    yes_rect = pygame.Rect(cx + dlg_w // 2 - 20 - btn_w, btn_y, btn_w, btn_h)
    rects["dialog_yes"] = yes_rect
    yes_bg = (120, 35, 35) if hovered == "dialog_yes" else (80, 25, 25)
    yes_br = (220, 80, 80) if hovered == "dialog_yes" else (150, 60, 60)
    pygame.draw.rect(screen, yes_bg, yes_rect, border_radius=8)
    pygame.draw.rect(screen, yes_br, yes_rect, 1, border_radius=8)
    yes_s = fonts["btn"].render(S.PROFILES_CONFIRM_DELETE, True, (255, 130, 130))
    screen.blit(yes_s, yes_s.get_rect(center=yes_rect.center))
