import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import StatusCard from './components/StatusCard';
import Login from './components/Login';
import TrocarSenha from './components/TrocarSenha';
import MetricChart from './components/MetricChart';
import RefreshSelector from './components/RefreshSelector';
import Tabs from './components/Tabs';
import ServerResourceCard from './components/ServerResourceCard';
import Auditoria from './components/Auditoria';
import Automacoes from './components/Automacoes';
import './App.css';

const API_URL = 'IP_INTERNO_AQUI:8000';

const ABAS = [
  { id: 'controller', label: 'Controller' },
  { id: 'servidores', label: 'Servidores' },
  { id: 'access_points', label: 'Access Points' },
  { id: 'impressoras', label: 'Impressoras' },
  { id: 'backups', label: 'Backups' },
  { id: 'links_internet', label: 'Links de Internet' },
];

function formatarTamanho(gb) {
  if (gb >= 1024) {
    return `${(gb / 1024).toFixed(1)} TB`;
  }
  return `${gb} GB`;
}

function calcularJanelaMinutos(intervaloMs) {
  if (intervaloMs <= 5000) return 3;
  if (intervaloMs <= 30000) return 15;
  if (intervaloMs <= 60000) return 60;
  if (intervaloMs <= 1800000) return 720;
  return 2880;
}

function App() {
  const [usuario, setUsuario] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('infraops_token'));
  const [deveTrocarSenha, setDeveTrocarSenha] = useState(false);
  const [dados, setDados] = useState(null);
  const [metricas, setMetricas] = useState(null);
  const [latencias, setLatencias] = useState({});
  const [agentes, setAgentes] = useState([]);
  const [controllerAtual, setControllerAtual] = useState(null);
  const [unifiAps, setUnifiAps] = useState([]);
  const [pfsenseLinks, setPfsenseLinks] = useState([]);
  const [pfsenseUptime, setPfsenseUptime] = useState([]);
  const [pfsenseTrafego, setPfsenseTrafego] = useState({});
  const [latenciaFluig, setLatenciaFluig] = useState([]);
  const [restartandoFluig, setRestartandoFluig] = useState(false);
  const [backups, setBackups] = useState([]);
  const [backupsHistorico, setBackupsHistorico] = useState([]);
  const [erro, setErro] = useState(false);
  const [detalheAberto, setDetalheAberto] = useState(null);
  const [intervaloAtualizacao, setIntervaloAtualizacao] = useState(30000);
  const [abaAtiva, setAbaAtiva] = useState('controller');
  const [navPrincipal, setNavPrincipal] = useState('dashboard');

  const buscarDados = useCallback(() => {
    if (!token) return;

    axios.get(`${API_URL}/dashboard/controller/current`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((response) => setControllerAtual(response.data)).catch(() => {});

    axios.get(`${API_URL}/dashboard/summary`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => {
        setDados(response.data);
        setErro(false);
      })
      .catch((err) => {
        if (err.response && err.response.status === 401) {
          handleLogout();
        }
        setErro(true);
      });

    axios.get(`${API_URL}/dashboard/metrics/host?minutos=${calcularJanelaMinutos(intervaloAtualizacao)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => {
        setMetricas(response.data);
      })
      .catch(() => {});
  }, [token, intervaloAtualizacao]);

  const buscarLatencia = useCallback((categoria) => {
    if (!token) return;

    axios.get(`${API_URL}/dashboard/metrics/latencia/${categoria}?minutos=${calcularJanelaMinutos(intervaloAtualizacao)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => {
        setLatencias((prev) => ({ ...prev, [categoria]: response.data }));
      })
      .catch(() => {});
  }, [token, intervaloAtualizacao]);

  const buscarDadosDaAbaAtiva = useCallback(() => {
    if (!token || deveTrocarSenha) return;

    if (["servidores", "access_points", "impressoras"].includes(abaAtiva)) {
      buscarLatencia(abaAtiva);
    }
    if (abaAtiva === "servidores") {
      axios.get(`${API_URL}/dashboard/agents`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setAgentes(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/metrics/latencia-agentes?minutos=${calcularJanelaMinutos(intervaloAtualizacao)}`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setLatenciaFluig(response.data)).catch(() => {});
    }
    if (abaAtiva === "access_points") {
      axios.get(`${API_URL}/dashboard/unifi/aps`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setUnifiAps(response.data)).catch(() => {});
    }
    if (abaAtiva === "links_internet") {
      axios.get(`${API_URL}/dashboard/pfsense/links`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setPfsenseLinks(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/pfsense/links/uptime?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setPfsenseUptime(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/pfsense/trafego/history?minutos=${calcularJanelaMinutos(intervaloAtualizacao)}`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setPfsenseTrafego(response.data)).catch(() => {});
    }
    if (abaAtiva === "backups") {
      axios.get(`${API_URL}/dashboard/backups`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setBackups(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/backups/history?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setBackupsHistorico(response.data)).catch(() => {});
    }
  }, [abaAtiva, token, deveTrocarSenha, buscarLatencia, intervaloAtualizacao]);

  useEffect(() => {
    if (!token || deveTrocarSenha) return;
    buscarDados();
    buscarDadosDaAbaAtiva();
    const intervalo = setInterval(() => {
      buscarDados();
      buscarDadosDaAbaAtiva();
    }, intervaloAtualizacao);
    return () => clearInterval(intervalo);
  }, [token, deveTrocarSenha, intervaloAtualizacao, buscarDados, buscarDadosDaAbaAtiva]);


  const handleRestartFluig = () => {
    if (!window.confirm('Tem certeza que deseja reiniciar o Fluig? Isso vai parar e reiniciar os 3 servicos em sequencia, com breve indisponibilidade.')) {
      return;
    }
    setRestartandoFluig(true);
    axios.post(`${API_URL}/automations/restart-fluig`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(() => {
        alert('Comando enviado! O restart deve iniciar em ate 1 minuto. Acompanhe pelo Telegram.');
      })
      .catch((err) => {
        alert('Erro ao solicitar restart: ' + (err.response?.data?.detail || 'erro desconhecido'));
      })
      .finally(() => setRestartandoFluig(false));
  };

  const handleLoginSuccess = (data) => {
    localStorage.setItem('infraops_token', data.access_token);
    setToken(data.access_token);
    setUsuario(data);
    setDeveTrocarSenha(data.deve_trocar_senha);
  };

  const handleSenhaTrocada = () => {
    setDeveTrocarSenha(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('infraops_token');
    setToken(null);
    setUsuario(null);
    setDados(null);
    setMetricas(null);
    setDeveTrocarSenha(false);
  };

  const abrirDetalhe = (chave) => {
    setDetalheAberto(detalheAberto === chave ? null : chave);
  };

  if (!token) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  if (deveTrocarSenha) {
    return <TrocarSenha token={token} onSenhaTrocada={handleSenhaTrocada} />;
  }

  const CORES = ['#2E86AB', '#F39C12', '#2ECC71', '#E74C3C', '#9B59B6', '#1ABC9C', '#E67E22'];

  return (
    <div className="app">
      <Header usuario={usuario} onLogout={handleLogout} />
      <div className="app-body">
        <Sidebar usuario={usuario} abaAtiva={navPrincipal} onChangeAba={setNavPrincipal} />
        <main className="app-content">
          {navPrincipal === 'auditoria' ? (
            <>
              <h2 className="page-title">Auditoria</h2>
              <Auditoria token={token} />
            </>
          ) : navPrincipal === 'automacoes' ? (
            <>
              <h2 className="page-title">Automações</h2>
              <Automacoes token={token} />
            </>
          ) : (
          <>
          <h2 className="page-title">Visão Geral</h2>

          {erro && (
            <div className="error-message">
              Não foi possível conectar à API. Verifique a conexão.
            </div>
          )}

          {!dados && !erro && (
            <div className="loading-message">Carregando dados...</div>
          )}

          {dados && (
            <div className="cards-grid">
              <div onClick={() => abrirDetalhe('servidores')} style={{ cursor: 'pointer' }}>
                <StatusCard
                  title="Servidores Online"
                  value={dados.servidores_online}
                  status="online"
                  subtitle={`${dados.servidores_offline} offline · clique para detalhes`}
                />
              </div>
              <div onClick={() => abrirDetalhe('access_points')} style={{ cursor: 'pointer' }}>
                <StatusCard
                  title="Access Points Online"
                  value={dados.access_points_online}
                  status={dados.access_points_offline > 0 ? 'warning' : 'online'}
                  subtitle={`${dados.access_points_offline} offline · clique para detalhes`}
                />
              </div>
              <StatusCard
                title="Painel UniFi"
                value={dados.painel_unifi === 'online' ? 'Online' : 'Offline'}
                status={dados.painel_unifi === 'online' ? 'online' : 'offline'}
              />
              <StatusCard
                title="Backups OK"
                value={dados.backups_ok}
                status={dados.backups_falharam > 0 ? 'offline' : 'online'}
                subtitle={`${dados.backups_falharam} falharam`}
              />
              <div onClick={() => abrirDetalhe('impressoras')} style={{ cursor: 'pointer' }}>
                <StatusCard
                  title="Impressoras Online"
                  value={dados.impressoras_online}
                  status={dados.impressoras_offline > 0 ? 'warning' : 'online'}
                  subtitle={`${dados.impressoras_offline} offline · clique para detalhes`}
                />
              </div>
            </div>
          )}

          {detalheAberto && dados[`${detalheAberto}_detalhe`] && (
            <div className="detail-table">
              <h3 className="detail-table-title">
                Detalhes — {detalheAberto === 'access_points' ? 'Access Points' : detalheAberto === 'servidores' ? 'Servidores' : 'Impressoras'}
              </h3>
              <table>
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Endereço</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {dados[`${detalheAberto}_detalhe`].map((item) => (
                    <tr key={item.instance}>
                      <td>{item.nome}</td>
                      <td>{item.instance}</td>
                      <td>
                        <span className={`status-tag status-tag-${item.status}`}>
                          {item.status === 'online' ? 'Online' : 'Offline'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 className="page-title" style={{ marginTop: '32px' }}>Métricas Detalhadas</h2>

          <Tabs abas={ABAS} abaAtiva={abaAtiva} onChange={setAbaAtiva} />

          {abaAtiva !== 'backups' && (
            <RefreshSelector
              intervaloAtual={intervaloAtualizacao}
              onChange={setIntervaloAtualizacao}
            />
          )}

          {abaAtiva === 'controller' && controllerAtual && (
            <div className="metrics-grid" style={{ marginBottom: '24px', maxWidth: '380px' }}>
              <ServerResourceCard agente={{ ...controllerAtual, uptime_horas: 0 }} />
            </div>
          )}

          {abaAtiva === 'controller' && metricas && (
            <div className="metrics-grid">
              <MetricChart titulo="CPU (%)" dados={metricas.cpu} cor="#2E86AB" unidade="%" />
              <MetricChart titulo="Memória RAM (%)" dados={metricas.ram} cor="#F39C12" unidade="%" />
              <MetricChart titulo="Disco (%)" dados={metricas.disco} cor="#9B59B6" unidade="%" />
              <MetricChart titulo="Rede — Download (Kbps)" dados={metricas.rede_rx_kbps} cor="#2ECC71" unidade="" />
              <MetricChart titulo="Rede — Upload (Kbps)" dados={metricas.rede_tx_kbps} cor="#E74C3C" unidade="" />
            </div>
          )}

          {abaAtiva === 'servidores' && agentes.length > 0 && (
            <>
              <h3 className="detail-table-title" style={{ marginBottom: '16px' }}>Recursos dos Servidores</h3>
              <div className="metrics-grid" style={{ marginBottom: '32px' }}>
                {agentes.map((agente) => (
                  <ServerResourceCard key={agente.instance} agente={agente} />
                ))}
              </div>
              <h3 className="detail-table-title" style={{ marginBottom: '16px' }}>Latência</h3>
            </>
          )}

          {abaAtiva === 'access_points' && unifiAps.length > 0 && (
            <>
              <h3 className="detail-table-title" style={{ marginBottom: '16px' }}>Access Points — Clientes Conectados</h3>
              <div className="detail-table" style={{ marginBottom: '32px' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Nome</th>
                      <th>Modelo</th>
                      <th>IP</th>
                      <th>Clientes Conectados</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unifiAps
                      .filter((ap) => ap.modelo !== 'USW 24 PoE')
                      .sort((a, b) => b.clientes_conectados - a.clientes_conectados)
                      .map((ap) => (
                        <tr key={ap.mac}>
                          <td>{ap.nome}</td>
                          <td>{ap.modelo}</td>
                          <td>{ap.ip}</td>
                          <td style={{ fontWeight: 700 }}>{ap.clientes_conectados}</td>
                          <td>
                            <span className={`status-tag status-tag-${ap.status === 'ONLINE' ? 'online' : 'offline'}`}>
                              {ap.status === 'ONLINE' ? 'Online' : 'Offline'}
                            </span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <h3 className="detail-table-title" style={{ marginBottom: '16px' }}>Latência</h3>
            </>
          )}

          {(abaAtiva === 'servidores' || abaAtiva === 'access_points' || abaAtiva === 'impressoras') && (
            <div className="metrics-grid">
              {abaAtiva === 'servidores' && latenciaFluig.map((item, idx) => (
                <MetricChart
                  key={`fluig-${item.instance}`}
                  titulo={`${item.nome} — Latência (ms)`}
                  dados={item.pontos}
                  cor="#F39C12"
                  unidade="ms"
                />
              ))}
              {(latencias[abaAtiva] || []).map((item, idx) => (
                <MetricChart
                  key={item.instance}
                  titulo={`${item.nome} — Latência (ms)`}
                  dados={item.pontos}
                  cor={CORES[idx % CORES.length]}
                  unidade="ms"
                />
              ))}
              {(!latencias[abaAtiva] || latencias[abaAtiva].length === 0) && (
                <div className="loading-message">Carregando métricas...</div>
              )}
            </div>
          )}

          {abaAtiva === 'links_internet' && (
            <div className="detail-table">
              <h3 className="detail-table-title">Links de Internet</h3>
              <table>
                <thead>
                  <tr>
                    <th>Link</th>
                    <th>Status Atual</th>
                    <th>Uptime (30 dias)</th>
                  </tr>
                </thead>
                <tbody>
                  {pfsenseLinks.map((link) => {
                    const uptimeInfo = pfsenseUptime.find((u) => u.nome === link.nome);
                    return (
                      <tr key={link.nome}>
                        <td>{link.nome}</td>
                        <td>
                          <span className={`status-tag status-tag-${link.status === 'online' ? 'online' : 'offline'}`}>
                            {link.status === 'online' ? 'Online' : 'Offline'}
                          </span>
                        </td>
                        <td>{uptimeInfo ? `${uptimeInfo.uptime_percent}%` : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <h3 className="detail-table-title" style={{ marginTop: '24px' }}>Tráfego em Tempo Real</h3>
              <div className="metrics-grid">
                {Object.keys(pfsenseTrafego).map((nomeLink) => (
                  <div key={nomeLink}>
                    <MetricChart
                      titulo={`${nomeLink} — Download (Mbps)`}
                      dados={pfsenseTrafego[nomeLink].download}
                      cor="#2ECC71"
                      unidade=""
                    />
                  </div>
                ))}
                {Object.keys(pfsenseTrafego).map((nomeLink) => (
                  <div key={`${nomeLink}-up`}>
                    <MetricChart
                      titulo={`${nomeLink} — Upload (Mbps)`}
                      dados={pfsenseTrafego[nomeLink].upload}
                      cor="#E74C3C"
                      unidade=""
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {abaAtiva === 'backups' && (
            <div className="detail-table">
              <h3 className="detail-table-title">Backups Veeam</h3>
              <table>
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Tamanho</th>
                    <th>Última Execução</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {backups.map((b) => (
                    <tr key={b.instance}>
                      <td>{b.nome}</td>
                      <td>{b.tamanho_gb > 0 ? `${b.tamanho_gb} GB` : '—'}</td>
                      <td>{b.ultima_execucao ? new Date(b.ultima_execucao).toLocaleString('pt-BR') : '—'}</td>
                      <td>
                        <span className={`status-tag status-tag-${b.sucesso ? 'online' : 'offline'}`}>
                          {b.sucesso ? 'Sucesso' : 'Falhou'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {backups.length === 0 && (
                    <tr><td colSpan="4">Carregando...</td></tr>
                  )}
                </tbody>
              </table>

              <h3 className="detail-table-title" style={{ marginTop: '24px' }}>Histórico — Últimos 30 dias</h3>
              <table>
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Tipo</th>
                    <th>Tamanho Transferido</th>
                    <th>Data/Hora</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {backupsHistorico.map((h) => (
                    <tr key={h.id}>
                      <td>{h.job_name}</td>
                      <td>{h.backup_type || '—'}</td>
                      <td>{formatarTamanho(h.tamanho_transferido_gb)}</td>
                      <td>{new Date(h.executado_em).toLocaleString('pt-BR')}</td>
                      <td>
                        <span className={`status-tag status-tag-${h.status === 'Success' ? 'online' : h.status === 'Warning' ? 'warning' : 'offline'}`}>
                          {h.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {backupsHistorico.length === 0 && (
                    <tr><td colSpan="5">Sem execuções registradas ainda</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {dados && (
            <div className="last-update">
              Última atualização: {new Date(dados.atualizado_em).toLocaleString('pt-BR')}
            </div>
          )}
          </>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
