import { useState, useEffect } from 'react';
import './Header.css';

function Header({ usuario, onLogout }) {
  const [menuAberto, setMenuAberto] = useState(false);
  const [temaClaro, setTemaClaro] = useState(
    localStorage.getItem('infraops_tema') === 'light'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', temaClaro ? 'light' : 'dark');
    localStorage.setItem('infraops_tema', temaClaro ? 'light' : 'dark');
  }, [temaClaro]);

  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo-wrapper">
          <img src="/logo-empresa.avif" alt="Logo" className="logo-img" />
        </div>
        <h1 className="header-title">InfraOps Center</h1>
      </div>
      {usuario && (
        <div className="header-menu">
          <button
            className="header-avatar"
            onClick={() => setMenuAberto(!menuAberto)}
          >
            {usuario.nome_completo?.charAt(0)?.toUpperCase() || '?'}
          </button>
          {menuAberto && (
            <div className="header-dropdown">
              <div className="header-dropdown-nome">{usuario.nome_completo}</div>
              <span className="header-user-role">{usuario.role}</span>
              <div className="header-dropdown-sep"></div>
              <button
                className="header-dropdown-item"
                onClick={() => setTemaClaro(!temaClaro)}
              >
                {temaClaro ? 'Modo escuro' : 'Modo claro'}
              </button>
              <div className="header-dropdown-sep"></div>
              <button className="header-dropdown-item" onClick={onLogout}>
                Sair
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
export default Header;
