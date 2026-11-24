; PCCam Windows 설치 파일 스크립트 (Inno Setup 6)
; 사용: iscc /DMyAppVersion=1.0.0 installer\pccam.iss
;  - 미리 PyInstaller 로 dist\PCCam\ 폴더를 만들어 두어야 함 (build_installer.bat 참고)

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "PCCam"
#define MyAppExeName "PCCam.exe"

[Setup]
AppId={{6F0B3C2E-8A4D-4C59-9E1B-ABCDEF000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=PCCam
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=PCCam-Setup-{#MyAppVersion}
SetupIconFile=..\assets\pccam.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "..\dist\PCCam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "PCCam 실행하기"; Flags: nowait postinstall skipifsilent
