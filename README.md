# NODARIS

O NODARIS monitora equipamentos de rede por ICMP no Windows e mantém uma visão operacional compartilhada entre o Admin e a TV.

## Arquitetura

- **NODARIS Core**: API FastAPI, `MonitorEngine`, máquina de estados e persistência.
- **NODARIS Admin**: cliente PySide6 para dashboard, detalhes e CRUD de equipamentos.
- **NODARIS TV**: wallboard PySide6 independente, otimizado para leitura à distância.
- **NODARIS Watchdog**: execução periódica que valida `/health` e recupera o Core.
- **SQLite**: histórico de probes, eventos, incidentes e último estado conhecido.
- **NativePingClient**: probes ICMP pelo `ping.exe` nativo do Windows.

O Admin e a TV nunca iniciam nem encerram o Core. As duas interfaces são clientes da API local em `http://127.0.0.1:8765` e se reconectam automaticamente após uma recuperação.

## Estados monitorados

O Core consolida os probes nos estados `ONLINE`, `SUSPECT`, `OFFLINE`, `RECOVERING` e `MAINTENANCE`. A regra atual declara `OFFLINE` após três falhas consecutivas e retorna a `ONLINE` após dois sucessos consecutivos.

O endpoint `/health` também diferencia um processo meramente ativo de um sistema operacionalmente saudável, incluindo atraso de scan, estado da tarefa do engine e erros consecutivos.

## Instalação no Windows

O instalador oficial é gerado em:

```text
installer/NODARIS_Setup_1.0.0.exe
```

Ele instala três aplicações independentes em `%ProgramFiles%\NODARIS`, cria as tarefas `NODARIS Core` e `NODARIS Watchdog`, inicia o Core e valida o health check. O arquivo inicial de equipamentos é vazio; uma configuração existente nunca é substituída durante update ou reinstalação.

Dados persistentes ficam fora da pasta dos executáveis:

```text
%ProgramData%\NODARIS\
├── config\ips.json
├── data\monitor_api.db
├── data\monitorping_watchdog_state.json
└── logs\
    ├── monitorping-core.log
    ├── monitorping-engine.log
    ├── monitorping-watchdog.log
    └── monitorping-error.log
```

O uninstall remove tarefas e binários, mas preserva `%ProgramData%\NODARIS` para evitar perda de configuração e histórico.

## Desenvolvimento

Requisitos: Windows 10/11 x64 e Python compatível com as versões declaradas no projeto.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
```

No modo fonte, `ips.json`, `data/` e `logs/` permanecem na raiz do projeto. Inicie cada componente separadamente:

```powershell
.\.venv\Scripts\python.exe -u -m core.main
.\.venv\Scripts\python.exe -u -m desktop.main
.\.venv\Scripts\python.exe -u -m desktop.tv_main --windowed
```

O Watchdog pode ser validado manualmente com:

```powershell
.\.venv\Scripts\python.exe -m core.watchdog
```

## Testes

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall api core desktop -q
```

Validação dos artefatos one-dir:

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_build.py
```

## Build

Instale também as dependências de build:

```powershell
.\.venv\Scripts\pip.exe install -r requirements-build.txt
```

Gere os três executáveis:

```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean .\NODARIS-Core.spec
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean .\NODARIS-Admin.spec
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean .\NODARIS-TV.spec
```

Compile `NODARIS.iss` com Inno Setup 6 para gerar o instalador.

## Compatibilidade

Alguns identificadores internos continuam com o nome histórico `monitorping` para preservar contratos, logs, banco e clientes existentes. Eles não são marca visível e não devem ser renomeados sem migração específica. Consulte [docs/REBRANDING.md](docs/REBRANDING.md) e [docs/DATA_RETENTION.md](docs/DATA_RETENTION.md).
