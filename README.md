# NODARIS

Sistema de monitoramento de disponibilidade de equipamentos de rede via ICMP.

O NODARIS é composto atualmente por:

- **NODARIS Core** — serviço responsável pelo monitoramento e API.
- **NODARIS Admin** — interface administrativa.
- **NODARIS TV** — wallboard para acompanhamento operacional.
- **NODARIS Watchdog** — mecanismo de supervisão e recuperação automática do Core.

> Alguns identificadores técnicos internos ainda utilizam o nome
> `monitorping` por compatibilidade. Consulte
> [docs/REBRANDING.md](docs/REBRANDING.md).

O NODARIS é um aplicativo desktop para Windows desenvolvido em Python para monitoramento contínuo de equipamentos e servidores por meio de ping. A aplicação acompanha o estado dos hosts em tempo real, identifica quedas e retornos de conexão, exibe indicadores em um dashboard moderno e envia notificações nativas do Windows. O aplicativo foi projetado para permanecer ativo 24 horas por dia. Ao clicar no botão de fechar, a janela é ocultada na bandeja do sistema, enquanto o monitoramento continua funcionando em segundo plano. O encerramento completo ocorre somente pelo menu de saída da bandeja. Principais recursos Monitoramento concorrente de vários endereços IP; Identificação de estados ONLINE, OFFLINE e AGUARDANDO; Nome e IP destacados em verde ou vermelho conforme o estado; Dashboard com total de equipamentos, online, offline, alertas e disponibilidade; Exibição de ping médio e tempo total offline; Notificações Toast nativas do Windows para quedas e retornos; Alertas sonoros opcionais; Janela compacta de monitoramento em tempo real; Execução contínua na bandeja do Windows; Inicialização automática com o Windows; Importação automática de configurações pelo arquivo ips.json; Importação e exportação de configurações em JSON; Importação e exportação de equipamentos em CSV; Histórico de eventos e logs rotativos; Persistência local com SQLite; Modo claro e modo escuro; Empacotamento com PyInstaller e instalação com Inno Setup. Tecnologias utilizadas Python, Tkinter, SQLite, ThreadPoolExecutor, PyInstaller, pygame-ce, pystray, Pillow, winotify e Inno Setup. Objetivo O NODARIS foi criado para oferecer uma solução simples, visual e confiável para acompanhar a disponibilidade de servidores, roteadores, switches, câmeras, impressoras, gateways e outros equipamentos de rede em ambientes Windows.
