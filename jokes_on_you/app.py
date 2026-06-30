"""QApplication wiring: captures screenshots, builds one TrapWindow per
screen, runs the grace countdown, then arms the trap.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from .screenshot import capture_screen
from .trap_window import TrapController, TrapWindow, ARMING, ARMED


class TrapApp:
    def __init__(self, password: str, grace: float, do_lock: bool, dry_run: bool,
                 decoy_image: Optional[str] = None) -> None:
        self.password = password
        self.grace = grace
        self.do_lock = do_lock
        self.dry_run = dry_run
        self.decoy_image = decoy_image
        self.qt_app: Optional[QApplication] = None
        self.controller: Optional[TrapController] = None

    def run(self) -> int:
        app = QApplication.instance() or QApplication(sys.argv)
        self.qt_app = app
        app.setQuitOnLastWindowClosed(True)

        screens = app.screens()
        if not screens:
            print("error: no screens detected", file=sys.stderr)
            return 2

        controller = TrapController(self.password, self.do_lock, self.dry_run)
        self.controller = controller
        controller.load_assets()

        # Decide decoy source: explicit image file wins; else live screenshot.
        shared_decoy: Optional[QPixmap] = None
        if self.decoy_image:
            p = Path(self.decoy_image)
            if not p.exists():
                print(f"error: --decoy-image not found: {p}", file=sys.stderr)
                return 2
            shared_decoy = QPixmap(str(p))
            if shared_decoy.isNull():
                print(f"error: could not load decoy image: {p}", file=sys.stderr)
                return 2

        decoys: list[Optional[QPixmap]] = []
        if shared_decoy is not None:
            decoys = [shared_decoy for _ in screens]
        else:
            # Live screenshot per screen.
            for scr in screens:
                try:
                    pix = capture_screen(scr)
                except Exception as e:
                    print(f"warning: screenshot failed for screen {scr.name()}: {e}",
                          file=sys.stderr)
                    pix = None
                decoys.append(pix)

        # Build one fullscreen window per screen. Keep them hidden during ARMING
        # so the user still sees the real desktop during the grace period.
        for scr, decoy in zip(screens, decoys):
            w = TrapWindow(scr, controller)
            controller.add_window(w)
            if decoy is not None and not decoy.isNull():
                if shared_decoy is not None:
                    w.set_decoy_scaled(decoy)
                else:
                    w.set_decoy(decoy)
            # Do NOT show yet; arm() will show them.

        controller.state = ARMING

        # Grace countdown -> arm
        ms = int(self.grace * 1000)
        QTimer.singleShot(max(0, ms), controller.arm)

        controller.unlocked.connect(app.quit)
        return app.exec()


def prompt_password() -> str:
    pw = getpass.getpass("Set unlock password: ")
    pw2 = getpass.getpass("Confirm password: ")
    if pw != pw2:
        print("error: passwords do not match", file=sys.stderr)
        sys.exit(2)
    if not pw:
        print("error: password cannot be empty", file=sys.stderr)
        sys.exit(2)
    return pw
