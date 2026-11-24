@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] 프로그램(exe) 빌드...
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name PCCam --icon assets\pccam.ico --add-data "assets;assets" main.py
if errorlevel 1 goto :fail
echo [2/2] 설치 파일 만들기 (Inno Setup 6 필요: https://jrsoftware.org/isdl.php)
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 이 설치되어 있지 않습니다. 설치 후 다시 실행하세요.
  goto :fail
)
%ISCC% installer\pccam.iss
if errorlevel 1 goto :fail
echo.
echo 완료: dist 폴더의 PCCam-Setup-*.exe
pause
exit /b 0
:fail
echo 실패했습니다.
pause
exit /b 1
