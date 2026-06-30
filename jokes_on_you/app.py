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

        # Build one fullscreen window per screen. Keep them hidden during ARMING
        # so the user still sees the real desktop during the grace period.
        # Live screenshots are NOT captured here: they are captured at the END
        # of the grace period (see _capture_and_arm) so the user can switch to
        # the desired screen/workspace during grace and have THAT frozen as the
        # decoy. A static --decoy-image is set now since it doesn't change.
        for scr in screens:
            w = TrapWindow(scr, controller)
            controller.add_window(w)
            if shared_decoy is not None and not shared_decoy.isNull():
                w.set_decoy_scaled(shared_decoy)
            # Do NOT show yet; _capture_and_arm will show them.

        controller.state = ARMING

        # Grace countdown -> capture live screenshots -> arm
        ms = int(self.grace * 1000)
        QTimer.singleShot(max(0, ms), self._capture_and_arm)

        controller.unlocked.connect(app.quit)
        return app.exec()

    def _capture_and_arm(self) -> None:
        """Called at the end of the grace period.

        Captures a live screenshot of each screen and installs it as that
        window's decoy, then arms the trap (shows the fullscreen windows).
        Capturing here — rather than at launch — lets the user switch to the
        screen they want frozen during the grace period. The windows are still
        hidden at capture time, so they never appear in their own screenshot.
        """
        if self.controller is None:
            return
        if self.decoy_image is None:
            for w in self.controller.windows:
                try:
                    pix = capture_screen(w.screen)
                except Exception as e:
                    print(f"warning: screenshot failed for screen {w.screen.name()}: {e}",
                          file=sys.stderr)
                    pix = None
                if pix is not None and not pix.isNull():
                    w.set_decoy(pix)
        self.controller.arm()


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
