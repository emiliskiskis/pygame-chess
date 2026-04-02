"""
app.py — GameApp: main game loop, event dispatch, and rendering.

Replaces the monolithic main() function.  All mutable state lives on self as
typed dataclass instances rather than 60-odd nonlocal variables.
"""

import sys
import threading
import time

import pygame

from .. import profiles, strings
from ..constants import (
    ASSET_DIR,
    MODE_AI,
    MODE_LANG_SELECT,
    MODE_LEARNING,
    MODE_MENU,
    MODE_ML_AI,
    MODE_ML_SELF,
    MODE_PROFILES,
    PIECE_SYMBOLS,
)
from ..engine.ai import ai_move
from ..engine.board import (
    execute_move,
    legal_moves,
    opponent,
    piece_color,
    piece_type,
    post_move_status,
    starting_board,
)
from ..engine.ml_ai import (
    clear_game_history,
    get_model_path_str,
    get_stats,
    ml_ai_mcts_move_for,
    ml_ai_move,
    ml_ai_move_for,
    record_game_result,
    record_position,
    start_selfplay_batch_training_async,
    start_training_async,
    unload_model,
)
from ..engine.notation import parse_algebraic
from ..engine.pieces import load_flags, load_pieces, reload_pieces
from ..savegame import (
    SAVEABLE_MODES,
    delete_save,
    load_game,
    save_exists,
    save_game,
)
from ..strings import S, available_locales
from ..strings import reload as reload_strings
from ..ui.board_renderer import (
    draw_board,
    draw_coordinates,
    draw_fallback_pieces,
    draw_highlights,
    draw_pieces,
    pixel_to_cell,
)
from ..ui.hud_renderer import (
    draw_ai_progress,
    draw_model_path,
    draw_move_panel,
    draw_notation_bar,
    draw_self_play_speed,
    draw_selfplay_stats,
    draw_status,
    draw_tip,
)
from ..ui.layout import Layout
from ..ui.menu_renderer import (
    draw_continue_popup,
    draw_corrupt_popup,
    draw_gameover_overlay,
    draw_lang_picker,
    draw_lang_select,
    draw_menu,
    draw_pause_menu,
    draw_profiles_screen,
    draw_selfplay_training_screen,
    make_fonts,
)
from .state import (
    AIState,
    ChessState,
    DragState,
    ProfilesDialogState,
    SavePopupState,
    SelfPlayState,
    TrainingState,
)


class GameApp:
    """
    Top-level application object.

    Call run() to enter the game loop.  All state is held as instance
    attributes so no nonlocal bookkeeping is needed.
    """

    INIT_W = 960
    INIT_H = 780
    RESIZE_DELAY = 100  # ms quiet period before re-layout
    NOTATION_CHARS = set("abcdefghABCDEFGH12345678KQRBNkqrbnxXoO0-+#")

    def __init__(self):
        pygame.init()

        profiles.try_migrate_from_prefs()

        active = profiles.get_active_profile()
        startup_lang = active["language"] if active else "en"
        reload_strings(startup_lang)

        self.screen = pygame.display.set_mode(
            (self.INIT_W, self.INIT_H), pygame.RESIZABLE
        )
        pygame.display.set_caption(S.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.fullscreen = False

        self.L = Layout(self.INIT_W, self.INIT_H)
        self.fonts = make_fonts(self.L)
        self.pieces = load_pieces(ASSET_DIR, self.L.tile)
        self.use_svg = bool(self.pieces)
        self.last_tile = self.L.tile

        self.locales = available_locales()
        self.flags = load_flags(ASSET_DIR, self.locales)

        # Resize debounce
        self.pending_size = None
        self.resize_timer = 0

        # Mode
        self.mode = MODE_MENU if profiles.profiles_exist() else MODE_LANG_SELECT

        # Per-mode hover / rect state
        self.lang_open = False
        self.lang_hovered = None
        self.lang_rects: dict = {}

        self.lang_select_hovered = None
        self.lang_select_rects: dict = {}

        self.menu_hovered = None
        self.menu_rects: dict = {}

        self.paused = False
        self.pause_hovered = None
        self.pause_rects: dict = {}

        self.over_hovered = None
        self.over_rects: dict = {}

        self.profiles_hovered = None
        self.profiles_rects: dict = {}

        # Notation bar
        self.bar_text = ""
        self.bar_error = False

        # Compound state objects
        self.chess: ChessState | None = None
        self.drag = DragState()
        self.ai = AIState()
        self.training = TrainingState()
        self.save_popup = SavePopupState()
        self.dialog = ProfilesDialogState()
        self.sp: SelfPlayState | None = None  # ML vs ML MCTS self-play state

        # Self-play speed control (legacy non-MCTS path; no longer shown)
        self.self_play_delay_ms = 0
        self.last_move_time = 0

    # ── Game state helpers ───────────────────────────────────────────────────────

    def _new_game(self, new_mode):
        self.chess = ChessState(
            board=starting_board(),
            status_msg=(
                S.STATUS_YOUR_TURN
                if new_mode in (MODE_AI, MODE_ML_AI)
                else S.STATUS_WHITE_TURN
            ),
        )
        if new_mode in (MODE_ML_AI, MODE_ML_SELF):
            clear_game_history()
        self.ai = AIState()
        self.training = TrainingState()
        self.bar_text = ""
        self.bar_error = False
        self.paused = False
        self.over_hovered = None
        self.over_rects = {}
        self.pause_hovered = None
        self.pause_rects = {}
        self.last_move_time = 0
        if new_mode == MODE_ML_SELF:
            if self.sp is None:
                # Fresh entry into this mode (e.g. from main menu)
                self.sp = SelfPlayState()
            else:
                # Restart within the mode: preserve replay buffer and stats
                self.sp.current_positions = []
                self.sp.mcts_result = [None, None, None]
                self.sp.game_start_time = time.time()

    def _apply_new_size(self, w, h):
        self.L = Layout(w, h)
        self.fonts = make_fonts(self.L)
        if self.L.tile != self.last_tile:
            self.pieces = reload_pieces(ASSET_DIR, self.L.tile, self.pieces)
            self.use_svg = bool(self.pieces)
            self.last_tile = self.L.tile

    def _toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(
                (self.INIT_W, self.INIT_H), pygame.RESIZABLE
            )
        self._apply_new_size(*self.screen.get_size())

    def _do_move(self, from_sq, to_sq, mcts_policy_dict=None, mcts_tensor=None):
        chess = self.chess
        if self.mode == MODE_ML_AI:
            record_position(
                chess.board, chess.turn, chess.castling_rights,
                chess.last_move, from_sq, to_sq,
            )
        elif self.mode == MODE_ML_SELF and mcts_policy_dict is not None and mcts_tensor is not None:
            self.sp.current_positions.append(
                (mcts_tensor, mcts_policy_dict, chess.turn)
            )
        chess.last_move, chess.castling_rights, notation = execute_move(
            chess.board, from_sq, to_sq, chess.last_move, chess.castling_rights, chess.turn
        )
        chess.move_history.append(notation)
        chess.turn = opponent(chess.turn)
        chess.selected = None
        chess.possible_moves = []
        chess.tip_text = ""
        self.bar_text = ""
        self.bar_error = False
        chess.status_msg, chess.game_over = post_move_status(
            chess.board, chess.turn, chess.last_move, chess.castling_rights, self.mode
        )
        # ML vs ML: enforce 200 half-move (100 full turn) draw limit
        if (
            self.mode == MODE_ML_SELF
            and not chess.game_over
            and len(chess.move_history) >= 200
        ):
            chess.status_msg = S.STATUS_STALEMATE
            chess.game_over = True
        if chess.game_over:
            if self.mode in (MODE_ML_AI, MODE_ML_SELF):
                if S.STATUS_CHECKMATE.split("{")[0] in chess.status_msg:
                    winner = opponent(chess.turn)
                    base = 1.0 if winner == "white" else -1.0
                    # Reward finishing faster: scale from 1.0 (move 0) down to 0.5 (move 200).
                    brevity = 1.0 - 0.5 * (len(chess.move_history) / 200)
                    ml_result = base * brevity
                else:
                    ml_result = 0.0
            if self.mode == MODE_ML_AI:
                record_game_result(ml_result)
                self.training.active = True
                self.training.thread = start_training_async(
                    ml_result, self.training.progress
                )
            elif self.mode == MODE_ML_SELF and self.sp is not None:
                # Flush current game positions into replay buffer
                for tensor, pd, turn_color in self.sp.current_positions:
                    self.sp.replay_buffer.append((tensor, pd, turn_color, ml_result))
                self.sp.current_positions = []
                # Update timing
                elapsed = time.time() - self.sp.game_start_time
                self.sp.avg_spg = (
                    (self.sp.avg_spg * self.sp.games_done + elapsed)
                    / (self.sp.games_done + 1)
                )
                # Update cumulative stats
                self.sp.games_done += 1
                if ml_result > 0:
                    self.sp.white_wins += 1
                elif ml_result < 0:
                    self.sp.black_wins += 1
                else:
                    self.sp.draws += 1
                self.sp.game_lengths.append(len(chess.move_history))
                # Start batch training in background
                self.sp.loss_result = [0.0, 0.0, 0.0]
                self.sp.progress = [0, 0]
                self.sp.training_active = True
                self.sp.training_thread = start_selfplay_batch_training_async(
                    self.sp.replay_buffer, 256, self.sp.progress, self.sp.loss_result
                )

    def _save_current_game(self):
        if (
            self.mode in SAVEABLE_MODES
            and self.chess is not None
            and not self.chess.game_over
        ):
            chess = self.chess
            save_game(
                self.mode,
                chess.board,
                chess.turn,
                chess.last_move,
                chess.castling_rights,
                chess.move_history or [],
                chess.flipped or False,
            )

    # ── Main loop ────────────────────────────────────────────────────────────────

    def run(self):
        while True:
            now = pygame.time.get_ticks()
            mx, my = pygame.mouse.get_pos()

            if self.pending_size and now >= self.resize_timer:
                self._apply_new_size(*self.pending_size)
                self.pending_size = None

            self._update_ai(now)

            for event in pygame.event.get():
                self._handle_event(event, now, mx, my)

            self._render(mx, my)
            pygame.display.flip()
            self.clock.tick(60)

    # ── Per-frame AI / training updates ─────────────────────────────────────────

    def _update_ai(self, now):
        chess = self.chess

        # ML self-play (MCTS): trigger search for whichever side is to move
        if (
            self.mode == MODE_ML_SELF
            and chess
            and not chess.game_over
            and not self.ai.thinking
            and not self.paused
            and self.sp is not None
            and not self.sp.training_active
        ):
            self.sp.mcts_result = [None, None, None]
            _board = chess.board
            _lm = chess.last_move
            _cr = chess.castling_rights
            _turn = chess.turn
            _mcts_result = self.sp.mcts_result

            def _run_mcts():
                policy_dict, move, board_tensor = ml_ai_mcts_move_for(
                    _board, _turn, _lm, _cr
                )
                _mcts_result[0] = policy_dict
                _mcts_result[1] = move
                _mcts_result[2] = board_tensor

            self.ai.thread = threading.Thread(target=_run_mcts, daemon=True)
            self.ai.thread.start()
            self.ai.thinking = True

        # Minimax AI turn (black)
        if (
            self.mode == MODE_AI
            and chess
            and chess.turn == "black"
            and not chess.game_over
            and not self.ai.thinking
            and not self.paused
        ):
            self.ai.progress[0] = 0
            self.ai.progress[1] = 1
            self.ai.result[0] = None
            _board = chess.board
            _lm = chess.last_move
            _cr = chess.castling_rights
            _result = self.ai.result
            _progress = self.ai.progress

            def _run_ai():
                _result[0] = ai_move(_board, _lm, _cr, _progress)

            self.ai.thread = threading.Thread(target=_run_ai, daemon=True)
            self.ai.thread.start()
            self.ai.thinking = True

        # ML AI turn (black)
        if (
            self.mode == MODE_ML_AI
            and chess
            and chess.turn == "black"
            and not chess.game_over
            and not self.ai.thinking
            and not self.paused
        ):
            self.ai.progress[0] = 0
            self.ai.progress[1] = 1
            self.ai.result[0] = None
            _board = chess.board
            _lm = chess.last_move
            _cr = chess.castling_rights
            _result = self.ai.result
            _progress = self.ai.progress

            def _run_ml_ai():
                _result[0] = ml_ai_move(_board, _lm, _cr, _progress)

            self.ai.thread = threading.Thread(target=_run_ml_ai, daemon=True)
            self.ai.thread.start()
            self.ai.thinking = True

        # Collect AI / MCTS result when thread finishes
        if self.ai.thinking and self.ai.thread is not None and not self.ai.thread.is_alive():
            self.ai.thinking = False
            self.ai.thread = None
            if self.mode == MODE_ML_SELF and self.sp is not None:
                policy_dict = self.sp.mcts_result[0]
                move = self.sp.mcts_result[1]
                board_tensor = self.sp.mcts_result[2]
                if move is not None:
                    self._do_move(
                        (move[0], move[1]), (move[2], move[3]),
                        mcts_policy_dict=policy_dict,
                        mcts_tensor=board_tensor,
                    )
            else:
                move = self.ai.result[0]
                if move:
                    self._do_move((move[0], move[1]), (move[2], move[3]))

        # Collect self-play training result when thread finishes
        if (
            self.mode == MODE_ML_SELF
            and self.sp is not None
            and self.sp.training_active
            and self.sp.training_thread is not None
            and not self.sp.training_thread.is_alive()
        ):
            self.sp.training_active = False
            self.sp.training_thread = None
            # Record the loss from this completed training run
            self.sp.losses.append(self.sp.loss_result[0])
            # Auto-restart the next game
            self._new_game(MODE_ML_SELF)

        # Collect ML_AI training result when thread finishes
        if (
            self.training.active
            and self.training.thread is not None
            and not self.training.thread.is_alive()
        ):
            self.training.active = False
            self.training.thread = None

    # ── Top-level event dispatch ─────────────────────────────────────────────────

    def _handle_event(self, event, now, mx, my):
        if event.type == pygame.QUIT:
            self._save_current_game()
            pygame.quit()
            sys.exit()

        if event.type == pygame.VIDEORESIZE:
            w = max(event.w, 400)
            h = max(event.h, 400)
            self.pending_size = (w, h)
            self.resize_timer = now + self.RESIZE_DELAY
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            self._toggle_fullscreen()
            return

        if self.mode == MODE_LANG_SELECT:
            self._handle_lang_select_event(event, mx, my)
            return

        if self.mode == MODE_PROFILES:
            self._handle_profiles_event(event, mx, my)
            return

        if self.mode == MODE_MENU:
            self._handle_menu_event(event, mx, my)
            return

        chess = self.chess

        # During self-play training screen: only ESC (to pause) passes through
        if (
            self.mode == MODE_ML_SELF
            and self.sp is not None
            and self.sp.training_active
        ):
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.paused = True
                self.pause_hovered = None
                self.lang_open = False
                self.lang_hovered = None
            return

        if self.paused and chess and not chess.game_over:
            self._handle_pause_event(event, mx, my)
            return

        if chess and chess.game_over:
            self._handle_gameover_event(event, mx, my)
            return

        if self.mode == MODE_ML_SELF and chess and not chess.game_over and not self.paused:
            self._handle_ml_self_event(event, mx, my)
            return

        self._handle_ingame_event(event, mx, my)

    # ── Mode-specific event handlers ─────────────────────────────────────────────

    def _handle_lang_select_event(self, event, mx, my):
        if event.type == pygame.MOUSEMOTION:
            self.lang_select_hovered = None
            for k, rect in self.lang_select_rects.items():
                if rect.collidepoint(mx, my):
                    self.lang_select_hovered = k
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for k, rect in self.lang_select_rects.items():
                if rect.collidepoint(mx, my):
                    reload_strings(k)
                    pygame.display.set_caption(S.WINDOW_TITLE)
                    p = profiles.create_profile("Player 1", k)
                    profiles.set_active_profile(p["id"])
                    self.mode = MODE_MENU
                    self.lang_select_hovered = None
                    break

    def _handle_profiles_event(self, event, mx, my):
        dlg = self.dialog
        any_dialog = (
            dlg.editing_id is not None or dlg.creating or dlg.deleting_id is not None
        )

        if event.type == pygame.KEYDOWN:
            if any_dialog and (dlg.editing_id is not None or dlg.creating):
                if event.key == pygame.K_ESCAPE:
                    dlg.editing_id = None
                    dlg.creating = False
                    dlg.edit_text = ""
                    dlg.create_text = ""
                    dlg.dialog_hovered = None
                elif event.key == pygame.K_RETURN:
                    txt = dlg.create_text if dlg.creating else dlg.edit_text
                    if txt.strip():
                        if dlg.creating:
                            active_p = profiles.get_active_profile()
                            lang = active_p["language"] if active_p else "en"
                            p = profiles.create_profile(txt.strip(), lang)
                            profiles.set_active_profile(p["id"])
                            unload_model()
                            reload_strings(lang)
                            pygame.display.set_caption(S.WINDOW_TITLE)
                            dlg.creating = False
                            dlg.create_text = ""
                        else:
                            profiles.rename_profile(dlg.editing_id, txt.strip())
                            dlg.editing_id = None
                            dlg.edit_text = ""
                        dlg.dialog_hovered = None
                elif event.key == pygame.K_BACKSPACE:
                    if dlg.creating:
                        dlg.create_text = dlg.create_text[:-1]
                    else:
                        dlg.edit_text = dlg.edit_text[:-1]
                else:
                    ch = event.unicode
                    if ch and ch.isprintable():
                        if dlg.creating:
                            if len(dlg.create_text) < 30:
                                dlg.create_text += ch
                        else:
                            if len(dlg.edit_text) < 30:
                                dlg.edit_text += ch
            elif any_dialog and dlg.deleting_id is not None:
                if event.key == pygame.K_ESCAPE:
                    dlg.deleting_id = None
                    dlg.dialog_hovered = None
            else:
                if event.key == pygame.K_ESCAPE:
                    self.mode = MODE_MENU
                    self.profiles_hovered = None
            return

        if event.type == pygame.MOUSEMOTION:
            dlg.dialog_hovered = None
            self.profiles_hovered = None
            for k, rect in self.profiles_rects.items():
                if rect.collidepoint(mx, my):
                    if any_dialog:
                        if k.startswith("dialog_"):
                            dlg.dialog_hovered = k
                            break
                    else:
                        self.profiles_hovered = k
                        break

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for k, rect in self.profiles_rects.items():
                if not rect.collidepoint(mx, my):
                    continue
                if any_dialog:
                    if k == "dialog_cancel":
                        dlg.editing_id = None
                        dlg.creating = False
                        dlg.edit_text = ""
                        dlg.create_text = ""
                        dlg.deleting_id = None
                        dlg.dialog_hovered = None
                    elif k == "dialog_ok":
                        txt = dlg.create_text if dlg.creating else dlg.edit_text
                        if txt.strip():
                            if dlg.creating:
                                active_p = profiles.get_active_profile()
                                lang = active_p["language"] if active_p else "en"
                                p = profiles.create_profile(txt.strip(), lang)
                                profiles.set_active_profile(p["id"])
                                unload_model()
                                reload_strings(lang)
                                pygame.display.set_caption(S.WINDOW_TITLE)
                                dlg.creating = False
                                dlg.create_text = ""
                            else:
                                profiles.rename_profile(dlg.editing_id, txt.strip())
                                dlg.editing_id = None
                                dlg.edit_text = ""
                            dlg.dialog_hovered = None
                    elif k == "dialog_yes":
                        profiles.delete_profile(dlg.deleting_id)
                        dlg.deleting_id = None
                        dlg.dialog_hovered = None
                    elif k == "dialog_no":
                        dlg.deleting_id = None
                        dlg.dialog_hovered = None
                else:
                    if k == "back":
                        self.mode = MODE_MENU
                        self.profiles_hovered = None
                    elif k == "new":
                        dlg.creating = True
                        dlg.create_text = ""
                        dlg.dialog_hovered = None
                    elif k.startswith("select_"):
                        pid = k[len("select_"):]
                        if pid != profiles.get_active_id():
                            self._save_current_game()
                            profiles.set_active_profile(pid)
                            unload_model()
                            active_p = profiles.get_active_profile()
                            lang = active_p["language"] if active_p else "en"
                            reload_strings(lang)
                            pygame.display.set_caption(S.WINDOW_TITLE)
                            self.mode = MODE_MENU
                            self.profiles_hovered = None
                    elif k.startswith("edit_"):
                        pid = k[len("edit_"):]
                        p = next(
                            (x for x in profiles.get_profiles() if x["id"] == pid), None
                        )
                        if p:
                            dlg.editing_id = pid
                            dlg.edit_text = p["name"]
                            dlg.dialog_hovered = None
                    elif k.startswith("delete_"):
                        pid = k[len("delete_"):]
                        dlg.deleting_id = pid
                        dlg.dialog_hovered = None
                break

    def _handle_menu_event(self, event, mx, my):
        popup = self.save_popup

        # Save-game popup overlays the menu while visible
        if popup.error or popup.pending_mode is not None:
            if event.type == pygame.MOUSEMOTION:
                popup.hovered = None
                for k, rect in popup.rects.items():
                    if rect.collidepoint(mx, my):
                        popup.hovered = k
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for k, rect in popup.rects.items():
                    if rect.collidepoint(mx, my):
                        if popup.error:
                            if k == "continue":
                                delete_save(popup.pending_mode)
                                self.mode = popup.pending_mode
                                self._new_game(popup.pending_mode)
                                popup.pending_mode = None
                                popup.error = False
                                popup.hovered = None
                        else:
                            if k == "yes":
                                try:
                                    data = load_game(popup.pending_mode)
                                    self._new_game(popup.pending_mode)
                                    self.mode = popup.pending_mode
                                    chess = self.chess
                                    chess.board = data["board"]
                                    chess.turn = data["turn"]
                                    chess.last_move = data["last_move"]
                                    chess.castling_rights = data["castling_rights"]
                                    chess.move_history = data["move_history"]
                                    chess.flipped = data.get("flipped", False)
                                    chess.status_msg, chess.game_over = post_move_status(
                                        chess.board, chess.turn, chess.last_move,
                                        chess.castling_rights, self.mode,
                                    )
                                    popup.pending_mode = None
                                    popup.hovered = None
                                except ValueError:
                                    popup.error = True
                                    popup.hovered = None
                            elif k == "no":
                                delete_save(popup.pending_mode)
                                self.mode = popup.pending_mode
                                self._new_game(popup.pending_mode)
                                popup.pending_mode = None
                                popup.hovered = None
                            elif k == "cancel":
                                popup.pending_mode = None
                                popup.error = False
                                popup.hovered = None
                        break
            return

        if event.type == pygame.MOUSEMOTION:
            self.menu_hovered = None
            self.lang_hovered = None
            for m, rect in self.menu_rects.items():
                if rect.collidepoint(mx, my):
                    self.menu_hovered = m
            for k, rect in self.lang_rects.items():
                if rect.collidepoint(mx, my):
                    self.lang_hovered = k

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            picked_lang = False
            for k, rect in self.lang_rects.items():
                if rect.collidepoint(mx, my):
                    if k == "toggle":
                        self.lang_open = not self.lang_open
                    else:
                        reload_strings(k)
                        profiles.set_active_language(k)
                        pygame.display.set_caption(S.WINDOW_TITLE)
                        if self.chess is not None:
                            chess = self.chess
                            chess.status_msg, chess.game_over = post_move_status(
                                chess.board, chess.turn, chess.last_move,
                                chess.castling_rights, self.mode,
                            )
                        self.lang_open = False
                    picked_lang = True
                    break
            if not picked_lang:
                self.lang_open = False
                for m, rect in self.menu_rects.items():
                    if rect.collidepoint(mx, my):
                        if m == MODE_PROFILES:
                            self.mode = MODE_PROFILES
                            self.profiles_hovered = None
                            self.profiles_rects = {}
                        elif m in SAVEABLE_MODES and save_exists(m):
                            popup.pending_mode = m
                            popup.hovered = None
                            popup.rects = {}
                        else:
                            # Reset self-play state on fresh mode entry from menu
                            if m == MODE_ML_SELF:
                                self.sp = None
                            self.mode = m
                            self._new_game(m)
                        break

    def _handle_pause_event(self, event, mx, my):
        if event.type == pygame.MOUSEMOTION:
            self.pause_hovered = None
            self.lang_hovered = None
            for k, rect in self.pause_rects.items():
                if rect.collidepoint(mx, my):
                    self.pause_hovered = k
            for k, rect in self.lang_rects.items():
                if rect.collidepoint(mx, my):
                    self.lang_hovered = k

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            picked_lang = False
            for k, rect in self.lang_rects.items():
                if rect.collidepoint(mx, my):
                    if k == "toggle":
                        self.lang_open = not self.lang_open
                    else:
                        reload_strings(k)
                        profiles.set_active_language(k)
                        pygame.display.set_caption(S.WINDOW_TITLE)
                        chess = self.chess
                        chess.status_msg, chess.game_over = post_move_status(
                            chess.board, chess.turn, chess.last_move,
                            chess.castling_rights, self.mode,
                        )
                        self.lang_open = False
                    picked_lang = True
                    break
            if not picked_lang:
                self.lang_open = False
                for k, rect in self.pause_rects.items():
                    if rect.collidepoint(mx, my):
                        if k == "resume":
                            self.paused = False
                        elif k == "restart":
                            self._new_game(self.mode)
                        elif k == "menu":
                            self._save_current_game()
                            self.mode = MODE_MENU
                        elif k == "fullscreen":
                            self._toggle_fullscreen()
                        elif k == "quit":
                            self._save_current_game()
                            pygame.quit()
                            sys.exit()
                        break

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.paused = False
            self.lang_open = False
            self.lang_hovered = None

    def _handle_gameover_event(self, event, mx, my):
        if event.type == pygame.MOUSEMOTION:
            self.over_hovered = None
            for k, rect in self.over_rects.items():
                if rect.collidepoint(mx, my):
                    self.over_hovered = k

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for k, rect in self.over_rects.items():
                if rect.collidepoint(mx, my):
                    if k == "restart":
                        self._new_game(self.mode)
                    elif k == "menu":
                        self.mode = MODE_MENU
                    elif k == "quit":
                        pygame.quit()
                        sys.exit()
                    break

    def _handle_ml_self_event(self, event, mx, my):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.paused = True
                self.pause_hovered = None
                self.lang_open = False
                self.lang_hovered = None
            elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.self_play_delay_ms = max(0, self.self_play_delay_ms - 50)
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.self_play_delay_ms = min(2000, self.self_play_delay_ms + 50)

    def _handle_ingame_event(self, event, mx, my):
        chess = self.chess
        if chess is None:
            return

        block = self.mode in (MODE_AI, MODE_ML_AI) and chess.turn == "black"

        if event.type == pygame.KEYDOWN and not block:
            if event.key == pygame.K_ESCAPE:
                if self.bar_text:
                    self.bar_text = ""
                    self.bar_error = False
                else:
                    self.paused = True
                    self.pause_hovered = None
                    self.lang_open = False
                    self.lang_hovered = None
                return

            if event.key == pygame.K_RETURN:
                if self.bar_text.strip():
                    result = parse_algebraic(
                        self.bar_text, chess.board, chess.turn,
                        chess.last_move, chess.castling_rights,
                    )
                    if result:
                        self._do_move(*result)
                    else:
                        self.bar_error = True
                elif chess.selected and chess.cursor in chess.possible_moves:
                    self._do_move(chess.selected, chess.cursor)
                return

            if event.key == pygame.K_BACKSPACE:
                self.bar_text = self.bar_text[:-1]
                self.bar_error = False
                return

            if (
                event.unicode
                and event.unicode.isprintable()
                and event.unicode in self.NOTATION_CHARS
                and len(self.bar_text) < 12
            ):
                self.bar_text += event.unicode
                self.bar_error = False
                return

            kn = pygame.key.name(event.key).upper()
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                dr = {"UP": -1, "DOWN": 1}.get(kn, 0)
                dc = {"LEFT": -1, "RIGHT": 1}.get(kn, 0)
                if chess.flipped:
                    dr, dc = -dr, -dc
                nr = max(0, min(7, chess.cursor[0] + dr))
                nc = max(0, min(7, chess.cursor[1] + dc))
                chess.cursor = (nr, nc)
                if self.mode == MODE_LEARNING and chess.board[nr][nc]:
                    chess.tip_text = S.TIPS.get(piece_type(chess.board[nr][nc]), "")
                else:
                    chess.tip_text = ""
                return

            if event.key == pygame.K_SPACE:
                r, c = chess.cursor
                clicked = chess.board[r][c]
                if chess.selected:
                    if chess.cursor in chess.possible_moves:
                        self._do_move(chess.selected, chess.cursor)
                    elif clicked and piece_color(clicked) == chess.turn:
                        chess.selected = chess.cursor
                        chess.possible_moves = legal_moves(
                            chess.board, r, c, chess.last_move, chess.castling_rights
                        )
                        if self.mode == MODE_LEARNING:
                            chess.tip_text = S.TIPS.get(piece_type(clicked), "")
                    else:
                        chess.selected = None
                        chess.possible_moves = []
                else:
                    if clicked and piece_color(clicked) == chess.turn:
                        chess.selected = chess.cursor
                        chess.possible_moves = legal_moves(
                            chess.board, r, c, chess.last_move, chess.castling_rights
                        )
                        if self.mode == MODE_LEARNING:
                            chess.tip_text = S.TIPS.get(piece_type(clicked), "")

        if not block:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cell = pixel_to_cell(mx, my, chess.flipped, self.L)
                if cell is None:
                    return
                r, c = cell
                clicked = chess.board[r][c]
                chess.cursor = cell
                if chess.selected:
                    if cell in chess.possible_moves:
                        self._do_move(chess.selected, cell)
                        self.drag.active = False
                        self.drag.piece_key = None
                        self.drag.from_cell = None
                    elif clicked and piece_color(clicked) == chess.turn:
                        chess.selected = cell
                        chess.possible_moves = legal_moves(
                            chess.board, r, c, chess.last_move, chess.castling_rights
                        )
                        self.drag.active = True
                        self.drag.piece_key = clicked
                        self.drag.from_cell = cell
                        self.drag.pos = (mx, my)
                        if self.mode == MODE_LEARNING:
                            chess.tip_text = S.TIPS.get(piece_type(clicked), "")
                    else:
                        chess.selected = None
                        chess.possible_moves = []
                        chess.tip_text = ""
                else:
                    if clicked and piece_color(clicked) == chess.turn:
                        chess.selected = cell
                        chess.possible_moves = legal_moves(
                            chess.board, r, c, chess.last_move, chess.castling_rights
                        )
                        self.drag.active = True
                        self.drag.piece_key = clicked
                        self.drag.from_cell = cell
                        self.drag.pos = (mx, my)
                        if self.mode == MODE_LEARNING:
                            chess.tip_text = S.TIPS.get(piece_type(clicked), "")

            if event.type == pygame.MOUSEMOTION:
                self.drag.pos = (mx, my)
                if self.mode == MODE_LEARNING and not chess.selected:
                    cell = pixel_to_cell(mx, my, chess.flipped, self.L)
                    if cell and chess.board[cell[0]][cell[1]]:
                        chess.tip_text = S.TIPS.get(
                            piece_type(chess.board[cell[0]][cell[1]]), ""
                        )
                    else:
                        chess.tip_text = ""

            if (
                event.type == pygame.MOUSEBUTTONUP
                and event.button == 1
                and self.drag.active
            ):
                self.drag.active = False
                cell = pixel_to_cell(mx, my, chess.flipped, self.L)
                if (
                    cell
                    and chess.selected
                    and cell in chess.possible_moves
                    and cell != chess.selected
                ):
                    self._do_move(chess.selected, cell)

    # ── Rendering ────────────────────────────────────────────────────────────────

    def _render(self, mx, my):
        if self.mode == MODE_LANG_SELECT:
            self.lang_select_rects = draw_lang_select(
                self.screen, self.fonts, self.flags, self.locales,
                self.lang_select_hovered, self.L,
            )

        elif self.mode == MODE_PROFILES:
            dlg = self.dialog
            self.profiles_rects = draw_profiles_screen(
                self.screen,
                self.fonts,
                profiles.get_profiles(),
                profiles.get_active_id(),
                self.profiles_hovered,
                self.L,
                editing_id=dlg.editing_id,
                edit_text=dlg.edit_text,
                creating=dlg.creating,
                create_text=dlg.create_text,
                deleting_id=dlg.deleting_id,
                dialog_hovered=dlg.dialog_hovered,
            )

        elif self.mode == MODE_MENU:
            active_p = profiles.get_active_profile()
            profile_name = active_p["name"] if active_p else ""
            self.menu_rects = draw_menu(
                self.screen, self.fonts, self.menu_hovered, self.L,
                profile_name=profile_name,
            )
            self.lang_rects = draw_lang_picker(
                self.screen, self.fonts, self.flags, self.locales,
                strings.CURRENT_LOCALE, self.lang_open, self.lang_hovered, self.L,
            )
            popup = self.save_popup
            if popup.error:
                popup.rects = draw_corrupt_popup(
                    self.screen, self.fonts, popup.hovered, self.L
                )
            elif popup.pending_mode is not None:
                popup.rects = draw_continue_popup(
                    self.screen, self.fonts, popup.hovered, self.L
                )

        else:
            self._render_game()

    def _render_game(self):
        chess = self.chess
        flipped = chess.flipped if chess else False

        draw_board(self.screen, self.L)

        if chess:
            bar_preview = None
            if self.bar_text and not chess.game_over and not self.paused:
                bar_preview = parse_algebraic(
                    self.bar_text, chess.board, chess.turn,
                    chess.last_move, chess.castling_rights,
                )
            draw_highlights(
                self.screen, chess.selected, chess.possible_moves,
                chess.last_move, chess.cursor, flipped, self.L,
                preview_move=bar_preview,
            )

        draw_coordinates(self.screen, self.fonts, flipped, self.L)

        skip = self.drag.from_cell if self.drag.active else None
        if chess:
            if self.use_svg:
                draw_pieces(self.screen, chess.board, self.pieces, flipped, self.L, skip=skip)
            else:
                draw_fallback_pieces(
                    self.screen, chess.board, self.fonts, flipped, self.L, skip=skip
                )

        if self.drag.active and self.drag.piece_key:
            if self.use_svg and self.drag.piece_key in self.pieces:
                img = self.pieces[self.drag.piece_key]
                self.screen.blit(img, img.get_rect(center=self.drag.pos))
            else:
                surf = self.fonts["piece"].render(
                    PIECE_SYMBOLS.get(self.drag.piece_key, "?"), True, (30, 30, 30)
                )
                self.screen.blit(surf, surf.get_rect(center=self.drag.pos))

        badges = {
            "pvp":     S.BADGE_PVP,
            "ai":      S.BADGE_AI,
            "learning": S.BADGE_LEARNING,
            "ml_ai":   S.BADGE_ML_AI,
            "ml_self": S.BADGE_ML_SELF,
        }
        badge = self.fonts["sub"].render(badges.get(self.mode, ""), True, (120, 120, 120))
        self.screen.blit(badge, (self.L.board_w - badge.get_width() - 8, 6))

        if chess and chess.status_msg:
            draw_status(self.screen, self.fonts, chess.status_msg, self.L)

        if self.mode in (MODE_AI, MODE_ML_AI) and self.ai.thinking:
            draw_ai_progress(self.screen, self.ai.progress, self.L)

        if self.mode == MODE_ML_SELF and self.sp is None:
            draw_self_play_speed(self.screen, self.fonts, self.self_play_delay_ms, self.L)

        if chess and self.mode == MODE_LEARNING and chess.tip_text:
            draw_tip(self.screen, self.fonts, chess.tip_text, self.L)
        elif self.mode == MODE_ML_SELF:
            draw_model_path(self.screen, self.fonts, get_model_path_str(), self.L)
            if self.sp is not None:
                draw_selfplay_stats(self.screen, self.fonts, self.sp, self.L)
        else:
            draw_notation_bar(self.screen, self.fonts, self.bar_text, self.bar_error, self.L)

        draw_move_panel(self.screen, self.fonts, chess.move_history if chess else [], self.L)

        if (
            self.mode == MODE_ML_SELF
            and self.sp is not None
            and self.sp.training_active
        ):
            # Show training stats screen; auto-restarts when thread completes
            if self.paused:
                self.pause_rects = draw_pause_menu(
                    self.screen, self.fonts, self.pause_hovered, self.L
                )
                self.lang_rects = draw_lang_picker(
                    self.screen, self.fonts, self.flags, self.locales,
                    strings.CURRENT_LOCALE, self.lang_open, self.lang_hovered, self.L,
                )
            else:
                draw_selfplay_training_screen(
                    self.screen, self.fonts, self.sp, self.L,
                    model_path=get_model_path_str(),
                )
        elif chess and chess.game_over:
            ml_data = None
            if self.mode in (MODE_ML_AI, MODE_ML_SELF):
                ml_data = get_stats()
                ml_data["game_length"] = len(chess.move_history) if chess.move_history else 0
            self.over_rects = draw_gameover_overlay(
                self.screen, self.fonts, chess.status_msg, self.over_hovered, self.L,
                ml_stats=ml_data,
                training_progress=(
                    self.training.progress if self.mode == MODE_ML_AI else None
                ),
                training_done=not self.training.active,
                self_play=self.mode == MODE_ML_SELF,
            )
        elif self.paused:
            self.pause_rects = draw_pause_menu(
                self.screen, self.fonts, self.pause_hovered, self.L
            )
            self.lang_rects = draw_lang_picker(
                self.screen, self.fonts, self.flags, self.locales,
                strings.CURRENT_LOCALE, self.lang_open, self.lang_hovered, self.L,
            )
