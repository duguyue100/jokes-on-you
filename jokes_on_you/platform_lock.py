"""Platform detection helpers."""

from __future__ import annotations

import os


def _is_wayland() -> bool:
    return (
        os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )