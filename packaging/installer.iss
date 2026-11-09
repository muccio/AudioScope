; ==============================================================================
; AudioScope Inno Setup Script
; Generates production Windows installer with Start Menu shortcuts and file associations
; ==============================================================================

#define MyAppName "AudioScope"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AudioScope Project"
#define MyAppURL "https://audioscope.app"
#define MyAppExeName "AudioScope.exe"

[Setup]
AppId={{9F570A74-D7BE-45C0-A491-C4B827DA81F4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\README.md
OutputDir=..\dist
OutputBaseFilename=AudioScope-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "Associate standard audio formats with AudioScope"; GroupDescription: "File Associations:"

[Files]
Source: "..\dist\AudioScope\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Registry]
; Context Menu: "Open with AudioScope" for audio files
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\audio\shell\AudioScope"; ValueType: string; ValueName: ""; ValueData: "Inspect with AudioScope"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\audio\shell\AudioScope\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
