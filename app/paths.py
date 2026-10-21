"""Where M75 Config keeps its own files (macros, effect choices, non-HE board settings)."""

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    r"""Next to the exe for the portable build; %APPDATA%\M75 Config for the installed copy
    (marked by installed.flag, which the installer writes) because Program Files is read-only.
    Running from source uses the repository folder."""
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent
    exe_dir = Path(sys.executable).parent
    if (exe_dir / "installed.flag").exists():
        d = Path(os.environ.get("APPDATA", Path.home())) / "M75 Config"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return exe_dir
