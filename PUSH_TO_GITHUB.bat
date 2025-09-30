@echo off
cd /d "%~dp0"

echo Pushing code to GitHub...
echo.

git branch -M main
git push -u origin main

echo.
echo Done!
pause