import { useState, useEffect } from 'react';
import axios from 'axios';
import './Auditoria.css';
import './Usuarios.css';

const API_URL = 'http://192.168.1.26:8000';

function Solicitacoes({ token }) {
  const [solicitacoes, setSolicitacoes] = useState([]);
  const [erro, setErro] = useState(false);
  const [roleEscolhido, setRoleEscolhido] = useState({});

  const carregarSolicitacoes = () => {
    axios.get(`${API_URL}/auth/solicitacoes`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => setSolicitacoes(response.data))
      .catch(() => setErro(true));
  };

  useEffect(() => {
    carregarSolicitacoes();
  }, [token]);

  const aprovar = (id) => {
    const role = roleEscolhido[id] || 'operador';
    if (!window.confirm(`Aprovar esta solicitação com o papel "${role}"?`)) return;
    axios.post(`${API_URL}/auth/solicitacoes/${id}/aprovar`, { role }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(() => {
      carregarSolicitacoes();
    }).catch((err) => {
      alert(err.response?.data?.detail || 'Erro ao aprovar solicitação');
    });
  };

  const rejeitar = (id) => {
    if (!window.confirm('Rejeitar esta solicitação? Essa ação não pode ser desfeita.')) return;
    axios.post(`${API_URL}/auth/solicitacoes/${id}/rejeitar`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(() => {
      carregarSolicitacoes();
    }).catch((err) => {
      alert(err.response?.data?.detail || 'Erro ao rejeitar solicitação');
    });
  };

  return (
    <div className="detail-table">
      <h3 className="detail-table-title">Solicitações de Acesso Pendentes</h3>

      {erro && (
        <div className="error-message">
          Você não tem permissão para ver esta página, ou houve um erro ao carregar.
        </div>
      )}

      {!erro && solicitacoes.length === 0 && (
        <p style={{ color: 'var(--text-tertiary, #6b6b70)', padding: '16px 0' }}>
          Nenhuma solicitação pendente no momento.
        </p>
      )}

      {!erro && solicitacoes.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>E-mail</th>
              <th>Usuário</th>
              <th>Solicitado em</th>
              <th>Papel</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {solicitacoes.map((s) => (
              <tr key={s.id}>
                <td>{s.nome_completo}</td>
                <td>{s.email}</td>
                <td>{s.username}</td>
                <td>{new Date(s.solicitado_em).toLocaleString('pt-BR')}</td>
                <td>
                  <select
                    value={roleEscolhido[s.id] || 'operador'}
                    onChange={(e) => setRoleEscolhido({ ...roleEscolhido, [s.id]: e.target.value })}
                  >
                    <option value="operador">Operador</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td>
                  <div className="usuarios-acoes">
                    <button className="btn btn-primary" onClick={() => aprovar(s.id)}>Aprovar</button>
                    <button className="btn btn-danger" onClick={() => rejeitar(s.id)}>Rejeitar</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default Solicitacoes;
