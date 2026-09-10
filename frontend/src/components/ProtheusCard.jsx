import './ProtheusCard.css';

const INFO_ESTADO = {
  online: { cor: 'var(--status-online)', label: 'Online' },
  intermitente: { cor: 'var(--status-warning)', label: 'Intermitente' },
  offline: { cor: 'var(--status-offline)', label: 'Offline' },
  desconhecido: { cor: 'var(--text-tertiary)', label: 'Sem dados' },
};

function tempoRelativo(isoString) {
  if (!isoString) return '—';
  const diffMin = Math.floor((new Date() - new Date(isoString)) / 60000);
  if (diffMin < 1) return 'menos de 1 min';
  if (diffMin < 60) return `${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ${diffMin % 60}min`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD}d ${diffH % 24}h`;
}

function formatarDuracao(segundos) {
  if (segundos === null || segundos === undefined) return 'em andamento';
  if (segundos < 60) return `${segundos}s`;
  const minutos = Math.floor(segundos / 60);
  if (minutos < 60) return `${minutos}min${segundos % 60 > 0 ? ` ${segundos % 60}s` : ''}`;
  const horas = Math.floor(minutos / 60);
  return `${horas}h${minutos % 60}min`;
}

function gerarPathSparkline(valores, largura = 200, altura = 44, margem = 4) {
  const validos = valores.filter((v) => v !== null && v !== undefined);
  if (validos.length < 2) return '';
  const min = Math.min(...validos), max = Math.max(...validos);
  const range = max - min || 1;
  const passoX = largura / (valores.length - 1);
  let path = '';
  let traçoAberto = false;
  valores.forEach((v, i) => {
    if (v === null || v === undefined) { traçoAberto = false; return; }
    const x = (i * passoX).toFixed(1);
    const y = (altura - margem - ((v - min) / range) * (altura - margem * 2)).toFixed(1);
    path += `${!traçoAberto ? 'M' : 'L'}${x},${y} `;
    traçoAberto = true;
  });
  return path.trim();
}

function ProtheusCard({ status, historico, eventos }) {
  if (!status) {
    return (
      <div className="protheus-card">
        <div className="protheus-header">
          <span className="protheus-name">Protheus (ERP)</span>
        </div>
        <div className="protheus-loading">Carregando...</div>
      </div>
    );
  }

  const info = INFO_ESTADO[status.estado] || INFO_ESTADO.desconhecido;
  const pathSparkline = gerarPathSparkline((historico || []).map((h) => h.latencia_ms));
  const ocorrencias = (eventos || []).filter((e) => e.estado !== 'online');

  return (
    <div className="protheus-card">
      <div className="protheus-header">
        <div className="protheus-title-group">
          <span className="protheus-name">Protheus (ERP)</span>
          <span className="protheus-hostname">protheus.elcop.eng.br</span>
        </div>
        <span className="protheus-badge">Monitorado via ICMP — sem agente</span>
      </div>

      <div className="protheus-status-row">
        <span className="protheus-status-dot" style={{ backgroundColor: info.cor }} />
        <span className="protheus-status-label" style={{ color: info.cor }}>{info.label}</span>
        <span className="protheus-status-since">há {tempoRelativo(status.desde)}</span>
      </div>

      <div className="protheus-metrics-row">
        <div className="protheus-metric">
          <span className="protheus-metric-value">{status.latencia_ms !== null ? `${status.latencia_ms.toFixed(1)}ms` : '—'}</span>
          <span className="protheus-metric-label">Latência</span>
        </div>
        <div className="protheus-metric">
          <span className="protheus-metric-value">{status.perda_pacotes_percentual}%</span>
          <span className="protheus-metric-label">Perda de pacotes</span>
        </div>
        <div className="protheus-metric">
          <span className="protheus-metric-value">{ocorrencias.length}</span>
          <span className="protheus-metric-label">Ocorrências (7d)</span>
        </div>
      </div>

      {pathSparkline && (
        <div className="protheus-sparkline">
          <span className="protheus-sparkline-label">Latência — últimas 24h</span>
          <svg width="100%" height="44" viewBox="0 0 200 44" preserveAspectRatio="none">
            <path d={pathSparkline} fill="none" stroke={info.cor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      )}

      <div className="protheus-uptime-row">
        <div className="protheus-uptime-item">
          <span className="protheus-uptime-value">{status.uptime_24h !== null ? `${status.uptime_24h}%` : '—'}</span>
          <span className="protheus-uptime-label">24h</span>
        </div>
        <div className="protheus-uptime-item">
          <span className="protheus-uptime-value">{status.uptime_7d !== null ? `${status.uptime_7d}%` : '—'}</span>
          <span className="protheus-uptime-label">7 dias</span>
        </div>
        <div className="protheus-uptime-item">
          <span className="protheus-uptime-value">{status.uptime_30d !== null ? `${status.uptime_30d}%` : '—'}</span>
          <span className="protheus-uptime-label">30 dias</span>
        </div>
      </div>

      {ocorrencias.length > 0 && (
        <div className="protheus-eventos">
          <span className="protheus-eventos-title">Últimas ocorrências</span>
          {ocorrencias.slice(0, 5).map((ev, idx) => (
            <div className="protheus-evento-item" key={idx}>
              <span className="protheus-evento-dot" style={{ backgroundColor: (INFO_ESTADO[ev.estado] || INFO_ESTADO.desconhecido).cor }} />
              <span className="protheus-evento-estado">{(INFO_ESTADO[ev.estado] || INFO_ESTADO.desconhecido).label}</span>
              <span className="protheus-evento-duracao">{formatarDuracao(ev.duracao_segundos)}</span>
              <span className="protheus-evento-data">
                {new Date(ev.inicio).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ProtheusCard;
