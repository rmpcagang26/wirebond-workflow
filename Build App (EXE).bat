@echo off
title Wire Bond Group — EXE Builder
color 0A

echo.
echo  =====================================================
echo    Wire Bond Group — Activity Flow System
echo    EXE Builder (powered by PyInstaller)
echo  =====================================================
echo.
echo  This will build TWO outputs:
echo    1. Admin Folder  — Full server + database + desktop app
echo    2. User Folder   — Lightweight client (connects over LAN)
echo.
pause

:: ── Step 1: Install PyInstaller ───────────────────────────────────────────
echo.
echo [1/6] Installing / updating PyInstaller...
pip install --upgrade pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: pip install failed. Make sure Python is installed and in PATH.
    pause & exit /b 1
)
echo        Done.

:: ── Step 2: Clean previous builds ─────────────────────────────────────────
echo.
echo [2/6] Cleaning previous builds...
if exist dist\WireBondActivityFlow rmdir /s /q dist\WireBondActivityFlow
if exist dist\WireBondClient rmdir /s /q dist\WireBondClient
if exist "dist\Admin" rmdir /s /q "dist\Admin"
if exist "dist\User" rmdir /s /q "dist\User"
if exist build rmdir /s /q build
:: NOTE: Do NOT delete .spec files — we need them for the build!
echo        Done.

:: ── Step 3: Build Admin EXE ───────────────────────────────────────────────
echo.
echo [3/6] Building ADMIN EXE — this takes 1-3 minutes...
echo.
pyinstaller --noconfirm WireBondActivityFlow.spec
if %errorlevel% neq 0 (
    echo.
    echo  ADMIN BUILD FAILED. Check the errors above.
    pause & exit /b 1
)
echo        Admin build complete.

:: ── Step 4: Build User (Client) EXE ──────────────────────────────────────
echo.
echo [4/6] Building USER (Client) EXE — this takes 1-2 minutes...
echo.
pyinstaller --noconfirm WireBondClient.spec
if %errorlevel% neq 0 (
    echo.
    echo  CLIENT BUILD FAILED. Check the errors above.
    pause & exit /b 1
)
echo        Client build complete.

:: ── Step 5: Organize into Admin / User folders ──────────────────────────
echo.
echo [5/6] Organizing into Admin and User folders...

:: Rename dist outputs into Admin / User
ren "dist\WireBondActivityFlow" "Admin"
ren "dist\WireBondClient" "User"

:: Copy config.txt into User folder
if exist config.txt copy /y config.txt "dist\User\config.txt" >nul
echo        Done.

:: ── Step 6: Done ─────────────────────────────────────────────────────────
echo.
echo [6/6] Build complete!
echo.
echo  ┌──────────────────────────────────────────────────────────┐
echo  │                                                          │
echo  │   ADMIN folder:   dist\Admin\                            │
echo  │     WireBondActivityFlow.exe                             │
echo  │     Contains: server + database + templates + static     │
echo  │     → Deploy on your laptop (admin) and boss laptop.     │
echo  │     → Runs the Flask server on the LAN.                  │
echo  │     → The database is saved next to the .exe.            │
echo  │                                                          │
echo  │   USER folder:    dist\User\                             │
echo  │     WireBondClient.exe + config.txt                      │
echo  │     Contains: lightweight client (no server/database)    │
echo  │     → Deploy on operator/engineer PCs.                   │
echo  │     → Edit config.txt with the Admin PC's IP address.    │
echo  │     → Connects to the admin server over LAN.             │
echo  │                                                          │
echo  │   SETUP INSTRUCTIONS:                                    │
echo  │   1. Copy "Admin" folder to admin laptop(s).             │
echo  │   2. Run WireBondActivityFlow.exe on admin laptop.       │
echo  │   3. Find admin laptop IP: open CMD → ipconfig           │
echo  │   4. Copy "User" folder to each user PC.                 │
echo  │   5. Edit config.txt: set SERVER_IP to admin IP.         │
echo  │   6. Run WireBondClient.exe on user PCs.                 │
echo  │                                                          │
echo  │   NOTE: All PCs must be on the same network.             │
echo  │   Python does NOT need to be installed on target PCs.    │
echo  │   Windows 10/11 with Edge WebView2 is required.          │
echo  │                                                          │
echo  └──────────────────────────────────────────────────────────┘
echo.
pause
