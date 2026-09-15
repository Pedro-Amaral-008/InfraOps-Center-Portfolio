import { useState, useEffect, useCallback } from 'react';

const API_URL = '';

const JANELAS_LISTA = [
  { label: '1h', horas: 1 },
  { label: '3h', horas: 3 },
  { label: '24h', horas: 24 },
  { label: '7 dias', horas: 168 },
];

const JANELAS_GRAFICO = [
  { label: '1 hora', dias: 1 },
  { label: '1 dia', dias: 2 },
  { label: '15 dias', dias: 15 },
  { label: '1 mês', dias: 30 },
  { label: '2 meses', dias: 60 },
];

function tempoRelativo(iso) {
  if (!iso) return '—';
  const agora = new Date();
  const data = new Date(iso);
  const diffMs = agora - data;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'agora mesmo';
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) {
    const restoMin = diffMin % 60;
    return restoMin > 0 ? `há ${diffH}h ${restoMin}min` : `há ${diffH}h`;
  }
  const diffDias = Math.floor(diffH / 24);
  return `há ${diffDias} dia${diffDias > 1 ? 's' : ''}`;
}

function formatarDataCurta(iso) {
  // Forca interpretacao no fuso local (sem isso, "YYYY-MM-DD" e
  // interpretado como meia-noite UTC e pode "voltar" um dia no Brasil)
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

function barraPath(x, largura, yTopo, yBase, raio) {
  const r = Math.min(raio, largura / 2, Math.max(0, yBase - yTopo));
  const direita = x + largura;
  if (r <= 0) {
    return `M${x},${yTopo} L${direita},${yTopo} L${direita},${yBase} L${x},${yBase} Z`;
  }
  return `M${x},${yTopo + r} Q${x},${yTopo} ${x + r},${yTopo} L${direita - r},${yTopo} Q${direita},${yTopo} ${direita},${yTopo + r} L${direita},${yBase} L${x},${yBase} Z`;
}

export default function AmeacasPotenciais({ token, role }) {
  const [janelaListaIdx, setJanelaListaIdx] = useState(2);
  const [janelaGraficoIdx, setJanelaGraficoIdx] = useState(2);
  const [filtroOrigem, setFiltroOrigem] = useState('todas');
  const [resumo, setResumo] = useState(null);
  const [grafico, setGrafico] = useState([]);
  const [lista, setLista] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [tooltip, setTooltip] = useState({ visivel: false, x: 0, y: 0, texto: '', confirmado: false });

  const horasLista = JANELAS_LISTA[janelaListaIdx].horas;
  const diasGrafico = JANELAS_GRAFICO[janelaGraficoIdx].dias;
  const podeGerenciar = role === 'admin' || role === 'super_admin';

  const carregar = useCallback(async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [rResumo, rGrafico, rLista] = await Promise.all([
        fetch(`${API_URL}/dashboard/ameacas/resumo?horas=${horasLista}`, { headers }),
        fetch(`${API_URL}/dashboard/ameacas/grafico?dias=${diasGrafico}`, { headers }),
        fetch(`${API_URL}/dashboard/ameacas/lista?horas=${horasLista}`, { headers }),
      ]);
      if (rResumo.ok) setResumo(await rResumo.json());
      if (rGrafico.ok) setGrafico(await rGrafico.json());
      if (rLista.ok) setLista(await rLista.json());
    } catch (erro) {
      console.error('Erro ao carregar ameaças:', erro);
    } finally {
      setCarregando(false);
    }
  }, [token, horasLista, diasGrafico]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function handleBloquear(mac) {
    await fetch(`${API_URL}/dashboard/ameacas/dispositivo/${mac}/bloquear`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    carregar();
  }

  async function handleDesbloquear(mac) {
    await fetch(`${API_URL}/dashboard/ameacas/dispositivo/${mac}/desbloquear`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    carregar();
  }

  async function handleRevisao(alertaId, valor) {
    await fetch(`${API_URL}/dashboard/ameacas/alerta/${alertaId}/revisao?valor=${valor}`, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}` },
    });
    carregar();
  }

  const listaFiltrada = lista.filter((item) => filtroOrigem === 'todas' || item.origem === filtroOrigem);

  // ---- construção do gráfico SVG ----
  const larguraTotal = 940;
  const margemEsq = 0;
  const yTopoArea = 15;
  const yBaseArea = 155;
  const maxValorBruto = Math.max(1, ...grafico.map((g) => g.total || 0));
  const niceMax = Math.max(3, Math.ceil(maxValorBruto / 3) * 3);
  const n = grafico.length || 1;
  const larguraUtil = larguraTotal - margemEsq;
  const slot = larguraUtil / n;
  const larguraBarra = Math.min(14, slot * 0.3);

  function corDaBarra(cor) {
    if (cor === 'critico') return 'ameacas-barra-critico';
    if (cor === 'atencao') return 'ameacas-barra-atencao';
    if (cor === 'resolvido') return 'ameacas-barra-resolvido';
    return 'ameacas-barra-vazio';
  }

  const pontosGrafico = grafico.map((g, i) => {
    const altura = ((g.total || 0) / niceMax) * (yBaseArea - yTopoArea);
    const yTopo = yBaseArea - altura;
    const x = margemEsq + slot * i + (slot - larguraBarra) / 2;
    return {
      ...g,
      x,
      yTopo,
      classe: corDaBarra(g.cor),
      path: barraPath(x, larguraBarra, yTopo, yBaseArea, 3),
    };
  });

  const ticks = [0, niceMax / 3, (niceMax * 2) / 3, niceMax];

  // ---- taxa de revisão a partir da lista (aproximação por período) ----
  const alertasSuricata = lista.filter((i) => i.origem === 'suricata');
  const totalOcorrencias = alertasSuricata.reduce((s, i) => s + (i.ocorrencias || 0), 0);
  const confirmados = alertasSuricata.filter((i) => i.revisao === 'confirmado').length;
  const falsos = alertasSuricata.filter((i) => i.revisao === 'falso_positivo').length;
  const pendentes = alertasSuricata.filter((i) => i.revisao === 'pendente').length;
  const taxaFalsoPositivo = confirmados + falsos > 0 ? Math.round((falsos / (confirmados + falsos)) * 100) : null;

  const LABEL_COR = { critico: 'crítico', atencao: 'atenção', resolvido: 'resolvido', vazio: 'sem detecção' };

  function mostrarTooltip(ev, ponto) {
    const rect = ev.currentTarget.closest('svg').parentElement.getBoundingClientRect();
    setTooltip({
      visivel: true,
      x: ev.clientX - rect.left,
      y: ev.clientY - rect.top - 10,
      data: formatarDataCurta(ponto.data),
      valor: ponto.total,
      cor: ponto.cor,
    });
  }

  function moverTooltip(ev) {
    const rect = ev.currentTarget.closest('svg').parentElement.getBoundingClientRect();
    setTooltip((t) => ({ ...t, x: ev.clientX - rect.left, y: ev.clientY - rect.top - 10 }));
  }

  function esconderTooltip() {
    setTooltip((t) => ({ ...t, visivel: false }));
  }

  return (
    <div className="ameacas-mockup">
      <style>{`
        .ameacas-mockup {
          --bg-panel: #1b1e27;
          --bg-panel-2: #20232e;
          --border: #2c303c;
          --text: #e4e6eb;
          --text-dim: #9aa0ac;
          --accent: #5b8def;
          --red: #ff5555;
          --red-bg: rgba(220, 50, 50, 0.12);
          --orange: #f5a623;
          --orange-bg: rgba(245, 166, 35, 0.12);
          --green: #2ecc71;
          color: var(--text);
          font-size: 14px;
        }
        .ameacas-mockup * { box-sizing: border-box; }
        .ameacas-header-row {
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
        }
        .ameacas-sub { color: var(--text-dim); font-size: 13px; margin-top: 4px; }
        .ameacas-janela { display: flex; gap: 6px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: 8px; padding: 4px; }
        .ameacas-janela button {
          background: transparent; border: none; color: var(--text-dim);
          padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer;
        }
        .ameacas-janela button.ativo { background: var(--accent); color: white; }
        .ameacas-janela.small button { padding: 5px 11px; font-size: 12px; }
        .ameacas-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
        .ameacas-card {
          background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px;
          box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset, 0 6px 14px rgba(0,0,0,0.18);
        }
        .ameacas-card .valor { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }
        .ameacas-card .label { color: var(--text-dim); font-size: 12px; margin-top: 4px; }
        .ameacas-card.critico .valor { color: var(--red); }
        .ameacas-card.atencao .valor { color: var(--orange); }
        .ameacas-card.ok .valor { color: var(--green); }
        .ameacas-painel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-bottom: 20px; }
        .ameacas-painel-titulo {
          padding: 14px 18px; border-bottom: 1px solid var(--border); font-weight: 600;
          display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
        }
        .ameacas-filtro-select { background: var(--bg-panel-2); border: 1px solid var(--border); color: var(--text); padding: 5px 10px; border-radius: 6px; font-size: 12px; }
        .ameacas-mockup table { width: 100%; border-collapse: collapse; }
        .ameacas-mockup thead th {
          text-align: left; padding: 10px 18px; font-size: 11px; text-transform: uppercase;
          letter-spacing: 0.04em; color: var(--text-dim); border-bottom: 1px solid var(--border);
        }
        .ameacas-mockup tbody td { padding: 12px 18px; border-bottom: 1px solid var(--border); vertical-align: top; }
        .ameacas-mockup tbody tr:last-child td { border-bottom: none; }
        .ameacas-mockup tbody tr:hover { background: rgba(255,255,255,0.02); }
        .ameacas-dispositivo-nome { font-weight: 600; }
        .ameacas-dispositivo-ip { color: var(--text-dim); font-size: 12px; }
        .ameacas-badge { display: inline-block; padding: 3px 9px; border-radius: 5px; font-size: 11px; font-weight: 600; }
        .ameacas-badge.critico { background: var(--red-bg); color: var(--red); }
        .ameacas-badge.atencao { background: var(--orange-bg); color: var(--orange); }
        .ameacas-badge.resolvido { background: rgba(46,204,113,0.12); color: var(--green); }
        .ameacas-badge.origem { background: rgba(91,141,239,0.12); color: var(--accent); font-weight: 500; }
        .ameacas-detalhe { max-width: 340px; }
        .ameacas-detalhe .principal { color: var(--text); }
        .ameacas-detalhe .secundario { color: var(--text-dim); font-size: 12px; margin-top: 2px; }
        .ameacas-contagem { font-weight: 700; font-size: 15px; }
        .ameacas-acoes { display: flex; gap: 6px; flex-wrap: wrap; }
        .ameacas-btn {
          border: 1px solid var(--border); background: var(--bg-panel-2); color: var(--text);
          padding: 6px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; white-space: nowrap;
        }
        .ameacas-btn:hover { border-color: var(--accent); }
        .ameacas-btn.bloquear { border-color: var(--red); color: var(--red); }
        .ameacas-btn.bloquear:hover { background: var(--red-bg); }
        .ameacas-btn.desbloquear { border-color: var(--green); color: var(--green); }
        .ameacas-btn.desbloquear:hover { background: rgba(46,204,113,0.12); }
        .ameacas-btn.link { color: var(--accent); border: none; background: none; padding: 6px 0; }
        .ameacas-revisao { display: flex; gap: 4px; margin-top: 6px; align-items: center; }
        .ameacas-revisao button {
          border: none; background: none; font-size: 11px; padding: 2px 6px; border-radius: 4px; cursor: pointer; color: var(--text-dim);
        }
        .ameacas-revisao button.marcado-confirmado { background: var(--red-bg); color: var(--red); }
        .ameacas-revisao button.marcado-falso { background: rgba(255,255,255,0.06); color: var(--text-dim); text-decoration: line-through; }
        .ameacas-status-bloqueado { font-size: 11px; color: var(--red); display: flex; align-items: center; gap: 4px; margin-top: 4px; }
        .ameacas-status-bloqueado::before { content: ""; width: 6px; height: 6px; background: var(--red); border-radius: 50%; display: inline-block; }
        .ameacas-grafico-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--border); flex-wrap: wrap; gap: 10px; }
        .ameacas-grafico-area { padding: 20px 18px 10px; }
        .ameacas-grafico-legenda { display: flex; gap: 18px; margin-bottom: 14px; font-size: 12px; color: var(--text-dim); }
        .ameacas-grafico-legenda span { display: flex; align-items: center; gap: 6px; }
        .ameacas-dot { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }
        .ameacas-grafico-wrap { position: relative; }
        .ameacas-grafico-svg { width: 100%; height: 190px; display: block; overflow: visible; }
        .ameacas-grade-linha { stroke: rgba(255,255,255,0.055); stroke-width: 1; }
        .ameacas-grade-base { stroke: var(--border); stroke-width: 1; }
        .ameacas-eixo-labels { display: flex; gap: 4px; margin-top: 8px; }
        .ameacas-eixo-labels span { flex: 1; text-align: center; font-size: 10px; color: var(--text-dim); }
        .ameacas-barra-critico { fill: var(--red); transition: fill 0.12s; cursor: pointer; }
        .ameacas-barra-critico:hover { fill: #ff7777; }
        .ameacas-barra-atencao { fill: var(--orange); transition: fill 0.12s; cursor: pointer; }
        .ameacas-barra-atencao:hover { fill: #ffbf5c; }
        .ameacas-barra-resolvido { fill: var(--green); transition: fill 0.12s; cursor: pointer; }
        .ameacas-barra-resolvido:hover { fill: #4ee08a; }
        .ameacas-barra-vazio { fill: #363a46; }
        .ameacas-tooltip-grafico {
          position: absolute; pointer-events: none; background: #0e0f14; border: 1px solid var(--border);
          border-radius: 6px; padding: 7px 10px; font-size: 11px; color: var(--text);
          box-shadow: 0 8px 20px rgba(0,0,0,0.4); opacity: 0; transition: opacity 0.1s;
          white-space: nowrap; z-index: 10; transform: translate(-50%, -100%);
        }
        .ameacas-tooltip-grafico.visivel { opacity: 1; }
        .ameacas-tooltip-grafico .tt-data { color: var(--text-dim); font-size: 10px; margin-bottom: 2px; }
        .ameacas-tooltip-grafico .tt-valor b { color: var(--text); }
        .ameacas-tooltip-grafico .tt-critico b { color: var(--red); }
        .ameacas-tooltip-grafico .tt-atencao b { color: var(--orange); }
        .ameacas-tooltip-grafico .tt-resolvido b { color: var(--green); }
        .ameacas-taxa-resumo { display: flex; gap: 24px; padding: 0 18px 18px; font-size: 12px; color: var(--text-dim); flex-wrap: wrap; }
        .ameacas-taxa-resumo b { color: var(--text); }
        .ameacas-ajuda { margin-top: 8px; font-size: 11px; display: flex; gap: 10px; flex-wrap: wrap; }
        .ameacas-ajuda a { color: var(--accent); text-decoration: none; }
        .ameacas-recorrencia { color: var(--text-dim); }
        .ameacas-recorrencia b { color: var(--orange); }
      `}</style>

      <div className="ameacas-header-row">
        <div>
          <h2 className="page-title" style={{ margin: 0 }}>Ameaças de Rede</h2>
          <div className="ameacas-sub">Domínios suspeitos (Fase 1) e alertas de assinatura do Suricata (Fase 2) detectados na rede</div>
        </div>
        <div className="ameacas-janela">
          {JANELAS_LISTA.map((j, i) => (
            <button key={j.label} className={i === janelaListaIdx ? 'ativo' : ''} onClick={() => setJanelaListaIdx(i)}>
              {j.label}
            </button>
          ))}
        </div>
      </div>

      <div className="ameacas-cards">
        <div className="ameacas-card critico">
          <div className="valor">{resumo ? resumo.criticos : '—'}</div>
          <div className="label">Detecções críticas ({JANELAS_LISTA[janelaListaIdx].label})</div>
        </div>
        <div className="ameacas-card atencao">
          <div className="valor">{resumo ? resumo.atencao : '—'}</div>
          <div className="label">Detecções de atenção ({JANELAS_LISTA[janelaListaIdx].label})</div>
        </div>
        <div className="ameacas-card">
          <div className="valor">{resumo ? resumo.dispositivos_afetados : '—'}</div>
          <div className="label">Dispositivos distintos afetados</div>
        </div>
        <div className="ameacas-card ok">
          <div className="valor">{resumo ? resumo.dispositivos_bloqueados : '—'}</div>
          <div className="label">Dispositivos bloqueados atualmente</div>
        </div>
      </div>

      <div className="ameacas-painel">
        <div className="ameacas-grafico-header">
          <span style={{ fontWeight: 600 }}>Detecções ao longo do tempo</span>
          <div className="ameacas-janela small">
            {JANELAS_GRAFICO.map((j, i) => (
              <button key={j.label} className={i === janelaGraficoIdx ? 'ativo' : ''} onClick={() => setJanelaGraficoIdx(i)}>
                {j.label}
              </button>
            ))}
          </div>
        </div>
        <div className="ameacas-grafico-area">
          <div className="ameacas-grafico-legenda">
            <span><i className="ameacas-dot" style={{ background: 'var(--red)' }}></i> Crítico</span>
            <span><i className="ameacas-dot" style={{ background: 'var(--orange)' }}></i> Atenção</span>
            <span><i className="ameacas-dot" style={{ background: 'var(--green)' }}></i> Resolvido / falso positivo</span>
          </div>
          <div className="ameacas-grafico-wrap">
            <svg viewBox={`0 0 ${larguraTotal} 175`} className="ameacas-grafico-svg" preserveAspectRatio="none">
              {[15, 50, 85, 120].map((y) => (
                <line key={y} x1={margemEsq} y1={y} x2={larguraTotal} y2={y} className="ameacas-grade-linha" />
              ))}
              <line x1={margemEsq} y1={yBaseArea} x2={larguraTotal} y2={yBaseArea} className="ameacas-grade-base" />
              {pontosGrafico.map((ponto, i) => (
                <path
                  key={i}
                  className={ponto.classe}
                  d={ponto.path}
                  onMouseEnter={(ev) => mostrarTooltip(ev, ponto)}
                  onMouseMove={moverTooltip}
                  onMouseLeave={esconderTooltip}
                />
              ))}
            </svg>
            <div className={`ameacas-tooltip-grafico ${tooltip.visivel ? 'visivel' : ''}`} style={{ left: tooltip.x, top: tooltip.y }}>
              <div className="tt-data">{tooltip.data}</div>
              <div className={`tt-valor tt-${tooltip.cor}`}>
                <b>{tooltip.valor}</b> alerta(s) — {LABEL_COR[tooltip.cor] || 'sem detecção'}
              </div>
            </div>
          </div>
          <div className="ameacas-eixo-labels">
            {pontosGrafico.map((ponto, i) => {
              const intervalo = Math.max(1, Math.ceil(pontosGrafico.length / 20));
              const mostrar = i % intervalo === 0 || i === pontosGrafico.length - 1;
              return <span key={i}>{mostrar ? formatarDataCurta(ponto.data) : ''}</span>;
            })}
          </div>
        </div>
        <div className="ameacas-taxa-resumo">
          <span>Ocorrências no período: <b>{totalOcorrencias}</b></span>
          <span>Confirmados: <b style={{ color: 'var(--red)' }}>{confirmados}</b></span>
          <span>Falso positivo: <b style={{ color: '#8a8f9c' }}>{falsos}</b></span>
          <span>Pendentes: <b style={{ color: 'var(--orange)' }}>{pendentes}</b></span>
          <span>Taxa de falso positivo (revisados): <b style={{ color: 'var(--orange)' }}>{taxaFalsoPositivo !== null ? `${taxaFalsoPositivo}%` : '—'}</b></span>
        </div>
      </div>

      <div className="ameacas-painel">
        <div className="ameacas-painel-titulo">
          <span>Dispositivos com detecção — {JANELAS_LISTA[janelaListaIdx].label}</span>
          <select className="ameacas-filtro-select" value={filtroOrigem} onChange={(e) => setFiltroOrigem(e.target.value)}>
            <option value="todas">Todas origens</option>
            <option value="dominio">Domínio suspeito (HaGeZi)</option>
            <option value="suricata">Assinatura Suricata (ET Open)</option>
          </select>
        </div>
        <table>
          <thead>
            <tr>
              <th>Dispositivo</th>
              <th>Detecção</th>
              <th>Origem</th>
              <th>Ocorrências</th>
              <th>Última vez</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-dim)' }}>Carregando...</td></tr>
            )}
            {!carregando && listaFiltrada.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-dim)' }}>Nenhuma detecção no período.</td></tr>
            )}
            {listaFiltrada.map((item, idx) => {
              const resolvido = item.origem === 'suricata' && item.revisao === 'falso_positivo';
              const critico = !resolvido && (item.origem === 'dominio' || item.severidade === 1 || item.revisao === 'confirmado');
              const classeBadge = resolvido ? 'resolvido' : critico ? 'critico' : 'atencao';
              const labelBadge = resolvido ? 'RESOLVIDO' : critico ? 'CRÍTICO' : 'ATENÇÃO';
              return (
                <tr key={idx}>
                  <td>
                    <div className="ameacas-dispositivo-nome">{item.hostname || 'Desconhecido'}</div>
                    <div className="ameacas-dispositivo-ip">{item.ip || item.mac}</div>
                    {item.bloqueado && <div className="ameacas-status-bloqueado">Bloqueado da rede</div>}
                  </td>
                  <td>
                    <span className={`ameacas-badge ${classeBadge}`}>{labelBadge}</span>
                    <div className="ameacas-detalhe">
                      <div className="principal">{item.dominio || item.detalhe_principal}</div>
                      {item.detalhe_secundario && <div className="secundario">{item.detalhe_secundario}</div>}
                      {item.origem === 'suricata' && (
                        <div className="ameacas-ajuda">
                          <span className="ameacas-recorrencia">Recorrência: <b>{item.ocorrencias}x</b></span>
                          {item.ip_destino && (
                            <>
                              <a href={`https://www.virustotal.com/gui/ip-address/${item.ip_destino}`} target="_blank" rel="noreferrer">Ver IP no VirusTotal ↗</a>
                              <a href={`https://www.abuseipdb.com/check/${item.ip_destino}`} target="_blank" rel="noreferrer">Ver IP no AbuseIPDB ↗</a>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className="ameacas-badge origem">{item.origem === 'dominio' ? 'Domínio (HaGeZi)' : 'Suricata (assinatura)'}</span>
                  </td>
                  <td><span className="ameacas-contagem">{item.ocorrencias}</span></td>
                  <td>{tempoRelativo(item.ultima_vez)}</td>
                  <td>
                    {podeGerenciar ? (
                      <>
                        <div className="ameacas-acoes">
                          {item.bloqueado ? (
                            <button className="ameacas-btn desbloquear" onClick={() => handleDesbloquear(item.mac)}>Desbloquear</button>
                          ) : (
                            <button className="ameacas-btn bloquear" onClick={() => handleBloquear(item.mac)}>Bloquear</button>
                          )}
                        </div>
                        {item.origem === 'suricata' && (
                          <div className="ameacas-revisao">
                            <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>Revisão:</span>
                            <button
                              className={item.revisao === 'confirmado' ? 'marcado-confirmado' : ''}
                              onClick={() => handleRevisao(item.alerta_id, 'confirmado')}
                            >
                              Confirmado
                            </button>
                            <button
                              className={item.revisao === 'falso_positivo' ? 'marcado-falso' : ''}
                              onClick={() => handleRevisao(item.alerta_id, 'falso_positivo')}
                            >
                              Falso positivo
                            </button>
                          </div>
                        )}
                      </>
                    ) : (
                      <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
