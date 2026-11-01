@echo off
rem Serves this folder and opens the walk-through. Close the window to stop.
cd /d "%~dp0"
start "" http://localhost:8765/
py -3 -m http.server 8765 --bind 127.0.0.1
