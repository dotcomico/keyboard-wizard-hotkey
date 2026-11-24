# Manual test checklist

These need a live desktop session (real clipboard, real hotkey, real input
languages), so they're run by hand. Run them after any change to
`kbwizard/win32/` (hotkey, clipboard, input, layout switch),
`kbwizard/app/controller.py`, `kbwizard/app/tray.py` or `kbwizard/main.py`,
and before every release build.

The two scripts in this folder test single modules in isolation
(`test_hotkey.py`, `test_clipboard_io.py`; steps are in their docstrings).
This file is the **end-to-end** checklist for the whole app.

## Before you start

1. Both **English (US)** and **Hebrew** keyboards are installed (Settings →
   Time & language → Language & region).
2. `.\.venv\Scripts\python.exe -m pytest` passes.
3. Start the app:

   ```powershell
   .\.venv\Scripts\python.exe -m kbwizard.main
   ```

   Expected: a blue "KW" keycap icon appears in the tray (check the `^`
   overflow area). Hovering it shows `Keyboard Wizard (Ctrl+Alt+W) — Ready.`
   and the right-click menu shows `Ready.` and `Hotkey: Ctrl+Alt+W`.
   The console logs `Listening for ctrl+alt+w`.
4. Copy a recognizable word, e.g. `CLIPCHECK`, to the clipboard. Most tests
   below check that it's still there afterwards (paste it somewhere with
   Ctrl+V).

## 1. English → Hebrew in Notepad

1. Open Notepad. Switch to English (Win+Space).
2. Type `akuo`, select it (Shift+Home or double-click).
3. Press **Ctrl+Alt+W**.

Expected: `akuo` is replaced by `שלום`. The input indicator on the taskbar
switches to Hebrew (typing now produces Hebrew). The clipboard still holds
`CLIPCHECK`. No balloon (successful conversions are silent); the tooltip
reads `Converted to Hebrew.`

## 2. Hebrew → English (and the hotkey under the Hebrew layout)

1. Still in Notepad, with **Hebrew active**, type `שלום` and select it.
2. Press **Ctrl+Alt+W**.

Expected: `שלום` becomes `akuo` and the layout switches to English. This also
proves the hotkey fires while Hebrew is active (the main use case).
Repeat with `vhh` → `היי` and back.

## 3. Browser and Electron apps

Repeat test 1 in:

- a Chrome/Edge `<textarea>` (e.g. a GitHub comment box),
- VS Code (editor, not the terminal),
- Slack or another Electron app (Discord, Teams, WhatsApp desktop).

Expected in each: the **converted** text is pasted — never `CLIPCHECK`. (If
you see `CLIPCHECK` pasted, the 0.25 s settle delay in `kbwizard/win32/clipboard_io.py` is
too short for that app.) Afterwards the clipboard holds `CLIPCHECK` again.

## 4. Read-only text

1. Open any web page and select a word of normal page text (not in an input).
2. Press **Ctrl+Alt+W**.

Expected: the page doesn't change, nothing breaks, and the clipboard holds
`CLIPCHECK`. The tooltip shows `Converted to …` (the paste was simply
ignored by the page) — that's by design.

## 5. Win+V clipboard history

1. Turn on clipboard history (Settings → System → Clipboard) and clear it.
2. Copy `CLIPCHECK`, then run test 1 three times.
3. Press **Win+V**.

Expected: no entries for `שלום`/`akuo` written by Keyboard Wizard, and no
duplicate `CLIPCHECK` from the restore. An entry for the original `akuo`
from the **target app's own** Ctrl+C may appear — known limitation (see
README).

## 6. Holding Ctrl+Alt after pressing W

1. In Notepad select `akuo`.
2. Press Ctrl+Alt+W, release **only W**, and keep holding Ctrl+Alt for 2
   seconds, then release.

Expected: the conversion happens only after you release Ctrl+Alt (the
worker waits up to 1 s for the keys, then forces key-ups). No `Ctrl+Alt+C`
side effect (e.g. no ©, nothing odd inserted), no Alt-menu underline or menu
activation in Notepad, and Ctrl/Alt aren't left "stuck" (typing afterwards
is normal).

Also: hold Ctrl+Alt+W down for 2 seconds. Expected: exactly one conversion
(`MOD_NOREPEAT`), not a flip-flop.

## 7. Second instance

With the app running, start it again from a second terminal:

```powershell
.\.venv\Scripts\python.exe -m kbwizard.main
```

Expected: the second process exits immediately and silently (no second
tray icon, no balloon). The log (`%APPDATA%\KeyboardWizard\kbwizard.log`)
contains `Another Keyboard Wizard instance is already running; exiting.`

## 8. Hotkey already taken

1. Quit Keyboard Wizard from the tray.
2. In a terminal, run `.\.venv\Scripts\python.exe manual_tests\test_hotkey.py`
   (it registers Ctrl+Alt+W and keeps it).
3. Start the app.

Expected: a balloon `The hotkey is used by another app.` titled
`Keyboard Wizard (Ctrl+Alt+W)`; the tray label shows the same text; the log
has `Hotkey ctrl+alt+w is already registered by another app`; the app keeps
running (Quit still works). Stop the test script, then restart the app →
`Ready` again.

## 9. Elevated (admin) window

1. Run Notepad as administrator; type and select `akuo`.
2. Press **Ctrl+Alt+W** (app running as a normal user).

Expected: balloon `No text selected.` and nothing changes. This is the
documented UIPI limitation, not a bug.

## 10. Tray menu

- Right-click the icon: the greyed-out first line shows the last status,
  the second `Hotkey: Ctrl+Alt+W`.
- Custom hotkey: quit, set `"hotkey": "ctrl+alt+shift+k"` in `config.json`,
  start the app. Expected: tooltip `Keyboard Wizard (Ctrl+Alt+Shift+K) — Ready.`,
  menu `Hotkey: Ctrl+Alt+Shift+K`, and that combo converts. Set it to
  `"ctrl+alt+banana"`: the log warns and the tray shows `Ctrl+Alt+W`.
  Restore the default afterwards.
- Untick **Switch keyboard language after convert**, run test 1: text
  converts but the layout stays English. Restart the app: still unticked
  (`config.json` has `"switch_layout_after_convert": false`). Tick it again.
- **About**: shows `Keyboard Wizard 1.0.0`, the copyright line and
  `Free for personal use. Not for sale.` (all greyed out). **View license**
  and **Third-party notices** each open the text in Notepad. Repeat with the
  built exe (test 11).
- **Quit**: the icon disappears and the process exits; Ctrl+Alt+W does
  nothing afterwards.

## 11. Built exe and Run at startup

1. Quit the dev app. Run `.\build.bat`. Expected: `dist\KeyboardWizard.exe`.
2. Double-click `dist\KeyboardWizard.exe`. Expected: the tray icon (the real
   keycap, not the fallback) and no console window.
3. Repeat tests 1–3 with the exe.
4. Tick **Run at startup**. Check `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
   (regedit) has `KeyboardWizard` = `"…\dist\KeyboardWizard.exe"`.
5. Reboot / sign out and back in. Expected: the tray icon appears on its
   own and test 1 works.
6. Untick **Run at startup**: the registry value is gone.
7. Dev variant: from the source run, tick Run at startup and check the
   value is `"…\.venv\Scripts\pythonw.exe" "…\kbwizard\main.py"`; after
   sign-in the app starts with no console window.
8. Remove the entry in Task Manager → Startup apps (or regedit) while the
   app is closed, then start it: the checkbox is unticked (the registry is
   re-read at launch).

## Privacy check

After the run, open `%APPDATA%\KeyboardWizard\kbwizard.log` and confirm it
contains **no** selected or converted text — only statuses, lengths and
directions.
