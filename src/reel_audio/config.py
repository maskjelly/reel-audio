import json
import os
import shutil
import subprocess
from pathlib import Path

from .core import random_name

CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "reel-audio" / "config.json"


def _downloads_dir() -> Path:
    """~/Downloads, or the localized XDG download folder on Linux."""
    if shutil.which("xdg-user-dir"):
        try:
            out = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True).stdout.strip()
            if out and Path(out) != Path.home():
                return Path(out)
        except OSError:
            pass
    return Path.home() / "Downloads"


DEFAULT_PARENT = _downloads_dir()


def load() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save(cfg: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def new_song_dir(parent: Path) -> Path:
    """Create an obfuscated folder inside `parent`."""
    while True:
        d = Path(parent).expanduser().resolve() / random_name(10)
        if not d.exists():
            d.mkdir(parents=True)
            return d


def song_dir() -> Path:
    """Configured song folder; created in ~/Downloads on first use if setup wasn't run."""
    cfg = load()
    d = cfg.get("song_dir")
    if d and Path(d).is_dir():
        return Path(d)
    parent = Path(cfg.get("parent_dir") or DEFAULT_PARENT)
    d = new_song_dir(parent if parent.is_dir() else DEFAULT_PARENT)
    save({**cfg, "parent_dir": str(d.parent), "song_dir": str(d)})
    return d
