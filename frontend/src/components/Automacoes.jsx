import { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = '';

function Automacoes({ token }) {
  const [historico, setHistorico] = useState([]);
  const [restartando, setRestartando] = useState(false);


  const buscarHistorico = (signal) => {
    axios.get(`${API_URL}/automations/jobs/historico`, {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    }).then((response) => setHistorico(response.data)).catch(() => {});
  };

  useEffect(() => {
    const controller = new AbortController();
    buscarHistorico(controller.signal);
    buscarStatusAutomatico();
    // ao sair da aba, para o timer E cancela a requisicao em andamento
    return () => {
      clearInterval(intervalo);
      controller.abort();
    };
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
