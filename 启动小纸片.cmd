@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "release\1.0.3\小纸片\小纸片.exe" (
  start "" "release\1.0.3\小纸片\小纸片.exe"
) else if exist "release\小纸片\小纸片.exe" (
  start "" "release\小纸片\小纸片.exe"
) else (
  start "" ".venv\Scripts\pythonw.exe" "main.py"
)
