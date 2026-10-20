# M75 Config

Desktop app that configures RK keyboards on Windows, replacing RK's web driver and Windows
software.

## RK HE boards (SparkLink, USB 1CA2:1601-161B)

Built and tested on the RK M75 HE. Every board in RK's web driver list is detected. Boards other
than the M75 HE are drawn from the key map the keyboard reports, and stay read-only until you
allow writes for that model.

- actuation, rapid trigger, deadzones
- remapping, Fn layers
- lighting with live effect preview, per-key colours
- advanced keys: DKS, multi-point, mod-tap, toggle, END, SOCD, rappy snappy, macros
- onboard configs 1-4, polling rate, calibration, key test

Close the RK web driver tab first, since it can hold the keyboard's config interface.

## RK non-HE boards (USB VID 258A, about 250 models)

Lighting effect, brightness, speed, sleep timer, per-key colours and key remapping.

- **Board data:** layouts, photos and effect names are read at run time from RK Keyboard Software,
  which you download from rkgaming.com. Nothing from RK is bundled.
- **Saved settings:** these boards cannot report their settings, so the app keeps them per board in
  `%APPDATA%\M75 Config\rk_classic` and sends them whole.
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

To build the app, run `build_config.bat`. It creates `release\M75Config.exe`.

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

MIT, see `LICENSE`. RK Keyboard Software and its board data belong to RK and are not part of
this repository.
