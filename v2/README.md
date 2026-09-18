# NODARIS V2

Reescrita do NODARIS com foco em monitoramento local de rede em larga escala, código modular, UI PySide6 e atualização automática.

## Objetivos

- Preservar a identidade visual e os fluxos úteis do NODARIS atual.
- Refazer o backend sem reaproveitar o acoplamento legado.
- Monitorar milhares de IPs sem disparar milhares de processos simultaneamente.
- Usar o ping nativo do sistema operacional como engine padrão.
- Separar coleta, estado, persistência, API, UI e atualização.
- Permitir atualização automática sem reinstalação manual.

## Estrutura inicial

```text
v2/
├── pyproject.toml
├── ARCHITECTURE.md
├── src/nodaris/
│   ├── settings.py
│   ├── probes/
│   │   └── native_ping.py
│   ├── monitoring/
│   │   └── scheduler.py
│   └── ui/
│       └── theme/
│           └── tokens.py
└── tests/
```

A branch `rewrite-v2` é isolada da `main`. O sistema antigo continua intacto e serve apenas como referência funcional e visual durante a migração.
