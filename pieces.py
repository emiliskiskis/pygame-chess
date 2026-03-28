import io
import os

import pygame

try:
    import cairosvg

    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False


def load_svg(path, size):
    png = cairosvg.svg2png(url=path, output_width=size, output_height=size)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def load_pieces(asset_dir, size):
    pieces = {}
    if not HAS_CAIRO or not os.path.isdir(asset_dir):
        return pieces
    for color in ("white", "black"):
        for name in ("king", "queen", "rook", "bishop", "knight", "pawn"):
            path = os.path.join(asset_dir, f"{name}_{color}.svg")
            key = f"{color}_{name}"
            if os.path.isfile(path):
                try:
                    pieces[key] = load_svg(path, size)
                except Exception:
                    pass
    return pieces


def reload_pieces(asset_dir, size, existing):
    if not HAS_CAIRO or not existing:
        return existing
    return load_pieces(asset_dir, size)
