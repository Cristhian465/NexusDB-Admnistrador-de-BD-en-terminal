; Inno Setup Script for Administrador de BD
; This script will create a professional installer for the DBAdmin CLI app.

[Setup]
AppId={{C78201A5-B7D4-4E8B-B0D1-20E5F1E544A4}
AppName=Administrador de BD
AppVersion=1.0
AppPublisher=Antigravity
DefaultDirName={autopf}\Administrador de BD
DefaultGroupName=Administrador de BD
AllowNoIcons=yes
; The output file name for the installer
OutputBaseFilename=Administrador_BD_Setup
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Include all files from the dist\DBAdmin folder created by PyInstaller
Source: "dist\DBAdmin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Administrador de BD"; Filename: "{app}\DBAdmin.exe"
Name: "{autodesktop}\Administrador de BD"; Filename: "{app}\DBAdmin.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DBAdmin.exe"; Description: "{cm:LaunchProgram,Administrador de BD}"; Flags: nowait postinstall skipifsilent
