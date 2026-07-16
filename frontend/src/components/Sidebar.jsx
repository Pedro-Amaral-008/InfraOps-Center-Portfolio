import './Sidebar.css';

function Sidebar({ usuario, abaAtiva, onChangeAba }) {
  const podeVerAdmin = usuario && ['super_admin', 'admin'].includes(usuario.role);

  const menuItems = [
    { id: 'dashboard', label: 'Visão Geral' },
    ...(podeVerAdmin ? [{ id: 'automacoes', label: 'Automações' }] : []),
    ...(podeVerAdmin ? [{ id: 'auditoria', label: 'Auditoria' }] : []),
  ];

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <div
            key={item.id}
            className={`sidebar-item active ${abaAtiva === item.id ? 'selected' : ''}`}
            onClick={() => onChangeAba && onChangeAba(item.id)}
          >
            <span className="sidebar-label">{item.label}</span>
          </div>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
