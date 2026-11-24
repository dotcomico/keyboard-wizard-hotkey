"""Unit tests for the tray's static resources and status texts."""

from __future__ import annotations

from kbwizard.app import tray
from kbwizard.app.status import Status


def test_icon_file_exists_in_dev_layout():
    assert tray._ICON_PATH.exists()


def test_status_texts_do_not_hard_code_a_hotkey():
    # The hotkey is configurable; the tray names the active one beside the status.
    assert all("Ctrl" not in status.text for status in Status)


def test_license_files_exist_in_dev_layout():
    assert tray._LICENSE_PATH.exists()
    assert tray._NOTICES_PATH.exists()
