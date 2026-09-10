import { useState, useEffect } from 'react';
import axios from 'axios';
import './Auditoria.css';

const API_URL = 'http://IP_INTERNO_AQUI:8000';

function Auditoria({ token }) {
  const [logs, setLogs] = useState([]);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    axios.get(`${API_URL}/audit/logs?dias=30`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => setLogs(response.data))
      .catch(() => setErro(true));
  }, [token]);

  return (
    <div className="detail-table">
      <h3 className="detail-table-title">Logs de Auditoria — Últimos 30 dias</h3>

      {erro && (
        <div className="error-message">
          Você não tem permissão para ver esta página, ou houve um erro ao carregar.
        </div>
      )}

      {!erro && (
                <div className="list-table">
          <div className="list-row head" style={{ gridTemplateColumns: '110px 170px 1fr 110px 120px 150px' }}>
            <span>Usuário</span>
            <span>Ação</span>
            <span>Detalhes</span>
            <span>Resultado</span>
            <span>IP de Origem</span>
            <span>Data/Hora</span>
          </div>
          {logs.map((log) => (
            <div className="list-row" style={{ gridTemplateColumns: '110px 170px 1fr 110px 120px 150px' }} key={log.id}>
              <span className="list-cell-strong">{log.username}</span>
              <span className="list-cell">{log.acao}</span>
              <span className="list-cell">{log.detalhes || '—'}</span>
              <span className={`status-tag status-tag-${log.resultado === 'sucesso' ? 'online' : log.resultado === 'solicitado' ? 'warning' : 'offline'}`}>
                {log.resultado === 'sucesso' ? 'Sucesso' : log.resultado === 'solicitado' ? 'Solicitado' : 'Falha'}
              </span>
              <span className="list-cell-mono">{log.ip_origem || '—'}</span>
              <span className="list-cell-mono">{new Date(log.criado_em).toLocaleString('pt-BR')}</span>
            </div>
          ))}
          {logs.length === 0 && (
            <div className="loading-message">Nenhum registro encontrado</div>
          )}
        </div>
      )}
    </div>
  );
}

export default Auditoria;
