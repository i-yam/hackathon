#!/usr/bin/env python3
"""Convenience launcher: opens the browser and starts the server."""
import webbrowser, threading, app
threading.Timer(1.3, lambda: webbrowser.open('http://localhost:5000')).start()
print('Opening Detect running at  http://localhost:5000   (Ctrl+C to stop)')
app.app.run(host='0.0.0.0', port=5000, debug=False)
