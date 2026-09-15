# Política de retenção de dados

## Remoção de equipamento

Ao remover um equipamento do NODARIS:

- o IP é removido do catálogo e deixa de participar do monitoramento;
- um incidente ativo desse IP é encerrado no momento da remoção;
- probes históricos, incidentes encerrados e o último estado persistido não
  são apagados pela operação de remoção;
- os dados preservados continuam disponíveis para auditoria técnica, embora o
  equipamento removido deixe de aparecer no catálogo operacional.

Essa política evita perda silenciosa de evidência e vale para upgrades e
reinstalações. O instalador não deve apagar `%ProgramData%\NODARIS` sem uma
decisão explícita do usuário.

## Retenção temporal atual

- histórico de probes: janela móvel de 7 dias, conforme
  `PROBE_HISTORY_RETENTION_DAYS`;
- incidentes, eventos e estado persistido: sem expurgo automático nesta
  versão.

Uma ampliação da janela de probes ou uma política de expurgo adicional exige
decisão explícita de produto e não faz parte da remoção de um equipamento.
