@echo off
cd /d "%~dp0"
echo Starting local server for the SecuGen demo...
echo Once started, open this URL in your browser:
echo   http://localhost:8080/Secugen-Demo1%%20-%%20SecuGen%%20Corporation.html
echo.
python -m http.server 8080
