# -*- mode: python ; coding: utf-8 -*-
# Build: build.bat  (= .venv\Scripts\python -m PyInstaller --clean --noconfirm KeyboardWizard.spec)
# Output: dist\KeyboardWizard.exe — one file, windowed (tray only, no console).


a = Analysis(
    ['kbwizard/main.py'],
    # '.' so `from kbwizard...` in the entry script resolves to the package.
    pathex=['.'],
    binaries=[],
    # `icon=` below only sets the .exe's file icon; the running tray loads
    # assets/icon.ico from sys._MEIPASS, so it must also be bundled as data.
    datas=[('assets/icon.ico', 'assets')],
    # pystray picks its backend dynamically; win32timezone is a pywin32
    # runtime import PyInstaller's analysis can miss.
    hiddenimports=['pystray._win32', 'win32timezone'],
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
    name='KeyboardWizard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Packed exes that use SendInput and the clipboard trip more antivirus heuristics.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
