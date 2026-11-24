"""Generate ``THIRD_PARTY_NOTICES.txt`` from the license files of the components bundled in the exe.

The texts are copied from the installed packages rather than pasted by hand, so
re-running this after a dependency bump keeps the notices matching what ships.

Usage: .venv/Scripts/python.exe tools/make_notices.py
"""

from __future__ import annotations

import sys
from importlib.metadata import distribution
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Make the project root importable when run as a script.
sys.path.insert(0, str(REPO_ROOT))

from kbwizard import APP_COPYRIGHT  # noqa: E402

OUTPUT = REPO_ROOT / "THIRD_PARTY_NOTICES.txt"

HEADER = """\
Keyboard Wizard - Third-Party Notices

Keyboard Wizard: {copyright}
It is licensed under the terms in LICENSE.

The executable also contains the open-source components listed below. Each one
stays under its own license, reproduced in full here, and nothing in Keyboard
Wizard's license limits the rights these licenses give you.

pystray is licensed under the GNU Lesser General Public License v3. It is
included unmodified; its source code is available at
https://github.com/moses-palmer/pystray (version {pystray_version}). You may
replace it with a modified version of the library, and Keyboard Wizard's
license does not restrict the reverse engineering needed to do so.

Components:
{summary}
"""

#: (display name, distribution name, project URL, license name)
PACKAGES = (
    ("pystray", "pystray", "https://github.com/moses-palmer/pystray", "LGPL-3.0"),
    ("Pillow", "pillow", "https://python-pillow.github.io", "MIT-CMU, plus bundled libraries"),
    ("pywin32", "pywin32", "https://github.com/mhammond/pywin32", "PSF-2.0"),
    ("six", "six", "https://github.com/benjaminp/six", "MIT"),
    (
        "PyInstaller bootloader",
        "pyinstaller",
        "https://pyinstaller.org",
        "GPL-2.0 with the bootloader exception",
    ),
)

#: pywin32 ships several license files for parts the exe doesn't use; only win32's applies.
_ONLY_FILES = {"pywin32": ("win32/License.txt",)}


def _license_texts(dist_name: str) -> list[str]:
    """Return the text of each license file a distribution declares."""
    dist = distribution(dist_name)
    wanted = _ONLY_FILES.get(dist_name)
    texts = []
    for file in dist.files or ():
        path = file.as_posix()
        in_license_dir = "/licenses/" in path or path.endswith(("COPYING", "COPYING.LGPL", "LICENSE"))
        if not in_license_dir or ".dist-info/" not in path:
            continue
        if wanted and not path.endswith(wanted):
            continue
        texts.append(file.read_text(encoding="utf-8").strip())
    if not texts:
        raise SystemExit(f"No license file found for {dist_name}")
    return texts


def _python_license() -> str:
    """Return the CPython license text that ships with the interpreter."""
    return (Path(sys.base_prefix) / "LICENSE.txt").read_text(encoding="utf-8").strip()


def _section(title: str, body: str) -> str:
    rule = "=" * 78
    return f"{rule}\n{title}\n{rule}\n\n{body}\n"


def build() -> str:
    """Assemble the full notices document."""
    python_version = ".".join(map(str, sys.version_info[:3]))
    rows = [f"  - Python {python_version}  (https://www.python.org)  PSF-2.0"]
    sections = [_section(f"Python {python_version}", _python_license())]
    for name, dist_name, url, license_name in PACKAGES:
        version = distribution(dist_name).version
        rows.append(f"  - {name} {version}  ({url})  {license_name}")
        sections.append(
            _section(f"{name} {version}", "\n\n".join(_license_texts(dist_name)))
        )
    header = HEADER.format(
        copyright=APP_COPYRIGHT,
        pystray_version=distribution("pystray").version, summary="\n".join(rows)
    )
    return header + "\n" + "\n".join(sections)


def main() -> None:
    OUTPUT.write_text(build(), encoding="utf-8", newline="\r\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
