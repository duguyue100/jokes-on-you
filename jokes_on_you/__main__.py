"""Entry point: parse CLI flags, prompt for password, launch the trap."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .app import TrapApp, prompt_password


def _read_password_file(path: str) -> str:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read password file: {e}", file=sys.stderr)
        sys.exit(2)
    # first non-empty line
    for line in text.splitlines():
        s = line.rstrip("\r")
        if s:
            return s
    print("error: password file is empty", file=sys.stderr)
    sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="joy",
        description=(
            "Decoy-screen prank trap. Shows a screenshot of your desktop; "
            "on any input, reveals Uncle Sam + 'JOKES ON YOU!'. "
            "Unlock by typing your secret password and pressing Enter."
        ),
    )
    p.add_argument(
        "--grace", type=float, default=5.0, metavar="SECONDS",
        help="seconds before the trap arms (default: 5). Use this to walk away.",
    )
    p.add_argument(
        "--lock", action="store_true",
        help="also lock the OS session when the trap fires (fight-back mode).",
    )
    p.add_argument(
        "--password-file", metavar="PATH",
        help="read unlock password from the first line of this file instead of prompting.",
    )
    p.add_argument(
        "--password-env", metavar="VAR", default="JOKES_PASSWORD",
        help="env var to consult for the password (default: JOKES_PASSWORD). "
             "Ignored if --password-file is set.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="do not actually invoke OS lock; print what would happen.",
    )
    p.add_argument(
        "--decoy-image", metavar="PATH",
        help="use this image file as the decoy background instead of a live "
             "screenshot. Useful on Wayland without `grim`, or for a staged "
             "wallpaper. The image is scaled to fill each screen.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.password_file:
        password = _read_password_file(args.password_file)
    else:
        env_pw = os.environ.get(args.password_env)
        if env_pw:
            password = env_pw
        else:
            password = prompt_password()

    if args.grace < 0:
        print("error: --grace must be >= 0", file=sys.stderr)
        return 2

    app = TrapApp(
        password=password,
        grace=args.grace,
        do_lock=args.lock,
        dry_run=args.dry_run,
        decoy_image=args.decoy_image,
    )
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
