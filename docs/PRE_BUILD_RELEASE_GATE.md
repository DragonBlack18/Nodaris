# NODARIS 1.0 — Gate pré-build

Data da validação: 15 de setembro de 2026.

## Decisão

O código-fonte e o candidato de build passaram em todos os gates que podem ser
executados nesta estação. Não há bloqueador CRITICAL ou HIGH conhecido no
source, nos builds one-dir ou no instalador compilado.

O release público permanece **condicional** até o teste do instalador em uma
máquina ou VM Windows limpa, sem Python, ambiente virtual ou árvore do projeto.
Essa restrição é deliberada: executar os binários fora do projeto nesta estação
é uma simulação forte, mas não prova a ausência física de dependências externas.

## Candidato validado

- Instalador: `installer/NODARIS_Setup_1.0.0.exe`
- Tamanho: `85.570.506` bytes
- SHA-256: `EBD5CE862BDCADFCFD42E63BA9FC62D567E7A227875DAB2F87BE69873630D9E4`
- Builds independentes: `NODARIS Core`, `NODARIS Admin` e `NODARIS TV`
- Estratégia: PyInstaller one-dir + Inno Setup

## Resultado da correção mestra

| Gate | Resultado | Evidência principal |
| --- | --- | --- |
| 11.0 — baseline Git | PASS | commit inicial e tag `pre-release-audit` |
| 11.1 — Watchdog preso | PASS | substituição segura coberta por testes e recuperação operacional |
| 11.2 — paths persistentes | PASS | modo frozen usa `ProgramData`; source preserva paths de desenvolvimento |
| 11.3 — SQLite | PASS | conexões fechadas deterministicamente; `quick_check=ok` |
| 11.4 — isolamento de probes | PASS | exceção de um probe não aborta o lote |
| 11.5 — latência backend | PASS | inválidos rejeitados e zero real preservado |
| 11.6 — histórico legado | PASS | `OFFLINE 0 ms` não contamina métricas |
| 11.7 — máquina de estados | PASS | regra oficial: terceira falha confirma `OFFLINE` |
| 11.8 — CRUD/maintenance | PASS | criação preserva `maintenance=true` |
| 11.9 — lifespan | PASS | `MonitorEngine.stop()` protegido por `finally` |
| 11.10 — rede | PASS | host, porta e URL centralizados |
| 11.11 — retenção | PASS | remoção fecha incidente e preserva histórico |
| 11.12 — requirements | PASS | instalação e execução em `.venv_clean` |
| 11.13 — specs | PASS | três entry points independentes |
| 11.14 — Qt/assets | PASS | `qwindows.dll` e quatro assets oficiais presentes |
| 11.15 — migrações | PASS | config e banco versionados, idempotentes e transacionais |
| 11.16 — installer | PASS local | compilação e contrato passaram; instalação elevada fica para VM limpa |
| 11.17 — documentação | PASS | arquitetura atual documentada |
| 11.18 — DPI | PASS | 100%, 125% e 150%, dimensões padrão e mínimas |
| 11.19 — máquina limpa | PENDENTE EXTERNO | simulação isolada passou; máquina literalmente limpa ainda necessária |
| 11.20 — regressão final | PASS local | evidências abaixo |

## Regressão final executada

- `compileall api core desktop`: PASS
- Imports ativos: `42/42` (a auditoria antiga tinha 41; o módulo adicional é o
  sistema de migrações)
- Testes automatizados: `78/78`
- Regressão do gráfico: `17/17`, incluída na suíte
- Verificador dos três builds: PASS
- SQLite: `quick_check=ok`, `foreign_key_check=[]`, schema version `1`
- Listener: exatamente um processo em `127.0.0.1:8765`
- Health: `ok`, engine `running`, operacional `healthy`, `stale=false`
- NativePing real: `127.0.0.1` ONLINE via `ping.exe`
- Parser NativePing: PT-BR e EN, incluindo `<1ms`: PASS
- Carga concorrente: `500/500` respostas HTTP 200 com JSON válido
- DPI smoke: 100%, 125% e 150%: PASS
- Core congelado em staging externo: PASS
- Seed congelado: config version `1`, zero equipamentos de desenvolvimento
- Banco congelado: schema version `1`
- Admin e TV congelados: processos responsivos contra o Core congelado
- Core congelado em modo `--watchdog`: exit code `0`, sem listener duplicado
- Core operacional de desenvolvimento restaurado após o teste: `healthy`, quatro
  equipamentos configurados

Os avisos gerados pelo PyInstaller foram revisados. Eles se referem a módulos
condicionais de outros sistemas operacionais ou extras não utilizados pelo
NODARIS (por exemplo `fcntl`, `pwd`, `uvloop`, `trio`, `gunicorn` e backends HTTP
opcionais). O smoke dos executáveis e o verificador de recursos são os gates de
runtime correspondentes.

## Gate obrigatório em Windows limpo

Antes de publicar o instalador:

1. Usar uma VM Windows sem Python, `.venv`, VS Code ou fonte do NODARIS.
2. Conferir o SHA-256 do instalador com o valor registrado acima.
3. Instalar o NODARIS como administrador.
4. Confirmar as tarefas `NODARIS Core` e `NODARIS Watchdog`.
5. Confirmar listener único em `127.0.0.1:8765` e `/health` saudável.
6. Abrir Admin e TV pelos atalhos e validar conexão e branding.
7. Encerrar o PID listener e comprovar recuperação automática sem intervenção.
8. Fazer uma atualização sobre a instalação existente e confirmar preservação de
   configuração, banco e histórico.
9. Desinstalar e confirmar remoção de tarefas e binários.
10. Confirmar que `%ProgramData%\NODARIS` foi preservado pelo uninstall.

Somente depois desses dez itens o NODARIS 1.0 pode mudar de **candidato** para
**release aprovado**.
