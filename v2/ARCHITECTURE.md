# NODARIS V2 — Arquitetura

## Princípio principal

O número de IPs cadastrados não pode definir o número de processos, threads,
conexões ou gravações simultâneas. Toda camada de I/O possui limite e backpressure.

## Módulos

```text
nodaris/
├── domain/          # entidades e regras de estado
├── probes/          # ping nativo e futuros providers
├── monitoring/      # scheduler, workers e agregação
├── storage/         # SQLite, writer único e repositórios
├── api/             # FastAPI REST + WebSocket
├── ui/              # Admin e TV em PySide6
├── updater/         # manifest, download, verificação e staging
├── launcher/        # inicia a versão ativa e executa rollback
└── infra/           # paths, logs, métricas e health
```

## Escala

O V1 executa uma varredura global, cria uma coroutine por equipamento e usa um
semaphore para limitar os probes. Na V2, cada equipamento possui um `next_due`
e entra numa fila temporal. Um conjunto fixo de workers consome essa fila.

Consequências:

- 3.000 equipamentos não viram 3.000 processos simultâneos.
- picos de CPU e criação de processos são limitados.
- equipamento lento não bloqueia a UI.
- atraso/backlog pode ser medido.
- o sistema pode reduzir ou aumentar a concorrência de forma controlada.

## Persistência

Não persistir todo ping bruto indefinidamente.

Para 3.000 IPs:

- a cada 5 s: 51.840.000 probes/dia;
- a cada 10 s: 25.920.000 probes/dia.

A V2 deve persistir:

1. estado atual;
2. mudanças de estado;
3. incidentes;
4. eventos;
5. agregados de latência/disponibilidade;
6. uma janela curta opcional de probes brutos para diagnóstico.

SQLite permanece válido para uma instalação local se houver writer único,
transações em lote e WAL. A interface de storage será separada para permitir
PostgreSQL no futuro sem alterar o monitoramento.

## API e UI

O Core é o único dono do monitoramento e da persistência.

Admin e TV:

- não executam ping;
- não acessam SQLite;
- consomem snapshot inicial por REST;
- recebem deltas por WebSocket;
- podem reconectar sem reiniciar o Core.

## Contrato visual importado do V1

Preservar:

- Dashboard Admin;
- cards TOTAL / ONLINE / SUSPECT / OFFLINE / RECOVERING;
- tela Equipamentos;
- formulário de equipamento;
- detalhe do equipamento;
- gráfico de latência;
- incidentes;
- Wallboard/TV;
- identidade visual escura e design tokens.

Refatorar:

- arquivos de janela muito grandes;
- polling duplicado de 1–3 s;
- estilos gigantes no mesmo módulo;
- responsabilidades de rede dentro das janelas.

## Atualização automática

O executável principal não tenta sobrescrever a si próprio.

Estrutura prevista:

```text
%ProgramFiles%/NODARIS/
├── launcher/
├── releases/
│   ├── 2.0.0/
│   └── 2.0.1/
└── current.json

%ProgramData%/NODARIS/
├── config/
├── data/
├── logs/
└── updates/
```

Fluxo:

1. Core consulta um manifest de release.
2. Baixa o pacote para staging.
3. Valida SHA-256 e assinatura.
4. Updater/Launcher encerra os processos da versão anterior.
5. Ativa a pasta nova por `current.json`.
6. Inicia e valida `/health`.
7. Se falhar, volta automaticamente para a release anterior.

Assim a aplicação atualiza sem reinstalação manual e sem misturar dados do
usuário com os binários.
