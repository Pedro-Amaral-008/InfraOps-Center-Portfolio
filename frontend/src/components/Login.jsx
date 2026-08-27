import { useState, useEffect } from 'react';
import axios from 'axios';
import './Login.css';

const API_URL = 'IP_INTERNO_AQUI:8000';

function Login({ onLoginSuccess }) {
  const [modo, setModo] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [erro, setErro] = useState('');
  const [mensagem, setMensagem] = useState('');
  const [carregando, setCarregando] = useState(false);

  const [nomeCompleto, setNomeCompleto] = useState('');
  const [email, setEmail] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');

  const [tokenReset, setTokenReset] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (window.location.pathname.includes('redefinir-senha') && token) {
      setTokenReset(token);
      setModo('redefinir-senha');
    }
  }, []);

  const limparMensagens = () => {
    setErro('');
    setMensagem('');
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    limparMensagens();
    setCarregando(true);
    try {
      const response = await axios.post(`${API_URL}/auth/login`, { username, password });
      onLoginSuccess(response.data);
    } catch (err) {
      setErro('Usuário ou senha inválidos');
    } finally {
      setCarregando(false);
    }
  };

  const handleCadastro = async (e) => {
    e.preventDefault();
    limparMensagens();
    if (password !== confirmarSenha) {
      setErro('As senhas não coincidem');
      return;
    }
    setCarregando(true);
    try {
      await axios.post(`${API_URL}/auth/solicitar-acesso`, {
        nome_completo: nomeCompleto,
        email,
        username,
        password,
      });
      setMensagem('Solicitação enviada! Você receberá um e-mail assim que for aprovada.');
      setModo('login');
    } catch (err) {
      setErro(err.response?.data?.detail || 'Erro ao enviar solicitação');
    } finally {
      setCarregando(false);
    }
  };

  const handleEsqueciSenha = async (e) => {
    e.preventDefault();
    limparMensagens();
    setCarregando(true);
    try {
      await axios.post(`${API_URL}/auth/esqueci-senha`, { email });
      setMensagem('Se o e-mail existir, um link de redefinição foi enviado.');
    } catch (err) {
      setErro('Erro ao solicitar redefinição');
    } finally {
      setCarregando(false);
    }
  };

  const handleRedefinirSenha = async (e) => {
    e.preventDefault();
    limparMensagens();
    if (password !== confirmarSenha) {
      setErro('As senhas não coincidem');
      return;
    }
    setCarregando(true);
    try {
      await axios.post(`${API_URL}/auth/redefinir-senha`, {
        token: tokenReset,
        nova_senha: password,
      });
      setMensagem('Senha redefinida com sucesso! Você já pode fazer login.');
      setTimeout(() => {
        window.location.href = '/';
      }, 2000);
    } catch (err) {
      setErro(err.response?.data?.detail || 'Token inválido ou expirado');
    } finally {
      setCarregando(false);
    }
  };

  const linkStyle = {
    background: 'none',
    border: 'none',
    color: 'var(--text-tertiary, #6b6b70)',
    fontSize: '13px',
    cursor: 'pointer',
    textDecoration: 'underline',
    padding: '4px',
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <div className="login-logo-wrapper">
          <img src="/logo-empresa.png" alt="Logo" className="login-logo" />
        </div>
        <h1 className="login-title">InfraOps Center</h1>
        <p className="login-subtitle">Elcop</p>

        {modo === 'login' && (
          <form onSubmit={handleLogin} className="login-form">
            <input
              type="text"
              placeholder="Usuário ou e-mail"
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
            {mensagem && <div className="login-error" style={{ color: 'var(--status-online, #2ecc71)' }}>{mensagem}</div>}
            <button type="submit" className="login-button" disabled={carregando}>
              {carregando ? 'Entrando...' : 'Entrar'}
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px' }}>
              <button type="button" style={linkStyle} onClick={() => { limparMensagens(); setModo('esqueci-senha'); }}>
                Esqueci minha senha
              </button>
              <button type="button" style={linkStyle} onClick={() => { limparMensagens(); setModo('cadastro'); }}>
                Solicitar acesso
              </button>
            </div>
          </form>
        )}

        {modo === 'cadastro' && (
          <form onSubmit={handleCadastro} className="login-form">
            <input
              type="text"
              placeholder="Nome completo"
              value={nomeCompleto}
              onChange={(e) => setNomeCompleto(e.target.value)}
              className="login-input"
              autoFocus
            />
            <input
              type="email"
              placeholder="E-mail corporativo (@elcop.eng.br)"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="login-input"
            />
            <input
              type="text"
              placeholder="Escolha um usuário"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="login-input"
            />
            <input
              type="password"
              placeholder="Senha"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="login-input"
            />
            <input
              type="password"
              placeholder="Confirmar senha"
              value={confirmarSenha}
              onChange={(e) => setConfirmarSenha(e.target.value)}
              className="login-input"
            />
            {erro && <div className="login-error">{erro}</div>}
            <button type="submit" className="login-button" disabled={carregando}>
              {carregando ? 'Enviando...' : 'Solicitar acesso'}
            </button>
            <div style={{ textAlign: 'center', marginTop: '12px' }}>
              <button type="button" style={linkStyle} onClick={() => { limparMensagens(); setModo('login'); }}>
                Voltar ao login
              </button>
            </div>
          </form>
        )}

        {modo === 'esqueci-senha' && (
          <form onSubmit={handleEsqueciSenha} className="login-form">
            <p className="login-subtitle" style={{ marginTop: 0 }}>Informe seu e-mail cadastrado para receber o link de redefinição.</p>
            <input
              type="email"
              placeholder="E-mail corporativo"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="login-input"
              autoFocus
            />
            {erro && <div className="login-error">{erro}</div>}
            {mensagem && <div className="login-error" style={{ color: 'var(--status-online, #2ecc71)' }}>{mensagem}</div>}
            <button type="submit" className="login-button" disabled={carregando}>
              {carregando ? 'Enviando...' : 'Enviar link'}
            </button>
            <div style={{ textAlign: 'center', marginTop: '12px' }}>
              <button type="button" style={linkStyle} onClick={() => { limparMensagens(); setModo('login'); }}>
                Voltar ao login
              </button>
            </div>
          </form>
        )}

        {modo === 'redefinir-senha' && (
          <form onSubmit={handleRedefinirSenha} className="login-form">
            <input
              type="password"
              placeholder="Nova senha"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="login-input"
              autoFocus
            />
            <input
              type="password"
              placeholder="Confirmar nova senha"
              value={confirmarSenha}
              onChange={(e) => setConfirmarSenha(e.target.value)}
              className="login-input"
            />
            {erro && <div className="login-error">{erro}</div>}
            {mensagem && <div className="login-error" style={{ color: 'var(--status-online, #2ecc71)' }}>{mensagem}</div>}
            <button type="submit" className="login-button" disabled={carregando}>
              {carregando ? 'Salvando...' : 'Redefinir senha'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default Login;
