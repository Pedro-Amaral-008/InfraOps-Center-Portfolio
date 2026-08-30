import { useState, useEffect } from 'react';
import axios from 'axios';
import './VisaoGeral.css';

const API_URL = 'IP_INTERNO_AQUI:8000';

const ORDEM_CATEGORIAS = ['Servidores', 'Access Points', 'Links de Rede', 'Backups', 'Impressoras'];

const CHAVE_PARA_NOME = {
  servidores: 'Servidores',
  access_points: 'Access Points',
  links: 'Links de Rede',
  backups: 'Backups',
  impressoras: 'Impressoras',
};

function corDoDia(uptimePercent) {
  if (uptimePercent >= 99) return 'good';
  if (uptimePercent >= 90) return 'low';
  return 'down';
}

function classePercentSemana(uptimePercent) {
  if (uptimePercent >= 99) return '';
  if (uptimePercent >= 95) return 'warn-num';
  return 'bad-num';
}

function gerarPathSparkline(valores, largura = 150, altura = 40, margem = 4) {
  if (!valores || valores.length < 2) return '';
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const range = max - min || 1;
  const passoX = largura / (valores.length - 1);
  const pontos = valores.map((v, i) => {
    const x = i * passoX;
    const yNorm = (v - min) / range;
    const y = altura - margem - yNorm * (altura - margem * 2);
    return [x, y];
  });
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

function VisaoGeral({ token, dados, parte = 'ambas' }) {
  const [eventos24h, setEventos24h] = useState(0);
  const [eventosRecentes, setEventosRecentes] = useState([]);
  const [tendencia, setTendencia] = useState([]);
  const [estabilidade, setEstabilidade] = useState({});

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };

    axios.get(`${API_URL}/dashboard/eventos/contagem-24h`, { headers })
      .then((r) => setEventos24h(r.data.total_24h)).catch(() => {});

    axios.get(`${API_URL}/dashboard/eventos/recentes?limite=8`, { headers })
      .then((r) => setEventosRecentes(r.data)).catch(() => {});

    axios.get(`${API_URL}/dashboard/tendencia-24h`, { headers })
      .then((r) => setTendencia(r.data)).catch(() => {});

    axios.get(`${API_URL}/dashboard/estabilidade-semanal`, { headers })
      .then((r) => setEstabilidade(r.data)).catch(() => {});
  }, [token]);

  if (!dados) return null;

  const totalOnline = (dados.servidores_online || 0) + (dados.access_points_online || 0) + (dados.links_online || 0) + (dados.backups_ok || 0) + (dados.impressoras_online || 0);
  const totalOffline = (dados.servidores_offline || 0) + (dados.access_points_offline || 0) + (dados.links_offline || 0) + (dados.backups_falharam || 0) + (dados.impressoras_offline || 0);
  const totalGeral = totalOnline + totalOffline;
  const uptimeMedio = totalGeral > 0 ? (totalOnline / totalGeral) * 100 : 100;

  const itensComProblema = [
    ...(dados.servidores_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
    ...(dados.access_points_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
    ...(dados.links_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
    ...(dados.impressoras_detalhe || []).filter((i) => i.status !== 'online').map((i) => i.nome),
  ];

  const nivel = itensComProblema.length === 0 ? 'good' : (itensComProblema.length <= 2 ? 'warn' : 'bad');
  const phrase = itensComProblema.length === 0
    ? 'Tudo operando normalmente'
    : `${itensComProblema.length} alerta${itensComProblema.length > 1 ? 's' : ''} ativo${itensComProblema.length > 1 ? 's' : ''}`;
  const sub = itensComProblema.length ? itensComProblema.join(', ') : '';

  const valoresTendencia = tendencia.map((p) => p.valor);
  const pathSparkline = gerarPathSparkline(valoresTendencia);

  // Monta o objeto de estabilidade com nomes amigaveis, na ordem oficial
  const estabilidadePorNome = {};
  Object.entries(estabilidade).forEach(([chave, valores]) => {
    const nome = CHAVE_PARA_NOME[chave];
    if (nome) estabilidadePorNome[nome] = (valores || []).filter((v) => v !== null);
  });

  return (
    <div id="visao-geral">
      
      {(parte === 'hero' || parte === 'ambas') && (

      <div className="card hero">
        <div className="hero-status">
          <div className={`beacon ${nivel}`} />
          <div>
            <div className="phrase">{phrase}</div>
            <div className="sub">{sub}</div>
          </div>
        </div>
        <div className="hero-stats">
          <div className="hero-stat"><div className="val">{totalGeral}</div><div className="lbl">equipamentos monitorados</div></div>
          <div className="hero-stat"><div className="val">{uptimeMedio.toFixed(1)}%</div><div className="lbl">uptime médio hoje</div></div>
          <div className="hero-stat"><div className="val">{eventos24h}</div><div className="lbl">eventos nas últimas 24h</div></div>
        </div>
        <div className="hero-trend">
          <div className="lbl">saudáveis · últimas 24h</div>
          <svg width="150" height="40" viewBox="0 0 150 40">
            {pathSparkline && (
              <path d={pathSparkline} fill="none" stroke="#5b8cff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            )}
          </svg>
        </div>
      </div>
      )}

      {(parte === 'bottom' || parte === 'ambas') && (
      <div className="bottom-grid">
        <div className="card panel-card">
          <div className="panel-title">Estabilidade · últimos 7 dias</div>
          <div className="panel-note">Uptime de cada categoria ao longo da semana.</div>
          <div className="stability">
            {ORDEM_CATEGORIAS.map((nome) => {
              const diasArr = estabilidadePorNome[nome] || [];
              const media = diasArr.length ? diasArr.reduce((a, b) => a + b, 0) / diasArr.length : 0;
              return (
                <div className="stability-row" key={nome}>
                  <div className="stability-name">{nome}</div>
                  <div className="stability-spark">
                    {diasArr.map((v, idx) => (
                      <div key={idx} className={`day ${corDoDia(v)}`} style={{ height: `${Math.max(v, 6)}%` }} />
                    ))}
                  </div>
                  <div className={`stability-pct ${classePercentSemana(media)}`}>{media.toFixed(1)}%</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card panel-card">
          <div className="panel-title"><span className="dot warn" />Feed de alertas</div>
          <div className="feed">
            {eventosRecentes.length === 0 && <div className="feed-empty">Nenhum evento registrado ainda.</div>}
            {eventosRecentes.map((ev) => {
              const classeCor = ev.tipo === 'bom' ? 'good' : ev.tipo === 'atencao' ? 'warn' : 'bad';
              return (
                <div key={ev.id} className={`feed-item ${classeCor}`}>
                  <div className="ic" />
                  <div className="feed-body">
                    <div className="msg">{ev.mensagem}</div>
                    <div className="time">{ev.detalhes ? `${ev.detalhes} · ` : ''}{tempoRelativo(ev.criado_em)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      )}
    </div>
  );
}

export default VisaoGeral;
