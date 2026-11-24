# -*- mode: python ; coding: utf-8 -*-
# Build: build.bat  (= .venv\Scripts\python -m PyInstaller --clean --noconfirm KeyboardWizard.spec)
# Output: dist\KeyboardWizard.exe — one file, windowed (tray only, no console).

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

from kbwizard import APP_AUTHOR, APP_COPYRIGHT, APP_DISPLAY_NAME, __version__

# Built from the package constants so the Properties > Details tab always
# matches the running app's version and owner.
_version_tuple = tuple(int(part) for part in __version__.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_version_tuple, prodvers=_version_tuple),
    kids=[
        StringFileInfo(
            [
                # 0409 = US English, 04B0 = Unicode.
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", APP_AUTHOR),
                        StringStruct("FileDescription", APP_DISPLAY_NAME),
                        StringStruct("FileVersion", __version__),
                        StringStruct("InternalName", "KeyboardWizard"),
                        StringStruct("LegalCopyright", APP_COPYRIGHT),
                        StringStruct("OriginalFilename", "KeyboardWizard.exe"),
                        StringStruct("ProductName", APP_DISPLAY_NAME),
                        StringStruct("ProductVersion", __version__),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x0409, 0x04B0])]),
    ],
)


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
    version=version_info,
)
