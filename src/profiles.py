"""
profiles.py — User profile management.

Each profile has its own:
  - language preference
  - saved games  (saves/<profile_id>/save_<mode>.json)
  - ML AI model  (models/<profile_id>/model.pt)

State is persisted in profiles.json at the project root.
On first run, if a legacy prefs.dat exists it is migrated automatically.
"""

import json
import shutil
import uuid
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_PROFILES_FILE = _ROOT / "profiles.json"

# In-memory state
_profiles: list = []   # list of {"id": str, "name": str, "language": str}
_active_id: str = ""


# ── Persistence ────────────────────────────────────────────────────────────────


def _save() -> None:
    try:
        _PROFILES_FILE.write_text(
            json.dumps({"active": _active_id, "profiles": _profiles}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _load() -> None:
    global _profiles, _active_id
    if not _PROFILES_FILE.exists():
        _profiles = []
        _active_id = ""
        return
    try:
        data = json.loads(_PROFILES_FILE.read_text(encoding="utf-8"))
        _profiles = data.get("profiles", [])
        _active_id = data.get("active", "")
    except Exception:
        _profiles = []
        _active_id = ""


# ── Public query API ───────────────────────────────────────────────────────────


def profiles_exist() -> bool:
    """Return True if at least one profile exists."""
    return bool(_profiles)


def get_profiles() -> list:
    """Return a copy of the profiles list."""
    return list(_profiles)


def get_active_id() -> str:
    return _active_id


def get_active_profile() -> dict | None:
    for p in _profiles:
        if p["id"] == _active_id:
            return p
    return None


# ── Profile CRUD ───────────────────────────────────────────────────────────────


def create_profile(name: str, language: str) -> dict:
    """Create a new profile, save, and return it."""
    profile = {"id": str(uuid.uuid4()), "name": name, "language": language}
    _profiles.append(profile)
    _save()
    return profile


def rename_profile(profile_id: str, new_name: str) -> None:
    for p in _profiles:
        if p["id"] == profile_id:
            p["name"] = new_name
            _save()
            return


def delete_profile(profile_id: str) -> None:
    """Delete a profile and all its data. Cannot delete the active profile."""
    global _profiles
    if profile_id == _active_id:
        return
    # Remove profile-specific saves directory
    saves_dir = _ROOT / "saves" / profile_id
    if saves_dir.exists():
        shutil.rmtree(saves_dir, ignore_errors=True)
    # Remove profile-specific model
    model_dir = _ROOT / "models" / profile_id
    if model_dir.exists():
        shutil.rmtree(model_dir, ignore_errors=True)
    _profiles = [p for p in _profiles if p["id"] != profile_id]
    _save()


def set_active_profile(profile_id: str) -> None:
    global _active_id
    for p in _profiles:
        if p["id"] == profile_id:
            _active_id = profile_id
            _save()
            return


def set_active_language(language: str) -> None:
    """Update the language stored in the active profile."""
    for p in _profiles:
        if p["id"] == _active_id:
            p["language"] = language
            _save()
            return


# ── Path helpers ───────────────────────────────────────────────────────────────


def get_save_dir(profile_id: str | None = None) -> Path:
    pid = profile_id if profile_id is not None else _active_id
    return _ROOT / "saves" / pid


def get_model_path(profile_id: str | None = None) -> Path:
    pid = profile_id if profile_id is not None else _active_id
    return _ROOT / "models" / pid / "model.pt"


# ── Migration ──────────────────────────────────────────────────────────────────


def try_migrate_from_prefs() -> None:
    """
    Migrate from legacy prefs.dat to profiles if needed.
    Safe to call on every startup — only runs when prefs.dat exists and
    profiles.json does not.
    """
    global _profiles, _active_id

    prefs_file = _ROOT / "prefs.dat"
    if _PROFILES_FILE.exists() or not prefs_file.exists():
        return

    try:
        language = prefs_file.read_text(encoding="utf-8").strip() or "en"
    except OSError:
        language = "en"

    profile_id = "default"
    _profiles = [{"id": profile_id, "name": "Player 1", "language": language}]
    _active_id = profile_id

    # Move flat saves/ files into saves/default/
    old_saves = _ROOT / "saves"
    new_saves = _ROOT / "saves" / profile_id
    if old_saves.exists():
        new_saves.mkdir(parents=True, exist_ok=True)
        for f in list(old_saves.glob("save_*.json")):
            try:
                f.rename(new_saves / f.name)
            except OSError:
                pass

    # Move legacy model.pt into models/default/
    old_model = _ROOT / "models" / "model.pt"
    if old_model.exists():
        new_model_dir = _ROOT / "models" / profile_id
        new_model_dir.mkdir(parents=True, exist_ok=True)
        try:
            old_model.rename(new_model_dir / "model.pt")
        except OSError:
            pass

    _save()

    try:
        prefs_file.unlink(missing_ok=True)
    except OSError:
        pass


# ── Load on import ─────────────────────────────────────────────────────────────
_load()
