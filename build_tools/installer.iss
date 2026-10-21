; Inno Setup script for Open HE Config. Built by build.bat from dist\OpenHEConfig (onedir build).

#define AppName "Open HE Config"
#ifndef AppVersion
  #define AppVersion "1.0.0"   // build.bat passes /DAppVersion=<version>
#endif
#define AppExe "OpenHEConfig.exe"

[Setup]
AppId={{3F9B2C64-8A1E-4D7B-B5C2-6E0F91A47D38}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=darsaliq00
AppPublisherURL=https://github.com/darsaliq00/open-he-config
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\assets\icon.ico
LicenseFile=..\LICENSE
OutputDir=..\release
OutputBaseFilename=OpenHEConfig-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
; the running app (it may sit in the tray) holds this mutex, so setup asks to close it
AppMutex=OpenHEConfig.SingleInstance

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\OpenHEConfig\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"

[INI]
; marker: tells the app it is installed, so it keeps user data in %APPDATA%
Filename: "{app}\installed.flag"; Section: "app"; Key: "installed"; String: "1"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExe}"; Flags: runhidden; RunOnceId: "KillApp"

[Registry]
; the app adds itself here when "Start with Windows" is on; remove that entry on uninstall
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "Open HE Config"; Flags: uninsdeletevalue

[UninstallDelete]
Type: files; Name: "{app}\installed.flag"
