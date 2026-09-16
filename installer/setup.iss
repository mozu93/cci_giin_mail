; 議員メール配信アプリ Inno Setup スクリプト
#ifndef AppVersion
#define AppVersion "0.0.0"
#endif

[Setup]
; AppId は旧名称のまま固定する（変更すると既存インストールが別アプリ扱いになる）
AppId=商工会議所メール配信システム
AppName=議員メール配信アプリ
AppVersion={#AppVersion}
AppPublisher=mozu93
AppPublisherURL=https://github.com/mozu93/cci_giin_mail
AppSupportURL=https://github.com/mozu93/cci_giin_mail/issues
DefaultDirName={localappdata}\CCIMail
DefaultGroupName=議員メール配信アプリ
DisableDirPage=yes
OutputDir={#SourcePath}\..\installer_output
OutputBaseFilename=CCIMail_Setup_{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[InstallDelete]
; 旧名称（商工会議所メール配信システム）のショートカットを削除する
Type: filesandordirs; Name: "{autoprograms}\商工会議所メール配信システム"
Type: files; Name: "{autodesktop}\商工会議所メール配信システム.lnk"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加タスク:"

[Files]
Source: "{#SourcePath}\..\dist\CCIMail\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\議員メール配信アプリ"; Filename: "{app}\CCIMail.exe"
Name: "{group}\アンインストール"; Filename: "{uninstallexe}"
Name: "{autodesktop}\議員メール配信アプリ"; Filename: "{app}\CCIMail.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CCIMail.exe"; Description: "議員メール配信アプリを起動する"; Flags: nowait postinstall skipifsilent
