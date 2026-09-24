[Setup]
AppId={{B7C5D61B-0C5E-4A0E-9A55-1D4A2C7E8F31}
AppName=ToDo POS
AppVersion=1.1.0
AppPublisher=ToDo
DefaultDirName={autopf}\ToDo POS
DefaultGroupName=ToDo POS
OutputDir=dist
OutputBaseFilename=ToDo-POS-1.1.0-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName=ToDo POS

[Files]
Source: "dist\ToDo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ToDo POS"; Filename: "{app}\ToDo.exe"
Name: "{autodesktop}\ToDo POS"; Filename: "{app}\ToDo.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Raccourcis supplémentaires:"; Flags: unchecked

[Run]
Filename: "{app}\ToDo.exe"; Description: "Lancer ToDo POS"; Flags: nowait postinstall skipifsilent
