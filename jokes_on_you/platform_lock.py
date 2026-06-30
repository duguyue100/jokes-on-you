"""OS session-lock invocation and platform detection helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def _is_wayland() -> bool:
    return (
        os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )


def lock_session(dry_run: bool = False) -> bool:
    """Best-effort lock of the OS session. Returns True if a command ran."""
    if dry_run:
        print("[dry-run] would lock the OS session")
        return True

    candidates: list[list[str]] = []
    if _is_wayland():
        candidates += [
            ["loginctl", "lock-session"],
        ]
    if sys.platform == "darwin":
        candidates += [
            ["/System/Library/CoreServices/Menu Extras/User.menu/"
             "Contents/Resources/CGSession", "-suspend"],
            ["pmset", "displaysleepnow"],
        ]
    elif sys.platform == "win32":
        candidates += [["rundll32.exe", "user32.dll,LockWorkStation"]]
    else:
        candidates += [
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["gnome-screensaver-command", "--lock"],
        ]

    for cmd in candidates:
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            continue
    return False
