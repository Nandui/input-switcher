[Setup]
AppName=Input Switcher
AppVersion=1.0.0
AppPublisher=Nandui
AppPublisherURL=https://github.com/Nandui/input-switcher
AppSupportURL=https://github.com/Nandui/input-switcher/issues

; Install per-user — no admin prompt
PrivilegesRequired=lowest
DefaultDirName={localappdata}\InputSwitcher
DefaultGroupName=Input Switcher
DisableProgramGroupPage=yes

; Output
OutputDir=installer
OutputBaseFilename=InputSwitcher-Setup
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Metadata shown in Add/Remove Programs
UninstallDisplayName=Input Switcher
UninstallDisplayIcon={app}\InputSwitcher.exe
VersionInfoVersion=1.0.0
VersionInfoDescription=MSI 321URX Input Switcher
VersionInfoCompany=Nandui

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\InputSwitcher.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Input Switcher";      Filename: "{app}\InputSwitcher.exe"
Name: "{group}\Uninstall";           Filename: "{uninstallexe}"
Name: "{autodesktop}\Input Switcher"; Filename: "{app}\InputSwitcher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\InputSwitcher.exe"; \
  Description: "Launch Input Switcher"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files;     Name: "{app}\config.json"
Type: dirifempty; Name: "{app}"
