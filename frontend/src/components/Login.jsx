import { useState, useEffect } from 'react';
import axios from 'axios';
import './Login.css';

const API_URL = 'IP_INTERNO_AQUI:8000';

const IconePessoa = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
  </svg>
);

const IconeOlhoAberto = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12s3.8-7 10-7 10 7 10 7-3.8 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" />
  </svg>
);

const IconeOlhoFechado = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.6 6.2A9.9 9.9 0 0 1 12 6c6.2 0 10 7 10 7a17 17 0 0 1-2.6 3.3M6.6 6.7A17 17 0 0 0 2 13s3.8 7 10 7a9.6 9.6 0 0 0 4.5-1.1" />
    <path d="M3 3l18 18M9.9 10.1a3 3 0 0 0 4.1 4.2" />
  </svg>
);

function ColunaApoio() {
  return (
    <div className="login-marca">
      <p className="login-marca-texto">
        Monitoramento de infraestrutura, servidores e rede em tempo real.
      </p>
      <ul className="login-recursos">
        <li className="login-recurso">
          <span className="login-recurso-icone">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="4" width="20" height="7" rx="2" /><rect x="2" y="13" width="20" height="7" rx="2" />
              <path d="M6 7.5h.01M6 16.5h.01" />
            </svg>
          </span>
          <span className="login-recurso-label">Servidores e serviços</span>
        </li>
        <li className="login-recurso">
          <span className="login-recurso-icone">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2 2 21h20L12 2z" /><path d="M12 9v5M12 17.5h.01" />
            </svg>
          </span>
          <span className="login-recurso-label">Alertas e ocorrências</span>
        </li>
        <li className="login-recurso">
          <span className="login-recurso-icone">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2" /><path d="M6 13l3.5-4 2.5 2.5L17 7M8 21h8M12 17v4" />
            </svg>
          </span>
          <span className="login-recurso-label">Visão operacional em tempo real</span>
        </li>
      </ul>
    </div>
  );
}

function Login({ onLoginSuccess }) {
  const [modo, setModo] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [verSenha, setVerSenha] = useState(false);
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

  const mudarModo = (novoModo) => {
    limparMensagens();
    setModo(novoModo);
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
      setTimeout(() => { window.location.href = '/'; }, 2000);
    } catch (err) {
      setErro(err.response?.data?.detail || 'Token inválido ou expirado');
    } finally {
      setCarregando(false);
    }
  };

  const titulos = {
    login: { titulo: 'Bem-vindo', subtitulo: 'Faça login para acessar o sistema.' },
    cadastro: { titulo: 'Solicitar acesso', subtitulo: 'Preencha seus dados para pedir acesso ao sistema.' },
    'esqueci-senha': { titulo: 'Esqueci minha senha', subtitulo: 'Informe seu e-mail cadastrado para receber o link de redefinição.' },
    'redefinir-senha': { titulo: 'Redefinir senha', subtitulo: 'Escolha uma nova senha para sua conta.' },
  };

  return (
    <div className="login-container">
      {modo === 'login' && <ColunaApoio />}

      <div className="login-box">
        <h2 className="login-title">{titulos[modo].titulo}</h2>
        <p className="login-subtitle">{titulos[modo].subtitulo}</p>

        {modo === 'login' && (
          <form className="login-form" onSubmit={handleLogin}>
            {erro && <div className="login-error" role="alert"><span aria-hidden="true">⚠</span><span>{erro}</span></div>}
            {mensagem && <div className="login-error" style={{ color: 'var(--status-online, #2ecc71)' }}>{mensagem}</div>}

            <div className="login-campo">
              <label className="login-label" htmlFor="login-usuario">E-mail ou nome de usuário</label>
              <div className="login-campo-caixa">
                <input
                  className="login-input" id="login-usuario" data-campo="usuario" type="text"
                  placeholder="seu@email.com ou usuário" autoComplete="username" autoFocus
                  value={username} onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </div>

            <div className="login-campo">
              <label className="login-label" htmlFor="login-senha">Senha</label>
              <div className="login-campo-caixa">
                <input
                  className="login-input" id="login-senha" data-campo="senha"
                  type={verSenha ? 'text' : 'password'} placeholder="Digite sua senha"
                  autoComplete="current-password" value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  className="login-olho" type="button" onClick={() => setVerSenha(!verSenha)}
                  aria-pressed={verSenha} aria-label={verSenha ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  {verSenha ? <IconeOlhoFechado /> : <IconeOlhoAberto />}
                </button>
              </div>
            </div>

            <a className="login-esqueci" href="#" onClick={(e) => { e.preventDefault(); mudarModo('esqueci-senha'); }}>
              Esqueci minha senha
            </a>

            <button className="login-button" type="submit" disabled={carregando}>
              {carregando ? 'Entrando...' : 'Entrar no sistema'}
            </button>

            <div className="login-ou"><span>ou</span></div>

            <button className="login-button-secundario" type="button" onClick={() => mudarModo('cadastro')}>
              Solicitar novo acesso
            </button>
          </form>
        )}

        {modo === 'cadastro' && (
          <form className="login-form" onSubmit={handleCadastro}>
            {erro && <div className="login-error" role="alert"><span aria-hidden="true">⚠</span><span>{erro}</span></div>}

            <div className="login-campo">
              <label className="login-label" htmlFor="cadastro-nome">Nome completo</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="cadastro-nome" type="text" autoFocus
                  value={nomeCompleto} onChange={(e) => setNomeCompleto(e.target.value)} />
              </div>
            </div>

            <div className="login-campo">
              <label className="login-label" htmlFor="cadastro-email">E-mail corporativo</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="cadastro-email" type="email" placeholder="seu@elcop.eng.br"
                  value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            </div>

            <div className="login-campo">
              <label className="login-label" htmlFor="cadastro-usuario">Escolha um usuário</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="cadastro-usuario" type="text" data-campo="usuario"
                  value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
            </div>

            <div className="login-campo">
              <label className="login-label" htmlFor="cadastro-senha">Senha</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="cadastro-senha" data-campo="senha"
                  type={verSenha ? 'text' : 'password'}
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <button className="login-olho" type="button" onClick={() => setVerSenha(!verSenha)}
                  aria-label={verSenha ? 'Ocultar senha' : 'Mostrar senha'}>
                  {verSenha ? <IconeOlhoFechado /> : <IconeOlhoAberto />}
                </button>
              </div>
            </div>

            <div className="login-campo">
              <label className="login-label" htmlFor="cadastro-confirmar">Confirmar senha</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="cadastro-confirmar" data-campo="senha"
                  type={verSenha ? 'text' : 'password'}
                  value={confirmarSenha} onChange={(e) => setConfirmarSenha(e.target.value)} />
              </div>
            </div>

            <button className="login-button" type="submit" disabled={carregando}>
              {carregando ? 'Enviando...' : 'Solicitar acesso'}
            </button>

            <div className="login-ou"><span>ou</span></div>

            <button className="login-button-secundario" type="button" onClick={() => mudarModo('login')}>
              Voltar ao login
            </button>
          </form>
        )}

        {modo === 'esqueci-senha' && (
          <form className="login-form" onSubmit={handleEsqueciSenha}>
            {erro && <div className="login-error" role="alert"><span aria-hidden="true">⚠</span><span>{erro}</span></div>}
            {mensagem && <div className="login-error" style={{ color: 'var(--status-online, #2ecc71)' }}>{mensagem}</div>}

            <div className="login-campo">
              <label className="login-label" htmlFor="esqueci-email">E-mail corporativo</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="esqueci-email" type="email" autoFocus
                  value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            </div>

            <button className="login-button" type="submit" disabled={carregando}>
              {carregando ? 'Enviando...' : 'Enviar link'}
            </button>

            <div className="login-ou"><span>ou</span></div>

            <button className="login-button-secundario" type="button" onClick={() => mudarModo('login')}>
              Voltar ao login
            </button>
          </form>
        )}

        {modo === 'redefinir-senha' && (
          <form className="login-form" onSubmit={handleRedefinirSenha}>
            {erro && <div className="login-error" role="alert"><span aria-hidden="true">⚠</span><span>{erro}</span></div>}
            {mensagem && <div className="login-error" style={{ color: 'var(--status-online, #2ecc71)' }}>{mensagem}</div>}

            <div className="login-campo">
              <label className="login-label" htmlFor="redefinir-senha">Nova senha</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="redefinir-senha" data-campo="senha"
                  type={verSenha ? 'text' : 'password'} autoFocus
                  value={password} onChange={(e) => setPassword(e.target.value)} />
                <button className="login-olho" type="button" onClick={() => setVerSenha(!verSenha)}
                  aria-label={verSenha ? 'Ocultar senha' : 'Mostrar senha'}>
                  {verSenha ? <IconeOlhoFechado /> : <IconeOlhoAberto />}
                </button>
              </div>
            </div>

            <div className="login-campo">
              <label className="login-label" htmlFor="redefinir-confirmar">Confirmar nova senha</label>
              <div className="login-campo-caixa">
                <input className="login-input" id="redefinir-confirmar" data-campo="senha"
                  type={verSenha ? 'text' : 'password'}
                  value={confirmarSenha} onChange={(e) => setConfirmarSenha(e.target.value)} />
              </div>
            </div>

            <button className="login-button" type="submit" disabled={carregando}>
              {carregando ? 'Salvando...' : 'Redefinir senha'}
            </button>
          </form>
        )}

        <p className="login-seguranca">Acesso seguro e protegido</p>
      </div>
    </div>
  );
}

export default Login;
