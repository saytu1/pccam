@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [PCCam] 필요한 패키지를 설치합니다...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo 설치 실패. Python 3.9 이상이 설치되어 있는지, 설치 시 "Add Python to PATH"를 체크했는지 확인하세요.
  pause
  exit /b 1
)
echo.
echo 설치 완료! run.bat 을 더블클릭해서 실행하세요.
pause
