; NODARIS 1.0 - instalador oficial

#define MyAppName "NODARIS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "NODARIS"
#define MyAppId "{{85D3D260-4F25-4CC3-A250-F65A67270B44}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\NODARIS
DefaultGroupName=NODARIS
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer
OutputBaseFilename=NODARIS_Setup_1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\branding\nodaris_icon.ico
UninstallDisplayName=NODARIS
UninstallDisplayIcon={app}\Admin\NODARIS Admin.exe
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopadmin"; Description: "Criar atalho do NODARIS Admin na area de trabalho"; GroupDescription: "Atalhos:"
Name: "desktoptv"; Description: "Criar atalho do NODARIS TV na area de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\NODARIS\config"; Permissions: users-modify
Name: "{commonappdata}\NODARIS\data"; Permissions: users-modify
Name: "{commonappdata}\NODARIS\logs"; Permissions: users-modify

[InstallDelete]
Type: filesandordirs; Name: "{app}\Core"
Type: filesandordirs; Name: "{app}\Admin"
Type: filesandordirs; Name: "{app}\TV"

[Files]
Source: "dist\NODARIS Core\*"; DestDir: "{app}\Core"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\NODARIS Admin\*"; DestDir: "{app}\Admin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\NODARIS TV\*"; DestDir: "{app}\TV"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "defaults\ips.json"; DestDir: "{commonappdata}\NODARIS\config"; Flags: ignoreversion onlyifdoesntexist
Source: "installer\install_tasks.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "installer\uninstall_tasks.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[Icons]
Name: "{group}\NODARIS Admin"; Filename: "{app}\Admin\NODARIS Admin.exe"
Name: "{group}\NODARIS TV"; Filename: "{app}\TV\NODARIS TV.exe"; Parameters: "--windowed"
Name: "{commondesktop}\NODARIS Admin"; Filename: "{app}\Admin\NODARIS Admin.exe"; Tasks: desktopadmin
Name: "{commondesktop}\NODARIS TV"; Filename: "{app}\TV\NODARIS TV.exe"; Parameters: "--windowed"; Tasks: desktoptv

[Run]
Filename: "{app}\Admin\NODARIS Admin.exe"; Description: "Abrir NODARIS Admin"; Flags: nowait postinstall skipifsilent

[Code]
function PowerShellPath(): String;
begin
  Result := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
end;

procedure EndTask(const TaskName: String);
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{sys}\schtasks.exe'),
    '/End /TN "' + TaskName + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  EndTask('NODARIS Watchdog');
  EndTask('NODARIS Core');
  Sleep(1500);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Parameters: String;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    ResultCode := -1;
    Parameters :=
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{app}\installer\install_tasks.ps1') +
      '" -InstallRoot "' + ExpandConstant('{app}') +
      '" -UserName "' + ExpandConstant('{username}') + '"';

    if (not Exec(
      PowerShellPath(),
      Parameters,
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    )) or (ResultCode <> 0) then
      RaiseException(
        'Falha ao criar as tarefas ou validar o NODARIS Core. Codigo: ' +
        IntToStr(ResultCode)
      );
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec(
      PowerShellPath(),
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      ExpandConstant('{app}\installer\uninstall_tasks.ps1') + '"',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    );
  end;
end;
