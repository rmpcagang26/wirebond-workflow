"""
Wire Bond Group - Activity Flow System
Client Launcher (User / Viewer)

Lightweight client that connects to the Admin server over LAN.
Reads server IP from config.txt and opens a pywebview window.

config.txt format:
    SERVER_IP=192.168.1.100
    SERVER_PORT=5000
"""

import sys
import os
import time

# ── webview MUST be imported at top level for PyInstaller ────────────────
import webview

# ── Resolve path (frozen exe vs plain .py) ──────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def read_config():
    """Read server connection info from config.txt next to the exe/script."""
    config_path = os.path.join(BASE_DIR, 'config.txt')
    server_ip = '127.0.0.1'
    server_port = '5000'

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip().upper()
                val = val.strip()
                if key == 'SERVER_IP':
                    server_ip = val
                elif key == 'SERVER_PORT':
                    server_port = val
    else:
        # Create a default config.txt if it doesn't exist
        with open(config_path, 'w') as f:
            f.write("# Wire Bond Group — Activity Flow System\n")
            f.write("# Client Configuration\n")
            f.write("#\n")
            f.write("# Set the IP address of the Admin PC running the server.\n")
            f.write("# To find the Admin PC's IP: open CMD and type 'ipconfig'\n")
            f.write("# Look for 'IPv4 Address' under your Wi-Fi or Ethernet adapter.\n")
            f.write("#\n")
            f.write("SERVER_IP=192.168.1.100\n")
            f.write("SERVER_PORT=5000\n")
        print(f"[INFO] Created default config.txt at: {config_path}")
        print("[INFO] Please edit config.txt with the Admin PC's IP address and restart.")

    return server_ip, server_port


if __name__ == '__main__':
    server_ip, server_port = read_config()
    url = f"http://{server_ip}:{server_port}"

    print()
    print("=" * 60)
    print("  Wire Bond Group — Activity Flow System (Client)")
    print(f"  Connecting to server: {url}")
    print("=" * 60)
    print()

    # ── Create the desktop window pointed at the remote server ───────────
    window = webview.create_window(
        title='Wire Bond Group — Activity Flow System',
        url=url,
        width=1366,
        height=860,
        min_size=(960, 640),
        resizable=True,
        text_select=True,
        confirm_close=False,
    )

    # Try Edge WebView2 first, fall back to default
    try:
        webview.start(gui='edgechromium', debug=False)
    except Exception:
        webview.start(debug=False)
