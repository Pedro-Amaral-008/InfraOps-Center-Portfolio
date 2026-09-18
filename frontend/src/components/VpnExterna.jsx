import { useState, useEffect, useCallback } from 'react';

const API_URL = '';

const JANELAS = [
  { label: '1h', horas: 1 },
  { label: '24h', horas: 24 },
  { label: '7 dias', horas: 168 },
  { label: '30 dias', horas: 720 },
  { label: '60 dias', horas: 1440 },
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

function formatarDataHora(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function formatarDuracao(segundos) {
  if (segundos == null) return '—';
  if (segundos < 60) return '< 1min';
  const min = Math.floor(segundos / 60);
  if (min < 60) return `${min}min`;
  const h = Math.floor(min / 60);
  const restoMin = min % 60;
  return restoMin > 0 ? `${h}h${restoMin}min` : `${h}h`;
}

export default function VpnExterna({ token }) {
  const [janelaIdx, setJanelaIdx] = useState(2);
  const [dispositivos, setDispositivos] = useState([]);
  const [carregando, setCarregando] = useState(true);

  const horas = JANELAS[janelaIdx].horas;

  const carregar = useCallback(async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const r = await fetch(`${API_URL}/dashboard/acessos/vpn?horas=${horas}`, { headers });
      if (r.ok) setDispositivos(await r.json());
    } catch (erro) {
      console.error('Erro ao carregar VPN externa:', erro);
    } finally {
      setCarregando(false);
    }
  }, [token, horas]);

  useEffect(() => {
    carregar();
    const intervalo = setInterval(carregar, 30000);
    return () => clearInterval(intervalo);
  }, [carregar]);

  const ativosAgora = dispositivos.filter((d) => d.ativo_agora).length;
  const totalEventos = dispositivos.reduce((s, d) => s + (d.eventos || 0), 0);
  const contagemProvedor = {};
  dispositivos.forEach((d) => {
    contagemProvedor[d.provedor] = (contagemProvedor[d.provedor] || 0) + 1;
  });
  const provedorMaisComum = Object.keys(contagemProvedor).length
    ? Object.entries(contagemProvedor).sort((a, b) => b[1] - a[1])[0][0]
    : '—';

  return (
    <div className="vpnx-mockup">
      <style>{`
        .vpnx-mockup {
          --bg-panel: #1b1e27;
          --bg-panel-2: #20232e;
          --border: #2c303c;
          --text: #e4e6eb;
          --text-dim: #9aa0ac;
          --accent: #5b8def;
          --vpn: #f5a623;
          --vpn-bg: rgba(245, 166, 35, 0.12);
          --good: #2ecc71;
          color: var(--text);
          font-size: 14px;
        }
        .vpnx-mockup * { box-sizing: border-box; }
        .vpnx-header-row {
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
        }
        .vpnx-sub { color: var(--text-dim); font-size: 13px; margin-top: 4px; }
        .vpnx-janela { display: flex; gap: 6px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: 8px; padding: 4px; }
        .vpnx-janela button {
          background: transparent; border: none; color: var(--text-dim);
          padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer;
        }
        .vpnx-janela button.ativo { background: var(--accent); color: white; }
        .vpnx-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
        .vpnx-card {
          background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px;
          box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset, 0 6px 14px rgba(0,0,0,0.18);
        }
        .vpnx-card .valor { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }
        .vpnx-card .label { color: var(--text-dim); font-size: 12px; margin-top: 4px; }
        .vpnx-card.destaque .valor { color: var(--vpn); }
        .vpnx-card.ok .valor { color: var(--good); }
        .vpnx-painel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-bottom: 20px; }
        .vpnx-painel-titulo {
          padding: 14px 18px; border-bottom: 1px solid var(--border); font-weight: 600;
          display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
        }
        .vpnx-mockup table { width: 100%; border-collapse: collapse; }
        .vpnx-mockup thead th {
          text-align: left; padding: 10px 18px; font-size: 11px; text-transform: uppercase;
          letter-spacing: 0.04em; color: var(--text-dim); border-bottom: 1px solid var(--border);
        }
        .vpnx-mockup tbody td { padding: 12px 18px; border-bottom: 1px solid var(--border); vertical-align: top; }
        .vpnx-mockup tbody tr:last-child td { border-bottom: none; }
        .vpnx-mockup tbody tr:hover { background: rgba(255,255,255,0.02); }
        .vpnx-dispositivo-nome { font-weight: 600; }
        .vpnx-dispositivo-mac { color: var(--text-dim); font-size: 12px; font-family: monospace; }
        .vpnx-badge { display: inline-block; padding: 3px 9px; border-radius: 5px; font-size: 11px; font-weight: 600; background: var(--vpn-bg); color: var(--vpn); }
        .vpnx-dominio { color: var(--text-dim); font-size: 12px; font-family: monospace; margin-top: 2px; }
        .vpnx-status { display: flex; align-items: center; gap: 8px; }
        .vpnx-live-dot { position: relative; width: 8px; height: 8px; border-radius: 50%; background: var(--good); flex-shrink: 0; }
        .vpnx-live-dot::after {
          content: ''; position: absolute; inset: -4px; border-radius: 50%;
          background: var(--good); opacity: 0.55; animation: vpnx-pulse 1.6s ease-out infinite;
        }
        @media (prefers-reduced-motion: reduce) { .vpnx-live-dot::after { animation: none; opacity: 0.25; } }
        @keyframes vpnx-pulse { 0% { transform: scale(0.6); opacity: 0.55; } 100% { transform: scale(2.2); opacity: 0; } }
        .vpnx-em-uso { color: var(--good); font-weight: 600; font-size: 11.5px; }
        .vpnx-nota {
          display: flex; gap: 10px; align-items: flex-start; background: var(--bg-panel);
          border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px;
          font-size: 12px; color: var(--text-dim); line-height: 1.5;
        }
      `}</style>

      <div className="vpnx-header-row">
        <div>
          <h2 className="page-title" style={{ margin: 0 }}>VPN Externa</h2>
          <div className="vpnx-sub">Dispositivos que acessaram serviços de VPN externos (possível contorno de bloqueios)</div>
        </div>
        <div className="vpnx-janela">
          {JANELAS.map((j, i) => (
            <button key={j.label} className={i === janelaIdx ? 'ativo' : ''} onClick={() => setJanelaIdx(i)}>
              {j.label}
            </button>
          ))}
        </div>
      </div>

      <div className="vpnx-cards">
        <div className="vpnx-card destaque">
          <div className="valor">{dispositivos.length}</div>
          <div className="label">Dispositivos com VPN ({JANELAS[janelaIdx].label})</div>
        </div>
        <div className="vpnx-card">
          <div className="valor">{provedorMaisComum}</div>
          <div className="label">Provedor mais comum</div>
        </div>
        <div className="vpnx-card">
          <div className="valor">{totalEventos}</div>
          <div className="label">Eventos no período</div>
        </div>
        <div className="vpnx-card ok">
          <div className="valor">{ativosAgora}</div>
          <div className="label">Em uso agora</div>
        </div>
      </div>

      <div className="vpnx-painel">
        <div className="vpnx-painel-titulo">
          <span>Dispositivos — {JANELAS[janelaIdx].label}</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Dispositivo</th>
              <th>Provedor</th>
              <th>Primeira detecção</th>
              <th>Última detecção</th>
              <th>Duração</th>
              <th style={{ textAlign: 'right' }}>Eventos</th>
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-dim)' }}>Carregando...</td></tr>
            )}
            {!carregando && dispositivos.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-dim)' }}>Nenhum uso de VPN detectado no período.</td></tr>
            )}
            {dispositivos.map((d) => (
              <tr key={d.mac}>
                <td>
                  <div className="vpnx-status">
                    {d.ativo_agora ? (
                      <>
                        <span className="vpnx-live-dot"></span>
                        <span className="vpnx-em-uso">Em uso</span>
                      </>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>—</span>
                    )}
                  </div>
                </td>
                <td>
                  <div className="vpnx-dispositivo-nome">{d.hostname || 'Desconhecido'}</div>
                  <div className="vpnx-dispositivo-mac">{d.mac}</div>
                </td>
                <td>
                  <span className="vpnx-badge">{d.provedor}</span>
                  <div className="vpnx-dominio">{d.dominio}</div>
                </td>
                <td>{formatarDataHora(d.primeira_deteccao)}</td>
                <td>{formatarDataHora(d.ultima_deteccao)} <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>({tempoRelativo(d.ultima_deteccao)})</span></td>
                <td>{formatarDuracao(d.duracao_ultima_sessao_segundos)}{d.ativo_agora ? ' (em andamento)' : ''}</td>
                <td style={{ textAlign: 'right' }}>{d.eventos}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="vpnx-nota">
        A duração é estimada agrupando eventos do mesmo dispositivo em sessões (intervalo curto entre eles). O conteúdo acessado dentro do túnel VPN não é visível — apenas a conexão inicial com o provedor é detectada, mantendo o monitoramento não invasivo.
      </div>
    </div>
  );
}
