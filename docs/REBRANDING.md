# NODARIS — Política de Rebranding e Compatibilidade

## Produto

Nome oficial do produto:

**NODARIS**

Aplicações visíveis:

- NODARIS Admin
- NODARIS TV
- NODARIS Core
- NODARIS Watchdog

Identificadores Win32:

- `NODARIS.Admin`
- `NODARIS.TV`

Tarefas agendadas:

- `NODARIS Core`
- `NODARIS Watchdog`

## Identidade visual

Assets oficiais:

```text
assets/branding/
├── nodaris_icon.ico
├── nodaris_icon.png
├── nodaris_icon_256.png
└── nodaris_logo_reference.jpg
```

A resolução dos assets é centralizada em:

```text
desktop/branding.py
```

O helper suporta:

- execução em desenvolvimento;
- empacotamento futuro via PyInstaller;
- `sys._MEIPASS`.

O `QIcon` deve ser materializado somente após existir uma instância válida de
`QApplication` ou `QGuiApplication`. Não usar testes de `QIcon` antes da
criação da aplicação Qt.

## Identificadores técnicos preservados

Os identificadores abaixo permanecem intencionalmente com o nome interno
antigo por compatibilidade:

```text
service: monitorping-api

mutex:
Global\MonitorPingCoreSingleton

logger namespace:
monitorping.*

logs:
monitorping-core.log
monitorping-engine.log
monitorping-watchdog.log
monitorping-error.log

watchdog state:
monitorping_watchdog_state.json

database:
monitor_api.db
```

Esses nomes não representam a marca exibida ao usuário. Não devem ser
renomeados apenas por motivo visual. Uma alteração futura nesses contratos
exige migração específica e validação de compatibilidade.

## Contratos ativos de produto

```text
Scheduled Task:
NODARIS Core

Scheduled Task:
NODARIS Watchdog

Watchdog CORE_TASK_NAME:
NODARIS Core

Admin:
NODARIS Admin

TV:
NODARIS TV

OpenAPI:
NODARIS API
```

## Estrutura e entradas

A estrutura dos módulos permanece:

```text
api/
core/
desktop/
```

Não renomear módulos apenas por rebranding.

Entradas atuais:

```text
python -m core.main
python -m core.watchdog
desktop/main.py
desktop/tv_main.py
```

Os executáveis futuros devem encapsular essas entradas sem alterar os módulos
internos.

## Arquivos legados

Os seguintes arquivos pertencem à arquitetura antiga e não devem ser usados
no empacotamento novo:

```text
monitorping.py
build_windows.bat
MonitorPing.spec
MonitorPing.iss
```

`MonitorPing.spec` empacota a aplicação monolítica antiga e não representa a
arquitetura atual Core/Admin/TV. A etapa de executáveis NODARIS criará
especificações próprias.

Também são referências ou rollback e não representam a arquitetura ativa:

```text
wallboard_window_13_2A_backup.py
desktop/process_manager.py
```

## Regra para novos nomes

Novos textos visíveis ao usuário devem utilizar:

```text
NODARIS
```

Novos nomes técnicos devem evitar introduzir identificadores `MonitorPing`
adicionais. Os identificadores `monitorping-*` existentes só permanecem quando
fazem parte dos contratos de compatibilidade documentados neste arquivo.
