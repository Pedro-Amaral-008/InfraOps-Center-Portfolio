import { useState } from 'react';
import './Sidebar.css';

function Sidebar({ usuario, abaAtiva, onChangeAba }) {
  const [fechada, setFechada] = useState(false);
  const podeVerAdmin = usuario && ['super_admin', 'admin'].includes(usuario.role);
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard' },
    ...(podeVerAdmin ? [{ id: 'automacoes', label: 'Automações' }] : []),
    ...(podeVerAdmin ? [{ id: 'auditoria', label: 'Auditoria' }] : []),
    ...(podeVerAdmin ? [{ id: 'usuarios', label: 'Usuários' }] : []),
    ...(podeVerAdmin ? [{ id: 'solicitacoes', label: 'Solicitações' }] : []),
  ];
  return (
    <aside className={`sidebar ${fechada ? 'sidebar-fechada' : ''}`}>
      <button
        className="sidebar-toggle"
        onClick={() => setFechada(!fechada)}
        title={fechada ? 'Expandir menu' : 'Recolher menu'}
      >
        {fechada ? '»' : '«'}
      </button>
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
