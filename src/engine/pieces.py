import io
import os

import pygame

try:
    import cairosvg

    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False

# If pre-baked PNGs exist alongside the SVGs (produced by build_assets.py),
# they are used at runtime so that cairosvg is not required in the packaged build.


FLAG_W = 36
FLAG_H = 24


# Sizes pre-baked by build_assets.py (must match PIECE_SIZES in that script).
_BAKED_SIZES = [40, 48, 56, 64, 72, 80, 96, 112, 128]


def _png_path(svg_path, size=None):
    """
    Return the pre-baked PNG path that corresponds to an SVG path.

    If `size` is given, look for the closest pre-baked size variant first
    (e.g. ``king_white_80.png``).  Fall back to the canonical name
    (``king_white.png``) when no sized variant exists.
    """
    base = os.path.splitext(svg_path)[0]
    if size is not None:
        # Pick the smallest baked size that is >= requested, or the largest available.
        best = min(_BAKED_SIZES, key=lambda s: (abs(s - size), s))
        sized = f"{base}_{best}.png"
        if os.path.isfile(sized):
            return sized
    return base + ".png"


def load_svg(path, size):
    """Load an SVG at `size`×`size`.  Uses a pre-baked PNG if available."""
    png_path = _png_path(path, size)
    if os.path.isfile(png_path):
        surf = pygame.image.load(png_path).convert_alpha()
        if surf.get_width() != size or surf.get_height() != size:
            surf = pygame.transform.smoothscale(surf, (size, size))
        return surf
    png = cairosvg.svg2png(url=path, output_width=size, output_height=size)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def load_flag(path):
    """Load a flag SVG.  Uses a pre-baked PNG if available."""
    png_path = _png_path(path)
    if os.path.isfile(png_path):
        surf = pygame.image.load(png_path).convert_alpha()
        if surf.get_width() != FLAG_W or surf.get_height() != FLAG_H:
            surf = pygame.transform.smoothscale(surf, (FLAG_W, FLAG_H))
        return surf
    png = cairosvg.svg2png(url=path, output_width=FLAG_W, output_height=FLAG_H)
    return pygame.image.load(io.BytesIO(png)).convert_alpha()


def _has_png_assets(asset_dir):
    """Return True if pre-baked PNGs are present for at least one piece."""
    pieces_dir = os.path.join(asset_dir, "pieces")
    if not os.path.isdir(pieces_dir):
        return False
    return any(f.endswith(".png") for f in os.listdir(pieces_dir))


def load_flags(asset_dir, locales):
    """Return {code: surface} for every locale that has a flag SVG or PNG."""
    flags = {}
    has_png = any(
        os.path.isfile(os.path.join(asset_dir, "flags", f"{code}.png"))
        for code, *_ in locales
    )
    if not HAS_CAIRO and not has_png:
        return flags
    flags_dir = os.path.join(asset_dir, "flags")
    if not os.path.isdir(flags_dir):
        return flags
    for code, *_ in locales:
        # Prefer pre-baked PNG; fall back to SVG (needs cairosvg).
        png_path = os.path.join(flags_dir, f"{code}.png")
        svg_path = os.path.join(flags_dir, f"{code}.svg")
        if os.path.isfile(png_path):
            try:
                flags[code] = load_flag(svg_path)  # load_flag resolves to PNG
            except Exception:
                pass
        elif HAS_CAIRO and os.path.isfile(svg_path):
            try:
                flags[code] = load_flag(svg_path)
            except Exception:
                pass
    return flags


def load_pieces(asset_dir, size):
    pieces = {}
    has_png = _has_png_assets(asset_dir)
    if not HAS_CAIRO and not has_png:
        return pieces
    if not os.path.isdir(asset_dir):
        return pieces
    for color in ("white", "black"):
        for name in ("king", "queen", "rook", "bishop", "knight", "pawn"):
            svg_path = os.path.join(asset_dir, "pieces", f"{name}_{color}.svg")
            png_path = _png_path(svg_path)
            key = f"{color}_{name}"
            # Use whichever source is available: pre-baked PNG preferred.
            if os.path.isfile(png_path) or (HAS_CAIRO and os.path.isfile(svg_path)):
                src = svg_path  # load_svg() will resolve to PNG internally
                try:
                    pieces[key] = load_svg(src, size)
                except Exception:
                    pass
    return pieces


def reload_pieces(asset_dir, size, existing):
    has_png = _has_png_assets(asset_dir)
    if not HAS_CAIRO and not has_png:
        return existing
    if not existing:
        return load_pieces(asset_dir, size)
    return load_pieces(asset_dir, size)
