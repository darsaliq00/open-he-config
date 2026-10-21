# Open HE Config

Desktop app that configures RK keyboards on Windows, replacing RK's web driver and Windows
software.

## RK HE boards (SparkLink, USB 1CA2:1601-161B)

Built and tested on the RK M75 HE. Every board in RK's web driver list is detected. Boards other
than the M75 HE are drawn from the key map the keyboard reports, and stay read-only until you
allow writes for that model.

- Performance Setting, laid out like RK's web driver: per-key values on the keys (green actuation,
  blue/orange rapid trigger), tabs for Normal Travel, Rapid Trigger, Advanced (dead zones, polling
  rate, top dead zone switch), Keyboard Adjusting (calibration) and Select Axis (switch type), plus
  Select All / WASD / Number / Letter / Uncheck / Reset Travel
- Custom Key, laid out like RK's web driver: WIN/MAC, FN0-FN3, and Letter, Number, Symbolic, Basic,
  Function, Keyboard Control, Mouse and Combination key tabs
- lighting with live effect preview, per-key colours
- advanced keys: DKS, multi-point, mod-tap, toggle, END, SOCD, rappy snappy, macros
- onboard configs 1-4, polling rate, calibration
- Travel Test: live key depth on a 0-4 mm ruler with the key's actuation point, plus Key Test
- Macro Management: record macros from the keyboard, rename, copy, delete and edit step delays;
  put one on a key from Advanced Key > Macro

- Knob: the volume knob is fixed in the keyboard's firmware to volume and mute, so the app remaps it on
  the PC instead (scroll, zoom, tracks, arrows, browser tabs, virtual desktops, undo/redo, ...). It works
  while the app runs, also from the tray; other volume keys on the PC are remapped too

The sidebar follows RK's web driver (Light Setting, Performance Setting, Custom Key, Advanced
Key, Macro Management) so it feels familiar. Firmware updates are not offered: this app never
flashes the keyboard.

Close the RK web driver tab first, since it can hold the keyboard's config interface.

## RK non-HE boards (USB VID 258A, about 250 models)

Lighting effect, brightness, speed, sleep timer, per-key colours and key remapping.

- **Board data:** layouts, photos and effect names are read at run time from RK Keyboard Software,
  which you download from rkgaming.com. Nothing from RK is bundled.
- **Saved settings:** these boards cannot report their settings, so the app keeps them per board in
  its data folder (see Build) and sends them whole.
- **When this window opens:** automatically when only a non-HE board is connected, or with `--classic`.
- **Testing:** not tested on a real non-HE board yet. The app asks before the first write to each board.

The feature-report format was learned from [Rangoli](https://github.com/rnayabed/rangoli) by
rnayabed, who reverse engineered it. The code here is written separately.

## Run

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run_config.py
```

## Build

`build.bat` makes, in `release\`:

- `OpenHEConfig-Portable.exe`: single file, run from anywhere. Its data (macros, effect choices,
  non-HE board settings) is kept next to the exe.
- `OpenHEConfig-1.0.0-Setup.exe`: installer (needs admin). Installs to Program Files with Start
  menu and optional desktop shortcuts. Data goes to `%APPDATA%\Open HE Config`.

Needs Inno Setup 6 (`winget install JRSoftware.InnoSetup`) for the installer.

## Tray

Closing the window keeps the app in the tray (Knob page, "Background"), and it can start with
Windows hidden in the tray. In the tray it reads nothing from the keyboard and builds no window
until you open it: measured at 0% CPU and about 47 MB of RAM. Starting it again opens the
running copy instead of a second one.

## Where your data is kept

The app's own files sit in one folder: next to `OpenHEConfig-Portable.exe` for the portable
build, `%APPDATA%\Open HE Config` for the installed copy, and the repository folder when run
from source.

- `macros.json`: copies of macros put on keys (the keyboard cannot report macro steps back)
- `macro_library.json`: the Macro Management list
- `effects.json`: lighting effect choices
- `app_settings.json`: knob actions, tray and start-with-Windows options
- `rk_classic\`: settings for each non-HE board (these boards cannot report their settings)

Everything else (actuation, rapid trigger, remaps, lighting, advanced keys) is stored in the
keyboard itself.

## Files

- `config_app/`: main window, panels and advanced keys for HE boards
- `app/protocol.py`, `app/kbconfig.py`: RK SparkLink HE configuration protocol
- `app/device.py`, `app/layout.py`, `app/keycodes.py`: device lookup and key layouts
- `rk_classic/`: non-HE boards
  - `rkdata.py`: reader for RK's software data
  - `protocol.py`: feature reports
  - also the HID link and the window
- `kbui/`: theme, keycap view, lighting preview, widgets
- `tests/`: offline tests, run with `python -m unittest discover tests`. The non-HE board-data
  tests also run when `RK_SOFTWARE_DIR` points to RK's software folder.

## License

GPL-3.0 or later, see `LICENSE`. You may use, change and share it; versions you share must
stay under the GPL with their source available. RK Keyboard Software and its board data belong to RK and are not part of
this repository.
