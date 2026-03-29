# Building & Distributing pygame-chess

This document explains how to produce a self-contained, distributable executable
that recipients can run without installing Python or any dependencies.

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| Python 3.12 or 3.13 | Runtime — 3.14 is not yet supported by PyInstaller |
| [uv](https://docs.astral.sh/uv/) | Dependency & virtualenv management |
| cairosvg (already a dependency) | Needed once to pre-bake the SVG assets |
| UPX *(optional)* | Compresses the final binaries by ~30 % |

> **You must build on the target platform.**  PyInstaller does not
> cross-compile: build on Windows to get a `.exe`, on macOS to get a `.app`,
> on Linux to get a Linux binary.

---

## Quick start

```sh
# 1. Install all dependencies (including the pyinstaller dev dependency)
uv sync --group dev

# 2. Convert SVG assets to PNG (only needs re-running when artwork changes)
uv run python build_assets.py

# 3. Build
uv run pyinstaller chess.spec
```

The finished bundle lands in `dist/chess/`.
Zip or tar that folder and distribute it — recipients just run the `chess`
binary inside it.

---

## Step-by-step

### 1 — Install dependencies

```sh
uv sync --group dev
```

This creates (or updates) the `.venv` with pygame, torch, torchvision,
cairosvg, and pyinstaller.

### 2 — Pre-bake SVG assets

```sh
uv run python build_assets.py
```

This renders every SVG in `assets/pieces/` and `assets/flags/` to PNG files
at several sizes.  The packaged executable then loads these PNGs directly and
does **not** need cairosvg (or any native Cairo / Pango / GLib system
libraries) at runtime.

Re-run this script whenever you change or add artwork.

### 3 — (Optional) Install UPX

UPX compresses native binaries and can trim the bundle by ~30 %.
It is optional — the build works without it.

| Platform | Install |
|----------|---------|
| Ubuntu / Debian | `sudo apt install upx` |
| macOS | `brew install upx` |
| Windows | Download from https://upx.github.io and add to `PATH` |

### 4 — Build

```sh
uv run pyinstaller chess.spec
```

PyInstaller writes:

```
dist/
└── chess/
    ├── chess          ← the executable (chess.exe on Windows)
    ├── assets/        ← bundled artwork (PNGs + original SVGs)
    ├── locale/        ← bundled translation files
    ├── models/        ← bundled model checkpoint (if present)
    └── _internal/     ← Python runtime, torch, pygame, …
```

### 5 — Test the bundle

Run the executable directly from the `dist/chess/` folder **before**
distributing it, to catch any missing imports or data files:

```sh
# Linux / macOS
./dist/chess/chess

# Windows
dist\chess\chess.exe
```

### 6 — Distribute

Zip the entire `dist/chess/` folder and share it.

```sh
# Linux / macOS
cd dist && zip -r chess-linux.zip chess/

# Windows (PowerShell)
Compress-Archive -Path dist\chess -DestinationPath chess-windows.zip
```

---

## Platform-specific notes

### Linux

- The binary should run on any distribution with glibc 2.17+ (roughly
  CentOS 7 / Ubuntu 16.04 era and newer).
- If you need broader compatibility, build inside a Docker container based
  on a slightly older image (e.g. `quay.io/pypa/manylinux2014_x86_64`).
- If the game window does not appear, ensure the target machine has a
  display server and the SDL2 libraries: `sudo apt install libsdl2-2.0-0`

### macOS

- Build on the oldest macOS version you want to support; the binary will
  not run on older systems than the one it was built on.
- Apple Silicon (M1/M2/M3): build natively for an `arm64` binary.
  For a universal binary that runs on both Intel and Apple Silicon, use
  [universal2 Python](https://www.python.org/downloads/) and add
  `target_arch="universal2"` to the `EXE()` call in `chess.spec`.
- You may need to codesign the app before distributing it, otherwise
  macOS Gatekeeper will block it:
  ```sh
  codesign --deep --force --sign - dist/chess/chess
  ```
  For proper App Store or notarisation distribution, a paid Apple Developer
  account is required.

### Windows

- Build on Windows 10 or 11.  The exe will run on Windows 10+ without
  any extra runtime because PyInstaller bundles the Visual C++ runtime.
- Windows Defender / SmartScreen will flag unsigned executables from
  unknown publishers.  Users will see a "Windows protected your PC" dialog;
  they must click "More info → Run anyway".  To remove this warning you
  need an Authenticode code-signing certificate.
- Add an icon by uncommenting the `icon=` line in `chess.spec` and
  providing an `.ico` file:
  ```python
  icon="assets/icon.ico",
  ```

---

## Including the trained model

If a `models/model.pt` checkpoint exists when `pyinstaller chess.spec` runs,
it is automatically bundled.  If it does not exist, the executable creates a
fresh model on the first completed ML game and saves it next to itself in the
`models/` subfolder of the distributed bundle.

To include the latest checkpoint:

```sh
# ensure models/model.pt exists, then rebuild
uv run pyinstaller chess.spec
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: torch` at launch | New torch internal module not in `hiddenimports` | Add the missing module to `hiddenimports` in `chess.spec` |
| Game starts but pieces/flags are missing | PNGs not pre-baked | Re-run `build_assets.py` |
| `FileNotFoundError: locale/en.json` | `locale/` not bundled | Check the `datas` section in `chess.spec`; path must be relative to `ROOT` |
| Bundle is larger than expected | `_STRIP_PREFIXES` in `chess.spec` not trimming enough | Add more paths to the strip list |
| Crash on launch with `SIGSEGV` / `access violation` | UPX corrupted a `.so`/`.dll` | Add the offending library to `upx_exclude` in `chess.spec` |
| Blank window / display error on Linux | SDL2 back-end issue | Try `SDL_VIDEODRIVER=x11 ./chess` or `SDL_VIDEODRIVER=wayland ./chess` |

---

## Automated builds with GitHub Actions

To produce platform binaries automatically on every release tag, create
`.github/workflows/build.yml`:

```yaml
name: Build executables

on:
  push:
    tags: ["v*"]

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-22.04, macos-13, windows-2022]

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --group dev

      - name: Pre-bake assets
        run: uv run python build_assets.py

      - name: Build with PyInstaller
        run: uv run pyinstaller chess.spec

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: chess-${{ matrix.os }}
          path: dist/chess/
```

Push a tag (`git tag v1.0.0 && git push --tags`) to trigger a build on all
three platforms simultaneously; the finished bundles appear as GitHub Actions
artefacts.