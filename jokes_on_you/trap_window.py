"""The trap: a fullscreen, always-on-top QWidget per screen acting as a
state machine. No global input hooks are used; the window itself receives
all input while it is focused / fullscreen, which keeps it Wayland-friendly.

States:
    ARMING    -> grace countdown, small overlay, not yet trapping
    ARMED     -> fullscreen decoy (screenshot) on every screen; any input fires
    REVEALED  -> Uncle Sam + "JOKES ON YOU!"; keystrokes buffer against password
    UNLOCKED  -> close everything, quit app
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRect
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QFontMetrics, QKeyEvent,
    QMouseEvent, QWheelEvent, QPainterPath,
)
from PySide6.QtWidgets import QWidget

from .platform_lock import lock_session

ASSETS = Path(__file__).resolve().parent / "assets"
UNCLE_SAM_PATH = ASSETS / "uncle_sam.png"

ARMING, ARMED, REVEALED, UNLOCKED = "arming", "armed", "revealed", "unlocked"


def _load_uncle_sam() -> Optional[QPixmap]:
    # Must be called AFTER QApplication is constructed.
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.instance() is None:
        return None
    if UNCLE_SAM_PATH.exists():
        pix = QPixmap(str(UNCLE_SAM_PATH))
        if not pix.isNull():
            return pix
    return None


class TrapWindow(QWidget):
    """One fullscreen window covering a single screen."""

    def __init__(self, screen, controller: "TrapController") -> None:
        super().__init__()
        # On macOS, Qt.Tool maps to an NSPanel which only floats above the
        # *owning* app's key window and cannot bring a background app to the
        # front. Since the trap arms from a timer while another app (Terminal/
        # IDE) is focused, a panel never rises above it. Use a regular
        # frameless borderless NSWindow instead so requestActivate() can force
        # [NSApp activateIgnoringOtherApps:YES] and genuinely steal focus.
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if sys.platform != "darwin":
            flags |= Qt.Tool  # keep panels off the taskbar on Linux/Windows
        self.setWindowFlags(flags)
        self.controller = controller
        self.screen = screen
        self.decoy: Optional[QPixmap] = None
        self.uncle_sam: Optional[QPixmap] = controller.uncle_sam

        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMouseTracking(True)
        self.setWindowFlag(Qt.WindowTransparentForInput, False)
        self.setCursor(Qt.BlankCursor)
        self._fullscreen = False

    def show_on_screen(self) -> None:
        self.setScreen(self.screen)
        geo = self.screen.geometry()
        self.setGeometry(geo)
        if sys.platform == "darwin":
            # Avoid native fullscreen: it animates into a separate Space,
            # delays the cover, and leaves the menu bar reachable. A plain
            # borderless window at the screen geometry covers instantly and
            # stays on the current Space.
            self.showNormal()
            self.setGeometry(geo)
        else:
            self.showFullScreen()
        self.raise_()
        self.activateWindow()
        # On macOS Tahoe, activateWindow() alone isn't enough to bring a
        # background app above the focused Terminal; force a real activation
        # request on the underlying QWindow so NSApp ignores other apps.
        if sys.platform == "darwin":
            wh = self.windowHandle()
            if wh is not None:
                wh.requestActivate()
        self._fullscreen = True

    def set_decoy(self, pix: QPixmap) -> None:
        self.decoy = pix
        self.update()

    def set_decoy_scaled(self, pix: QPixmap) -> None:
        """Scale a single shared decoy image to this window's geometry."""
        if pix.isNull():
            self.decoy = pix
        else:
            self.decoy = pix.scaled(
                self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
        self.update()

    def set_state(self, state: str) -> None:
        self.controller.state = state
        if state == REVEALED:
            self.unsetCursor()
        self.update()

    # ---- input: any event in ARMED fires the trap ----
    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        self.controller.on_any_input("mouse-move")
        if self.controller.state == REVEALED:
            self.controller.feed_key("")

    def mousePressEvent(self, e: QMouseEvent) -> None:
        self.controller.on_any_input("mouse-press")

    def wheelEvent(self, e: QWheelEvent) -> None:
        self.controller.on_any_input("wheel")

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if self.controller.state == REVEALED:
            self.controller.feed_qkeyevent(e)
        else:
            self.controller.on_any_input("key")

    # ---- painting ----
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        state = self.controller.state

        if state == ARMED and self.decoy is not None and not self.decoy.isNull():
            p.drawPixmap(self.rect(), self.decoy)
            return

        if state == REVEALED:
            self._paint_revealed(p)
            return

        # ARMING / fallback: black
        p.fillRect(self.rect(), QColor(0, 0, 0))

    def _paint_revealed(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        # background
        p.fillRect(self.rect(), QColor(15, 23, 42))

        if self.uncle_sam is not None and not self.uncle_sam.isNull():
            # scale image to fit while preserving aspect, centered, leaving room for caption
            caption_h = int(h * 0.18)
            avail = QRect(0, 0, w, h - caption_h)
            pix = self.uncle_sam
            scaled = pix.scaled(
                avail.width(), avail.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            x = (w - scaled.width()) // 2
            y = max(0, (avail.height() - scaled.height()) // 2)
            p.drawPixmap(x, y, scaled)
        else:
            self._paint_procedural_poster(p, w, h)

        # caption "JOKES ON YOU!"
        self._paint_caption(p, w, h)

    def _paint_procedural_poster(self, p: QPainter, w: int, h: int) -> None:
        # Fallback poster: Uncle Sam style "I WANT YOU" text block in red/white/blue.
        bg = QRect(0, 0, w, h)
        p.fillRect(bg, QColor(0xb0, 0x10, 0x10))
        band = h // 3
        p.fillRect(QRect(0, band, w, band), QColor(0xf5, 0xf5, 0xf5))
        p.fillRect(QRect(0, 2 * band, w, band), QColor(0x1a, 0x2a, 0x6a))

        p.setPen(QColor(0xff, 0xd7, 0x00))
        f = QFont("Sans", pointSize=max(12, h // 12))
        f.setBold(True)
        p.setFont(f)
        p.drawText(bg, Qt.AlignCenter, "I WANT\nYOU")

    def _paint_caption(self, p: QPainter, w: int, h: int) -> None:
        text = "JOKES ON YOU!"
        f = QFont("Sans")
        f.setBold(True)
        target = int(h * 0.14)
        size = target
        while size > 8:
            f.setPixelSize(size)
            fm = QFontMetrics(f)
            if fm.horizontalAdvance(text) <= w * 0.92:
                break
            size -= 2
        p.setFont(f)
        # shadow
        p.setPen(QColor(0, 0, 0, 200))
        p.drawText(
            QRect(0, h - int(h * 0.18) + 3, w, int(h * 0.18)),
            Qt.AlignCenter, text,
        )
        p.setPen(QColor(0xff, 0xd7, 0x00))
        p.drawText(
            QRect(0, h - int(h * 0.18), w, int(h * 0.18)),
            Qt.AlignCenter, text,
        )


class TrapController(QObject):
    """Owns shared state across all TrapWindow instances."""

    unlocked = Signal()

    def __init__(self, password: str, do_lock: bool, dry_run: bool) -> None:
        super().__init__()
        self.password = password
        self.do_lock = do_lock
        self.dry_run = dry_run
        self.state: str = ARMING
        self.buffer: str = ""
        self.uncle_sam: Optional[QPixmap] = None  # loaded in load_assets()
        self.windows: list[TrapWindow] = []
        self._reveal_done = False

    def load_assets(self) -> None:
        """Call after QApplication is constructed."""
        self.uncle_sam = _load_uncle_sam()

    def add_window(self, w: TrapWindow) -> None:
        self.windows.append(w)

    # ---- arming ----
    def arm(self) -> None:
        if self.state != ARMING:
            return
        self.state = ARMED
        for w in self.windows:
            w.set_state(ARMED)
            w.show_on_screen()
            w.setCursor(Qt.BlankCursor)

    # ---- input handling ----
    def on_any_input(self, _kind: str) -> None:
        if self.state == ARMED:
            self._reveal()

    def _reveal(self) -> None:
        self.state = REVEALED
        for w in self.windows:
            w.set_state(REVEALED)
            w.show_on_screen()
            w.setFocus()
        if self.do_lock and not self._reveal_done:
            self._reveal_done = True
            try:
                lock_session(self.dry_run)
            except Exception:
                pass

    # ---- password entry ----
    def feed_qkeyevent(self, e: QKeyEvent) -> None:
        key = e.key()
        text = e.text()
        if key == Qt.Key_Backspace:
            self.buffer = self.buffer[:-1]
            return
        if key == Qt.Key_Return or key == Qt.Key_Enter:
            self._check()
            return
        if key == Qt.Key_Escape:
            # don't allow escape to unlock; treat as input noise
            self.buffer = ""
            return
        if text and not e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier):
            self.buffer += text
            # auto-check on exact match (so Enter isn't required)
            if self.buffer == self.password:
                self._unlock()
                return
            # prefix-aware reset: if what's typed so far can't possibly be a
            # prefix of the password, drop the buffer so a typo doesn't lock
            # you out permanently.
            plen = len(self.password)
            if len(self.buffer) > plen or not self.password.startswith(self.buffer):
                # keep just the last char in case it's the start of a retry
                self.buffer = text if (plen > 0 and self.password[0] == text) else ""

    def feed_key(self, _s: str) -> None:
        # placeholder for mouse-driven flushing if needed
        pass

    def _check(self) -> None:
        if self.buffer == self.password:
            self._unlock()
        else:
            self.buffer = ""

    def _unlock(self) -> None:
        self.state = UNLOCKED
        self.unlocked.emit()
        for w in self.windows:
            w.close()
