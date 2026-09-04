import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import GraficoHistoricoConsumo from './GraficoHistoricoConsumo';

const API_URL = 'http://192.168.1.26:8000';
const JANELA_GRAFICO = 40;

function fmtMbps(v) {
  return (v ?? 0).toFixed(2).replace('.', ',') + ' Mbps';
}

function ConsumoRede({ token }) {
  const [modo, setModo] = useState('vivo');
  const [clientes, setClientes] = useState([]);
  const [semanal, setSemanal] = useState([]);
  const [carregandoSemanal, setCarregandoSemanal] = useState(false);
  const historicoRef = useRef({ download: [], upload: [] });
  const [, forceRender] = useState(0);

  useEffect(() => {
    if (!token || modo !== 'vivo') return;
    const buscar = () => {
      axios.get(`${API_URL}/dashboard/unifi/top-consumo`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((r) => {
        setClientes(r.data);
        const totalDown = r.data.reduce((s, c) => s + c.download_mbps, 0);
        const totalUp = r.data.reduce((s, c) => s + c.upload_mbps, 0);
        historicoRef.current.download.push(totalDown);
        historicoRef.current.upload.push(totalUp);
        if (historicoRef.current.download.length > JANELA_GRAFICO) {
          historicoRef.current.download.shift();
          historicoRef.current.upload.shift();
        }
        forceRender((n) => n + 1);
      }).catch(() => {});
    };
    buscar();
    const intervalo = setInterval(buscar, 15000);
    return () => clearInterval(intervalo);
  }, [token, modo]);

  useEffect(() => {
    if (!token || modo !== 'semanal') return;
    setCarregandoSemanal(true);
    axios.get(`${API_URL}/dashboard/unifi/top-consumo-semanal`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setSemanal(r.data)).catch(() => {}).finally(() => setCarregandoSemanal(false));
  }, [token, modo]);

  const totalDownload = clientes.reduce((s, c) => s + c.download_mbps, 0);
  const totalUpload = clientes.reduce((s, c) => s + c.upload_mbps, 0);
  const qtdAlerta = clientes.filter((c) => c.sustentado).length;
  const maxTotal = Math.max(...clientes.map((c) => c.total_mbps), 1);
  const ordenados = [...clientes].sort((a, b) => b.total_mbps - a.total_mbps);

  const hist = historicoRef.current;
  const n = hist.download.length;
  let svgConteudo = null;
  if (n >= 2) {
    const L = 900, A = 160, pad = 10;
    const max = Math.max(...hist.download, ...hist.upload, 5) * 1.15;
    const passo = (L - pad * 2) / (JANELA_GRAFICO - 1);
    const offsetX = (JANELA_GRAFICO - n) * passo;
    const yDe = (v) => A - pad - (v / max) * (A - pad * 2);
    const linha = (vals, cor) => {
      const pts = vals.map((v, i) => `${(offsetX + pad + i * passo).toFixed(1)},${yDe(v).toFixed(1)}`).join(' ');
      return <polyline points={pts} fill="none" stroke={cor} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />;
    };
    svgConteudo = (
      <>
        {[0.25, 0.5, 0.75].map((f, i) => (
          <line key={i} x1={pad} y1={(A - pad * 2) * f + pad} x2={L - pad} y2={(A - pad * 2) * f + pad} stroke="rgba(255,255,255,.06)" strokeDasharray="2 4" />
        ))}
        {linha(hist.download, '#3987e5')}
        {linha(hist.upload, '#d55181')}
      </>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
        <button className={`btn ${modo === 'vivo' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setModo('vivo')}>Ao Vivo</button>
        <button className={`btn ${modo === 'semanal' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setModo('semanal')}>Top 7 dias</button>
      </div>

      {modo === 'vivo' && (
        <>
          <h3 className="detail-table-title">Consumo de Rede — Ao Vivo</h3>
          <p style={{ fontSize: '13px', opacity: 0.7, marginBottom: '16px' }}>
            Atualiza a cada 15 segundos. Linhas piscando indicam consumo acima de 60 Mbps por mais de 60 segundos seguidos — um pico rápido não dispara o alerta.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '18px' }}>
            <div className="metric-card">
              <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Download total</div>
              <div style={{ fontSize: '23px', fontWeight: 800, color: '#3987e5' }}>{fmtMbps(totalDownload)}</div>
            </div>
            <div className="metric-card">
              <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Upload total</div>
              <div style={{ fontSize: '23px', fontWeight: 800, color: '#d55181' }}>{fmtMbps(totalUpload)}</div>
            </div>
            <div className="metric-card">
              <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Dispositivos ativos</div>
              <div style={{ fontSize: '23px', fontWeight: 800 }}>{clientes.length}</div>
            </div>
            <div className="metric-card">
              <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Acima do limite (60s+)</div>
              <div style={{ fontSize: '23px', fontWeight: 800, color: qtdAlerta > 0 ? '#ef4444' : undefined }}>{qtdAlerta}</div>
            </div>
          </div>

          <GraficoHistoricoConsumo token={token} apiUrl={API_URL} />

          <table>
            <thead>
              <tr><th>Dispositivo</th><th>IP</th><th>Download</th><th>Upload</th><th>Total</th></tr>
            </thead>
            <tbody>
              {ordenados.map((c) => (
                <tr key={c.mac} style={c.sustentado ? { background: 'rgba(239, 68, 68, 0.14)', animation: 'pulso-linha-consumo 1.1s ease-in-out infinite' } : undefined}>
                  <td>
                    {c.hostname}
                    {c.sustentado && (
                      <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 7px', borderRadius: '5px', background: '#ef4444', color: '#fff', marginLeft: '8px' }}>
                        ACIMA 60s+
                      </span>
                    )}
                  </td>
                  <td style={{ opacity: 0.6, fontSize: '12px' }}>{c.ip}</td>
                  <td style={c.download_mbps >= 60 ? { color: '#ef4444', fontWeight: 700 } : undefined}>{fmtMbps(c.download_mbps)}</td>
                  <td style={c.upload_mbps >= 60 ? { color: '#ef4444', fontWeight: 700 } : undefined}>{fmtMbps(c.upload_mbps)}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end' }}>
                      <div style={{ width: '90px', height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                        <div style={{ height: '100%', borderRadius: '3px', background: c.sustentado ? '#ef4444' : '#6172f3', width: `${(c.total_mbps / maxTotal * 100).toFixed(0)}%`, transition: 'width 0.5s ease' }} />
                      </div>
                      <span style={{ minWidth: '58px', textAlign: 'right', display: 'inline-block', fontWeight: 700, color: c.sustentado ? '#ef4444' : undefined }}>{fmtMbps(c.total_mbps)}</span>
                    </div>
                  </td>
                </tr>
              ))}
              {clientes.length === 0 && (
                <tr><td colSpan="5" style={{ textAlign: 'center', opacity: 0.6 }}>Carregando dados de consumo...</td></tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {modo === 'semanal' && (
        <>
          <h3 className="detail-table-title">Top Consumo — Últimos 7 dias</h3>
          <p style={{ fontSize: '13px', opacity: 0.7, marginBottom: '16px' }}>
            Média e pico de consumo por dispositivo, calculados a partir das amostras coletadas a cada 15-20 segundos.
          </p>
          <table>
            <thead>
              <tr><th>Dispositivo</th><th>IP</th><th>Download (média/pico)</th><th>Upload (média/pico)</th><th>Total médio</th></tr>
            </thead>
            <tbody>
              {semanal.map((c) => (
                <tr key={c.mac}>
                  <td>{c.hostname}</td>
                  <td style={{ opacity: 0.6, fontSize: '12px' }}>{c.ip}</td>
                  <td>{fmtMbps(c.download_medio_mbps)} <span style={{ opacity: 0.5, fontSize: '11px' }}>(pico {fmtMbps(c.download_pico_mbps)})</span></td>
                  <td>{fmtMbps(c.upload_medio_mbps)} <span style={{ opacity: 0.5, fontSize: '11px' }}>(pico {fmtMbps(c.upload_pico_mbps)})</span></td>
                  <td style={{ fontWeight: 700 }}>{fmtMbps(c.total_medio_mbps)}</td>
                </tr>
              ))}
              {semanal.length === 0 && !carregandoSemanal && (
                <tr><td colSpan="5" style={{ textAlign: 'center', opacity: 0.6 }}>Ainda não há dados suficientes acumulados (o histórico começou a ser coletado agora).</td></tr>
              )}
              {carregandoSemanal && (
                <tr><td colSpan="5" style={{ textAlign: 'center', opacity: 0.6 }}>Carregando...</td></tr>
              )}
            </tbody>
          </table>
        </>
      )}

      <style>{`
        @keyframes pulso-linha-consumo {
          0%, 100% { background: rgba(239,68,68,.08); }
          50% { background: rgba(239,68,68,.22); }
        }
        .metric-card {
          background: var(--bg-elevated, #1b2330);
          border: 1px solid var(--border-subtle, rgba(255,255,255,0.1));
          border-radius: 12px;
          padding: 14px 16px;
        }
      `}</style>
    </div>
  );
}

export default ConsumoRede;
