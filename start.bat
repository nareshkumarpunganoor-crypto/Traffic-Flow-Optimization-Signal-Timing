@echo off
title Traffic Flow Optimization
echo Starting app...
cd /d "N:\Deep Learning Projects\Traffic Flow Optimization & Signal Timing"
start "App" cmd /k "N: && cd "N:\Deep Learning Projects\Traffic Flow Optimization & Signal Timing" && python run.py"
timeout /t 5 /nobreak
start "Ngrok" cmd /k "ngrok http 5000"
echo Done! Check ngrok window for URL.
pause