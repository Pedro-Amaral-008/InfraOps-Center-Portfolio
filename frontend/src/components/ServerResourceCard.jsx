import './ServerResourceCard.css';

function formatarTamanho(gb) {
  if (gb >= 1024) {
    return `${(gb / 1024).toFixed(1)} TB`;
  }
  return `${gb} GB`;
}

function BarraRecurso({ label, percent, corLimite = 90 }) {
  const cor = percent >= corLimite ? 'var(--status-offline)' : percent >= 75 ? 'var(--status-warning)' : 'var(--status-online)';

  return (
    <div className="resource-bar-group">
      <div className="resource-bar-header">
        <span className="resource-bar-label">{label}</span>
        <span className="resource-bar-value" style={{ color: cor }}>{percent}%</span>
      </div>
      <div className="resource-bar-track">
        <div
          className="resource-bar-fill"
          style={{ width: `${percent}%`, backgroundColor: cor }}
        />
      </div>
    </div>
  );
}

function corTemperatura(temp) {
  if (temp >= 75) return 'var(--status-offline)';
  if (temp >= 60) return 'var(--status-warning)';
  return 'var(--status-online)';
}

function ServerResourceCard({ agente }) {
  const uptimeDias = Math.floor(agente.uptime_horas / 24);
  const uptimeHorasResto = agente.uptime_horas % 24;

  const temMultiplosDiscos = agente.discos && agente.discos.length > 0;
  const temTemperatura = agente.temperatura_celsius !== undefined && agente.temperatura_celsius !== null;

  return (
    <div className="server-resource-card">
      <div className="server-resource-header">
        <span className="server-resource-name">{agente.hostname}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {temTemperatura && (
            <span
              className="server-resource-uptime"
              style={{ color: corTemperatura(agente.temperatura_celsius), fontWeight: 600 }}
            >
              {agente.temperatura_celsius}°C
            </span>
          )}
          <span className="server-resource-uptime">
            {uptimeDias > 0 ? `${uptimeDias}d ` : ''}{uptimeHorasResto}h online
          </span>
        </div>
      </div>

      <BarraRecurso label="CPU" percent={agente.cpu_percent} />
      <BarraRecurso label={`RAM (${formatarTamanho(agente.ram_total_gb)})`} percent={agente.ram_percent} />

      {temMultiplosDiscos ? (
        agente.discos.map((disco) => (
          <BarraRecurso
            key={disco.drive}
            label={`Disco ${disco.drive} (${formatarTamanho(disco.total_gb)})`}
            percent={disco.percent}
          />
        ))
      ) : (
        <BarraRecurso label={`Disco (${formatarTamanho(agente.disco_total_gb)})`} percent={agente.disco_percent} />
      )}
    </div>
  );
}

export default ServerResourceCard;
