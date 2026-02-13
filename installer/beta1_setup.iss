; =============================================================================
; Beta1 Portfolio Tracker - Inno Setup Script
; Creates Windows installer with embedded Python + all dependencies
; =============================================================================

#define MyAppName "Beta1 Portfolio Tracker"
#define MyAppVersion "1.0"
#define MyAppPublisher "Beta1"
#define MyAppURL "https://github.com/sonex-on/beta1-portfolio"

[Setup]
AppId={{B3A7F1E2-9C4D-4A8B-B5E6-1F2A3B4C5D6E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Beta1Portfolio
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Beta1_Portfolio_Setup
SetupIconFile=..\build\app\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\assets\icon.ico

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\build\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launch.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\Odinstaluj {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launch.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\launch.pyw"""; Description: "Uruchom {#MyAppName}"; Flags: nowait postinstall skipifsilent
