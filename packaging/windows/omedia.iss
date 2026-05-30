#ifndef OMEDIA_VERSION
#define OMEDIA_VERSION "0.1.0"
#endif
#define REPO_ROOT AddBackslash(SourcePath) + "..\.."

[Setup]
AppId={{8C44C751-91D6-4772-B8BB-AEC567B28CC5}
AppName=OMEDIA
AppVersion={#OMEDIA_VERSION}
AppPublisher=OMEDIA
DefaultDirName={autopf}\omedia
DefaultGroupName=OMEDIA
DisableProgramGroupPage=yes
OutputDir={#REPO_ROOT}\dist\installer
OutputBaseFilename=omedia-setup-v{#OMEDIA_VERSION}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName=OMEDIA
SourceDir={#REPO_ROOT}

[Dirs]
Name: "{commonappdata}\omedia"; Permissions: users-modify
Name: "{commonappdata}\omedia\data"; Permissions: users-modify
Name: "{commonappdata}\omedia\data\logs"; Permissions: users-modify
Name: "{commonappdata}\omedia\logs"; Permissions: users-modify
Name: "{commonappdata}\omedia\logs\service"; Permissions: users-modify

[Files]
Source: "dist\windows\omedia\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\windows\winsw\omedia-service.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "packaging\windows\omedia-service.xml"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\omedia-service.exe"; Parameters: "install"; StatusMsg: "Installing OMEDIA service..."; Flags: runhidden waituntilterminated
Filename: "{app}\omedia-service.exe"; Parameters: "start"; StatusMsg: "Starting OMEDIA service..."; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "{app}\omedia-service.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated skipifdoesntexist
Filename: "{app}\omedia-service.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated skipifdoesntexist
