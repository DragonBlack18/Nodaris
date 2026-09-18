# NODARIS V2

Reescrita do NODARIS com foco em monitoramento local de rede em larga escala, código modular, UI PySide6 e atualização automática.

## Objetivos

- Preservar a identidade visual e os fluxos úteis do NODARIS atual.
- Refazer o backend sem reaproveitar o acoplamento legado.
- Monitorar milhares de IPs sem disparar milhares de processos simultaneamente.
- Usar o ping nativo do sistema operacional como engine padrão.
- Separar coleta, estado, persistência, API, UI e atualização.
- Permitir atualização automática sem reinstalação manual.

## Estado atual

A primeira etapa já contém:

- contrato visual migrado do NODARIS V1;
- Dashboard Admin;
- tela de equipamentos;
- formulário de equipamento;
- detalhe do equipamento;
- métricas de saúde e disponibilidade;
- gráfico de latência;
- Wallboard/TV;
- design tokens centralizados;
- probe ICMP via ping nativo;
- scheduler com fila temporal e workers limitados;
- arquitetura documentada para persistência, API e updater.

O backend da V1 não é utilizado pela V2.

## Preparar ambiente no Windows

Na raiz do repositório:

```powershell
git switch rewrite-v2
cd v2
.\scripts\setup_windows.ps1
```

O script cria `.venv` e instala dependências de runtime, desenvolvimento e build.

## Validar somente a parte visual

```powershell
.\.venv\Scripts\python.exe -m nodaris.ui.preview
```

Esse modo usa dados fictícios exclusivamente para validar as telas. Ele não executa o backend antigo e não grava dados.

## Abrir a UI limpa

```powershell
.\scripts\run_ui.ps1
```

A UI limpa inicia sem dados até o novo Core ser conectado.

## Estrutura

```text
v2/
├── pyproject.toml
├── ARCHITECTURE.md
├── scripts/
│   ├── setup_windows.ps1
│   └── run_ui.ps1
└── src/nodaris/
    ├── settings.py
    ├── probes/
    │   └── native_ping.py
    ├── monitoring/
    │   └── scheduler.py
    └── ui/
        ├── components/
        ├── dialogs/
        ├── theme/
        ├── windows/
        ├── main.py
        └── preview.py
```

## Regra de migração

A branch `rewrite-v2` é isolada da `main`. O sistema antigo continua intacto e serve apenas como referência funcional e visual durante a migração.

Código do backend antigo não deve ser copiado para os novos módulos. Regras úteis devem ser reimplementadas com contratos e testes novos.
