"""
Wire Bond Group - Activity Flow System
Desktop Application Launcher

Uses pywebview to wrap the Flask app in a native OS window.
Install:  pip install pywebview
Run:      python launcher.py
"""

import threading
import time
import sys
import os

# ── webview MUST be imported at the top level so PyInstaller's static
#    analysis detects it and bundles the full package into the .exe ─────────
import webview

# ── Resolve paths correctly whether running as .py or as a bundled .exe ────
if getattr(sys, 'frozen', False):
    # PyInstaller: exe is in dist/AppName/; bundled modules auto-importable
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)


def start_flask():
    """Run Flask server in a background daemon thread."""
    from app import app, init_db

    # Ensure upload/data directories exist
    os.makedirs(app.config['UPLOAD_PHOTOS'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FILES'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
    init_db()

    # Run on 0.0.0.0 so other PCs on the LAN can connect
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    # ── Start Flask in background ──────────────────────────────────────────
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Give Flask a moment to bind its port before opening the window
    time.sleep(1.5)

    # ── Create the desktop window ──────────────────────────────────────────
    window = webview.create_window(
        title='Wire Bond Group — Activity Flow System',
        url='http://127.0.0.1:5000',
        width=1366,
        height=860,
        min_size=(960, 640),
        resizable=True,
        text_select=True,
        confirm_close=True,        # Ask before closing
    )

    # Try Edge WebView2 (best on Windows 10/11), fall back to default
    try:
        webview.start(gui='edgechromium', debug=False)
    except Exception:
        webview.start(debug=False)
