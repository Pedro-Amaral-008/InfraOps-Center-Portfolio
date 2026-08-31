import { useState, useEffect } from 'react';
import axios from 'axios';
import './EopsDashboard.css';

const API_URL = 'IP_INTERNO_AQUI:8000';

const ORDEM_CATEGORIAS = ['Servidores', 'Access Points', 'Links de Rede', 'Backups', 'Impressoras'];

const CHAVE_PARA_NOME = {
  servidores: 'Servidores',
  access_points: 'Access Points',
  links: 'Links de Rede',
  backups: 'Backups',
  impressoras: 'Impressoras',
};

const ICONE_CATEGORIA = {
  'Servidores': <><rect x="3" y="4" width="18" height="6" rx="1.2" /><rect x="3" y="14" width="18" height="6" rx="1.2" /></>,
  'Access Points': <><circle cx="12" cy="12" r="2" /><path d="M5 12a7 7 0 0 1 14 0M2 12a10 10 0 0 1 20 0" /></>,
  'Links de Rede': <path d="M4 12h4l2-6 4 12 2-6h4" />,
  'Backups': <><path d="M12 3v6M12 15v6M4 12h4M16 12h4" strokeLinecap="round" /><rect x="8" y="8" width="8" height="8" rx="1.5" /></>,
  'Impressoras': <><rect x="4" y="9" width="16" height="10" rx="1.5" /><path d="M8 9V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v3" /></>,
};

const ICONE_TIPO = {
  bad: <path d="M4 12h4l2-6 4 12 2-6h4" />,
  warn: <><path d="M12 2 2 20h20L12 2z" /><path d="M12 9v5M12 17h.01" /></>,
  good: <path d="M20 6 9 17l-5-5" />,
};

function corDoDia(uptimePercent) {
  if (uptimePercent >= 99) return '#22c55e';
  if (uptimePercent >= 90) return '#f5a524';
  return '#ef4444';
}
function classePercentSemana(uptimePercent) {
  if (uptimePercent >= 99) return '';
  if (uptimePercent >= 95) return 'warn-num';
  return 'bad-num';
}
function gerarPathSparkline(valores, largura = 150, altura = 40, margem = 4) {
  if (!valores || valores.length < 2) return '';
  const min = Math.min(...valores), max = Math.max(...valores);
  const range = max - min || 1;
  const passoX = largura / (valores.length - 1);
  const pontos = valores.map((v, i) => [i * passoX, altura - margem - ((v - min) / range) * (altura - margem * 2)]);
  return pontos.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
}
function tempoRelativo(isoString) {
  const agora = new Date();
  const data = new Date(isoString);
  const diffMs = agora - data;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'agora mesmo';
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `há ${diffH}h ${diffMin % 60}min`;
  const diffD = Math.floor(diffH / 24);
  return `há ${diffD}d`;
}

function EopsDashboard({ token, dados }) {
  const [eventos24h, setEventos24h] = useState(0);
  const [eventosRecentes, setEventosRecentes] = useState([]);
  const [tendencia, setTendencia] = useState([]);
  const [estabilidade, setEstabilidade] = useState({});
  const [alertasAtivos, setAlertasAtivos] = useState([]);
  const [piorDesempenho, setPiorDesempenho] = useState(null);
  const [filtroFeed, setFiltroFeed] = useState('todos');

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };

    axios.get(`${API_URL}/dashboard/eventos/contagem-24h`, { headers })
      .then((r) => setEventos24h(r.data.total_24h)).catch(() => {});
    axios.get(`${API_URL}/dashboard/eventos/recentes?limite=15`, { headers })
      .then((r) => setEventosRecentes(r.data)).catch(() => {});
    axios.get(`${API_URL}/dashboard/tendencia-24h`, { headers })
      .then((r) => setTendencia(r.data)).catch(() => {});
    axios.get(`${API_URL}/dashboard/estabilidade-semanal`, { headers })
      .then((r) => setEstabilidade(r.data)).catch(() => {});
    axios.get(`${API_URL}/dashboard/pior-desempenho-semana`, { headers })
      .then((r) => setPiorDesempenho(r.data)).catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!token || !dados) return;
    const headers = { Authorization: `Bearer ${token}` };
    const nomesOffline = [
      ...(dados.servidores_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
      ...(dados.access_points_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
      ...(dados.links_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
      ...(dados.impressoras_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
    ];
    if (nomesOffline.length === 0) {
      setAlertasAtivos([]);
      return;
    }
    axios.post(`${API_URL}/dashboard/alertas-ativos-duracao`, { nomes: nomesOffline }, { headers })
      .then((r) => setAlertasAtivos(r.data)).catch(() => {});
  }, [token, dados]);

  if (!dados) return null;

  const categorias = {
    'Servidores': { online: dados.servidores_online || 0, total: (dados.servidores_online || 0) + (dados.servidores_offline || 0), offline: dados.servidores_offline || 0 },
    'Access Points': { online: dados.access_points_online || 0, total: (dados.access_points_online || 0) + (dados.access_points_offline || 0), offline: dados.access_points_offline || 0 },
    'Links de Rede': { online: dados.links_online || 0, total: (dados.links_online || 0) + (dados.links_offline || 0), offline: dados.links_offline || 0 },
    'Backups': { online: dados.backups_ok || 0, total: (dados.backups_ok || 0) + (dados.backups_falharam || 0), offline: dados.backups_falharam || 0 },
    'Impressoras': { online: dados.impressoras_online || 0, total: (dados.impressoras_online || 0) + (dados.impressoras_offline || 0), offline: dados.impressoras_offline || 0 },
  };

  const totalOnline = Object.values(categorias).reduce((s, c) => s + c.online, 0);
  const totalGeral = Object.values(categorias).reduce((s, c) => s + c.total, 0);
  const uptimeMedio = totalGeral > 0 ? (totalOnline / totalGeral) * 100 : 100;

  const nAlertas = alertasAtivos.length;
  const nivel = nAlertas === 0 ? 'good' : (nAlertas <= 2 ? 'warn' : 'bad');
  const frase = nAlertas === 0 ? 'Tudo operando normalmente' : `${nAlertas} alerta${nAlertas > 1 ? 's' : ''} ativo${nAlertas > 1 ? 's' : ''}`;

  const valoresTendencia = tendencia.map((p) => p.valor);
  const pathSparkline = gerarPathSparkline(valoresTendencia);

  const estabilidadePorNome = {};
  Object.entries(estabilidade).forEach(([chave, valores]) => {
    const nome = CHAVE_PARA_NOME[chave];
    if (nome) estabilidadePorNome[nome] = (valores || []).filter((v) => v !== null);
  });

  const ehRuim = piorDesempenho && piorDesempenho.percentSemana < 99;

  const listaFeed = filtroFeed === 'todos' ? eventosRecentes : eventosRecentes.filter((ev) => {
    const cor = ev.tipo === 'bom' ? 'good' : ev.tipo === 'atencao' ? 'warn' : 'bad';
    return cor === filtroFeed;
  });

  return (
    <div id="eops-dashboard">
      <div className="stage">
        <div className="topbar">
          <h2><span className="live-dot" />Dashboard</h2>
          <div className="updated">Atualizado agora</div>
        </div>

        <div className="card hero">
          <div className="hero-top">
            <div className="hero-status">
              <div className={`beacon ${nivel}`} />
              <div className="phrase">{frase}</div>
            </div>
            <div className="hero-stats">
              <div className="hero-stat">
                <div className="ic"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#5b8cff" strokeWidth="2"><rect x="3" y="4" width="18" height="6" rx="1.5" /><rect x="3" y="14" width="18" height="6" rx="1.5" /><circle cx="7" cy="7" r="0.8" fill="#5b8cff" /><circle cx="7" cy="17" r="0.8" fill="#5b8cff" /></svg></div>
                <div><div className="val">{totalGeral}</div><div className="lbl">monitorados</div></div>
              </div>
              <div className="hero-stat">
                <div className="ic"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#5b8cff" strokeWidth="2"><path d="M12 2v20M2 12h20" /></svg></div>
                <div><div className="val">{uptimeMedio.toFixed(1)}%</div><div className="lbl">uptime hoje</div></div>
              </div>
              <div className="hero-stat">
                <div className="ic"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#5b8cff" strokeWidth="2"><path d="M12 8v4l3 3" /><circle cx="12" cy="12" r="9" /></svg></div>
                <div><div className="val">{eventos24h}</div><div className="lbl">eventos 24h</div></div>
              </div>
            </div>
            <div className="hero-trend">
              <div className="lbl">saudáveis · últimas 24h</div>
              <svg width="150" height="40" viewBox="0 0 150 40">
                {pathSparkline && <path d={pathSparkline} fill="none" stroke="#5b8cff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />}
              </svg>
            </div>
          </div>

          {nAlertas === 0 ? (
            <div className="no-alerts">Nenhum alerta ativo no momento.</div>
          ) : (
            <div className="active-alerts">
              {alertasAtivos.map((a, idx) => (
                <div className="alert-chip" key={idx}>
                  <span className="dot bad" />
                  <span className="name">{a.nome}</span>
                  <span className="sep" />
                  <span className="duration">offline há {a.duracaoTexto}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {piorDesempenho && (
          <div className={`card spotlight ${ehRuim ? '' : 'spotlight-ok'}`}>
            <div className="ic"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke={ehRuim ? '#ef4444' : '#22c55e'} strokeWidth="2">{ICONE_CATEGORIA[piorDesempenho.categoria]}</svg></div>
            <div>
              <div className="label">{ehRuim ? 'Pior desempenho da semana' : 'Melhor desempenho da semana'}</div>
              <div className="title">{piorDesempenho.categoria}</div>
              <div className="sub">{piorDesempenho.quedas7dias} queda{piorDesempenho.quedas7dias === 1 ? '' : 's'} nos últimos 7 dias — {ehRuim ? 'a mais instável' : 'a mais estável'} entre as {ORDEM_CATEGORIAS.length} categorias</div>
            </div>
            <div className="pct">
              {piorDesempenho.percentSemana.toFixed(1)}%
              <span className="arrow">{piorDesempenho.deltaVsSemanaPassada >= 0 ? '▲' : '▼'} {Math.abs(piorDesempenho.deltaVsSemanaPassada).toFixed(1)}% vs. semana passada</span>
            </div>
          </div>
        )}

        <div className="cat-row">
          {ORDEM_CATEGORIAS.map((nome) => {
            const c = categorias[nome];
            const ok = c.offline === 0;
            return (
              <div className="card cat-tile" key={nome}>
                <div className="head">
                  <div className="name-row">
                    <span className={`ic ${ok ? 'good' : 'bad'}`}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={ok ? '#22c55e' : '#ef4444'} strokeWidth="2.2">{ICONE_CATEGORIA[nome]}</svg>
                    </span>
                    {nome}
                  </div>
                </div>
                <div className="num-row">
                  <span className={`num ${ok ? '' : 'bad-num'}`}>
                    {ok ? c.online : <>{c.online}<span className="of"> / {c.total}</span></>}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="bottom-grid">
          <div className="card panel-card">
            <div className="panel-title">Estabilidade · últimos 7 dias</div>
            <div className="panel-note">Uptime diário por categoria — quanto mais vermelho, mais instável o dia.</div>
            <div className="heatmap">
              <div></div>
              {['S', 'T', 'Q', 'Q', 'S', 'S', 'D'].map((c, idx) => <div className="col-head" key={idx}>{c}</div>)}
              <div></div>
              {ORDEM_CATEGORIAS.map((nome) => {
                const diasArrOriginal = estabilidadePorNome[nome] || [];
                const media = diasArrOriginal.length ? diasArrOriginal.reduce((a, b) => a + b, 0) / diasArrOriginal.length : 0;
                // Garante sempre exatamente 7 colunas, preenchendo com null (celula vazia) a esquerda
                // quando a categoria tiver menos de 7 dias de historico (ex: impressoras so tem dias uteis).
                const faltam = Math.max(0, 7 - diasArrOriginal.length);
                const diasArr = [...Array(faltam).fill(null), ...diasArrOriginal.slice(-7)];
                return (
                  <>
                    <div className="cat-name" key={`${nome}-nome`}>{nome}</div>
                    {diasArr.map((v, idx) => (
                      <div className="cell" key={`${nome}-${idx}`} style={{ background: v === null ? 'var(--card-border)' : corDoDia(v), opacity: v === null ? 0.3 : 1 }} />
                    ))}
                    <div className={`pct ${classePercentSemana(media)}`} key={`${nome}-pct`}>{media.toFixed(1)}%</div>
                  </>
                );
              })}
            </div>
            <div className="legend-row">
              <div className="legend-item"><span className="sw" style={{ background: '#22c55e' }} />≥99%</div>
              <div className="legend-item"><span className="sw" style={{ background: '#f5a524' }} />90–98.9%</div>
              <div className="legend-item"><span className="sw" style={{ background: '#ef4444' }} />&lt;90%</div>
            </div>
          </div>

          <div className="card panel-card">
            <div className="panel-title"><span className="dot warn" />Feed de alertas</div>
            <div className="feed-filters">
              {[['todos', 'Todos'], ['bad', 'Críticos'], ['warn', 'Avisos'], ['good', 'Resolvidos']].map(([valor, label]) => (
                <div
                  key={valor}
                  className={`filter-chip ${filtroFeed === valor ? 'active' : ''}`}
                  onClick={() => setFiltroFeed(valor)}
                >
                  {label}
                </div>
              ))}
            </div>
            <div className="feed">
              {listaFeed.length === 0 && <div className="feed-empty">Nenhum evento registrado ainda.</div>}
              {listaFeed.map((ev) => {
                const cor = ev.tipo === 'bom' ? 'good' : ev.tipo === 'atencao' ? 'warn' : 'bad';
                return (
                  <div key={ev.id} className={`feed-item ${cor}`}>
                    <div className="ic"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">{ICONE_TIPO[cor]}</svg></div>
                    <div className="feed-body">
                      <div className="msg-row">
                        <div className="msg">{ev.mensagem}</div>
                      </div>
                      <div className="meta">
                        {ev.detalhes && <><span>{ev.detalhes}</span><span>·</span></>}
                        <span>{tempoRelativo(ev.criado_em)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EopsDashboard;
