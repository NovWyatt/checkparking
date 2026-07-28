#define MyAppName "Check Vehicle OCR"
#define MyAppVersion "1.6.12"
#define MyAppPublisher "Check Vehicle"
#define MyAppExeName "CheckVehicleOCR.exe"
#ifndef SourceDir
#define SourceDir "..\release\CheckVehicleOCR"
#endif

[Setup]
AppId={{9F7D0429-9F2E-4B51-B579-F978E00C3D0A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CheckVehicleOCR
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=CheckVehicleOCR_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
