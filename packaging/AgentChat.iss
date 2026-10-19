; Inno Setup script -> AgentChat-Setup-<version>.exe
; Build:  ISCC.exe /DAppVersion=1.0.0 packaging\AgentChat.iss   (after building release\dist\AgentChat.exe)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{7B1E5C0A-4D3F-4B8E-9C52-3A6F0D2E8A91}
AppName=Agent Chat
AppVersion={#AppVersion}
AppPublisher=Agent Chat
DefaultDirName={autopf}\Agent Chat
DefaultGroupName=Agent Chat
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=AgentChat-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\AgentChat.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; per-user install: no admin prompt. Users can still choose "all users" in the wizard.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\release\dist\AgentChat.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Agent Chat"; Filename: "{app}\AgentChat.exe"
Name: "{autodesktop}\Agent Chat"; Filename: "{app}\AgentChat.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AgentChat.exe"; Description: "Launch Agent Chat"; Flags: nowait postinstall skipifsilent

; Chats and settings live in %APPDATA%\AgentChat and are intentionally kept on uninstall.
