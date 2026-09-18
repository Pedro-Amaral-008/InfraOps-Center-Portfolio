import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_URL = '';

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
  const [apelido, setApelido] = useState(null);
  const [apelidoVisivel, setApelidoVisivel] = useState(false);
  const [carregandoApelido, setCarregandoApelido] = useState(false);
  const [editandoApelido, setEditandoApelido] = useState(false);
  const [rascunhoApelido, setRascunhoApelido] = useState('');
  const [salvandoApelido, setSalvandoApelido] = useState(false);
  const [filtroProdutividade, setFiltroProdutividade] = useState('geral');
  const [timelineExpandida, setTimelineExpandida] = useState(false);
  const [horaSelecionada, setHoraSelecionada] = useState(null);
  const [tooltipHora, setTooltipHora] = useState(null);
  const [tooltipLeft, setTooltipLeft] = useState(0);
  const barrasRef = useRef(null);

  useEffect(() => {
    if (!token || !mac) return;
    setDetalhe(null);
    axios.get(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}`, {
      params: { horas },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setDetalhe(r.data)).catch(() => {});
  }, [token, mac, horas]);

  const [dominiosAmeaca, setDominiosAmeaca] = useState([]);
  useEffect(() => {
    if (!token || !mac) return;
    setDominiosAmeaca([]);
    axios.get(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}/ameacas`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setDominiosAmeaca(r.data || [])).catch(() => {});
  }, [token, mac]);

  useEffect(() => {
    if (subAba !== 'por_hora' || !token || !mac) return;
    setPorHora(null);
    axios.get(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}/por-hora`, {
      params: { horas },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => setPorHora(r.data)).catch(() => {});
  }, [subAba, token, mac, horas]);
  useEffect(() => {
    setApelido(null);
    setApelidoVisivel(false);
    setEditandoApelido(false);
  }, [mac]);
  useEffect(() => { setTimelineExpandida(false); }, [mac, horas, filtroProdutividade]);
  useEffect(() => { setHoraSelecionada(null); }, [mac, horas, filtroProdutividade, subAba]);

  if (!detalhe) {
    return <div className="loading-message">Carregando detalhe do dispositivo...</div>;
  }

  const ativoAgora = detalhe.ultima_atividade && (Date.now() - new Date(detalhe.ultima_atividade).getTime()) / 1000 <= 600;
  const categoriaTipoMap = Object.fromEntries(detalhe.top_sites.map((s) => [s.categoria, s.tipo]));
  const topSitesFiltrados = (() => {
    if (filtroProdutividade === 'geral') return detalhe.top_sites;
    const filtrados = detalhe.top_sites.filter((s) => s.tipo === filtroProdutividade);
    const totalFiltrado = filtrados.reduce((acc, s) => acc + s.volume_bytes, 0);
    return filtrados.map((s) => ({ ...s, percentual: totalFiltrado ? Math.round((s.volume_bytes / totalFiltrado) * 1000) / 10 : 0 }));
  })();
  const linhaDoTempoFiltrada = filtroProdutividade === 'geral' ? detalhe.linha_do_tempo : detalhe.linha_do_tempo.filter((s) => categoriaTipoMap[s.categoria] === filtroProdutividade);
  const timelineParaMostrar = timelineExpandida ? linhaDoTempoFiltrada : linhaDoTempoFiltrada.slice(0, 20);
  const maxDuracao = Math.max(...topSitesFiltrados.map((s) => s.duracao_segundos), 1);
  const maxPorHora = porHora ? Math.max(...porHora.map((b) => b.produtivo_segundos_media + b.nao_produtivo_segundos_media + b.neutro_segundos_media), 1) : 1;
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
  const mostrarApelido = () => {
    if (carregandoApelido) return;
    if (apelido !== null) {
      setApelidoVisivel(true);
      return;
    }
    setCarregandoApelido(true);
    axios.get(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}/apelido`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => {
      setApelido(r.data.apelido || '');
      setApelidoVisivel(true);
    }).catch(() => {})
      .finally(() => setCarregandoApelido(false));
  };
  const salvarApelido = () => {
    if (salvandoApelido) return;
    setSalvandoApelido(true);
    axios.put(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}/apelido`, null, {
      params: { apelido: rascunhoApelido },
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => {
      setApelido(r.data.apelido);
      setEditandoApelido(false);
    }).catch(() => {})
      .finally(() => setSalvandoApelido(false));
  };
  const periodoAtual = PERIODOS.find((p) => p.horas === horas) || PERIODOS[0];
  const baixarRelatorioDispositivo = async (formato) => {
    const resp = await axios.get(`${API_URL}/dashboard/acessos/dispositivo/${encodeURIComponent(mac)}/relatorio.${formato}`, {
      params: { horas, periodo_label: periodoAtual.label },
      headers: { Authorization: `Bearer ${token}` },
      responseType: 'blob',
    });
    const mime = formato === 'pdf' ? 'application/pdf' : 'text/html';
    const url = window.URL.createObjectURL(new Blob([resp.data], { type: mime }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio-${detalhe.hostname || mac}.${formato}`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div style={{ fontSize: '12.5px', opacity: 0.7, cursor: 'pointer', marginBottom: '14px' }} onClick={onVoltar}>
        ‹ Voltar para todos os dispositivos
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', marginBottom: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h3 className="detail-table-title" style={{ margin: 0 }}>{detalhe.hostname || 'Desconhecido'}</h3>
          {podeRevelarIdentidade && (
            editandoApelido ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input
                  type="text"
                  value={rascunhoApelido}
                  onChange={(e) => setRascunhoApelido(e.target.value)}
                  placeholder="apelido do dispositivo"
                  style={{ fontSize: '12.5px', padding: '3px 8px', borderRadius: '6px' }}
                  autoFocus
                />
                <button className="btn btn-secondary" disabled={salvandoApelido} onClick={salvarApelido}>
                  {salvandoApelido ? 'salvando...' : 'salvar'}
                </button>
                <span style={{ cursor: 'pointer', opacity: 0.6, fontSize: '12px' }} onClick={() => setEditandoApelido(false)}>
                  cancelar
                </span>
              </span>
            ) : apelidoVisivel ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '12.5px', opacity: 0.85 }}>{apelido ? apelido : '(sem apelido)'}</span>
                <span
                  style={{ cursor: 'pointer', textDecoration: 'underline dotted', opacity: 0.6, fontSize: '12px' }}
                  onClick={() => { setRascunhoApelido(apelido || ''); setEditandoApelido(true); }}
                >
                  editar
                </span>
                <span
                  style={{ cursor: 'pointer', textDecoration: 'underline dotted', opacity: 0.6, fontSize: '12px' }}
                  onClick={() => setApelidoVisivel(false)}
                >
                  ocultar
                </span>
              </span>
            ) : (
              <span
                style={{ fontSize: '12.5px', opacity: 0.7, cursor: 'pointer', textDecoration: 'underline dotted' }}
                onClick={mostrarApelido}
              >
                {carregandoApelido ? 'consultando...' : 'mostrar apelido'}
              </span>
            )
          )}
          {ativoAgora && (
            <span style={{ fontSize: '11px', padding: '3px 9px', borderRadius: '999px', background: 'rgba(58, 185, 122, 0.18)', color: '#3ab97a' }}>
              ● ativo agora
            </span>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '9px', padding: '3px' }}>
            <button className={`btn ${filtroProdutividade === 'geral' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFiltroProdutividade('geral')}>Geral</button>
            <button className={`btn ${filtroProdutividade === 'produtivo' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFiltroProdutividade('produtivo')}>Produtivo</button>
            <button className={`btn ${filtroProdutividade === 'nao_produtivo' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFiltroProdutividade('nao_produtivo')}>Não produtivo</button>
          </div>
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            {PERIODOS.map((p) => (
              <button key={p.horas} className={`btn ${horas === p.horas ? 'btn-primary' : 'btn-secondary'}`} onClick={() => onHorasChange(p.horas)}>
                {p.label}
              </button>
            ))}
          </div>
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

      {podeRevelarIdentidade && (
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={() => baixarRelatorioDispositivo('pdf')}>
            Baixar relatório (PDF) — {periodoAtual.label}
          </button>
          <button className="btn btn-secondary" onClick={() => baixarRelatorioDispositivo('html')}>
            Baixar relatório (HTML) — {periodoAtual.label}
          </button>
        </div>
      )}

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

      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '12px', padding: '16px 18px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
          <h4 className="detail-table-title" style={{ fontSize: '14px', margin: 0 }}>Produtividade no período</h4>
          <span style={{ fontSize: '11px', opacity: 0.55 }}>calculado por tempo com atividade, não por bytes</span>
        </div>
        <div style={{ display: 'flex', height: '10px', borderRadius: '999px', overflow: 'hidden', background: 'rgba(255,255,255,0.06)', marginBottom: '12px' }}>
          <div style={{ width: `${detalhe.produtividade.produtivo_pct}%`, background: '#3ab97a' }} />
          <div style={{ width: `${detalhe.produtividade.nao_produtivo_pct}%`, background: '#e5a23a' }} />
          <div style={{ width: `${detalhe.produtividade.neutro_pct}%`, background: '#576078' }} />
        </div>
        <div style={{ display: 'flex', gap: '18px', flexWrap: 'wrap', fontSize: '12.5px' }}>
          <span><span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#3ab97a', marginRight: '6px' }} />Produtivo <b>{detalhe.produtividade.produtivo_pct}%</b> <span style={{ opacity: 0.6 }}>· {fmtDuracao(detalhe.produtividade.produtivo_segundos)}</span></span>
          <span><span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#e5a23a', marginRight: '6px' }} />Não produtivo <b>{detalhe.produtividade.nao_produtivo_pct}%</b> <span style={{ opacity: 0.6 }}>· {fmtDuracao(detalhe.produtividade.nao_produtivo_segundos)}</span></span>
          <span><span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#576078', marginRight: '6px' }} />Não classificado <b>{detalhe.produtividade.neutro_pct}%</b> <span style={{ opacity: 0.6 }}>· {fmtDuracao(detalhe.produtividade.neutro_segundos)}</span></span>
        </div>
      </div>

      <h4 className="detail-table-title" style={{ fontSize: '14px' }}>Top sites acessados{filtroProdutividade !== 'geral' && (
        <span style={{ fontWeight: 400, opacity: 0.55, fontSize: '12px' }}> — filtrado em {filtroProdutividade === 'produtivo' ? 'Produtivo' : 'Não produtivo'}</span>
      )}</h4>
      <Donut dados={topSitesFiltrados} campoValor="volume_bytes" campoLabel="categoria" />

      <div style={{ display: 'flex', gap: '4px', marginTop: '24px', marginBottom: '12px' }}>
        <button className={`btn ${subAba === 'linha_do_tempo' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setSubAba('linha_do_tempo')}>Linha do tempo</button>
        <button className={`btn ${subAba === 'duracao' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setSubAba('duracao')}>Duração por site</button>
        <button className={`btn ${subAba === 'por_hora' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setSubAba('por_hora')}>Por hora do dia</button>
      </div>

      {subAba === 'linha_do_tempo' && (
        <table>
          <thead>
            <tr><th>Início</th><th>Domínio</th><th>Duração</th><th>Tipo</th><th>Volume</th></tr>
          </thead>
          <tbody>
            {timelineParaMostrar.map((s, i) => {
              const ehAmeaca = s.dominios.some((d) => dominiosAmeaca.includes(d));
              const tipoSessao = categoriaTipoMap[s.categoria];
              const corTag = tipoSessao === 'produtivo' ? '#3ab97a' : tipoSessao === 'nao_produtivo' ? '#e5a23a' : '#8792a8';
              return (
                <tr key={i} style={ehAmeaca ? { background: 'rgba(220,50,50,0.12)' } : undefined}>
                  <td style={{ fontSize: '12px', opacity: 0.7 }}>{fmtHora(s.inicio)}</td>
                  <td style={ehAmeaca ? { color: '#ff5555', fontWeight: 600 } : undefined}>
                    {ehAmeaca && '⚠️ '}{s.dominio_principal}{s.dominios.length > 1 ? ` (+${s.dominios.length - 1})` : ''}
                  </td>
                  <td style={{ fontSize: '12px' }}>{fmtDuracao(s.duracao_segundos)}</td>
                  <td>
                    <span style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '999px', background: `${corTag}26`, color: corTag }}>
                      {tipoSessao === 'produtivo' ? 'produtivo' : tipoSessao === 'nao_produtivo' ? 'não produtivo' : 'neutro'}
                    </span>
                  </td>
                  <td style={{ fontSize: '12px', opacity: 0.7 }}>{fmtBytes(s.bytes_download + s.bytes_upload)}</td>
                </tr>
              );
            })}
            {linhaDoTempoFiltrada.length === 0 && (
              <tr><td colSpan="5" style={{ textAlign: 'center', opacity: 0.6 }}>Sem acessos {filtroProdutividade === 'geral' ? '' : filtroProdutividade === 'produtivo' ? 'produtivos ' : 'não produtivos '}no período selecionado.</td></tr>
            )}
          </tbody>
        </table>
      )}
      {subAba === 'linha_do_tempo' && linhaDoTempoFiltrada.length > 20 && (
        <div style={{ textAlign: 'center', marginTop: '10px' }}>
          <button className="btn btn-secondary" onClick={() => setTimelineExpandida(!timelineExpandida)}>
            {timelineExpandida ? 'Mostrar menos' : `Mostrar linha do tempo completa (${linhaDoTempoFiltrada.length} sessões)`}
          </button>
        </div>
      )}

      {subAba === 'duracao' && (
        <table>
          <thead>
            <tr><th>Site</th><th>Tempo conectado</th><th></th></tr>
          </thead>
          <tbody>
            {[...topSitesFiltrados].sort((a, b) => b.duracao_segundos - a.duracao_segundos).map((s, i) => (
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
            {topSitesFiltrados.length === 0 && (
              <tr><td colSpan="3" style={{ textAlign: 'center', opacity: 0.6 }}>Sem acessos no período selecionado.</td></tr>
            )}
          </tbody>
        </table>
      )}
      {subAba === 'por_hora' && (
  <div>
    {(!porHora || porHora.length === 0) ? (
      <div style={{ padding: '24px 0', textAlign: 'center', opacity: 0.6, fontSize: 13 }}>Carregando dados por hora...</div>
    ) : (
    <>
    <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'nowrap' }}>
      <div style={{ background: '#151b24', border: '1px solid rgba(255,255,255,0.10)', borderRadius: 14, padding: '20px 22px 18px', flex: '2.2 1 0', minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 4, fontSize: 11.5, color: '#97a3b5' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: '#22c55e', flexShrink: 0 }} />
            Produtivo
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: '#f59e0b', flexShrink: 0 }} />
            Não produtivo
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: '#4b5563', flexShrink: 0 }} />
            Neutro
          </div>
        </div>

        <div style={{ position: 'relative', marginTop: 18, overflow: 'visible' }}>
          <div style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 34, pointerEvents: 'none' }}>
            {[0, 1, 2, 3, 4].map((i) => {
              const val = (maxPorHora / 4) * i;
              return (
                <div key={i} style={{ position: 'absolute', left: 0, right: 0, bottom: `${(i / 4) * 200}px`, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                  <span style={{ position: 'absolute', left: 0, fontSize: 9.5, color: '#7c8a9c', transform: 'translateY(-6px)' }}>
                    {i === 0 ? '' : fmtDuracao(Math.round(val))}
                  </span>
                </div>
              );
            })}
          </div>

          <div ref={barrasRef} style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 200, position: 'relative', paddingLeft: 34, overflow: 'visible' }}>
            {porHora.map((b) => {
              const total = b.produtivo_segundos_media + b.nao_produtivo_segundos_media + b.neutro_segundos_media;
              const dias = b.dias_amostrados ?? 0;
              const segmentos = [
                { val: b.produtivo_segundos_media, cor: '#22c55e' },
                { val: b.nao_produtivo_segundos_media, cor: '#f59e0b' },
                { val: b.neutro_segundos_media, cor: '#4b5563' },
              ].filter((s) => s.val > 0);

              const dotClasse = dias >= 10 ? 'alta' : dias >= 4 ? 'media' : dias >= 1 ? 'baixa' : null;
              const dotOpacidade = dotClasse === 'alta' ? 1 : dotClasse === 'media' ? 0.65 : dotClasse === 'baixa' ? 0.35 : 0;

              return (
                <div
                  key={b.hora}
                  onClick={() => setHoraSelecionada((prev) => (prev === b.hora ? null : b.hora))}
                  onMouseEnter={() => setTooltipHora(b)}
                  onMouseMove={(e) => {
                    if (!barrasRef.current) return;
                    const rect = barrasRef.current.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    setTooltipLeft(Math.min(Math.max(x - 80, 0), rect.width - 170));
                  }}
                  onMouseLeave={() => setTooltipHora(null)}
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column-reverse',
                    alignItems: 'stretch',
                    height: '100%',
                    position: 'relative',
                    cursor: 'pointer',
                    overflow: 'visible',
                  }}
                >
                  {segmentos.map((s, idx) => (
                    <div
                      key={idx}
                      style={{
                        width: '100%',
                        height: `${(s.val / maxPorHora) * 200}px`,
                        background: s.cor,
                        marginBottom: idx === segmentos.length - 1 ? 0 : 2,
                        borderRadius:
                          idx === 0 && idx === segmentos.length - 1
                            ? '3px 3px 3px 3px'
                            : idx === 0
                            ? '0 0 3px 3px'
                            : idx === segmentos.length - 1
                            ? '3px 3px 0 0'
                            : 0,
                      }}
                    />
                  ))}
                  {dotClasse && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: -16,
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: '#7c8a9c',
                        opacity: dotOpacidade,
                      }}
                    />
                  )}
                </div>
              );
            })}

            {tooltipHora && (
              <div
                style={{
                  position: 'absolute',
                  left: tooltipLeft,
                  top: -96,
                  background: '#0d1117',
                  border: '1px solid rgba(255,255,255,0.10)',
                  borderRadius: 8,
                  padding: '10px 12px',
                  fontSize: 11,
                  minWidth: 160,
                  boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                  pointerEvents: 'none',
                  zIndex: 10,
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 11.5 }}>
                  {String(tooltipHora.hora).padStart(2, '0')}:00 – {String((tooltipHora.hora + 1) % 24).padStart(2, '0')}:00
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, marginBottom: 3 }}>
                  <span style={{ color: '#97a3b5', display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 7, height: 7, borderRadius: 2, background: '#22c55e' }} />
                    Produtivo
                  </span>
                  <b>{fmtDuracao(tooltipHora.produtivo_segundos_media)}</b>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, marginBottom: 3 }}>
                  <span style={{ color: '#97a3b5', display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 7, height: 7, borderRadius: 2, background: '#f59e0b' }} />
                    Não produtivo
                  </span>
                  <b>{fmtDuracao(tooltipHora.nao_produtivo_segundos_media)}</b>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, marginBottom: 3 }}>
                  <span style={{ color: '#97a3b5', display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span style={{ width: 7, height: 7, borderRadius: 2, background: '#4b5563' }} />
                    Neutro
                  </span>
                  <b>{fmtDuracao(tooltipHora.neutro_segundos_media)}</b>
                </div>
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.08)', color: '#7c8a9c', fontSize: 10 }}>
                  Média por dia · baseado em {tooltipHora.dias_amostrados ?? 0} dia(s) com atividade nessa hora
                </div>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 3, paddingLeft: 34, marginTop: 26 }}>
          {porHora.map((b) => (
            <div key={b.hora} style={{ flex: 1, textAlign: 'center', fontSize: 10, color: '#7c8a9c' }}>
              {b.hora % 3 === 0 ? String(b.hora).padStart(2, '0') : ''}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 30, fontSize: 11, color: '#7c8a9c', flexWrap: 'wrap' }}>
          <span>Amostra por hora:</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#7c8a9c', opacity: 0.35 }} /> fraca (1–3 dias)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#7c8a9c', opacity: 0.65 }} /> média (4–9 dias)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#7c8a9c', opacity: 1 }} /> forte (10+ dias)
          </span>
        </div>
      </div>

      <div style={{ background: '#151b24', border: '1px solid rgba(255,255,255,0.10)', borderRadius: 14, padding: '20px 22px 18px', flex: '1 1 0', minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Top 3 categorias do período</div>
        <div style={{ fontSize: 11.5, color: '#97a3b5', marginBottom: 16 }}>Por tempo conectado</div>
        {[...topSitesFiltrados].sort((a, b) => b.duracao_segundos - a.duracao_segundos).slice(0, 3).map((s, i) => {
          const tipoSessao = categoriaTipoMap[s.categoria];
          const cor = tipoSessao === 'produtivo' ? '#22c55e' : tipoSessao === 'nao_produtivo' ? '#f59e0b' : '#4b5563';
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '10px 0', borderBottom: i < 2 ? '1px solid rgba(255,255,255,0.08)' : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: cor, flexShrink: 0 }} />
                <span style={{ fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.categoria}</span>
              </div>
              <span style={{ fontSize: 12, color: '#97a3b5', flexShrink: 0 }}>{fmtDuracao(s.duracao_segundos)}</span>
            </div>
          );
        })}
        {topSitesFiltrados.length === 0 && (
          <div style={{ opacity: 0.6, fontSize: 12 }}>Sem dados no período.</div>
        )}
      </div>
    </div>

    {horaSelecionada !== null && (() => {
      const sessoesHora = linhaDoTempoFiltrada
        .filter((s) => s.hora_local === horaSelecionada)
        .sort((a, b) => new Date(a.inicio) - new Date(b.inicio));
      return (
        <div style={{ marginTop: 16, background: '#1b2330', border: '1px solid rgba(255,255,255,0.10)', borderRadius: 10, padding: '14px 16px', fontSize: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <b>Acessos entre {String(horaSelecionada).padStart(2, '0')}:00 e {String((horaSelecionada + 1) % 24).padStart(2, '0')}:00</b>
            <span style={{ color: '#97a3b5', cursor: 'pointer', fontSize: 11 }} onClick={() => setHoraSelecionada(null)}>fechar ✕</span>
          </div>
          {sessoesHora.length === 0 ? (
            <div style={{ opacity: 0.6 }}>Sem acessos registrados nesse horário.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', color: '#97a3b5', fontWeight: 500, padding: '4px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)', fontSize: 11 }}>Horário</th>
                  <th style={{ textAlign: 'left', color: '#97a3b5', fontWeight: 500, padding: '4px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)', fontSize: 11 }}>Categoria</th>
                  <th style={{ textAlign: 'left', color: '#97a3b5', fontWeight: 500, padding: '4px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)', fontSize: 11 }}>Tipo</th>
                  <th style={{ textAlign: 'left', color: '#97a3b5', fontWeight: 500, padding: '4px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)', fontSize: 11 }}>Duração</th>
                </tr>
              </thead>
              <tbody>
                {sessoesHora.map((s, i) => {
                  const tipoSessao = categoriaTipoMap[s.categoria];
                  const corTag = tipoSessao === 'produtivo' ? '#3ab97a' : tipoSessao === 'nao_produtivo' ? '#e5a23a' : '#8792a8';
                  return (
                    <tr key={i}>
                      <td style={{ padding: '5px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>{fmtHora(s.inicio)}</td>
                      <td style={{ padding: '5px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>{s.categoria}</td>
                      <td style={{ padding: '5px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                        <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 999, background: `${corTag}26`, color: corTag }}>
                          {tipoSessao === 'produtivo' ? 'produtivo' : tipoSessao === 'nao_produtivo' ? 'não produtivo' : 'neutro'}
                        </span>
                      </td>
                      <td style={{ padding: '5px 8px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>{fmtDuracao(s.duracao_segundos)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      );
    })()}
    </>
    )}
  </div>
)}
    </div>
  );
}

function Acessos({ token, role, macInicial, onMacInicialConsumido }) {
  const [horas, setHoras] = useState(24);
  const [dispositivos, setDispositivos] = useState([]);
  const [topSites, setTopSites] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [macSelecionado, setMacSelecionado] = useState(null);
  const [busca, setBusca] = useState('');
  useEffect(() => {
    if (macInicial) {
      setMacSelecionado(macInicial);
      if (onMacInicialConsumido) onMacInicialConsumido();
    }
  }, [macInicial]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setCarregando(true);
    Promise.all([
      axios.get(`${API_URL}/dashboard/acessos/dispositivos`, { params: { horas }, headers: { Authorization: `Bearer ${token}` }, signal: controller.signal }),
      axios.get(`${API_URL}/dashboard/acessos/top-sites`, { params: { horas }, headers: { Authorization: `Bearer ${token}` }, signal: controller.signal }),
    ]).then(([respDispositivos, respTopSites]) => {
      setDispositivos(respDispositivos.data);
      setTopSites(respTopSites.data);
    }).catch(() => {}).finally(() => setCarregando(false));
    // cancela a requisicao de verdade se o usuario sair da aba antes de terminar
    return () => controller.abort();
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
  const podeVerApelido = role === 'admin' || role === 'super_admin';
  const buscaNormalizada = busca.trim().toLowerCase();
  const dispositivosFiltrados = buscaNormalizada
    ? dispositivos.filter((d) =>
        (d.hostname || '').toLowerCase().includes(buscaNormalizada) ||
        (podeVerApelido && d.apelido && d.apelido.toLowerCase().includes(buscaNormalizada))
      )
    : dispositivos;

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

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px', margin: '22px 0 16px', flexWrap: 'wrap' }}>
        <input
          type="text"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder={podeVerApelido ? 'Buscar por nome ou apelido...' : 'Buscar por nome do dispositivo...'}
          style={{ flex: 1, minWidth: '260px', maxWidth: '380px', padding: '9px 12px', borderRadius: '8px', border: '1px solid var(--border-default)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: '13.5px' }}
        />
        <div style={{ color: 'var(--text-tertiary)', fontSize: '12.5px', whiteSpace: 'nowrap' }}>
          {buscaNormalizada ? `${dispositivosFiltrados.length} de ${dispositivos.length} dispositivos` : `${dispositivos.length} dispositivos monitorados`}
        </div>
      </div>

      <table>
        <thead>
          <tr><th>Dispositivo</th><th>IP</th><th>MAC</th><th>Sites diferentes</th><th>Volume</th><th>Última atividade</th></tr>
        </thead>
        <tbody>
          {dispositivosFiltrados.map((d) => (
            <tr key={d.mac} style={{ cursor: 'pointer' }} onClick={() => setMacSelecionado(d.mac)}>
              <td>{d.hostname}</td>
              <td style={{ opacity: 0.6, fontSize: '12px', fontFamily: 'monospace' }}>{d.ip}</td>
              <td style={{ opacity: 0.6, fontSize: '12px', fontFamily: 'monospace' }}>{d.mac}</td>
              <td>{d.sites_diferentes}</td>
              <td>{fmtBytes(d.volume_bytes)}</td>
              <td style={d.ativo_agora ? { color: '#3ab97a' } : { opacity: 0.6 }}>{d.ativo_agora ? 'agora' : tempoRelativo(d.ultima_atividade)}</td>
            </tr>
          ))}
          {!carregando && dispositivos.length > 0 && dispositivosFiltrados.length === 0 && (
            <tr><td colSpan="6" style={{ textAlign: 'center', opacity: 0.6 }}>Nenhum dispositivo encontrado{podeVerApelido ? ' com esse nome ou apelido.' : ' com esse nome.'}</td></tr>
          )}
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
