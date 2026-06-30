# JOKES ON YOU!

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
uv venv --python 3.12
uv pip install -e .
```

This installs a console script named **`joy`**.

System screenshot helpers (pick the one for your platform):

| Platform | Tool   | Install                       |
|----------|--------|-------------------------------|
| GNOME Wayland | `gnome-screenshot` | `apt install gnome-screenshot` |
| wlroots Wayland | `grim` | `apt install grim`            |
| X11      | `scrot`| `apt install scrot`           |
| macOS    | built-in `screencapture` | — (needs Screen Recording permission for the launching app) |
| Windows  | `mss` (pip) | see above                |

## Asset

Drop the public-domain Uncle Sam poster at
`jokes_on_you/assets/uncle_sam.png` (see `jokes_on_you/assets/README.md`
for download links). If missing, a procedural fallback poster is drawn.

## Run

```bash
joy                              # prompts for password, 5s grace
joy --grace 10                   # 10 seconds to switch to the screen you want frozen
joy --pass hunter2               # no prompt
joy --decoy-image wallpaper.png  # static decoy instead of a live screenshot
```

The screenshot is captured **at the end** of the grace period, so you can
start `joy`, switch to the screen/workspace you want frozen, and that frame
becomes the decoy. When the trap fires, type your password and press
**Enter** to unlock.

## Flags

| Flag              | Default | Purpose                                     |
|-------------------|---------|---------------------------------------------|
| `--grace SECONDS` | `5`     | delay before the screenshot is captured and the trap arms |
| `--pass PASSWORD` | —       | unlock password (default: prompt interactively) |
| `--decoy-image PATH` | —   | use a static image as the decoy instead of a live screenshot |
| `--password-file PATH` | — | read password from the first line of a file |

## Wayland note

On Wayland, `mss` and Qt's `grabWindow` only see the XWayland root window
(black). For a *convincing* live-screenshot decoy you need a compositor-native
capturer:

* **GNOME Wayland**: `sudo apt install gnome-screenshot` (auto-detected)
* **wlroots (Sway/Hyprland/etc)**: `sudo apt install grim` (auto-detected)

The fallback chain tries `grim` → `gnome-screenshot` → `mss` → Qt. If none
produce a non-blank image, either pass `--decoy-image PATH` with a pre-taken
screenshot, or (on macOS) grant Screen Recording permission to the launching
app. Otherwise the app raises a clear error instead of silently painting a
black decoy.

## How it works

1. Prompts for a password (never persisted).
2. Waits `--grace` seconds so you can switch to the screen you want frozen.
3. Captures a screenshot of every screen (Qt `grabWindow` → `grim`/`scrot`/
   `screencapture`/`mss` fallback chain).
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
  Super, Cmd+Tab, Ctrl+Alt+Del) can still escape the overlay.
* macOS: Screen Recording permission must be granted to the app that
  launches `joy` (e.g. Ghostty/Terminal/iTerm) in System Settings →
  Privacy & Security → Screen Recording, otherwise the decoy is blank.
  On macOS the trap windows are regular borderless windows (not panels)
  and force-activate the app to the foreground, so `joy` briefly appears
  in the Dock during the trap.
* First Wayland screenshot may pop a portal consent dialog.

## License

MIT. See `LICENSE`.
