# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Wire Bond Group - Activity Flow System
# This file is used by: Build App (EXE).bat
#
# Using a spec file (instead of command-line flags) gives reliable control
# over complex packages like pywebview that have dynamic/conditional imports.

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ── Collect ALL files from pywebview (data, binaries, hidden imports) ───────
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=webview_binaries,
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
    ] + webview_datas,
    hiddenimports=webview_hiddenimports + [
        # pywebview core + platform backends (Windows)
        'webview',
        'webview.platforms',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        # Flask stack
        'flask',
        'flask.templating',
        'flask.json',
        'jinja2',
        'jinja2.ext',
        'werkzeug',
        'werkzeug.security',
        'werkzeug.utils',
        'werkzeug.routing',
        'werkzeug.serving',
        # Standard library
        'sqlite3',
        '_sqlite3',
        # Pillow (optional photo handling)
        'PIL',
        'PIL.Image',
        'PIL._tkinter_finder',
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
    name='WireBondActivityFlow',
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
    name='WireBondActivityFlow',
)
