const CHANGELOG = [
  {
    versao: 'v0.8',
    categorias: [
      {
        nome: 'Clima',
        cor: '#22d3ee',
        itens: [
          'Nova aba Clima com dados meteorológicos em tempo real (temperatura, umidade, vento, precipitação, nuvens e visibilidade).',
          'Radar de precipitação interativo centralizado na região da empresa.',
          'Previsão climática das próximas horas com cards visuais.',
          'Alertas automáticos via Telegram para chuva forte e severa, com verificação a cada 10 minutos.',
        ],
      },
      {
        nome: 'Frontend',
        cor: '#f59e0b',
        itens: [
          'Sidebar atualizada com link para a nova aba Clima.',
          'Cards do Clima com tema escuro integrado ao visual do dashboard.',
        ],
      },
      {
        nome: 'Backend',
        cor: '#a78bfa',
        itens: [
          'Novo módulo clima.py com endpoints para dados atuais, previsão e teste de alertas.',
          'Loop de verificação em background para disparo automático de alertas meteorológicos.',
        ],
      },
    ],
  },
  {
    versao: 'v0.7',
    categorias: [
      {
        nome: 'Acessos',
        cor: '#60a5fa',
        itens: [
          'Busca de dispositivos expandida para encontrar também por IP e MAC, não só por nome ou apelido.',
          'Corrigido travamento geral do sistema causado pela sincronização de acessos processando dados de forma bloqueante.',
          'Relatório para períodos longos (15 dias, 1 mês, 2 meses) não trava mais com erro de timeout.',
          'Tela de detalhe do dispositivo, que levava 20-25s para abrir, agora abre em poucos segundos.',
          'Categorização de domínios passou a cruzar com uma lista pública de rastreadores/anúncios, atualizada semanalmente.',
          'Ao filtrar o relatório só pela categoria Acessos, seções que não se aplicam deixam de aparecer.',
          'Ranking de produtividade consulta o controller Wi-Fi como fallback para resolver nomes "Desconhecido".',
          'Relatório de dispositivo ganhou novas seções e fuso horário corrigido nos gráficos.',
          'Gráfico de atividade por hora adicionado ao relatório de dispositivo, restrito ao horário comercial (seg-sex, 8h–18h).',
        ],
      },
      {
        nome: 'Dashboard e Estabilidade',
        cor: '#f59e0b',
        itens: [
          'Separação visual entre Operação (Servidores, Links, Backups) e Local (Access Points, Impressoras).',
          'Cartão "Uptime por categoria" corrigido para não listar mais Acessos como categoria plotável.',
          'Badge de status nos cartões não estoura mais os limites do cartão em telas estreitas.',
          'Categorização de eventos e títulos de ranking no painel corrigidos.',
          'Monitoramento de impressoras, VPNs e links estabilizado após a migração de servidor.',
        ],
      },
      {
        nome: 'Protheus',
        cor: '#38bdf8',
        itens: [
          'Health-check HTTP adicionado como fonte adicional de monitoramento, complementando o ICMP.',
        ],
      },
      {
        nome: 'VPNs',
        cor: '#a78bfa',
        itens: [
          'Status reflete a conexão real do túnel, em vez de estimativa por tráfego — evita marcar como offline uma VPN conectada mas ociosa.',
        ],
      },
      {
        nome: 'Infraestrutura',
        cor: '#94a3b8',
        itens: [
          'Plataforma migrada para um servidor novo (6 núcleos/12 threads, 16GB RAM, SSD interno).',
          'Capacidade do banco e do backend aumentada para aproveitar o hardware novo.',
          'Corrigida condição de corrida na checagem de status dos links do pfSense.',
          'Frequências de sincronização ajustadas pós-migração (cache, prewarm e sincronização de dados).',
          'Configuração de chave SSH do pfSense migrada para variável de ambiente, eliminando caminho fixo.',
          'Corrigido build do frontend que pulava dependências de compilação em ambiente de produção.',
        ],
      },
    ],
  },
  {
    versao: 'v0.6',
    categorias: [
      {
        nome: 'Protheus',
        cor: '#38bdf8',
        itens: [
          'Novo monitoramento via ICMP, com card próprio mostrando status, latência, uptime e ocorrências.',
          'Ping de referência ao Google em paralelo, para diferenciar queda isolada de instabilidade geral.',
          'Traceroute automático no alerta de queda confirmada, como diagnóstico principal de causa.',
          'Resumo periódico (08h/18h) comparando as fontes de verificação lado a lado.',
          'Alerta imediato após 5+ minutos offline confirmado por múltiplas origens.',
        ],
      },
      {
        nome: 'Ameaças de Rede',
        cor: '#f87171',
        itens: [
          'Nova aba dentro de Redes, liberada para todos os papéis (ações restritas a admin/super_admin).',
          'Corrigido gráfico de ameaças (cores e fuso horário) e integração da revisão com a severidade.',
          'Revisão de um alerta fica marcada de forma persistente por IP/assinatura.',
        ],
      },
      {
        nome: 'Redesign visual',
        cor: '#f472b6',
        itens: [
          'Backups: histórico e disponibilidade viraram lista com ícone de tipo e chips de uptime.',
          'Links, VPNs e VLANs viraram cards com indicador de status e gráfico embutido.',
          'Access Points, Automações, Auditoria e Usuários viraram listas, visual consistente.',
          'Servidores: barras de CPU/RAM/Disco redesenhadas, status de rede em todos os cards.',
        ],
      },
      {
        nome: 'Acessos',
        cor: '#60a5fa',
        itens: [
          'Busca na lista de dispositivos por nome ou apelido.',
          'Dispositivos agrupados por identidade lógica, evitando duplicar histórico.',
        ],
      },
      {
        nome: 'Consumo de Rede',
        cor: '#34d399',
        itens: [
          'Corrigido cálculo de pico sustentado que descartava picos rápidos isolados.',
          'Corrigido bug de login no controller Wi-Fi, com cooldown para evitar bloqueio da conta.',
        ],
      },
    ],
  },
  {
    versao: 'v0.5',
    categorias: [
      {
        nome: 'Relatórios',
        cor: '#fbbf24',
        itens: [
          'Novo módulo com períodos configuráveis de 24 horas a 12 meses, exportação em HTML e PDF, sem cortes de página entre seções.',
          'Seção de Acessos à Internet incluída também na exportação em HTML avulsa, com o mesmo conteúdo do PDF.',
        ],
      },
      {
        nome: 'Acessos',
        cor: '#60a5fa',
        itens: [
          'Nova seção nos Relatórios com volume total trafegado, categoria mais acessada e número de dispositivos monitorados no período.',
          'Gráfico de rosca com as categorias mais acessadas e o percentual de tráfego de cada uma.',
          'Duas tabelas de ranking de dispositivos por consumo (geral e pessoal), agora exibindo corretamente a categoria principal de cada equipamento.',
          'Filtro por categoria no relatório geral, independente para o ranking geral e o ranking pessoal — mostra o top 10 dispositivos daquela categoria específica.',
          'Botão "Revelar identidade" disponível apenas para dispositivos conectados via VPN, preservando o anonimato dos demais.',
          'Corrigido reconhecimento de dispositivos "Desconhecido" e duplicados, unificando o histórico de acesso de cada equipamento sob o nome real.',
          'Rotina diária que reclassifica domínios que caíram em "Outros", combinando regras próprias com uma lista pública de rastreadores/anúncios atualizada automaticamente toda semana.',
          'Agora é possível gerar um relatório (PDF ou HTML) de um dispositivo específico, com períodos de 1 hora, 1 dia, 15 dias, 1 mês ou 2 meses.',
          'Campo de apelido por dispositivo na tela de detalhe, visível e editável apenas por admin/super_admin (oculto por padrão), nunca exibido no relatório em PDF.',
        ],
      },
      {
        nome: 'Consumo de Rede',
        cor: '#34d399',
        itens: [
          'Tela ao vivo mostrando quem está consumindo mais banda agora, atualizando a cada 15 segundos.',
          'Alerta visual para consumo sustentado acima de 60 Mbps por 60 segundos ou mais — picos rápidos não disparam o alerta.',
          'Evento automático registrado no Feed de Alertas do Dashboard quando um dispositivo fica sustentado acima do limite, com a duração total e o valor de pico atingido.',
          'Alertas de consumo acima do limite no Feed do Dashboard agora são clicáveis e levam direto para o dispositivo correspondente na tela de Acessos.',
          'Nova visão consolidada dos últimos 7 dias, com média e pico de consumo por dispositivo.',
          'Gráfico histórico com marcação dos picos que ultrapassaram o limite.',
        ],
      },
      {
        nome: 'Monitoramento e Estabilidade',
        cor: '#94a3b8',
        itens: [
          'Novo alerta automático de uso elevado de CPU do servidor principal.',
          'Estabilidade: animação mais suave e eixo dinâmico, ajustando a escala automaticamente conforme os dados.',
        ],
      },
    ],
  },
  {
    versao: 'v0.4',
    categorias: [
      {
        nome: 'Dashboard',
        cor: '#f59e0b',
        itens: [
          'Nova seção "Visão Geral" no Dashboard: indicador de saúde geral (semáforo + frase + itens com problema), números resumidos (equipamentos monitorados, uptime médio hoje, eventos nas últimas 24h), gráfico de tendência das últimas 24h, estabilidade por categoria nos últimos 7 dias, e feed de alertas com histórico real classificado em 3 níveis de cor.',
          'Nova aba "Métricas Detalhadas" na barra lateral, expansível, reunindo Controller, Servidores, Impressoras, Backups e Redes em tela cheia, sem os cards de resumo do topo.',
          'Dashboard totalmente redesenhado: painel de status geral com alertas ativos e há quanto tempo cada um está no ar, comparativo de "melhor/pior desempenho da semana" entre as categorias, cards de cada categoria com contagem online/offline, mapa de calor mostrando a estabilidade dos últimos 7 dias, e feed de alertas com filtros (Todos, Críticos, Avisos, Resolvidos).',
          'Todos os alertas de infraestrutura agora ficam registrados no Feed do painel, não só no Telegram.',
          'Cards de resumo do Dashboard reduzidos de tamanho para ficarem mais compactos.',
        ],
      },
      {
        nome: 'Redes',
        cor: '#a78bfa',
        itens: [
          'Nova aba "Redes", unificando Links de Internet, VPNs, VLANs e Access Points numa única seção com sub-abas.',
          'VPNs e VLANs agora com status (online/offline), tráfego em tempo real e histórico de disponibilidade.',
          'Alertas automáticos no Telegram quando uma VPN ou VLAN cai ou volta a funcionar.',
        ],
      },
      {
        nome: 'Backups',
        cor: '#94a3b8',
        itens: [
          'Uptime de 30 dias para Backups, com separação automática por tipo (Full/Incremental) e texto mais claro sobre execuções.',
          'Backup do próprio sistema E-Ops agora monitorado.',
          'Corrigido nome do backup do E-Ops e formato de tamanho dos backups (MB/GB/TB automático).',
        ],
      },
      {
        nome: 'Diversos',
        cor: '#7c869c',
        itens: [
          'Corrigido nome e tempo de atividade exibidos do Controller.',
          'Novo favicon e nome da aba do navegador atualizados.',
          'Uptime semanal das impressoras agora considera só o horário comercial (seg-sex, 8h-18h), evitando que o modo de economia de energia fora do expediente seja contado como falha.',
        ],
      },
    ],
  },
  {
    versao: 'v0.3',
    categorias: [
      {
        nome: 'Contas e acesso',
        cor: '#60a5fa',
        itens: [
          'Novo: solicitação de acesso — quem ainda não tem conta pode se cadastrar com nome, e-mail corporativo e senha, e aguardar aprovação de um administrador.',
          'Novo: recuperação de senha por e-mail, caso o usuário esqueça a senha.',
          'Novo: login pode ser feito com o nome de usuário ou o e-mail corporativo.',
          'Novo: histórico de disponibilidade dos últimos 30 dias também para Servidores e Access Points (já existia para Links de Internet).',
        ],
      },
      {
        nome: 'Identidade visual',
        cor: '#f472b6',
        itens: [
          'Nova marca aplicada em todas as telas: entrada, menu lateral e cabeçalho.',
          'Criada uma versão da marca para o tema claro, com as letras em grafite e o "E" no vermelho institucional.',
          'Tela de entrada com layout novo em duas colunas: a marca, a descrição do sistema e os três recursos principais à esquerda; o formulário à direita.',
          'Fundo azul-noite com traços em curva na tela de entrada, no lugar do fundo preto anterior.',
          'Novo tema escuro: fundo azul-noite e cartões escuros, no lugar dos cartões cinza-claro. A tela ficou mais confortável para uso prolongado.',
          'Os números dos cartões agora têm a cor do estado — verde para normal, âmbar para alerta, vermelho para falha — em vez de todos brancos.',
          'Títulos dos gráficos com mais destaque.',
        ],
      },
      {
        nome: 'Menu lateral',
        cor: '#a78bfa',
        itens: [
          'Menu lateral reorganizado: Automações, Auditoria, Usuários e Solicitações agora ficam agrupados em "Administração".',
          'Menu lateral deixou de ser um painel flutuante e virou uma coluna fixa, encostada na borda e da altura inteira da tela.',
          'A marca subiu para o topo do menu lateral.',
          'Novo indicador "Sistema online" no menu, que muda de cor quando há alertas ou falhas.',
          'Menu recolhível: vira um trilho de ícones, e a marca encolhe para o símbolo do logo.',
          'Barra superior removida do painel. O acesso ao usuário passou para o canto superior direito do conteúdo.',
        ],
      },
      {
        nome: 'Correções',
        cor: '#f87171',
        itens: [
          'Corrigido: o ícone de cadeado do campo de senha que desaparecia ao clicar em "mostrar senha".',
          'Corrigido: o cartão de login que não atingia a largura configurada.',
          'Corrigido: os campos da tela de troca de senha que esticavam verticalmente.',
          'Corrigido: as barras de uso de recurso que ficavam invisíveis no tema escuro.',
          'Corrigido: status dos links de internet e histórico de disponibilidade, que haviam parado de aparecer no painel.',
          'Melhorado o contraste de textos de apoio que estavam abaixo do mínimo de leitura.',
          'Removido do monitoramento um servidor de backup que não existe mais na infraestrutura.',
        ],
      },
      {
        nome: 'Acessibilidade',
        cor: '#94a3b8',
        itens: [
          'Todos os textos revisados para atender ao mínimo de contraste de leitura; animações continuam desativadas automaticamente para quem configurou "reduzir movimento" no sistema operacional; botões e campos com rótulos para leitores de tela.',
        ],
      },
    ],
  },
  {
    versao: 'v0.2',
    categorias: [
      {
        nome: 'Identidade visual',
        cor: '#f472b6',
        itens: [
          'Nome do sistema atualizado de "InfraOps Center" para "Dashboard".',
          'Nova identidade visual: tema claro/escuro, menu lateral retrátil, e animações de entrada na tela de login.',
          'Ajustes visuais: menu lateral mais compacto, espaçamento entre itens, logo duplicada removida.',
          'Nova fonte no título da tela de login.',
        ],
      },
      {
        nome: 'Correções',
        cor: '#f87171',
        itens: [
          'Corrigida uma instabilidade de rede que afetava o acesso ao painel de forma intermitente.',
        ],
      },
    ],
  },
];

export default CHANGELOG;
