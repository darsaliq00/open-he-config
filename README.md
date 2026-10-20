# Analog Drive

Turns the Hall effect switches of an RK M75 HE into a virtual Xbox 360 controller.
Any RK board listed by RK's web driver (USB 1CA2:1601-161B) is detected; boards other than the
M75 HE are drawn from the key map the keyboard reports and have not been tested.
Press W a little and the car accelerates a little; press it fully for full throttle.

Also supports the AJAZZ AK680 V2 (detected automatically). That path reads the keyboard's
travel-test stream and has not been tested on real hardware yet.

The repository also contains **M75 Config** (`config_app/`, `run_config.py`), a separate
desktop app that configures the RK M75 HE itself: actuation, rapid trigger, deadzones,
remapping, lighting, advanced keys (DKS, multi-point, mod-tap, toggle, END, SOCD, rappy
snappy, macros), onboard configs 1-4, polling rate and calibration. Other RK boards from RK's list
work read-only until you allow writes for that untested model. Build it with
`build_config.bat` into `release/M75Config.exe`.

## Run

Double-click `start.bat` (first run creates `.venv` and installs `hidapi`, `vgamepad`, `PySide6`).
A native window opens and a tray icon appears.

Requirements: Windows, Python 3.12, the ViGEmBus driver (installed together with `vgamepad`).
Close the RK web driver tab first; it can hold the keyboard's config interface.

## Build exe

`build.bat` produces, in `release/`:

- `AnalogDrive-Portable.exe` – single file, run from anywhere. Profiles and calibration are
  stored next to the exe.
- `AnalogDrive-1.0.0-Setup.exe` – installer (needs admin). Installs to Program Files, adds
  Start menu / optional desktop and autostart shortcuts, installs the ViGEmBus driver if
  missing. Data goes to `%APPDATA%\Analog Drive`.

The exe is a native Qt (PySide6) desktop app with a tray icon: no browser, no web engine,
no local server. Closing the window keeps it running in the tray; quit from the tray menu.
`--tray` starts it hidden in the tray (used by the "start with Windows" option). Launching
it again shows the existing window. Only one copy can run at a time.

Needs Inno Setup 6 (`winget install JRSoftware.InnoSetup`) for the installer step.

## Use

- **Output on/off**: switch top right, tray menu, or **Ctrl+Alt+J** from inside a game
  (high beep = on, low beep = off). Output starts off.
- **Default profile "Racing"**: W = right trigger (throttle), S = left trigger (brake),
  A/D = left stick steering, Space = A, E/R = bumpers.
- Click any key to bind it to a stick direction, trigger or button, then tune:
  - start / end deadzone
  - response curve (drag 5 points; presets for fine start, quick start, S-curve)
  - smoothing
  - press point (for button bindings)
- **Block normal key presses**: while output is on, bound keys stop typing letters, so the
  game sees only the controller, not "W" plus throttle.
- **A + D together**: deeper press wins, last press wins, or cancel out.
- Calibration is automatic: rest position is learned on connect, full-press depth is learned
  the first time you bottom out each key. Saved in `calibration.json`.
  Use "Recalibrate rest" (hands off the keyboard) if readings look off.

## Files

- `app/device.py` – RK M75 HE HID protocol (diagnostic ADC reports, two pages of 63 keys)
- `app/device_ajazz.py` – AJAZZ AK680 V2 travel stream reader
- `app/layout.py` – key layouts for both keyboards, picks the connected one
- `app/protocol.py`, `app/kbconfig.py` – RK M75 HE configuration protocol (used by M75 Config)
- `config_app/` – M75 Config window and panels (`run_config.py`, `build_config.bat`)
- `ajazz_config/` – AJAZZ Config for the AK680 V2 (`run_ajazz_config.py`, `build_ajazz_config.bat`);
  so far device info and live Key Test, settings sections still to build and test on the keyboard
- `kbui/` – UI shared by both config apps: light theme, keycap keyboard view, lighting preview,
  small widgets
- `tests/` – offline tests: `python -m unittest discover tests`
- `app/engine.py` – calibration, deadzone, curve, smoothing, mixing, virtual pad output
- `app/blocker.py` – low-level keyboard hook for blocking bound keys and the hotkey
- `app/main.py` – entry point, single instance, data location
- `app/ui.py` – main window and tray icon
- `app/widgets.py` – custom-painted keyboard map, controller view, curve editor
- `profiles/` – saved profiles (JSON)
