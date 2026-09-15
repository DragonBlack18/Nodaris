; MonitorPing - instalador Inno Setup
; Compile este arquivo depois de gerar dist\MonitorPing\MonitorPing.exe

#define MyAppName "MonitorPing"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MonitorPing"
#define MyAppExeName "MonitorPing.exe"

[Setup]
AppId={{D5C4A2D7-9B3A-4E84-AF7D-6D9D2E7B9F21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=MonitorPing_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}

; Para adicionar um ícone, descomente a linha abaixo e coloque monitorping.ico nesta pasta.
; SetupIconFile=monitorping.ico

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"
Name: "startup"; Description: "Iniciar o MonitorPing com o Windows"; GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
; O conteúdo completo da pasta onedir gerada pelo PyInstaller.
Source: "dist\MonitorPing\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Preserva os equipamentos do usuário em reinstalações.
Source: "ips.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\MonitorPing"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\MonitorPing"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\MonitorPing"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar o MonitorPing"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove apenas arquivos temporários do aplicativo.
; O banco e os logs são preservados para não apagar os dados do usuário.
Type: filesandordirs; Name: "{app}\_internal"
