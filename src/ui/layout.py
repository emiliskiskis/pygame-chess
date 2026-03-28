from ..constants import MIN_TILE, DEFAULT_TILE


class Layout:
    PANEL_MIN = 160

    def __init__(self, win_w, win_h):
        self.update(win_w, win_h)

    def update(self, win_w, win_h):
        self.win_w = win_w
        self.win_h = win_h

        # Reserve fixed fractions for borders, then fit 8 tiles
        bt_est = max(50, win_h // 9)
        bb_est = max(70, win_h // 7)
        bs_est = max(20, win_w // 24)

        tile_h = (win_h - bt_est - bb_est) // 8
        tile_w = (win_w - bs_est * 2 - self.PANEL_MIN) // 8
        tile = max(MIN_TILE, min(tile_h, tile_w))

        self.tile = tile
        self.border_side = max(20, tile // 2)
        self.border_top = max(50, tile + 5)

        # Bottom border must fit the coordinate letters row and the notation bar
        bar_h = max(24, tile // 3)
        letters_h = max(24, tile // 2)
        self.border_bottom = letters_h + bar_h + 12

        self.board_px = tile * 8
        self.board_w = self.board_px + self.border_side * 2
        self.panel_w = max(self.PANEL_MIN, win_w - self.board_w)
        self.window_w = self.board_w + self.panel_w
        self.window_h = self.board_px + self.border_top + self.border_bottom

        # Coordinate letters sit in the upper portion of the bottom border
        self.coord_bottom_y = self.border_top + self.board_px + letters_h // 2

        # Notation bar sits below the coordinate letters
        self.bar_h = bar_h
        self.bar_y = self.border_top + self.board_px + letters_h + (self.border_bottom - letters_h - bar_h) // 2
        self.bar_x = self.border_side
        self.bar_w = self.board_px

        # Font sizes scale with tile
        s = tile / DEFAULT_TILE
        self.fs_coord = max(10, int(16 * s))
        self.fs_status = max(12, int(18 * s))
        self.fs_piece = max(24, int(52 * s))
        self.fs_panel = max(10, int(14 * s))
        self.fs_header = max(11, int(17 * s))
        self.fs_tip = max(9, int(13 * s))
        self.fs_title = max(28, int(56 * s))
        self.fs_btn = max(14, int(20 * s))
        self.fs_sub = max(10, int(14 * s))
        self.fs_over = max(20, int(34 * s))
        self.fs_bar = max(11, int(15 * s))
        self.panel_line = max(16, int(22 * s))
