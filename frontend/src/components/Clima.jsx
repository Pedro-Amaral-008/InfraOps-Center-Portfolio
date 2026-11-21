import './Clima.css';
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import MapaRadar from './MapaRadar';

const API_URL = '';

const CLASSIFICACAO_CHUVA = [
  { label: 'Sem chuva', min: 0, max: 0, cor: 'var(--status-online)', icone: '☀️' },
  { label: 'Chuva Leve', min: 0.1, max: 2.5, cor: '#3498db', icone: '🌦️' },
  { label: 'Chuva Moderada', min: 2.5, max: 7.5, cor: '#f39c12', icone: '🌧️' },
  { label: 'Chuva Forte', min: 7.5, max: 50, cor: '#e67e22', icone: '⛈️' },
  { label: 'Chuva Severa', min: 50, max: Infinity, cor: '#e74c3c', icone: '🌊' },
];

function classificarChuva(mm) {
  if (!mm || mm <= 0) return CLASSIFICACAO_CHUVA[0];
  return CLASSIFICACAO_CHUVA.find(c => mm >= c.min && mm < c.max) || CLASSIFICACAO_CHUVA[4];
}

function direcaoVento(graus) {
  if (graus == null) return '—';
  const dirs = ['N', 'NE', 'L', 'SE', 'S', 'SO', 'O', 'NO'];
  return dirs[Math.round(graus / 45) % 8];
}

function CardClima({ titulo, valor, unidade, icone, destaque }) {
  return (
    <div className="clima-card" style={destaque ? { borderColor: destaque } : {}}>
      <div className="clima-card-header">
        <span className="clima-card-icone">{icone}</span>
        <span className="clima-card-titulo">{titulo}</span>
      </div>
      <div className="clima-card-valor">
        <span className="clima-card-numero">{valor ?? '—'}</span>
        {unidade && <span className="clima-card-unidade">{unidade}</span>}
      </div>
    </div>
  );
}

function AlertaClima({ tipo, mensagem, hora }) {
  const cores = {
    critical: { bg: 'rgba(231,76,60,0.12)', border: '#e74c3c', label: 'CRÍTICO' },
    warning: { bg: 'rgba(243,156,18,0.12)', border: '#f39c12', label: 'AVISO' },
    info: { bg: 'rgba(52,152,219,0.12)', border: '#3498db', label: 'INFO' },
    ok: { bg: 'rgba(46,204,113,0.12)', border: '#2ecc71', label: 'OK' },
  };
  const estilo = cores[tipo] || cores.info;
  return (
    <div className="clima-alerta" style={{ background: estilo.bg, borderLeft: `3px solid ${estilo.border}` }}>
      <span className="clima-alerta-badge" style={{ color: estilo.border }}>{estilo.label}</span>
      <span className="clima-alerta-msg">{mensagem}</span>
      {hora && <span className="clima-alerta-hora">{hora}</span>}
    </div>
  );
}

function Clima({ token }) {
  const [dados, setDados] = useState(null);
  const [alertas, setAlertas] = useState([]);
  const [previsaoHoras, setPrevisaoHoras] = useState([]);

  const [erroApi, setErroApi] = useState(false);
  const [ultimaAtualizacao, setUltimaAtualizacao] = useState(null);

  const buscarClima = useCallback(() => {
    if (!token) return;

    axios.get(`${API_URL}/clima/atual`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (r.data && r.data.temperatura !== undefined) {
          setDados(r.data);
          setErroApi(false);
          setUltimaAtualizacao(new Date());
        } else {
          setErroApi(true);
        }
      })
      .catch(() => setErroApi(true));

    axios.get(`${API_URL}/clima/alertas`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (Array.isArray(r.data)) setAlertas(r.data); })
      .catch(() => {});

    axios.get(`${API_URL}/clima/previsao-horas`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (Array.isArray(r.data)) setPrevisaoHoras(r.data); })
      .catch(() => {});

  }, [token]);

  useEffect(() => {
    buscarClima();
    const intervalo = setInterval(buscarClima, 600000);
    return () => clearInterval(intervalo);
  }, [buscarClima]);



  const chuvaAtual = dados ? classificarChuva(dados.precipitacao_mm) : CLASSIFICACAO_CHUVA[0];

  return (
    <div className="clima-container">
      <div className="clima-header">
        <div>
          <h2 className="page-title" style={{ marginBottom: '4px' }}>Clima — Goiânia</h2>
          <span className="clima-subtitulo">
            Monitoramento meteorológico em tempo real
            {ultimaAtualizacao && (
              <> · Atualizado às {ultimaAtualizacao.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</>
            )}
          </span>
        </div>
        <div className="clima-status-badge" style={{ background: chuvaAtual.cor + '22', color: chuvaAtual.cor, border: `1px solid ${chuvaAtual.cor}44` }}>
          <span>{chuvaAtual.icone}</span> {chuvaAtual.label}
        </div>
      </div>

      {erroApi && (
        <div className="clima-erro">
          ⚠️ API de clima não disponível. Verifique se o endpoint <code>/clima</code> está configurado e a chave OpenWeatherMap está definida no <code>.env</code>.
        </div>
      )}

      <div className="clima-cards-grid">
        <CardClima titulo="Temperatura" valor={dados ? `${dados.temperatura?.toFixed(1)}` : null} unidade="°C" icone="🌡️" />
        <CardClima titulo="Umidade" valor={dados ? `${dados.umidade}` : null} unidade="%" icone="💧" />
        <CardClima titulo="Vento" valor={dados ? `${dados.vento_kmh?.toFixed(1)}` : null} unidade={dados ? `km/h ${direcaoVento(dados.vento_direcao)}` : 'km/h'} icone="💨" />
        <CardClima titulo="Precipitação" valor={dados ? `${dados.precipitacao_mm?.toFixed(1)}` : null} unidade="mm/h" icone="🌧️" destaque={chuvaAtual.cor} />
        <CardClima titulo="Visibilidade" valor={dados ? `${(dados.visibilidade_m / 1000).toFixed(1)}` : null} unidade="km" icone="👁️" />
        <CardClima titulo="Nuvens" valor={dados ? `${dados.nuvens}` : null} unidade="%" icone="☁️" />
      </div>

      <div className="clima-main-grid">
        <div className="clima-radar-section">
          <h3 className="clima-section-title">Radar Meteorológico</h3>
          <div className="clima-radar-wrap">
            <MapaRadar />
          </div>
          <span className="clima-radar-credit">Dados do radar: RainViewer · Mapa: CARTO</span>
        </div>

        <div className="clima-alertas-section">
          <h3 className="clima-section-title">Alertas Ativos</h3>
          <div className="clima-alertas-lista">
            {alertas.length === 0 && !erroApi && (
              <AlertaClima tipo="ok" mensagem="Nenhum alerta meteorológico ativo no momento." />
            )}
            {alertas.map((a, i) => (
              <AlertaClima key={i} tipo={a.tipo} mensagem={a.mensagem} hora={a.hora ? new Date(a.hora).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : null} />
            ))}
          </div>
        </div>
      </div>

      {previsaoHoras.length > 0 && (
        <div className="clima-previsao-section">
          <h3 className="clima-section-title">Previsão — Próximas Horas</h3>
          <div className="clima-previsao-scroll">
            {previsaoHoras.map((h, i) => {
              const prob = h.probabilidade_chuva ?? 0;
              const temChuva = prob > 50;
              return (
                <div className={`clima-hora-card ${temChuva ? 'clima-hora-chuva' : ''}`} key={i}>
                  <span className="clima-hora-label">{h.hora}</span>
                  <span className="clima-hora-icone">{h.icone || (temChuva ? '🌧️' : '☀️')}</span>
                  <span className="clima-hora-temp">{h.temperatura?.toFixed(0)}°</span>
                  <span className="clima-hora-prob" style={{ color: temChuva ? '#3498db' : 'var(--text-tertiary)' }}>{prob}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

    </div>
  );
}

export default Clima;
