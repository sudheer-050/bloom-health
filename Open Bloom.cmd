@echo off
cd /d "%~dp0"
echo Open http://localhost:4317 in your browser once the server starts.
echo Keep this window open while using Bloom. Press Ctrl+C to stop.
python server.py
pause
