import { useState, useEffect } from 'react';
import axios from 'axios';
import './Auditoria.css';
import './Usuarios.css';

const API_URL = 'IP_INTERNO_AQUI:8000';

function Usuarios({ token, meuUsername, meuRole }) {
  const [usuarios, setUsuarios] = useState([]);
  const [erro, setErro] = useState(false);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [novoUsername, setNovoUsername] = useState('');
  const [novoNome, setNovoNome] = useState('');
  const [novoRole, setNovoRole] = useState('operador');
  const [senhaGerada, setSenhaGerada] = useState(null);
  const [usuarioSenhaGerada, setUsuarioSenhaGerada] = useState('');

  const carregarUsuarios = () => {
    axios.get(`${API_URL}/usuarios`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => setUsuarios(response.data))
      .catch(() => setErro(true));
  };

  useEffect(() => {
    carregarUsuarios();
  }, [token]);

  const criarUsuario = (e) => {
    e.preventDefault();
    axios.post(`${API_URL}/usuarios`, {
      username: novoUsername,
      nome_completo: novoNome,
      role: novoRole,
    }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((response) => {
      setSenhaGerada(response.data.senha_temporaria);
      setUsuarioSenhaGerada(response.data.username);
      setNovoUsername('');
      setNovoNome('');
      setNovoRole('operador');
      setMostrarForm(false);
      carregarUsuarios();
    }).catch((err) => {
      alert(err.response?.data?.detail || 'Erro ao criar usuário');
    });
  };

  const resetarSenha = (username) => {
    if (!window.confirm(`Resetar a senha de ${username}?`)) return;
    axios.post(`${API_URL}/usuarios/${username}/resetar-senha`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((response) => {
      setSenhaGerada(response.data.senha_temporaria);
      setUsuarioSenhaGerada(response.data.username);
      carregarUsuarios();
    }).catch((err) => {
      alert(err.response?.data?.detail || 'Erro ao resetar senha');
    });
  };

  const alterarRole = (username, roleAtual) => {
    const novoRoleEscolhido = window.prompt(
      `Novo papel para ${username} (super_admin / admin / operador):`,
      roleAtual
    );
    if (!novoRoleEscolhido || novoRoleEscolhido === roleAtual) return;
    axios.patch(`${API_URL}/usuarios/${username}/role`, {
      role: novoRoleEscolhido,
    }, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(() => {
      carregarUsuarios();
    }).catch((err) => {
      alert(err.response?.data?.detail || 'Erro ao alterar papel');
    });
  };

  const desativarUsuario = (username) => {
    if (!window.confirm(`Desativar o usuário ${username}? Ele não poderá mais fazer login.`)) return;
    axios.delete(`${API_URL}/usuarios/${username}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(() => {
      carregarUsuarios();
    }).catch((err) => {
      alert(err.response?.data?.detail || 'Erro ao desativar usuário');
    });
  };

  return (
    <div className="detail-table">
      <h3 className="detail-table-title">Gerenciamento de Usuários</h3>

      {erro && (
        <div className="error-message">
          Você não tem permissão para ver esta página, ou houve um erro ao carregar.
        </div>
      )}

      {!erro && (
        <>
          {senhaGerada && (
            <div className="senha-gerada-box">
              <span>Senha temporária para <b>{usuarioSenhaGerada}</b>: <code>{senhaGerada}</code> — repasse com segurança, o usuário deverá trocá-la no primeiro login.</span>
              <button className="btn btn-secondary" onClick={() => setSenhaGerada(null)}>Fechar</button>
            </div>
          )}

          {!mostrarForm && (
            <button className="btn btn-primary" onClick={() => setMostrarForm(true)} style={{ marginBottom: '16px' }}>
              + Novo Usuário
            </button>
          )}

          {mostrarForm && (
            <form onSubmit={criarUsuario} className="usuarios-form">
              <input
                type="text"
                placeholder="username"
                value={novoUsername}
                onChange={(e) => setNovoUsername(e.target.value)}
                required
              />
              <input
                type="text"
                placeholder="Nome completo"
                value={novoNome}
                onChange={(e) => setNovoNome(e.target.value)}
                required
              />
              <select value={novoRole} onChange={(e) => setNovoRole(e.target.value)}>
                <option value="operador">Operador</option>
                <option value="admin">Admin</option>
                {meuRole === 'super_admin' && <option value="super_admin">Super Admin</option>}
              </select>
              <button type="submit" className="btn btn-primary">Criar</button>
              <button type="button" className="btn btn-secondary" onClick={() => setMostrarForm(false)}>Cancelar</button>
            </form>
          )}

          <table>
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Nome</th>
                <th>Papel</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.nome_completo}</td>
                  <td>{u.role}</td>
                  <td>
                    <span className={`status-tag status-tag-${u.ativo ? 'online' : 'offline'}`}>
                      {u.ativo ? 'Ativo' : 'Desativado'}
                    </span>
                  </td>
                  <td>
                    {u.username !== meuUsername && (
                      <div className="usuarios-acoes">
                        <button className="btn btn-secondary" onClick={() => resetarSenha(u.username)}>Resetar Senha</button>
                        <button className="btn btn-warning" onClick={() => alterarRole(u.username, u.role)}>Alterar Papel</button>
                        {u.ativo && <button className="btn btn-danger" onClick={() => desativarUsuario(u.username)}>Desativar</button>}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

export default Usuarios;
