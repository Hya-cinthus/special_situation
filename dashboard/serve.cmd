@echo off
REM Persistent local server for the Special Situations dashboard.
REM Serves dashboard/ on 127.0.0.1:8200 for Tailscale funnel to proxy.
REM Registered as a Scheduled Task (onlogon) so it survives reboots/sessions.
cd /d "%~dp0"
"C:\Users\vanna\AppData\Local\Programs\Python\Python314\pythonw.exe" -m http.server 8200 --bind 127.0.0.1
