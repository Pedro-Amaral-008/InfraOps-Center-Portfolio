import { useState } from 'react';
import axios from 'axios';
import './Login.css';

const API_URL = 'http://IP_INTERNO_AQUI:8000';

function TrocarSenha({ token, onSenhaTrocada }) {
  const [senhaAtual, setSenhaAtual] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmaSenha, setConfirmaSenha] = useState('');
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErro('');

    if (novaSenha.length < 8) {
      setErro('A nova senha deve ter no mínimo 8 caracteres');
      return;
    }

    if (novaSenha !== confirmaSenha) {
      setErro('As senhas não coincidem');
      return;
    }

    setCarregando(true);

    try {
      await axios.post(
        `${API_URL}/auth/trocar-senha`,
        { senha_atual: senhaAtual, nova_senha: novaSenha },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      onSenhaTrocada();
    } catch (err) {
      setErro(err.response?.data?.detail || 'Erro ao trocar senha');
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1 className="login-title">Troca de Senha Obrigatória</h1>
        <p className="login-subtitle">Primeiro acesso — defina uma nova senha</p>

        <form onSubmit={handleSubmit} className="login-form">
          <input
            type="password"
            placeholder="Senha temporária atual"
            value={senhaAtual}
            onChange={(e) => setSenhaAtual(e.target.value)}
            className="login-input"
            autoFocus
          />
          <input
            type="password"
            placeholder="Nova senha (mín. 8 caracteres)"
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
            className="login-input"
          />
          <input
            type="password"
            placeholder="Confirmar nova senha"
            value={confirmaSenha}
            onChange={(e) => setConfirmaSenha(e.target.value)}
            className="login-input"
          />

          {erro && <div className="login-error">{erro}</div>}

          <button type="submit" className="login-button" disabled={carregando}>
            {carregando ? 'Salvando...' : 'Trocar Senha'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default TrocarSenha;
