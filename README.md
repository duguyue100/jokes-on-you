# jokes-on-you

Fighting back friendly fires.

A decoy-screen prank trap. When activated, it shows a screenshot of your
desktop that looks exactly like an unlocked session. The instant anyone
touches the mouse or keyboard, the screen flips to Uncle Sam pointing at
them with **"JOKES ON YOU!"**. The only way out is to type your secret
password (then Enter).

Built for the office prank where someone sneaks over to an unattended
laptop and posts "I'm buying everyone beer!" on Slack.

## Install

Requires Python 3.9+. Recommended: use `uv` or `pip` in a venv.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .
# optional fallback screenshot backends:
uv pip install --python .venv/bin/python mss Pillow
```

This installs a console script named **`joy`**.

System screenshot helpers (pick the one for your platform):

| Platform | Tool   | Install                       |
|----------|--------|-------------------------------|
| Wayland  | `grim` | `apt install grim`            |
| X11      | `scrot`| `apt install scrot`           |
| macOS    | built-in `screencapture` | —                |
| Windows  | `mss` (pip) | see above                |

## Asset

Drop the public-domain Uncle Sam poster at
`jokes_on_you/assets/uncle_sam.png` (see `jokes_on_you/assets/README.md`
for download links). If missing, a procedural fallback poster is drawn.

## Run

```bash
joy                              # prompts for password, 5s grace
joy --grace 10                   # 10 seconds to walk away
joy --lock                       # also truly lock the OS session
joy --dry-run --lock             # preview the lock command
JOKES_PASSWORD=hunter2 joy       # no prompt
```

When the trap fires, type your password and press **Enter** to unlock.

## Flags

| Flag              | Default | Purpose                                     |
|-------------------|---------|---------------------------------------------|
| `--grace SECONDS` | `5`     | delay before the trap arms                   |
| `--lock`          | off     | also invoke the OS session lock on reveal    |
| `--decoy-image PATH` | —   | use a static image as the decoy instead of a live screenshot |
| `--password-file` | —       | read password from first line of a file      |
| `--password-env`  | `JOKES_PASSWORD` | env var name for the password        |
| `--dry-run`       | off     | don't actually lock; print what would happen |

## Wayland note

On a real Wayland session, `mss` and Qt's `grabWindow` only see the XWayland
root window (black). For a *convincing* live-screenshot decoy you must install
a Wayland-native capturer:

```bash
sudo apt install grim     # or: dnf install grim, pacman -S grim
```

Without `grim`, either:
* pass `--decoy-image PATH` with a pre-taken screenshot or wallpaper, or
* accept a black decoy (the trap still fires; it's just less convincing).

## How it works

1. Prompts for a password (never persisted).
2. Captures a screenshot of every screen (Qt `grabWindow` → `grim`/`scrot`/
   `screencapture`/`mss` fallback chain).
3. Waits `--grace` seconds so you can walk away.
4. Opens one borderless, always-on-top, fullscreen window per screen
   showing the screenshot — the decoy.
5. Any mouse-move / click / scroll / keypress trips the reveal: Uncle Sam
   + "JOKES ON YOU!".
6. Keystrokes are buffered and compared to your password; Enter checks.
   Match → windows close, app exits.

No global keylogger hooks are used — all input is caught locally by the
fullscreen window. This keeps it Wayland-friendly and ethically clean.

## Limitations

* OS shortcuts the compositor doesn't let clients intercept (Alt+Tab,
  Super, Cmd+Tab, Ctrl+Alt+Del) can still escape the overlay. Use
  `--lock` to genuinely lock the session on reveal.
* macOS may require Accessibility and/or Screen Recording permission.
* First Wayland screenshot may pop a portal consent dialog.

## License

MIT. See `LICENSE`.
