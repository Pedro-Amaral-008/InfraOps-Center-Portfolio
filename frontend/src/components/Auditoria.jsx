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
        <table>
          <thead>
            <tr>
              <th>Usuário</th>
              <th>Ação</th>
              <th>Detalhes</th>
              <th>Resultado</th>
              <th>IP de Origem</th>
              <th>Data/Hora</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>{log.username}</td>
                <td>{log.acao}</td>
                <td>{log.detalhes || '—'}</td>
                <td>
                  <span className={`status-tag status-tag-${log.resultado === 'sucesso' ? 'online' : log.resultado === 'solicitado' ? 'warning' : 'offline'}`}>
                    {log.resultado === 'sucesso' ? 'Sucesso' : log.resultado === 'solicitado' ? 'Solicitado' : 'Falha'}
                  </span>
                </td>
                <td>{log.ip_origem || '—'}</td>
                <td>{new Date(log.criado_em).toLocaleString('pt-BR')}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr><td colSpan="6">Nenhum registro encontrado</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default Auditoria;
