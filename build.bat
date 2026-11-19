@echo off
rem Builds dist\KeyboardWizard.exe from KeyboardWizard.spec (run from the repo root).
cd /d "%~dp0"
.venv\Scripts\python -m PyInstaller --clean --noconfirm KeyboardWizard.spec
