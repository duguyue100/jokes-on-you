"""Cross-platform screenshot capture with a layered fallback chain.

Primary: Qt's ``QScreen.grabWindow`` (works on X11 / Windows / macOS).
Fallbacks (in order):
  * Wayland with ``grim``   -> per-screen geometry capture
  * X11 with ``scrot``      -> whole-display, then crop
  * macOS with ``screencapture``
  * Windows / cross-platform with ``mss``
  * Qt grabWindow (last resort, may be black on Wayland)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication

from .platform_lock import _is_wayland


def _pixmap_from_grim(geometry: QRect) -> Optional[QPixmap]:
    if not shutil.which("grim"):
        return None
    geo = f"{geometry.x()},{geometry.y()} {geometry.width()}x{geometry.height()}"
    try:
        proc = subprocess.run(
            ["grim", "-g", geo, "-t", "png", "-"],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    img = QImage.fromData(proc.stdout, "png")
    if img.isNull():
        return None
    return QPixmap.fromImage(img)


def _pixmap_from_scrot(geometry: QRect) -> Optional[QPixmap]:
    if not shutil.which("scrot"):
        return None
    try:
        proc = subprocess.run(
            ["scrot", "-o", "-"], check=True, capture_output=True, timeout=5
        )
        img = QImage.fromData(proc.stdout, "png")
    except (subprocess.SubprocessError, OSError):
        return None
    if img.isNull():
        return None
    full = QPixmap.fromImage(img)
    return full.copy(geometry)


def _pixmap_from_screencapture(geometry: QRect) -> Optional[QPixmap]:
    if sys.platform != "darwin" or not shutil.which("screencapture"):
        return None
    # On macOS 26 (Tahoe) `screencapture` silently ignores the stdout `-`
    # form and writes zero bytes, so we capture to a temp file instead --
    # same approach used for gnome-screenshot below.
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        subprocess.run(
            ["screencapture", "-x", "-R",
             f"{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}",
             tmp.name],
            check=True, capture_output=True, timeout=5,
        )
        img = QImage(tmp.name)
    except (subprocess.SubprocessError, OSError):
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    if img.isNull():
        return None
    return QPixmap.fromImage(img)


def _pixmap_from_gnome_screenshot(geometry: QRect) -> Optional[QPixmap]:
    """GNOME Wayland: use gnome-screenshot (whole-display), then crop.

    gnome-screenshot has no per-region CLI flag on Wayland, so we capture the
    full screen to a temp file and crop to the requested geometry.
    """
    if not shutil.which("gnome-screenshot"):
        return None
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        subprocess.run(
            ["gnome-screenshot", f"--file={tmp.name}"],
            check=True, capture_output=True, timeout=8,
        )
        img = QImage(tmp.name)
    except (subprocess.SubprocessError, OSError):
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    if img.isNull():
        return None
    full = QPixmap.fromImage(img)
    # Crop to the requested screen geometry (gnome-screenshot captures the
    # whole desktop including any taskbar across all monitors).
    return full.copy(geometry)


def _pixmap_from_mss(geometry: QRect) -> Optional[QPixmap]:
    try:
        import mss
    except ImportError:
        return None
    try:
        with mss.mss() as sct:
            shot = sct.grab({
                "left": geometry.x(), "top": geometry.y(),
                "width": geometry.width(), "height": geometry.height(),
            })
            import mss.tools
            import io
            buf = io.BytesIO()
            mss.tools.to_png(shot.rgb, shot.size, buf)
            img = QImage.fromData(buf.getvalue(), "png")
    except Exception:
        return None
    if img.isNull():
        return None
    return QPixmap.fromImage(img)


def _pixmap_is_blank(pix: QPixmap) -> bool:
    if pix.isNull():
        return True
    small = pix.scaled(8, 8).toImage()
    first = small.pixelColor(0, 0)
    for y in range(8):
        for x in range(8):
            c = small.pixelColor(x, y)
            if c.red() != first.red() or c.green() != first.green() or c.blue() != first.blue():
                return False
    return True


def capture_screen(qscreen) -> QPixmap:
    """Return a QPixmap of the given QScreen's current contents.

    Tries the most reliable backend first for the current platform.
    Raises RuntimeError if every backend fails.
    """
    geo = qscreen.geometry()
    candidates = []

    if _is_wayland():
        candidates += [_pixmap_from_grim, _pixmap_from_gnome_screenshot, _pixmap_from_mss]
    elif sys.platform == "darwin":
        candidates += [_pixmap_from_screencapture, _pixmap_from_mss]
    elif sys.platform == "win32":
        candidates += [_pixmap_from_mss]
    else:
        candidates += [_pixmap_from_scrot, _pixmap_from_mss]

    def _qt_grab():
        try:
            return qscreen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
        except Exception:
            return None

    candidates.append(lambda g: _qt_grab())

    last: Optional[QPixmap] = None
    for fn in candidates:
        try:
            pix = fn(geo)
        except Exception:
            pix = None
        if pix is not None and not pix.isNull() and not _pixmap_is_blank(pix):
            return pix
        if pix is not None and not pix.isNull():
            last = pix

    if last is not None and not last.isNull():
        # Every backend produced only a blank image. On macOS this almost
        # always means Screen Recording permission was not granted to the
        # launching app (Terminal/iTerm/IDE), so be explicit rather than
        # silently painting a black decoy.
        if sys.platform == "darwin":
            raise RuntimeError(
                "Screenshot captured an all-blank image. On macOS this usually "
                "means Screen Recording permission is missing: open System "
                "Settings > Privacy & Security > Screen Recording and enable "
                "the app that launched `joy` (e.g. Ghostty/Terminal/iTerm), "
                "then restart it. Alternatively `pip install mss Pillow` and "
                "ensure the same app has Screen Recording access."
            )
        return last
    raise RuntimeError(
        "All screenshot backends failed. On Wayland install `grim`; "
        "on X11 install `scrot`; on macOS grant Screen Recording permission "
        "to the launching app; or `pip install mss Pillow`."
    )
