import { useState } from 'react';
import axios from 'axios';
import './Login.css';

const API_URL = 'http://IP_INTERNO_AQUI:8000';

function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErro('');
    setCarregando(true);

    try {
      const response = await axios.post(`${API_URL}/auth/login`, {
        username,
        password,
      });
      onLoginSuccess(response.data);
    } catch (err) {
      setErro('Usuário ou senha inválidos');
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <div className="login-logo-wrapper">
          <img src="/logo-empresa.png" alt="Logo" className="login-logo" />
        </div>
        <h1 className="login-title">InfraOps Center</h1>
        <p className="login-subtitle">Elcop</p>

        <form onSubmit={handleSubmit} className="login-form">
          <input
            type="text"
            placeholder="Usuário"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="login-input"
            autoFocus
          />
          <input
            type="password"
            placeholder="Senha"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="login-input"
          />

          {erro && <div className="login-error">{erro}</div>}

          <button type="submit" className="login-button" disabled={carregando}>
            {carregando ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;
