import { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'IP_INTERNO_AQUI:8000';

function Automacoes({ token }) {
  const [historico, setHistorico] = useState([]);
  const [restartando, setRestartando] = useState(false);
  const [fazendoFailover, setFazendoFailover] = useState(false);
  const [failoverAutomatico, setFailoverAutomatico] = useState(false);
  const [alternandoAutomatico, setAlternandoAutomatico] = useState(false);

  const buscarStatusAutomatico = () => {
    axios.get(`${API_URL}/automations/failover-automatico`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((response) => setFailoverAutomatico(response.data.ativo)).catch(() => {});
  };

  const handleAlternarAutomatico = () => {
    setAlternandoAutomatico(true);
    axios.post(`${API_URL}/automations/failover-automatico/alternar`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => {
        setFailoverAutomatico(response.data.ativo);
      })
      .catch(() => {
        alert('Erro ao alternar failover automatico');
      })
      .finally(() => setAlternandoAutomatico(false));
  };

  const buscarHistorico = () => {
    axios.get(`${API_URL}/automations/jobs/historico`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((response) => setHistorico(response.data)).catch(() => {});
  };

  useEffect(() => {
    buscarHistorico();
    buscarStatusAutomatico();
    const intervalo = setInterval(buscarHistorico, 10000);
    return () => clearInterval(intervalo);
  }, [token]);

  const handleRestartFluig = () => {
    if (!window.confirm('Tem certeza que deseja reiniciar o Fluig? Isso vai parar e reiniciar os 3 servicos em sequencia, com breve indisponibilidade.')) {
      return;
    }
    setRestartando(true);
    axios.post(`${API_URL}/automations/restart-fluig`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(() => {
        alert('Comando enviado! O restart deve iniciar em ate 1 minuto. Acompanhe pelo Telegram.');
        buscarHistorico();
      })
      .catch((err) => {
        alert('Erro ao solicitar restart: ' + (err.response?.data?.detail || 'erro desconhecido'));
      })
      .finally(() => setRestartando(false));
  };

  const handleFailover = () => {
    if (!window.confirm('ATENCAO: isso vai trocar o IP do servidor redundante (SrvArqRed) para assumir o lugar do servidor principal de arquivos. Use apenas se o servidor principal estiver realmente fora do ar. Confirma o failover?')) {
      return;
    }
    setFazendoFailover(true);
    axios.post(`${API_URL}/automations/failover-srv-arquivos`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(() => {
        alert('Comando enviado! O failover deve iniciar em ate 1 minuto. Acompanhe pelo Telegram.');
        buscarHistorico();
      })
      .catch((err) => {
        alert('Erro ao solicitar failover: ' + (err.response?.data?.detail || 'erro desconhecido'));
      })
      .finally(() => setFazendoFailover(false));
  };

  const handleDesfazerFailover = () => {
    if (!window.confirm('ATENCAO: isso vai trocar o IP de volta, sem checagem de seguranca. So use se tiver certeza que o servidor principal (SRV-ARQ) esta online. Confirma a reversao do failover?')) {
      return;
    }
    setFazendoFailover(true);
    axios.post(`${API_URL}/automations/desfazer-failover-srv-arquivos`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(() => {
        alert('Comando enviado! A reversao deve iniciar em ate 1 minuto. Acompanhe pelo Telegram.');
        buscarHistorico();
      })
      .catch((err) => {
        alert('Erro ao solicitar reversao: ' + (err.response?.data?.detail || 'erro desconhecido'));
      })
      .finally(() => setFazendoFailover(false));
  };
  const statusLabel = (status) => {
    if (status === 'concluido') return 'Concluído';
    if (status === 'erro') return 'Erro';
    if (status === 'executando') return 'Executando';
    return 'Pendente';
  };

  const statusClasse = (status) => {
    if (status === 'concluido') return 'online';
    if (status === 'erro') return 'offline';
    return 'warning';
  };

  return (
    <>
      <div className="detail-table" style={{ marginBottom: '24px' }}>
        <h3 className="detail-table-title">Ações Disponíveis</h3>
        <button
          onClick={handleFailover}
          disabled={fazendoFailover}
          style={{
            backgroundColor: 'var(--status-offline)',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 20px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: fazendoFailover ? 'not-allowed' : 'pointer',
            opacity: fazendoFailover ? 0.6 : 1,
          }}
        >
          {fazendoFailover ? 'Enviando...' : 'Failover Srv Arquivos'}
        </button>
        <button
          onClick={handleDesfazerFailover}
          disabled={fazendoFailover}
          style={{
            backgroundColor: "#8A5A00",
            color: "#FFFFFF",
            border: "none",
            borderRadius: "var(--radius-sm)",
            padding: "10px 20px",
            fontSize: "13px",
            fontWeight: 600,
            cursor: fazendoFailover ? "not-allowed" : "pointer",
            opacity: fazendoFailover ? 0.6 : 1,
            marginLeft: "12px",
          }}
        >
          {fazendoFailover ? "Enviando..." : "Desfazer Failover Srv Arquivos"}
        </button>

        <button
          onClick={handleAlternarAutomatico}
          disabled={alternandoAutomatico}
          style={{
            backgroundColor: failoverAutomatico ? 'var(--status-online)' : '#5A5A5A',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 20px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: alternandoAutomatico ? 'not-allowed' : 'pointer',
            opacity: alternandoAutomatico ? 0.6 : 1,
            marginLeft: '12px',
          }}
        >
          {alternandoAutomatico ? 'Alterando...' : `Failover Srv Arquivos: ${failoverAutomatico ? 'ON' : 'OFF'}`}
        </button>
      </div>

      <div className="detail-table">
                <h3 className="detail-table-title">Histórico de Execuções</h3>
        <div className="list-table">
          <div className="list-row head" style={{ gridTemplateColumns: '1fr 110px 130px 110px 1fr 150px' }}>
            <span>Ação</span>
            <span>Alvo</span>
            <span>Solicitado por</span>
            <span>Status</span>
            <span>Resultado</span>
            <span>Data</span>
          </div>
          {historico.map((h) => (
            <div className="list-row" style={{ gridTemplateColumns: '1fr 110px 130px 110px 1fr 150px' }} key={h.id}>
              <span className="list-cell-strong">{h.tipo}</span>
              <span className="list-cell">{h.alvo}</span>
              <span className="list-cell">{h.solicitado_por}</span>
              <span className={`status-tag status-tag-${statusClasse(h.status)}`}>
                {statusLabel(h.status)}
              </span>
              <span className="list-cell">{h.resultado || '—'}</span>
              <span className="list-cell-mono">{new Date(h.criado_em).toLocaleString('pt-BR')}</span>
            </div>
          ))}
          {historico.length === 0 && (
            <div className="loading-message">Nenhuma execução registrada</div>
          )}
        </div>
      </div>
    </>
  );
}

export default Automacoes;
