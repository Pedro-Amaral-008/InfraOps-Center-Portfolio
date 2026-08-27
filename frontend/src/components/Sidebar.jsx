import { useState } from 'react';
import './Sidebar.css';

const ITENS_ADMINISTRACAO = [
  { id: 'automacoes', label: 'Automações' },
  { id: 'auditoria', label: 'Auditoria' },
  { id: 'usuarios', label: 'Usuários' },
  { id: 'solicitacoes', label: 'Solicitações' },
];

function Sidebar({ usuario, abaAtiva, onChangeAba }) {
  const [fechada, setFechada] = useState(false);
  const podeVerAdmin = usuario && ['super_admin', 'admin'].includes(usuario.role);
  const administracaoAtiva = ITENS_ADMINISTRACAO.some((item) => item.id === abaAtiva);
  const [adminAberto, setAdminAberto] = useState(administracaoAtiva);

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
        <div
          className={`sidebar-item active ${abaAtiva === 'dashboard' ? 'selected' : ''}`}
          onClick={() => onChangeAba && onChangeAba('dashboard')}
        >
          <span className="sidebar-label">Dashboard</span>
        </div>

        {podeVerAdmin && (
          <>
            <div
              className={`sidebar-item active ${administracaoAtiva && !adminAberto ? 'selected' : ''}`}
              onClick={() => setAdminAberto(!adminAberto)}
            >
              <span className="sidebar-label">Administração</span>
              <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.7 }}>
                {adminAberto ? '▾' : '▸'}
              </span>
            </div>
            {adminAberto && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginLeft: '12px', marginTop: '8px' }}>
                {ITENS_ADMINISTRACAO.map((item) => (
                  <div
                    key={item.id}
                    className={`sidebar-item active ${abaAtiva === item.id ? 'selected' : ''}`}
                    onClick={() => onChangeAba && onChangeAba(item.id)}
                    style={{ fontSize: '13px' }}
                  >
                    <span className="sidebar-label">{item.label}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </nav>
    </aside>
  );
}
export default Sidebar;
