"""
Chess — entry point.

Controls
--------
Mouse           : click / drag pieces
Notation box    : always-visible bar at the bottom; type e.g. "e4", "Nf3", "O-O" + Enter
Arrow keys      : move board cursor
Space / Enter   : confirm cursor selection (when notation bar is empty)
Escape          : open / close pause menu  (clears notation bar if text is present)
F11             : toggle fullscreen
"""

from .game.app import GameApp


def main():
    app = GameApp()
    app.run()


if __name__ == "__main__":
    main()
