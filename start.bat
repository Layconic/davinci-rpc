@echo off
cd /d "%~dp0"
if not exist config.json copy config.example.json config.json >nul
python -m pip install -q -r requirements.txt
python -m davinci_rpc %*
pause
