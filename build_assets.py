#!/usr/bin/env python3
"""
build_assets.py — pre-bake all SVGs in assets/ into PNGs.

Run this once before packaging with PyInstaller:

    python build_assets.py

The resulting .png files sit next to the .svg files and are preferred
by src/engine/pieces.py at runtime, so the packaged executable does not
need cairosvg (or any native Cairo/Pango system libraries) at all.

Piece PNGs are rendered at several sizes so that resize events can use
the nearest pre-baked size instead of re-rasterising on the fly.
"""

import os
import sys

# ── Resolve project root so the script can be run from anywhere ───────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(ROOT, "assets")
PIECES_DIR = os.path.join(ASSETS_DIR, "pieces")
FLAGS_DIR = os.path.join(ASSETS_DIR, "flags")

# Piece sizes to pre-bake (pixels).  Layout.tile normally falls between 40–120.
PIECE_SIZES = [40, 48, 56, 64, 72, 80, 96, 112, 128]

# Flag dimensions (fixed by FLAG_W / FLAG_H in pieces.py)
FLAG_W = 36
FLAG_H = 24

# ── Dependency check ──────────────────────────────────────────────────────────

try:
    import cairosvg
except ImportError:
    sys.exit(
        "ERROR: cairosvg is not installed.\n"
        "Install it with:  pip install cairosvg\n"
        "or, if you use uv:  uv run python build_assets.py"
    )

# ── Helpers ───────────────────────────────────────────────────────────────────


def svg_to_png(svg_path: str, out_path: str, width: int, height: int) -> None:
    cairosvg.svg2png(
        url=svg_path,
        write_to=out_path,
        output_width=width,
        output_height=height,
    )


def bake_pieces() -> None:
    """Rasterise every piece SVG at every size in PIECE_SIZES."""
    if not os.path.isdir(PIECES_DIR):
        print(f"  [skip] pieces directory not found: {PIECES_DIR}")
        return

    svgs = sorted(f for f in os.listdir(PIECES_DIR) if f.endswith(".svg"))
    if not svgs:
        print("  [skip] no SVG files found in pieces/")
        return

    total = len(svgs) * len(PIECE_SIZES)
    done = 0

    for svg_name in svgs:
        svg_path = os.path.join(PIECES_DIR, svg_name)
        base = os.path.splitext(svg_name)[0]

        for size in PIECE_SIZES:
            out_name = f"{base}_{size}.png"
            out_path = os.path.join(PIECES_DIR, out_name)
            try:
                svg_to_png(svg_path, out_path, size, size)
                done += 1
                print(f"  [{done}/{total}] {out_name}")
            except Exception as exc:
                print(f"  [ERROR] {svg_name} @ {size}px — {exc}")

    # Also write a canonical (default 80 px) PNG with the plain name so that
    # src/engine/pieces.py can find it via _png_path(svg_path) directly.
    for svg_name in svgs:
        svg_path = os.path.join(PIECES_DIR, svg_name)
        base = os.path.splitext(svg_name)[0]
        canonical = os.path.join(PIECES_DIR, f"{base}.png")
        if not os.path.isfile(canonical):
            try:
                svg_to_png(svg_path, canonical, 80, 80)
                print(f"  [canonical] {base}.png")
            except Exception as exc:
                print(f"  [ERROR] canonical {base}.png — {exc}")


def bake_flags() -> None:
    """Rasterise every flag SVG at FLAG_W × FLAG_H."""
    if not os.path.isdir(FLAGS_DIR):
        print(f"  [skip] flags directory not found: {FLAGS_DIR}")
        return

    svgs = sorted(f for f in os.listdir(FLAGS_DIR) if f.endswith(".svg"))
    if not svgs:
        print("  [skip] no SVG files found in flags/")
        return

    for i, svg_name in enumerate(svgs, 1):
        svg_path = os.path.join(FLAGS_DIR, svg_name)
        base = os.path.splitext(svg_name)[0]
        out_path = os.path.join(FLAGS_DIR, f"{base}.png")
        try:
            svg_to_png(svg_path, out_path, FLAG_W, FLAG_H)
            print(f"  [{i}/{len(svgs)}] {base}.png  ({FLAG_W}×{FLAG_H})")
        except Exception as exc:
            print(f"  [ERROR] {svg_name} — {exc}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Baking piece SVGs ===")
    bake_pieces()
    print()
    print("=== Baking flag SVGs ===")
    bake_flags()
    print()
    print("Done.  You can now run PyInstaller:")
    print("  pyinstaller chess.spec")
