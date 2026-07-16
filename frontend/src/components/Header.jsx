import './Header.css';

function Header({ usuario, onLogout }) {
  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo-wrapper">
          <img src="/logo-empresa.avif" alt="Logo" className="logo-img" />
        </div>
        <h1 className="header-title">InfraOps Center</h1>
      </div>

      {usuario && (
        <div className="header-user">
          <span className="header-user-name">{usuario.nome_completo}</span>
          <span className="header-user-role">{usuario.role}</span>
          <button className="header-logout-btn" onClick={onLogout}>
            Sair
          </button>
        </div>
      )}
    </header>
  );
}

export default Header;
