@echo off
cd /d "%~dp0"

echo Pushing admin path fix to GitHub...
echo.

git push origin main

echo.
echo Done! Check Render for automatic redeployment.
pause