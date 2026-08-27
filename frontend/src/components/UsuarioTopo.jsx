/* ==========================================================================
   Bloco do usuario - canto superior direito do conteudo

   Saiu do cabecalho quando a barra do topo foi removida, e depois saiu do
   pe do menu lateral. Agora fica solto no alto da area de conteudo, sem
   faixa nenhuma atras.

   NAO E UMA BARRA: e o PRIMEIRO elemento do conteudo da pagina, alinhado a
   direita. Por isso rola junto com o resto. O estilo mora no Header.css,
   junto com o resto do menu suspenso do usuario - e o mesmo componente, so
   que em outro lugar da tela.

   COMO USAR: e o primeiro filho da area de conteudo, antes do titulo da
   pagina.

     <main className="app-main">
       <UsuarioTopo usuario={usuario} aoSair={sair} aoAlternarTema={tema} />
       <h2>Dashboard</h2>
       ...
     </main>
   ========================================================================== */

import { useEffect, useRef, useState } from 'react';
import './Header.css';

function UsuarioTopo({ usuario = {}, aoAlternarTema, aoSair }) {
  const [aberto, setAberto] = useState(false);
  const caixa = useRef(null);

  /* Fecha ao clicar fora e no Esc. Sem isso o painel fica aberto para sempre
     depois que a pessoa desiste dele e clica em outro lugar da tela. */
  useEffect(() => {
    if (!aberto) return undefined;

    function cliqueFora(e) {
      if (caixa.current && !caixa.current.contains(e.target)) setAberto(false);
    }
    function tecla(e) {
      if (e.key === 'Escape') setAberto(false);
    }

    document.addEventListener('mousedown', cliqueFora);
    document.addEventListener('keydown', tecla);
    return () => {
      document.removeEventListener('mousedown', cliqueFora);
      document.removeEventListener('keydown', tecla);
    };
  }, [aberto]);

  const nome = usuario.nome || 'Usuário';
  const perfil = usuario.perfil || 'Operador';

  return (
    <div className="usuario-topo">
      <div className="header-menu" ref={caixa}>

        <button
          className="header-avatar"
          type="button"
          onClick={() => setAberto(!aberto)}
          aria-expanded={aberto}
          aria-haspopup="menu"
          aria-label="Menu do usuário"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
               strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </button>

        <div className="usuario-topo-info">
          <span className="usuario-topo-nome">{nome}</span>
          <span className="header-user-role">{perfil}</span>
        </div>

        {aberto && (
          <div className="header-dropdown" role="menu">
            <div className="header-dropdown-nome">{nome}</div>
            <span className="header-user-role">{perfil}</span>
            <div className="header-dropdown-sep" />

            <button
              className="header-dropdown-item"
              type="button"
              role="menuitem"
              onClick={() => { setAberto(false); aoAlternarTema && aoAlternarTema(); }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                   strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </svg>
              Alternar tema
            </button>

            <button
              className="header-dropdown-item"
              type="button"
              role="menuitem"
              onClick={() => { setAberto(false); aoSair && aoSair(); }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
              </svg>
              Sair
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default UsuarioTopo;
