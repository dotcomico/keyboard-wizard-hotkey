"""Unit tests for startup: Run-key command building and enable/disable/is_enabled."""

from __future__ import annotations

import sys
import winreg
from pathlib import Path
from unittest.mock import MagicMock

from kbwizard.app import startup


def test_dev_mode_uses_pythonw_beside_interpreter_when_present(monkeypatch, tmp_path):
    (tmp_path / "python.exe").touch()
    (tmp_path / "pythonw.exe").touch()
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(startup, "_MAIN_SCRIPT", Path(r"C:\repo\kbwizard\main.py"))

    cmd = startup._launch_cmd()

    assert cmd == f'"{tmp_path / "pythonw.exe"}" "C:\\repo\\kbwizard\\main.py"'


def test_dev_mode_falls_back_to_interpreter_without_pythonw(monkeypatch, tmp_path):
    (tmp_path / "python.exe").touch()
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(startup, "_MAIN_SCRIPT", Path(r"C:\repo\kbwizard\main.py"))

    cmd = startup._launch_cmd()

    assert cmd == f'"{tmp_path / "python.exe"}" "C:\\repo\\kbwizard\\main.py"'


def test_dev_mode_script_is_this_packages_main():
    # Independent of sys.argv[0], which differs between `-m` and script runs.
    assert startup._MAIN_SCRIPT.name == "main.py"
    assert startup._MAIN_SCRIPT.parent.name == "kbwizard"
    assert startup._MAIN_SCRIPT.exists()


def test_frozen_mode_uses_exe_path_only(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\KeyboardWizard.exe")

    cmd = startup._launch_cmd()

    assert cmd == r'"C:\Apps\KeyboardWizard.exe"'


def test_frozen_mode_quotes_path_with_spaces(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Users\Example User\KeyboardWizard.exe")

    cmd = startup._launch_cmd()

    assert cmd == r'"C:\Users\Example User\KeyboardWizard.exe"'
    # Frozen build must not pass a script path alongside sys.executable.
    assert cmd.count('"') == 2


def test_dev_mode_quotes_both_paths_with_spaces(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\Python314\python.exe")
    monkeypatch.setattr(startup, "_console_free_interpreter", lambda: sys.executable)
    monkeypatch.setattr(
        startup, "_MAIN_SCRIPT", Path(r"C:\Vs Projects\keyboard-wizard-hotkey\kbwizard\main.py")
    )

    cmd = startup._launch_cmd()

    assert cmd == (
        r'"C:\Program Files\Python314\python.exe" '
        r'"C:\Vs Projects\keyboard-wizard-hotkey\kbwizard\main.py"'
    )


def test_app_name_is_keyboard_wizard():
    assert startup._RUN_VALUE_NAME == "KeyboardWizard"


def test_enable_writes_registry_value(monkeypatch):
    mock_key = MagicMock()
    mock_open = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_key
    mock_set = MagicMock()
    monkeypatch.setattr(winreg, "OpenKey", mock_open)
    monkeypatch.setattr(winreg, "SetValueEx", mock_set)
    monkeypatch.setattr(startup, "_launch_cmd", lambda: '"cmd"')

    startup.enable()

    mock_set.assert_called_once_with(mock_key, startup._RUN_VALUE_NAME, 0, winreg.REG_SZ, '"cmd"')


def test_disable_removes_registry_value(monkeypatch):
    mock_key = MagicMock()
    mock_open = MagicMock()
    mock_open.return_value.__enter__.return_value = mock_key
    mock_delete = MagicMock()
    monkeypatch.setattr(winreg, "OpenKey", mock_open)
    monkeypatch.setattr(winreg, "DeleteValue", mock_delete)

    startup.disable()

    mock_delete.assert_called_once_with(mock_key, startup._RUN_VALUE_NAME)


def test_disable_is_noop_when_key_already_missing(monkeypatch):
    monkeypatch.setattr(winreg, "OpenKey", MagicMock(side_effect=FileNotFoundError))

    startup.disable()  # must not raise


def test_disable_is_noop_on_generic_os_error(monkeypatch):
    monkeypatch.setattr(winreg, "OpenKey", MagicMock(side_effect=OSError))

    startup.disable()  # must not raise


def test_is_enabled_true_when_key_present(monkeypatch):
    mock_open = MagicMock()
    mock_open.return_value.__enter__.return_value = MagicMock()
    monkeypatch.setattr(winreg, "OpenKey", mock_open)
    monkeypatch.setattr(winreg, "QueryValueEx", MagicMock(return_value=("cmd", 1)))

    assert startup.is_enabled() is True


def test_is_enabled_false_when_key_missing(monkeypatch):
    monkeypatch.setattr(winreg, "OpenKey", MagicMock(side_effect=FileNotFoundError))

    assert startup.is_enabled() is False


def test_is_enabled_false_on_generic_os_error(monkeypatch):
    # Any registry error, e.g. a permissions issue, reads as "not enabled".
    monkeypatch.setattr(winreg, "OpenKey", MagicMock(side_effect=OSError))

    assert startup.is_enabled() is False
