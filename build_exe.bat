@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [PCCam] 단독 실행 파일(exe)을 만듭니다...
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name PCCam main.py
echo.
echo 완료: dist\PCCam.exe
pause
