#ifndef AppVersion
  #define AppVersion "0.6.0"
#endif
#ifndef BundleDir
  #define BundleDir "..\dist\v0.6.0\LyricsStudio"
#endif
[Setup]
AppId={{3B2DDE8A-F81E-49F5-89E9-5A747A86305F}
AppName=Lyrics Studio
AppVersion={#AppVersion}
AppPublisher=Yasmin Mahr
AppPublisherURL=https://github.com/yasmin78-gif/LyricsStudio
AppSupportURL=https://github.com/yasmin78-gif/LyricsStudio/issues
AppUpdatesURL=https://github.com/yasmin78-gif/LyricsStudio/releases
DefaultDirName={localappdata}\Programs\Lyrics Studio
DefaultGroupName=Lyrics Studio
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir=..\dist\release-v{#AppVersion}
OutputBaseFilename=LyricsStudio-{#AppVersion}-Windows-x64-Setup
SetupIconFile=..\lyrics_studio\assets\icon.ico
UninstallDisplayIcon={app}\LyricsStudio.exe
LicenseFile=..\LICENSE
InfoBeforeFile=..\installer\INSTALL-HINWEISE.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=Lyrics Studio
[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; Flags: unchecked
[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Lyrics Studio"; Filename: "{app}\LyricsStudio.exe"
Name: "{autodesktop}\Lyrics Studio"; Filename: "{app}\LyricsStudio.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\LyricsStudio.exe"; Description: "Lyrics Studio starten"; Flags: nowait postinstall skipifsilent
