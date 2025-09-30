@echo off
chcp 65001 >nul
echo ========================================
echo   Installing TTS System Dependencies
echo ========================================
echo.

echo Installing gradio...
python -m pip install gradio

echo.
echo Installing requests...
python -m pip install requests

echo.
echo Installing python-dotenv...
python -m pip install python-dotenv

echo.
echo ========================================
echo   Installation Complete!
echo   Run run_app.bat to start
echo ========================================
pause