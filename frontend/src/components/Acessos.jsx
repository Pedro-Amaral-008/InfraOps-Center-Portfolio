import { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://192.168.1.26:8000';

const PERIODOS = [
  { label: '1 hora', horas: 1 },
  { label: '1 dia', horas: 24 },
  { label: '15 dias', horas: 360 },
  { label: '1 mês', horas: 720 },
  { label: '2 meses', horas: 1440 },
];

const CORES_DONUT = ['#3987e5', '#3ab97a', '#e5b23a', '#d55181', '#8f6ee0', '#4bb8c7', '#e57a3a', '#576078'];

function fmtBytes(bytes) {
  if (!bytes) return '0 B';
  const unidades = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < unidades.length - 1) {
    v /= 1024;
    i++;
  }
  return v.toFixed(i === 0 ? 0 : 1).replace('.', ',') + ' ' + unidades[i];
}

function fmtDuracao(segundos) {
  if (!segundos || segundos < 1) return '<1min';
  const h = Math.floor(segundos / 3600);
  const m = Math.round((segundos % 3600) / 60);
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}min`;
  if (m > 0) return `${m}min`;
  return `${Math.round(segundos)}s`;
}

function fmtDataHora(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function fmtHora(iso) {
  if (!iso) return '-';
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function tempoRelativo(iso) {
  if (!iso) return '-';
  const segundos = (Date.now() - new Date(iso).getTime()) / 1000;
  if (segundos < 120) return 'agora';
  if (segundos < 3600) return `${Math.round(segundos / 60)} min`;
  if (segundos < 86400) return `${Math.round(segundos / 3600)}h`;
  return `${Math.round(segundos / 86400)}d`;
}

function Donut({ dados, campoValor, campoLabel, tamanho = 160 }) {
  const total = dados.reduce((s, d) => s + (d[campoValor] || 0), 0);
  if (total === 0) {
    return <div style={{ opacity: 0.6, fontSize: '13px' }}>Sem dados suficientes no período.</div>;
  }
  let acumulado = 0;
  const raio = 15.9;
  const circunferencia = 2 * Math.PI * raio;
  const segmentos = dados.map((d, i) => {
    const fracao = (d[campoValor] || 0) / total;
    const comprimento = fracao * circunferencia;
    const offset = circunferencia * 0.25 - acumulado;
    acumulado += comprimento;
    return (
      <circle
        key={i}
        cx="21" cy="21" r={raio}
        fill="transparent"
        stroke={CORES_DONUT[i % CORES_DONUT.length]}
        strokeWidth="6"
        strokeDasharray={`${comprimento} ${circunferencia - comprimento}`}
        strokeDashoffset={offset}
      />
    );
  });
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '26px', flexWrap: 'wrap' }}>
      <svg width={tamanho} height={tamanho} viewBox="0 0 42 42" style={{ flexShrink: 0 }}>
        <circle cx="21" cy="21" r={raio} fill="transparent" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
        {segmentos}
        <text x="21" y="19.5" textAnchor="middle" fontSize="4.6" fill="#f2f5fb" fontWeight="700">{fmtBytes(total)}</text>
        <text x="21" y="24.5" textAnchor="middle" fontSize="2.6" fill="#8792a8">total</text>
      </svg>
      <div style={{ flex: 1, minWidth: '220px' }}>
        {dados.map((d, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.06)', fontSize: '13px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: CORES_DONUT[i % CORES_DONUT.length], flexShrink: 0 }} />
            <span style={{ flex: 1 }}>{d[campoLabel]}</span>
            <span style={{ opacity: 0.7, fontSize: '12px', width: '42px', textAlign: 'right' }}>{d.percentual}%</span>
            <span style={{ opacity: 0.5, fontSize: '11.5px', width: '64px', textAlign: 'right' }}>{fmtBytes(d[campoValor])}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DetalheDispositivo({ token, mac, horas, onHorasChange, onVoltar, role }) {
  const [detalhe, setDetalhe] = useState(null);
  const [subAba, setSubAba] = useState('linha_do_tempo');
  const [nomeRevelado, setNomeRevelado] = useState(null);
  const [carregandoNome, setCarregandoNome] = useState(false);
  const [porHora, setPorHora] = useState(null);

  useEffect(() => {
    if (!token || !mac) return;
    setDetalhe(null);
    axios.get(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}`, {
      params: { horas },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setDetalhe(r.data)).catch(() => {});
  }, [token, mac, horas]);

  useEffect(() => {
    if (subAba !== 'por_hora' || !token || !mac) return;
    setPorHora(null);
    axios.get(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}/por-hora`, {
      params: { horas },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setPorHora(r.data)).catch(() => {});
  }, [subAba, token, mac, horas]);

  if (!detalhe) {
    return <div className="loading-message">Carregando detalhe do dispositivo...</div>;
  }

  const ativoAgora = detalhe.ultima_atividade && (Date.now() - new Date(detalhe.ultima_atividade).getTime()) / 1000 <= 600;
  const maxDuracao = Math.max(...detalhe.top_sites.map((s) => s.duracao_segundos), 1);
  const maxPorHora = porHora ? Math.max(...porHora.map((b) => b.duracao_segundos), 1) : 1;
  const podeRevelarIdentidade = role === 'admin' || role === 'super_admin';
  const ehDispositivoNaoResolvido = mac && mac.startsWith('desconhecido-');

  const revelarIdentidade = () => {
    if (carregandoNome || nomeRevelado) return;
    setCarregandoNome(true);
    axios.get(`${API_URL}/dashboard/acessos/identidade-vpn`, {
      params: { ip: detalhe.ip },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setNomeRevelado(r.data.nome || 'Nao encontrado'))
      .catch(() => setNomeRevelado('Erro ao consultar'))
      .finally(() => setCarregandoNome(false));
  };

  return (
    <div>
      <div style={{ fontSize: '12.5px', opacity: 0.7, cursor: 'pointer', marginBottom: '14px' }} onClick={onVoltar}>
        ‹ Voltar para todos os dispositivos
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', marginBottom: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h3 className="detail-table-title" style={{ margin: 0 }}>{detalhe.hostname || 'Desconhecido'}</h3>
          {ativoAgora && (
            <span style={{ fontSize: '11px', padding: '3px 9px', borderRadius: '999px', background: 'rgba(58, 185, 122, 0.18)', color: '#3ab97a' }}>
              ● ativo agora
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {PERIODOS.map((p) => (
            <button key={p.horas} className={`btn ${horas === p.horas ? 'btn-primary' : 'btn-secondary'}`} onClick={() => onHorasChange(p.horas)}>
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ fontSize: '12.5px', opacity: 0.6, fontFamily: 'monospace', marginBottom: '18px' }}>
        {detalhe.ip} &nbsp;·&nbsp; {mac} {detalhe.ap ? <>&nbsp;·&nbsp; {detalhe.ap}</> : null}
        {podeRevelarIdentidade && ehDispositivoNaoResolvido && (
          <>
            &nbsp;·&nbsp;
            {nomeRevelado ? (
              <span style={{ opacity: 0.85 }}>{nomeRevelado}</span>
            ) : (
              <span
                style={{ cursor: 'pointer', textDecoration: 'underline dotted', opacity: 0.7 }}
                onClick={revelarIdentidade}
              >
                {carregandoNome ? 'consultando...' : 'revelar identidade'}
              </span>
            )}
          </>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', marginBottom: '20px' }}>
        <div className="metric-card">
          <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Sites diferentes</div>
          <div style={{ fontSize: '21px', fontWeight: 800 }}>{detalhe.sites_diferentes}</div>
        </div>
        <div className="metric-card">
          <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Volume total</div>
          <div style={{ fontSize: '21px', fontWeight: 800 }}>{fmtBytes(detalhe.volume_total_bytes)}</div>
        </div>
        <div className="metric-card">
          <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Última atividade</div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: ativoAgora ? '#3ab97a' : undefined }}>{tempoRelativo(detalhe.ultima_atividade)}</div>
        </div>
      </div>

      <h4 className="detail-table-title" style={{ fontSize: '14px' }}>Top sites acessados</h4>
      <Donut dados={detalhe.top_sites} campoValor="volume_bytes" campoLabel="categoria" />

      <div style={{ display: 'flex', gap: '4px', marginTop: '24px', marginBottom: '12px' }}>
        <button className={`btn ${subAba === 'linha_do_tempo' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setSubAba('linha_do_tempo')}>Linha do tempo</button>
        <button className={`btn ${subAba === 'duracao' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setSubAba('duracao')}>Duração por site</button>
        <button className={`btn ${subAba === 'por_hora' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setSubAba('por_hora')}>Por hora do dia</button>
      </div>

      {subAba === 'linha_do_tempo' && (
        <table>
          <thead>
            <tr><th>Início</th><th>Domínio</th><th>Duração</th><th>Volume</th></tr>
          </thead>
          <tbody>
            {detalhe.linha_do_tempo.map((s, i) => (
              <tr key={i}>
                <td style={{ fontSize: '12px', opacity: 0.7 }}>{fmtHora(s.inicio)}</td>
                <td>{s.dominio_principal}{s.dominios.length > 1 ? ` (+${s.dominios.length - 1})` : ''}</td>
                <td style={{ fontSize: '12px' }}>{fmtDuracao(s.duracao_segundos)}</td>
                <td style={{ fontSize: '12px', opacity: 0.7 }}>{fmtBytes(s.bytes_download + s.bytes_upload)}</td>
              </tr>
            ))}
            {detalhe.linha_do_tempo.length === 0 && (
              <tr><td colSpan="4" style={{ textAlign: 'center', opacity: 0.6 }}>Sem acessos no período selecionado.</td></tr>
            )}
          </tbody>
        </table>
      )}

      {subAba === 'duracao' && (
        <table>
          <thead>
            <tr><th>Site</th><th>Tempo conectado</th><th></th></tr>
          </thead>
          <tbody>
            {[...detalhe.top_sites].sort((a, b) => b.duracao_segundos - a.duracao_segundos).map((s, i) => (
              <tr key={i}>
                <td>{s.categoria}</td>
                <td style={{ fontSize: '12px', opacity: 0.7, width: '90px' }}>{fmtDuracao(s.duracao_segundos)}</td>
                <td>
                  <div style={{ width: '100%', height: '8px', borderRadius: '4px', background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', borderRadius: '4px', background: CORES_DONUT[i % CORES_DONUT.length], width: `${(s.duracao_segundos / maxDuracao * 100).toFixed(0)}%` }} />
                  </div>
                </td>
              </tr>
            ))}
            {detalhe.top_sites.length === 0 && (
              <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.6 }}>Sem acessos no período selecionado.</td></tr>
            )}
          </tbody>
        </table>
      )}
      {subAba === 'por_hora' && (
        <div>
          {!porHora ? (
            <div className="loading-message">Carregando...</div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: '3px', height: '160px', marginBottom: '4px' }}>
                {porHora.map((b) => (
                  <div
                    key={b.hora}
                    style={{ flex: 1, display: 'flex', alignItems: 'flex-end', height: '100%' }}
                    title={`${b.hora}h - ${fmtDuracao(b.duracao_segundos)} - ${fmtBytes(b.bytes_total)}`}
                  >
                    <div
                      style={{
                        width: '100%',
                        borderRadius: '3px 3px 0 0',
                        background: CORES_DONUT[0],
                        height: `${Math.max((b.duracao_segundos / maxPorHora) * 100, b.duracao_segundos > 0 ? 3 : 0)}%`,
                      }}
                    />
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '3px' }}>
                {porHora.map((b) => (
                  <div key={b.hora} style={{ flex: 1, textAlign: 'center', fontSize: '9px', opacity: 0.55 }}>
                    {b.hora}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Acessos({ token, role }) {
  const [horas, setHoras] = useState(1440);
  const [dispositivos, setDispositivos] = useState([]);
  const [topSites, setTopSites] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [macSelecionado, setMacSelecionado] = useState(null);

  useEffect(() => {
    if (!token) return;
    setCarregando(true);
    Promise.all([
      axios.get(`${API_URL}/dashboard/acessos/dispositivos`, { params: { horas }, headers: { Authorization: `Bearer ${token}` } }),
      axios.get(`${API_URL}/dashboard/acessos/top-sites`, { params: { horas }, headers: { Authorization: `Bearer ${token}` } }),
    ]).then(([respDispositivos, respTopSites]) => {
      setDispositivos(respDispositivos.data);
      setTopSites(respTopSites.data);
    }).catch(() => {}).finally(() => setCarregando(false));
  }, [token, horas]);

  if (macSelecionado) {
    return (
      <DetalheDispositivo
        token={token}
        mac={macSelecionado}
        horas={horas}
        onHorasChange={setHoras}
        onVoltar={() => setMacSelecionado(null)}
        role={role}
      />
    );
  }

  const volumeTotal = dispositivos.reduce((s, d) => s + d.volume_bytes, 0);
  const sitesUnicosAprox = dispositivos.reduce((s, d) => s + d.sites_diferentes, 0);
  const ativosAgora = dispositivos.filter((d) => d.ativo_agora).length;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '20px', marginBottom: '18px', flexWrap: 'wrap' }}>
        <div>
          <h3 className="detail-table-title" style={{ margin: '0 0 4px 0' }}>Histórico de Acessos</h3>
          <p style={{ fontSize: '13px', opacity: 0.7, maxWidth: '620px', margin: 0 }}>
            Domínios acessados via HTTPS, capturados pelo Suricata (SNI) e cruzados com hostname/IP/MAC da rede. Retenção de 60 dias — dados brutos no HD externo.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {PERIODOS.map((p) => (
            <button key={p.horas} className={`btn ${horas === p.horas ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setHoras(p.horas)}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '20px' }}>
        <div className="metric-card">
          <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Dispositivos monitorados</div>
          <div style={{ fontSize: '23px', fontWeight: 800 }}>{dispositivos.length}</div>
        </div>
        <div className="metric-card">
          <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Sites diferentes (soma por dispositivo)</div>
          <div style={{ fontSize: '23px', fontWeight: 800 }}>{sitesUnicosAprox}</div>
        </div>
        <div className="metric-card">
          <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Volume total</div>
          <div style={{ fontSize: '23px', fontWeight: 800 }}>{fmtBytes(volumeTotal)}</div>
        </div>
        <div className="metric-card">
          <div style={{ fontSize: '11.5px', opacity: 0.7, marginBottom: '6px' }}>Ativos agora</div>
          <div style={{ fontSize: '23px', fontWeight: 800, color: '#3ab97a' }}>{ativosAgora}</div>
        </div>
      </div>

      <h4 className="detail-table-title" style={{ fontSize: '14px' }}>Top sites acessados na rede</h4>
      <Donut dados={topSites} campoValor="volume_bytes" campoLabel="categoria" />

      <table style={{ marginTop: '22px' }}>
        <thead>
          <tr><th>Dispositivo</th><th>IP</th><th>MAC</th><th>Sites diferentes</th><th>Volume</th><th>Última atividade</th></tr>
        </thead>
        <tbody>
          {dispositivos.map((d) => (
            <tr key={d.mac} style={{ cursor: 'pointer' }} onClick={() => setMacSelecionado(d.mac)}>
              <td>{d.hostname}</td>
              <td style={{ opacity: 0.6, fontSize: '12px', fontFamily: 'monospace' }}>{d.ip}</td>
              <td style={{ opacity: 0.6, fontSize: '12px', fontFamily: 'monospace' }}>{d.mac}</td>
              <td>{d.sites_diferentes}</td>
              <td>{fmtBytes(d.volume_bytes)}</td>
              <td style={d.ativo_agora ? { color: '#3ab97a' } : { opacity: 0.6 }}>{d.ativo_agora ? 'agora' : tempoRelativo(d.ultima_atividade)}</td>
            </tr>
          ))}
          {!carregando && dispositivos.length === 0 && (
            <tr><td colSpan="6" style={{ textAlign: 'center', opacity: 0.6 }}>Nenhum acesso registrado no período selecionado.</td></tr>
          )}
          {carregando && dispositivos.length === 0 && (
            <tr><td colSpan="6" style={{ textAlign: 'center', opacity: 0.6 }}>Carregando dispositivos...</td></tr>
          )}
        </tbody>
      </table>
      <p style={{ marginTop: '12px', fontSize: '12px', opacity: 0.5 }}>Clique em um dispositivo para ver o detalhe (sites acessados, linha do tempo).</p>
    </div>
  );
}

export default Acessos;
