import { useState } from 'react';
import CHANGELOG from '../changelog';
import './Header.css';
import './Sidebar.css';

const ICONES = {
  painel: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" /><rect x="14" y="3" width="7" height="5" />
      <rect x="14" y="12" width="7" height="9" /><rect x="3" y="16" width="7" height="5" />
    </svg>
  ),
  administracao: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15H4a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 6 9.4l-.06-.06a2 2 0 1 1 2.83-2.83L9 6.6A1.65 1.65 0 0 0 11 4.6V4a2 2 0 1 1 4 0v.09c0 .67.4 1.27 1 1.51" />
    </svg>
  ),
  automacoes: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" /><path d="M7 15l4-5 3 3 5-7" />
    </svg>
  ),
  auditoria: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M9 15h6M9 11h3" />
    </svg>
  ),
  usuarios: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
    </svg>
  ),
  controller: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" />
    </svg>
  ),
  servidores_metricas: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="6" rx="1" />
      <rect x="2" y="15" width="20" height="6" rx="1" />
      <circle cx="6" cy="6" r="0.5" fill="currentColor" />
      <circle cx="6" cy="18" r="0.5" fill="currentColor" />
    </svg>
  ),
  impressoras_metricas: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 6 2 18 2 18 9" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" />
    </svg>
  ),
  backups_metricas: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19.5 17.5a4.5 4.5 0 0 0-1.4-8.8 6 6 0 0 0-11.8 1.9A4 4 0 0 0 5 18.5" />
      <polyline points="12 12 12 21" />
      <polyline points="9 18 12 21 15 18" />
    </svg>
  ),
  redes_metricas: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  solicitacoes: (
    <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 12l2 2 4-4" /><path d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9c2.06 0 3.96.7 5.47 1.87" />
    </svg>
  ),
};

const ITENS_ADMINISTRACAO = [
  { id: 'automacoes', label: 'Automações', icone: 'automacoes' },
  { id: 'auditoria', label: 'Auditoria', icone: 'auditoria' },
  { id: 'usuarios', label: 'Usuários', icone: 'usuarios' },
  { id: 'solicitacoes', label: 'Solicitações', icone: 'solicitacoes' },
];

const ITENS_METRICAS = [
  { id: 'controller', label: 'Controller', icone: 'controller' },
  { id: 'servidores', label: 'Servidores', icone: 'servidores_metricas' },
  { id: 'impressoras', label: 'Impressoras', icone: 'impressoras_metricas' },
  { id: 'backups', label: 'Backups', icone: 'backups_metricas' },
  { id: 'links_internet', label: 'Redes', icone: 'redes_metricas' },
];

const ROTULO_ESTADO = {
  online: 'Sistema online',
  alerta: 'Sistema com alertas',
  queda: 'Sistema com falhas',
};

const CLASSE_ESTADO = {
  online: '',
  alerta: ' status-alerta',
  queda: ' status-queda',
};

function Sidebar({ usuario, abaAtiva, onChangeAba, onChangeAbaInterna, abaInterna, estadoSistema = 'online', onAbrirNovidades }) {
  const [fechada, setFechada] = useState(false);
  const podeVerAdmin = usuario && ['super_admin', 'admin'].includes(usuario.role);
  const administracaoAtiva = ITENS_ADMINISTRACAO.some((item) => item.id === abaAtiva);
  const [adminAberto, setAdminAberto] = useState(administracaoAtiva);
  const metricasAtivas = abaAtiva === 'metricas';
  const [metricasAberto, setMetricasAberto] = useState(metricasAtivas);
  const versaoAtual = (CHANGELOG[0]?.versao || '').replace('v', '');

  return (
    <aside className={fechada ? 'sidebar sidebar-fechada' : 'sidebar'}>
      <button
        className="sidebar-toggle"
        type="button"
        onClick={() => setFechada(!fechada)}
        aria-expanded={!fechada}
        aria-label={fechada ? 'Expandir menu' : 'Recolher menu'}
      >
        {fechada ? '›' : '‹'}
      </button>

      <div className={'sidebar-status' + CLASSE_ESTADO[estadoSistema]}>
        {ROTULO_ESTADO[estadoSistema]}
      </div>

      <nav className="sidebar-nav">
        <div
          className={`sidebar-item ${abaAtiva === 'dashboard' ? 'active' : ''}`}
          onClick={() => onChangeAba && onChangeAba('dashboard')}
          role="button"
          tabIndex={0}
          title={fechada ? 'Dashboard' : undefined}
        >
          {ICONES.painel}
          <span className="sidebar-label">Dashboard</span>
        </div>

        <div
          className={`sidebar-item ${metricasAtivas && !metricasAberto ? 'active' : ''}`}
          onClick={() => setMetricasAberto(!metricasAberto)}
          role="button"
          tabIndex={0}
          title={fechada ? 'Métricas Detalhadas' : undefined}
        >
          {ICONES.automacoes}
          <span className="sidebar-label">Métricas Detalhadas</span>
          {!fechada && (
            <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.7 }}>
              {metricasAberto ? '▾' : '▸'}
            </span>
          )}
        </div>
        {metricasAberto && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
            {ITENS_METRICAS.map((item) => (
              <div
                key={item.id}
                className={`sidebar-item ${abaAtiva === 'metricas' && abaInterna === item.id ? 'active' : ''}`}
                onClick={() => {
                  onChangeAba && onChangeAba('metricas');
                  onChangeAbaInterna && onChangeAbaInterna(item.id);
                }}
                role="button"
                tabIndex={0}
                style={{ marginLeft: fechada ? 0 : '12px', fontSize: '13px' }}
                title={fechada ? item.label : undefined}
              >
                {ICONES[item.icone]}
                <span className="sidebar-label">{item.label}</span>
              </div>
            ))}
          </div>
        )}

        {podeVerAdmin && (
          <>
            <div
              className={`sidebar-item ${administracaoAtiva && !adminAberto ? 'active' : ''}`}
              onClick={() => setAdminAberto(!adminAberto)}
              role="button"
              tabIndex={0}
              title={fechada ? 'Administração' : undefined}
            >
              {ICONES.administracao}
              <span className="sidebar-label">Administração</span>
              {!fechada && (
                <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.7 }}>
                  {adminAberto ? '▾' : '▸'}
                </span>
              )}
            </div>
            {adminAberto && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                {ITENS_ADMINISTRACAO.map((item) => (
                  <div
                    key={item.id}
                    className={`sidebar-item ${abaAtiva === item.id ? 'active' : ''}`}
                    onClick={() => onChangeAba && onChangeAba(item.id)}
                    role="button"
                    tabIndex={0}
                    style={{ marginLeft: fechada ? 0 : '12px', fontSize: '13px' }}
                    title={fechada ? item.label : undefined}
                  >
                    {ICONES[item.icone]}
                    <span className="sidebar-label">{item.label}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </nav>

      <div className="sidebar-rodape">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
             strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3l1.9 4.9L18.8 9.8 13.9 11.7 12 16.6 10.1 11.7 5.2 9.8l4.9-1.9L12 3z" />
          <path d="M18.5 16.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z" />
        </svg>
        <span className="sidebar-rodape-texto">
          v{versaoAtual} &middot;{' '}
          <a href="#" onClick={(e) => { e.preventDefault(); onAbrirNovidades && onAbrirNovidades(); }}>
            Novidades
          </a>
        </span>
      </div>
    </aside>
  );
}
export default Sidebar;
