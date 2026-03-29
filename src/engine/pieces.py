import io
import os

import pygame

try:
    import cairosvg

    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False


FLAG_W = 36
FLAG_H = 24


def load_svg(path, size):
    png = cairosvg.svg2png(url=path, output_width=size, output_height=size)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def load_flag(path):
    png = cairosvg.svg2png(url=path, output_width=FLAG_W, output_height=FLAG_H)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def load_flags(asset_dir, locales):
    """Return {code: surface} for every locale that has a flag SVG."""
    flags = {}
    if not HAS_CAIRO:
        return flags
    flags_dir = os.path.join(asset_dir, "flags")
    if not os.path.isdir(flags_dir):
        return flags
    for code, *_ in locales:
        path = os.path.join(flags_dir, f"{code}.svg")
        if os.path.isfile(path):
            try:
                flags[code] = load_flag(path)
            except Exception:
                pass
    return flags


def load_pieces(asset_dir, size):
    pieces = {}
    if not HAS_CAIRO or not os.path.isdir(asset_dir):
        return pieces
    for color in ("white", "black"):
        for name in ("king", "queen", "rook", "bishop", "knight", "pawn"):
            path = os.path.join(asset_dir, "pieces", f"{name}_{color}.svg")
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
