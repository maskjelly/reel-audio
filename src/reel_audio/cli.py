import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config
from .core import ReelAudioError, download_song
from .picker import pick_folder

# Public reels known to use a licensed song; setup picks one at random for its trial run.
TRIAL_REELS = [
    "https://www.instagram.com/reel/DRevbteiTt6/",
]


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _need_ffmpeg() -> bool:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    _err("ffmpeg not found on PATH (brew install ffmpeg)")
    return False


def cmd_download(argv) -> int:
    p = argparse.ArgumentParser(prog="reel-audio", description=(
        "Download the song used in an Instagram reel. Prints only the saved file's path; "
        "file and folder names are random and audio tags are stripped. Run `reel-audio setup` first."))
    p.add_argument("urls", nargs="+", metavar="URL")
    p.add_argument("--cookies", help="Netscape cookies.txt for Instagram")
    p.add_argument("--yt-cookies", help="Netscape cookies.txt for YouTube")
    p.add_argument("--cookies-from-browser", metavar="BROWSER", help="e.g. chrome, firefox, safari")
    a = p.parse_args(argv)
    if not _need_ffmpeg():
        return 1
    failed = 0
    for url in a.urls:
        try:
            print(download_song(url, config.song_dir, cookies=a.cookies, browser=a.cookies_from_browser,
                                yt_cookies=a.yt_cookies), flush=True)
        except ReelAudioError as e:
            failed += 1
            _err(str(e))
    return 1 if failed else 0


def _verify(path: str) -> float:
    """Return duration in seconds; raise if the file is unreadable or still carries tags."""
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", path],
                       capture_output=True, text=True)
    fmt = json.loads(r.stdout or "{}").get("format", {})
    duration = float(fmt.get("duration") or 0)
    if r.returncode or duration <= 0:
        raise ReelAudioError("downloaded file is not valid audio")
    if fmt.get("tags"):
        raise ReelAudioError("downloaded file still has metadata tags")
    return duration


def _trial(urls) -> bool:
    for url in random.sample(urls, len(urls)):
        tmp = tempfile.mkdtemp(prefix="tmp")
        try:
            path = download_song(url, tmp)
            _verify(path)
            size = Path(path).stat().st_size / 1e6
            print(f"      ✓ song found, downloaded and verified ({size:.1f} MB, no tags); trial file deleted")
            return True
        except ReelAudioError as e:
            print(f"      ✗ {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return False


def _ask_yes(prompt: str, default: bool = True) -> bool:
    try:
        ans = input(f"{prompt} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except EOFError:
        return default
    return default if not ans else ans.startswith("y")


def _add_alias() -> None:
    try:
        name = input("      Short alias for reel-audio (e.g. song), Enter to skip: ").strip()
    except EOFError:
        return
    if not name:
        return
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name):
        print("      ✗ invalid alias name, skipped")
        return
    rc = Path.home() / (".bashrc" if os.environ.get("SHELL", "").endswith("bash") else ".zshrc")
    line = f"alias {name}='reel-audio'"
    if rc.exists() and line in rc.read_text():
        print(f"      ✓ alias already in {rc}")
        return
    with rc.open("a") as f:
        f.write(f"\n{line}\n")
    print(f"      ✓ added to {rc} (open a new terminal, then: {name} <reel url>)")


def cmd_setup(argv) -> int:
    p = argparse.ArgumentParser(prog="reel-audio setup", description="Check requirements, do a trial "
                                "download, and choose where songs are saved.")
    p.add_argument("--terminal", action="store_true", help="use the in-terminal folder browser instead of a window")
    p.add_argument("--trial-url", action="append", help="reel(s) to use for the trial instead of the built-in list")
    p.add_argument("--skip-trial", action="store_true")
    a = p.parse_args(argv)

    print("[1/3] Checking requirements")
    if not _need_ffmpeg():
        return 1
    print("      ✓ ffmpeg")

    print("[2/3] Trial run with a random sample reel")
    if a.skip_trial:
        print("      skipped")
    elif not _trial(a.trial_url or TRIAL_REELS):
        _err("trial failed; check your connection, or retry with --trial-url <a public reel that uses a song>")
        return 1

    print("[3/3] Choose where downloaded songs should go")
    cfg = config.load()
    start = Path(cfg.get("parent_dir") or config.DEFAULT_PARENT)
    start = start if start.is_dir() else Path.home()
    try:
        input(f"      Press Enter to open the folder picker (starts at {start}) ")
    except EOFError:
        pass
    chosen = pick_folder(start, terminal=a.terminal)
    if chosen is None:
        if not _ask_yes(f"      No folder chosen. Use {config.DEFAULT_PARENT}?"):
            print("      Setup cancelled; nothing changed.")
            return 1
        chosen = config.DEFAULT_PARENT
    song_dir = config.new_song_dir(chosen)
    config.save({**cfg, "parent_dir": str(song_dir.parent), "song_dir": str(song_dir)})
    print(f"      ✓ songs will be saved in {song_dir}")
    _add_alias()
    print("\n✓ Setup complete.")
    print("Usage: reel-audio <instagram reel url>")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv and argv[0] == "setup":
            return cmd_setup(argv[1:])
        return cmd_download(argv)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
