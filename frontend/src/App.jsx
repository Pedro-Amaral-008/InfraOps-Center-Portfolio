import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import UsuarioTopo from './components/UsuarioTopo';
import Novidades from './components/Novidades';
import Sidebar from './components/Sidebar';
import StatusCard from './components/StatusCard';
import Login from './components/Login';
import TrocarSenha from './components/TrocarSenha';
import MetricChart from './components/MetricChart';
import RefreshSelector from './components/RefreshSelector';
import EopsDashboard from './components/EopsDashboard';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis } from 'recharts';
import Tabs from './components/Tabs';
import ServerResourceCard from './components/ServerResourceCard';
import ProtheusCard from './components/ProtheusCard';
import Auditoria from './components/Auditoria';
import Automacoes from './components/Automacoes';
import Usuarios from './components/Usuarios';
import Solicitacoes from './components/Solicitacoes';
import Relatorios from './components/Relatorios';
import ConsumoRede from './components/ConsumoRede';
import Acessos from './components/Acessos';
import './App.css';

const API_URL = 'http://IP_AQUI:8000';

const ABAS = [
  { id: 'controller', label: 'Controller' },
  { id: 'servidores', label: 'Servidores' },
  { id: 'impressoras', label: 'Impressoras' },
  { id: 'backups', label: 'Backups' },
  { id: 'links_internet', label: 'Redes' },
];

function formatarTamanho(gb) {
  if (gb >= 1024) {
    return `${(gb / 1024).toFixed(2)} TB`;
  }
  if (gb < 1 && gb > 0) {
    return `${(gb * 1024).toFixed(1)} MB`;
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
  useEffect(() => {
    const temaSalvo = localStorage.getItem('infraops_tema') === 'light' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', temaSalvo);
  }, []);
  const [usuario, setUsuario] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('infraops_token'));
  const [deveTrocarSenha, setDeveTrocarSenha] = useState(false);
  const [dados, setDados] = useState(null);
  const [eventosRecentes, setEventosRecentes] = useState([]);
  const [saudeExpandida, setSaudeExpandida] = useState(false);
  const [metricas, setMetricas] = useState(null);
  const [latencias, setLatencias] = useState({});
  const [agentes, setAgentes] = useState([]);
  const [controllerAtual, setControllerAtual] = useState(null);
  const [unifiAps, setUnifiAps] = useState([]);
  const [pfsenseLinks, setPfsenseLinks] = useState([]);
  const [pfsenseUptime, setPfsenseUptime] = useState([]);
  const [servidoresStatusCompleto, setServidoresStatusCompleto] = useState({});
  const [protheusStatus, setProtheusStatus] = useState(null);
  const [protheusHistorico, setProtheusHistorico] = useState([]);
  const [protheusEventos, setProtheusEventos] = useState([]);
  const [apsUptime, setApsUptime] = useState([]);
  const [pfsenseTrafego, setPfsenseTrafego] = useState({});
  const [pfsenseVpns, setPfsenseVpns] = useState([]);
  const [pfsenseVlans, setPfsenseVlans] = useState([]);
  const [subAbaRede, setSubAbaRede] = useState('links');
  const [macAcessosAlvo, setMacAcessosAlvo] = useState(null);
  const abrirDispositivoAcessos = (mac) => {
    setNavPrincipal('metricas');
    setAbaAtiva('links_internet');
    setSubAbaRede('acessos');
    setMacAcessosAlvo(mac);
  };
  const [vpnsUptime, setVpnsUptime] = useState([]);
  const [vlansUptime, setVlansUptime] = useState([]);
  const [restartandoFluig, setRestartandoFluig] = useState(false);
  const [backups, setBackups] = useState([]);
  const [backupsHistorico, setBackupsHistorico] = useState([]);
  const [backupsUptime, setBackupsUptime] = useState([]);
  const [erro, setErro] = useState(false);
  const [detalheAberto, setDetalheAberto] = useState(null);
  const [intervaloAtualizacao, setIntervaloAtualizacao] = useState(30000);
  const [abaAtiva, setAbaAtiva] = useState('controller');


  useEffect(() => {
    if (!token || usuario) return;
    axios.get(`${API_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => setUsuario(response.data))
      .catch(() => {
        localStorage.removeItem('infraops_token');
        setToken(null);
        setUsuario(null);
      });
  }, [token, usuario]);
  const [navPrincipal, setNavPrincipal] = useState('dashboard');

  const buscarDados = useCallback(() => {
    if (!token) return;

    axios.get(`${API_URL}/dashboard/eventos/recentes`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((response) => setEventosRecentes(response.data)).catch(() => {});

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

    if (abaAtiva === "impressoras") {
      buscarLatencia(abaAtiva);
    }
    if (abaAtiva === "links_internet" && subAbaRede === "access_points") {
      buscarLatencia("access_points");
    }
    if (abaAtiva === "servidores") {
      axios.get(`${API_URL}/dashboard/agents`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setAgentes(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/servidores/status-completo?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setServidoresStatusCompleto(response.data)).catch(() => {});

      axios.get(`${API_URL}/dashboard/protheus/status`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setProtheusStatus(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/protheus/historico?horas=24`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setProtheusHistorico(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/protheus/eventos?dias=7`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setProtheusEventos(response.data)).catch(() => {});
    }
    if (abaAtiva === "links_internet") {
      axios.get(`${API_URL}/dashboard/unifi/aps`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setUnifiAps(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/access-points/uptime?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setApsUptime(response.data)).catch(() => {});
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
      axios.get(`${API_URL}/dashboard/pfsense/vpns`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setPfsenseVpns(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/pfsense/vlans`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setPfsenseVlans(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/pfsense/vpns/uptime?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setVpnsUptime(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/pfsense/vlans/uptime?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setVlansUptime(response.data)).catch(() => {});
    }
    if (abaAtiva === "backups") {
      axios.get(`${API_URL}/dashboard/backups`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setBackups(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/backups/history?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setBackupsHistorico(response.data)).catch(() => {});
      axios.get(`${API_URL}/dashboard/backups/uptime?dias=30`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setBackupsUptime(response.data)).catch(() => {});
    }
  }, [abaAtiva, token, deveTrocarSenha, buscarLatencia, intervaloAtualizacao, subAbaRede]);

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

  const [novidadesAbertas, setNovidadesAbertas] = useState(false);
  const alternarTema = () => {
    const atual = localStorage.getItem('infraops_tema') === 'light';
    const novoTema = atual ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', novoTema);
    localStorage.setItem('infraops_tema', novoTema);
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
      <div className="app-body">
        <Sidebar
          usuario={usuario}
          abaAtiva={navPrincipal}
          onChangeAba={setNavPrincipal}
          abaInterna={abaAtiva}
          onChangeAbaInterna={setAbaAtiva}
          onAbrirNovidades={() => setNovidadesAbertas(true)}
        />
        <main className="app-content">
          <UsuarioTopo
            usuario={{ nome: usuario?.nome_completo, perfil: usuario?.role }}
            aoSair={handleLogout}
            aoAlternarTema={alternarTema}
          />
          {novidadesAbertas && <Novidades onFechar={() => setNovidadesAbertas(false)} />}
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
          ) : navPrincipal === 'usuarios' ? (
            <>
              <h2 className="page-title">Usuários</h2>
              <Usuarios token={token} meuUsername={usuario?.username} meuRole={usuario?.role} />
            </>
          ) : navPrincipal === 'solicitacoes' ? (
            <>
              <h2 className="page-title">Solicitações</h2>
              <Solicitacoes token={token} />
            </>
          ) : navPrincipal === 'relatorios' ? (
            <Relatorios token={token} role={usuario?.role} />
          ) : navPrincipal === 'metricas' ? (
          <>
          <h2 className="page-title">
            {abaAtiva === 'controller' ? 'Controller' : abaAtiva === 'servidores' ? 'Servidores' : abaAtiva === 'impressoras' ? 'Impressoras' : abaAtiva === 'backups' ? 'Backups' : 'Redes'}
          </h2>


          {abaAtiva !== 'backups' && (
            <RefreshSelector
              intervaloAtual={intervaloAtualizacao}
              onChange={setIntervaloAtualizacao}
            />
          )}

          {abaAtiva === 'controller' && controllerAtual && (
            <div className="metrics-grid" style={{ marginBottom: '24px', maxWidth: '380px' }}>
              <ServerResourceCard agente={controllerAtual} />
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

          {abaAtiva === 'servidores' && (agentes.length > 0 || protheusStatus) && (
            <>
              <h3 className="detail-table-title" style={{ marginBottom: '16px' }}>Recursos dos Servidores</h3>
              <div className="metrics-grid" style={{ marginBottom: '32px' }}>
                {agentes.map((agente) => (
                  <ServerResourceCard key={agente.instance} agente={agente} statusRede={servidoresStatusCompleto[agente.instance]} />
                ))}
                {protheusStatus && (
                  <ProtheusCard status={protheusStatus} historico={protheusHistorico} eventos={protheusEventos} />
                )}
              </div>
            </>
          )}

          {abaAtiva === 'impressoras' && dados && dados.impressoras_detalhe && (
            <div className="detail-table" style={{ marginBottom: '32px' }}>
              <h3 className="detail-table-title">Impressoras</h3>
              <table>
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Endereço</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {dados.impressoras_detalhe.map((item) => (
                    <tr key={item.nome}>
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
          {abaAtiva === 'impressoras' && (
            <div className="metrics-grid">
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
              <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
                <button
                  className={`btn ${subAbaRede === 'links' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSubAbaRede('links')}
                >
                  Links de Internet
                </button>
                <button
                  className={`btn ${subAbaRede === 'vpns' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSubAbaRede('vpns')}
                >
                  VPNs
                </button>
                <button
                  className={`btn ${subAbaRede === 'vlans' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSubAbaRede('vlans')}
                >
                  VLANs
                </button>
                <button
                  className={`btn ${subAbaRede === 'access_points' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSubAbaRede('access_points')}
                >
                  Access Points
                </button>
                <button
                  className={`btn ${subAbaRede === 'consumo' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSubAbaRede('consumo')}
                >
                  Consumo de Rede
                </button>
                <button
                  className={`btn ${subAbaRede === 'acessos' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSubAbaRede('acessos')}
                >
                  Acessos
                </button>
              </div>

                            {subAbaRede === 'links' && (
                <>
                  <h3 className="detail-table-title">Links de Internet</h3>
                  <div className="link-cards-grid-wrap">
                    {pfsenseLinks.map((link) => {
                      const uptimeInfo = pfsenseUptime.find((u) => u.nome === link.nome);
                      return (
                        <div className="link-card" key={link.nome}>
                          <div className="link-card-header">
                            <span className="link-card-name">{link.nome}</span>
                            <span className={`status-tag status-tag-${link.status === 'online' ? 'online' : 'offline'}`}>
                              {link.status === 'online' ? 'Online' : 'Offline'}
                            </span>
                            <span className="link-card-uptime">{uptimeInfo && uptimeInfo.uptime_percent !== null ? `${uptimeInfo.uptime_percent}% uptime (30 dias)` : 'uptime indisponível'}</span>
                          </div>
                          {pfsenseTrafego[link.nome] && (
                            <div className="link-card-charts">
                              <MetricChart titulo="Download (Mbps)" dados={pfsenseTrafego[link.nome].download} cor="#2ECC71" unidade="" altura={150} />
                              <MetricChart titulo="Upload (Mbps)" dados={pfsenseTrafego[link.nome].upload} cor="#E74C3C" unidade="" altura={150} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                    {pfsenseLinks.length === 0 && (
                      <div className="loading-message">Carregando...</div>
                    )}
                  </div>
                </>
              )}

{subAbaRede === 'vpns' && (
  <>
    <h3 className="detail-table-title">VPNs</h3>
    <div className="link-cards-grid-wrap">
      {pfsenseVpns.map((vpn) => {
        const uptimeInfo = vpnsUptime.find((u) => u.nome === vpn.nome);
        return (
          <div className="link-card" key={vpn.nome}>
            <div className="link-card-header">
              <span className="link-card-name">{vpn.nome}</span>
              <span className={`status-tag status-tag-${vpn.status === 'online' ? 'online' : 'offline'}`}>
                {vpn.status === 'online' ? 'Online' : 'Offline'}
              </span>
              <span className="link-card-uptime">{uptimeInfo && uptimeInfo.uptime_percent !== null ? `${uptimeInfo.uptime_percent}% uptime (30 dias)` : 'uptime indisponível'}</span>
            </div>
            {pfsenseTrafego[vpn.nome] && (
              <div className="link-card-charts">
                <MetricChart titulo="Download (Mbps)" dados={pfsenseTrafego[vpn.nome].download} cor="#2ECC71" unidade="" altura={150} />
                <MetricChart titulo="Upload (Mbps)" dados={pfsenseTrafego[vpn.nome].upload} cor="#E74C3C" unidade="" altura={150} />
              </div>
            )}
          </div>
        );
      })}
      {pfsenseVpns.length === 0 && (
        <div className="loading-message">Carregando...</div>
      )}
    </div>
  </>
)}

{subAbaRede === 'vlans' && (
  <>
    <h3 className="detail-table-title">VLANs</h3>
    <div className="link-cards-grid-wrap">
      {pfsenseVlans.map((vlan) => {
        const uptimeInfo = vlansUptime.find((u) => u.nome === vlan.nome);
        return (
          <div className="link-card" key={vlan.nome}>
            <div className="link-card-header">
              <span className="link-card-name">{vlan.nome}</span>
              <span className={`status-tag status-tag-${vlan.status === 'online' ? 'online' : 'offline'}`}>
                {vlan.status === 'online' ? 'Online' : 'Offline'}
              </span>
              <span className="link-card-uptime">{uptimeInfo && uptimeInfo.uptime_percent !== null ? `${uptimeInfo.uptime_percent}% uptime (30 dias)` : 'uptime indisponível'}</span>
            </div>
            {pfsenseTrafego[vlan.nome] && (
              <div className="link-card-charts">
                <MetricChart titulo="Download (Mbps)" dados={pfsenseTrafego[vlan.nome].download} cor="#2ECC71" unidade="" altura={150} />
                <MetricChart titulo="Upload (Mbps)" dados={pfsenseTrafego[vlan.nome].upload} cor="#E74C3C" unidade="" altura={150} />
              </div>
            )}
          </div>
        );
      })}
      {pfsenseVlans.length === 0 && (
        <div className="loading-message">Carregando...</div>
      )}
    </div>
  </>
)}

{subAbaRede === 'access_points' && unifiAps.length > 0 && (
                <>
                  <h3 className="detail-table-title">Access Points — Clientes Conectados</h3>
                  <table>
                    <thead>
                      <tr>
                        <th>Nome</th>
                        <th>Modelo</th>
                        <th>IP</th>
                        <th>Clientes Conectados</th>
                        <th>Status</th>
                        <th>Uptime (30 dias)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {unifiAps
                        .filter((ap) => ap.modelo !== 'USW 24 PoE')
                        .sort((a, b) => b.clientes_conectados - a.clientes_conectados)
                        .map((ap) => {
                          const uptimeInfo = apsUptime.find((u) => u.instance === ap.ip);
                          return (
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
                            <td>{uptimeInfo ? `${uptimeInfo.uptime_percent}%` : '—'}</td>
                          </tr>
                          );
                        })}
                    </tbody>
                  </table>
                  <h3 className="detail-table-title" style={{ marginTop: '24px' }}>Latência</h3>
                  <div className="metrics-grid">
                    {(latencias['access_points'] || []).map((item, idx) => (
                      <MetricChart
                        key={item.instance}
                        titulo={`${item.nome} — Latência (ms)`}
                        dados={item.pontos}
                        cor={CORES[idx % CORES.length]}
                        unidade="ms"
                      />
                    ))}
                    {(!latencias['access_points'] || latencias['access_points'].length === 0) && (
                      <div className="loading-message">Carregando métricas...</div>
                    )}
                  </div>
                </>
              )}
              {subAbaRede === 'consumo' && <ConsumoRede token={token} />}
              {subAbaRede === 'acessos' && <Acessos token={token} role={usuario?.role} macInicial={macAcessosAlvo} onMacInicialConsumido={() => setMacAcessosAlvo(null)} />}
            </div>
          )}
          {abaAtiva === 'backups' && (
            <div className="detail-table">
                            <h3 className="detail-table-title">Backups Veeam</h3>
              <div className="backup-list">
                <div className="backup-row head">
                  <span>Nome</span>
                  <span style={{ textAlign: 'right' }}>Tamanho</span>
                  <span>Última Execução</span>
                  <span></span>
                </div>
                {backups.map((b) => (
                  <div className="backup-row" key={b.instance}>
                    <span className="hist-name">{b.nome}</span>
                    <span className="hist-size">{b.tamanho_gb > 0 ? formatarTamanho(b.tamanho_gb) : '—'}</span>
                    <span className="hist-when">{b.ultima_execucao ? new Date(b.ultima_execucao).toLocaleString('pt-BR') : '—'}</span>
                    <span className={`status-tag status-tag-${b.sucesso ? 'online' : 'offline'}`} style={{ justifySelf: 'end' }}>
                      {b.sucesso ? 'Sucesso' : 'Falhou'}
                    </span>
                  </div>
                ))}
                {backups.length === 0 && (
                  <div className="loading-message">Carregando...</div>
                )}
              </div>
                            <h3 className="detail-table-title" style={{ marginTop: '24px' }}>Disponibilidade — Últimos 30 dias</h3>
              <div className="uptime-chip-grid">
                {backupsUptime.map((u) => {
                  const cor = u.uptime_percent === null ? 'var(--text-tertiary)' : u.uptime_percent >= 90 ? 'var(--status-online)' : u.uptime_percent >= 70 ? 'var(--status-warning)' : 'var(--status-offline)';
                  return (
                    <div className="uptime-chip" key={`${u.instance}-${u.backup_type}`}>
                      <div className="uptime-chip-label">{u.nome}</div>
                      <span className="uptime-chip-pct" style={{ color: cor }}>{u.uptime_percent !== null ? `${u.uptime_percent}%` : '—'}</span>
                      <div className="uptime-chip-execs">{u.execucoes_com_sucesso} de {u.total_execucoes} execuções</div>
                      <div className="uptime-chip-track">
                        <div className="uptime-chip-fill" style={{ width: `${u.uptime_percent ?? 0}%`, backgroundColor: cor }} />
                      </div>
                    </div>
                  );
                })}
                {backupsUptime.length === 0 && (
                  <div className="loading-message">Carregando...</div>
                )}
              </div>

                            <h3 className="detail-table-title" style={{ marginTop: '24px' }}>Histórico — Últimos 30 dias</h3>
              <div className="hist-list">
                <div className="hist-row head">
                  <span></span>
                  <span>Job</span>
                  <span>Tipo</span>
                  <span style={{ textAlign: 'right' }}>Tamanho</span>
                  <span>Data/Hora</span>
                  <span></span>
                </div>
                {backupsHistorico.map((h) => {
                  const corStatus = h.status === 'Success' ? 'var(--status-online)' : h.status === 'Warning' ? 'var(--status-warning)' : 'var(--status-offline)';
                  const bgStatus = h.status === 'Success' ? 'rgba(46, 204, 113, 0.15)' : h.status === 'Warning' ? 'rgba(243, 156, 18, 0.15)' : 'rgba(231, 76, 60, 0.15)';
                  return (
                    <div className="hist-row" key={h.id}>
                      <span className="hist-icon" style={{ color: corStatus, backgroundColor: bgStatus }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <ellipse cx="12" cy="5" rx="8" ry="3" />
                          <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
                          <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
                        </svg>
                      </span>
                      <span className="hist-name">{h.job_name}</span>
                      <span className="hist-type">{h.backup_type || '—'}</span>
                      <span className="hist-size">{formatarTamanho(h.tamanho_transferido_gb)}</span>
                      <span className="hist-when">{new Date(h.executado_em).toLocaleString('pt-BR')}</span>
                      <span className={`status-tag status-tag-${h.status === 'Success' ? 'online' : h.status === 'Warning' ? 'warning' : 'offline'}`} style={{ justifySelf: 'end' }}>
                        {h.status}
                      </span>
                    </div>
                  );
                })}
                {backupsHistorico.length === 0 && (
                  <div className="loading-message">Sem execuções registradas ainda</div>
                )}
              </div>
            </div>
          )}

          {dados && (
            <div className="last-update">
              Última atualização: {new Date(dados.atualizado_em).toLocaleString('pt-BR')}
            </div>
          )}
          </>
          ) : (
          <>

          {erro && (
            <div className="error-message">
              Não foi possível conectar à API. Verifique a conexão.
            </div>
          )}

          {!dados && !erro && (
            <div className="loading-message">Carregando dados...</div>
          )}


          <EopsDashboard token={token} dados={dados} onAbrirDispositivo={abrirDispositivoAcessos} />

          {detalheAberto && dados[`${detalheAberto}_detalhe`] && (
            <div className="detail-table">
              <h3 className="detail-table-title">
                Detalhes — {detalheAberto === 'access_points' ? 'Access Points' : detalheAberto === 'servidores' ? 'Servidores' : detalheAberto === 'links' ? 'Links de Rede' : detalheAberto === 'backups' ? 'Backups' : 'Impressoras'}
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
                    <tr key={`${detalheAberto}-${item.nome}`}>
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

          </>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
