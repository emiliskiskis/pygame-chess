"""
hud_renderer.py — In-game HUD: status bar, move panel, notation bar, tips, AI progress.

Pure rendering functions: no game logic, no state mutation.
"""

import pygame

from ..constants import PANEL_BG, PANEL_HEADER, PANEL_TEXT_B, PANEL_TEXT_W
from ..strings import S


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


def draw_model_path(screen, fonts, path, L):
    """Show the model file path in the first bottom bar (ML vs ML mode)."""
    f = fonts["bar"]
    bx, by = L.bar_x, L.bar_y
    bw, bh = L.bar_w, L.bar_h
    pad = max(4, bh // 5)

    pygame.draw.rect(screen, (20, 20, 20), (bx, by, bw, bh), border_radius=4)
    pygame.draw.rect(screen, (55, 55, 70), (bx, by, bw, bh), 1, border_radius=4)

    path_s = f.render(path, True, (90, 90, 105))
    screen.blit(path_s, path_s.get_rect(midleft=(bx + pad, by + bh // 2)))


def draw_selfplay_stats(screen, fonts, sp, L):
    """Show live training stats in the second bottom bar (ML vs ML mode).

    Mirrors the terminal line printed by train_selfplay.py:
      Game #N · loss X.XXXX · avg X.XXXX · W:N D:N B:N · avg_len XX.X · X.Xs/game
    """
    import time as _time

    f = fonts["bar"]
    bx, by = L.stats_bar_x, L.stats_bar_y
    bw, bh = L.stats_bar_w, L.stats_bar_h
    pad = max(4, bh // 5)
    sep = "  ·  "

    pygame.draw.rect(screen, (18, 18, 25), (bx, by, bw, bh), border_radius=4)
    pygame.draw.rect(screen, (45, 45, 60), (bx, by, bw, bh), 1, border_radius=4)

    last_loss = sp.losses[-1] if sp.losses else None
    avg_loss = sum(sp.losses[-10:]) / len(sp.losses[-10:]) if sp.losses else None
    avg_len = sum(sp.game_lengths) / len(sp.game_lengths) if sp.game_lengths else 0.0

    # Seconds into the current (in-progress) game
    cur_spg = _time.time() - sp.game_start_time

    parts = [f"Game\u202f#{sp.games_done + 1}"]

    if last_loss is not None:
        parts.append(f"loss\u202f{last_loss:.4f}")
    if avg_loss is not None:
        parts.append(f"avg\u202f{avg_loss:.4f}")

    parts.append(f"W:{sp.white_wins}\u202fD:{sp.draws}\u202fB:{sp.black_wins}")

    if sp.game_lengths:
        parts.append(f"avg_len\u202f{avg_len:.1f}")

    if sp.avg_spg > 0:
        parts.append(f"{sp.avg_spg:.1f}s/game")
    else:
        parts.append(f"{cur_spg:.0f}s")

    buf_size = len(sp.replay_buffer)
    parts.append(f"buf\u202f{buf_size}")

    line = sep.join(parts)
    text_s = f.render(line, True, (140, 155, 140))
    screen.blit(text_s, text_s.get_rect(midleft=(bx + pad, by + bh // 2)))


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


def draw_self_play_speed(screen, fonts, delay_ms, L):
    """Small speed indicator in the top-right corner during ML self-play."""
    label = S.ML_SELF_DELAY.format(ms=delay_ms)
    hint = S.ML_SELF_SPEED_HINT
    delay_surf = fonts["sub"].render(label, True, (100, 200, 170))
    hint_surf = fonts["sub"].render(hint, True, (80, 80, 80))
    x = L.board_w - max(delay_surf.get_width(), hint_surf.get_width()) - 8
    screen.blit(delay_surf, (x, 6 + fonts["sub"].get_height() + 4))
    screen.blit(hint_surf, (x, 6 + fonts["sub"].get_height() * 2 + 6))
