' Persistent local server for the Special Situations dashboard.
' Launches python http.server on 127.0.0.1:8200 with NO visible window.
' A copy of this file lives in the user Startup folder so it runs at logon
' (no admin / no Scheduled Task privileges required). Tailscale funnel proxies
' 127.0.0.1:8200 to the public URL.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\vanna\Documents\special_situation\dashboard"
sh.Run """C:\Users\vanna\AppData\Local\Programs\Python\Python314\pythonw.exe"" -m http.server 8200 --bind 127.0.0.1", 0, False
