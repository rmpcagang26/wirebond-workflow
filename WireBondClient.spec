# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Wire Bond Group - Client (User) App
# This is the lightweight client that connects to the Admin server over LAN.

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ── Collect ALL files from pywebview ─────────────────────────────────────
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

a = Analysis(
    ['client_launcher.py'],
    pathex=['.'],
    binaries=webview_binaries,
    datas=webview_datas,
    hiddenimports=webview_hiddenimports + [
        'webview',
        'webview.platforms',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WireBondClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No console window (desktop app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WireBondClient',
)
