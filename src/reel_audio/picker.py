"""Folder pickers: native dialog (macOS Finder, Linux zenity/kdialog, tkinter), with a keyboard-driven terminal browser fallback."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROMPT = "Choose where downloaded songs should go"


def _applescript_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def pick_native(start: Path) -> Path | None:
    """Returns the chosen folder, None if cancelled. Raises RuntimeError if no GUI is available."""
    if sys.platform == "darwin":
        script = (f"POSIX path of (choose folder with prompt {_applescript_str(PROMPT)} "
                  f"default location (POSIX file {_applescript_str(str(start))}))")
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
        if "-128" in r.stderr:  # user cancelled
            return None
        raise RuntimeError(r.stderr.strip() or "Finder dialog unavailable")
    # Linux desktops: GTK (zenity) or KDE (kdialog) dialogs; exit code 1 means cancelled.
    for cmd in (["zenity", "--file-selection", "--directory", f"--title={PROMPT}", f"--filename={start}/"],
                ["kdialog", "--title", PROMPT, "--getexistingdirectory", str(start)]):
        if shutil.which(cmd[0]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return Path(r.stdout.strip())
            if r.returncode == 1:
                return None
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as e:
        raise RuntimeError("tkinter not available") from e
    try:
        root = tkinter.Tk()
    except tkinter.TclError as e:
        raise RuntimeError("no display") from e
    root.withdraw()
    root.attributes("-topmost", True)
    chosen = filedialog.askdirectory(title=PROMPT, initialdir=str(start), mustexist=True)
    root.destroy()
    return Path(chosen) if chosen else None


HELP = "↑/↓ move  →/Enter open  ←/Backspace up  s select this folder  n new folder  . hidden  ~ home  q cancel"


def pick_terminal(start: Path) -> Path | None:
    import curses

    def run(scr):
        curses.curs_set(0)
        cwd, pos, top, show_hidden, msg = start.resolve(), 0, 0, False, ""
        while True:
            try:
                dirs = sorted((p for p in cwd.iterdir() if p.is_dir() and (show_hidden or not p.name.startswith("."))),
                              key=lambda p: p.name.lower())
            except OSError:
                dirs, msg = [], "can't read this folder"
            items = [".. (up)"] + [p.name + "/" for p in dirs]
            pos = max(0, min(pos, len(items) - 1))
            h, w = scr.getmaxyx()
            rows = max(1, h - 5)
            top = min(max(top, pos - rows + 1), pos)
            scr.erase()
            scr.addnstr(0, 0, PROMPT, w - 1, curses.A_BOLD)
            scr.addnstr(1, 0, str(cwd), w - 1, curses.A_UNDERLINE)
            for i, name in enumerate(items[top:top + rows]):
                attr = curses.A_REVERSE if top + i == pos else curses.A_NORMAL
                scr.addnstr(2 + i, 2, name, w - 3, attr)
            scr.addnstr(h - 2, 0, msg, w - 1, curses.A_DIM)
            scr.addnstr(h - 1, 0, HELP, w - 1, curses.A_DIM)
            scr.refresh()
            msg = ""
            k = scr.getch()
            if k in (curses.KEY_UP, ord("k")):
                pos -= 1
            elif k in (curses.KEY_DOWN, ord("j")):
                pos += 1
            elif k == curses.KEY_PPAGE:
                pos -= rows
            elif k == curses.KEY_NPAGE:
                pos += rows
            elif k in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, 8, ord("h")) or (
                    k in (curses.KEY_RIGHT, 10, 13, ord("l")) and pos == 0):
                cwd, pos, top = cwd.parent, 0, 0
            elif k in (curses.KEY_RIGHT, 10, 13, ord("l")):
                cwd, pos, top = dirs[pos - 1], 0, 0
            elif k == ord("s"):
                return cwd
            elif k == ord("."):
                show_hidden = not show_hidden
            elif k == ord("~"):
                cwd, pos, top = Path.home(), 0, 0
            elif k == ord("n"):
                curses.echo(); curses.curs_set(1)
                scr.addnstr(h - 2, 0, "New folder name: ".ljust(w - 1), w - 1)
                name = scr.getstr(h - 2, 17, 100).decode(errors="ignore").strip()
                curses.noecho(); curses.curs_set(0)
                if name and "/" not in name:
                    try:
                        (cwd / name).mkdir()
                        cwd, pos, top = cwd / name, 0, 0
                    except OSError as e:
                        msg = f"can't create folder: {e.strerror}"
            elif k == ord("q"):
                return None

    return curses.wrapper(run)


def pick_folder(start: Path, terminal: bool = False) -> Path | None:
    if not terminal and (sys.platform == "darwin" or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        try:
            return pick_native(start)
        except RuntimeError:
            pass
    return pick_terminal(start)
