# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

PY2EXE_DIR = Path(SPECPATH).resolve()
PROJECT_DIR = PY2EXE_DIR.parent

ENTRY_FILE = PROJECT_DIR / "app.py"
ICON_FILE = PROJECT_DIR / "waltrone1-System-Diagnostics-Report.ico"
VERSION_FILE = PROJECT_DIR / "version_info.txt"
APP_NAME = "waltrone1-System-Diagnostics-Report"

if not ENTRY_FILE.exists():
    raise SystemExit(f"Startdatei nicht gefunden: {ENTRY_FILE}")
if not ICON_FILE.exists():
    raise SystemExit(f"Icon nicht gefunden: {ICON_FILE}")

datas = []
for folder in ("templates", "static"):
    source = PROJECT_DIR / folder
    if source.exists():
        datas.append((str(source), folder))

exe_kwargs = {}
if VERSION_FILE.exists():
    exe_kwargs["version"] = str(VERSION_FILE)

a = Analysis(
    [str(ENTRY_FILE)],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_FILE),
    **exe_kwargs,
)
