; Inno Setup script for Photo Organizer.
; Builds a per-user installer (no admin rights required) that installs to
; %LOCALAPPDATA%\Programs\PhotoOrganizer, adds a Start Menu shortcut and an
; optional Desktop shortcut, and registers a normal Windows uninstaller.
;
; Prerequisite: dist\PhotoOrganizer.exe must already be built
;   (pyinstaller photo_organizer\packaging\photo_organizer.spec --noconfirm)
;
; Build with:
;   "C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" photo_organizer\packaging\installer.iss
; Output: photo_organizer\packaging\dist_installer\PhotoOrganizer-Setup.exe

#define MyAppName "Photo Organizer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Photo Organizer"
#define MyAppExeName "PhotoOrganizer.exe"
#define RepoRoot ".."  ; relative to this .iss file's directory (photo_organizer\packaging)

[Setup]
AppId={{B6E2B6B4-6C3E-4E9E-9F2C-6E7B6B0F1A2D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=PhotoOrganizer-Setup
SetupIconFile={#RepoRoot}\app\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
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
Source: "{#RepoRoot}\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
