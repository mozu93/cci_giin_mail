; 商工会議所メール配信システム Inno Setup スクリプト
#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

[Setup]
AppName=商工会議所メール配信システム
AppVersion={#AppVersion}
AppPublisher=mozu93
AppPublisherURL=https://github.com/mozu93/cci_giin_mail
AppSupportURL=https://github.com/mozu93/cci_giin_mail/issues
DefaultDirName={localappdata}\CCIMail
DefaultGroupName=商工会議所メール配信システム
DisableDirPage=yes
OutputDir={#SourcePath}\..\installer_output
OutputBaseFilename=CCIMail_Setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"

[Files]
Source: "{#SourcePath}\..\dist\CCIMail\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\商工会議所メール配信システム"; Filename: "{app}\CCIMail.exe"
Name: "{group}\アンインストール"; Filename: "{uninstallexe}"
Name: "{autodesktop}\商工会議所メール配信システム"; Filename: "{app}\CCIMail.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CCIMail.exe"; Description: "商工会議所メール配信システムを起動する"; Flags: nowait postinstall skipifsilent
