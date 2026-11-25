import { useState } from 'react';
import CHANGELOG from '../changelog';
import './Novidades.css';

export default function Novidades({ onFechar }) {
  const [versaoAtiva, setVersaoAtiva] = useState(CHANGELOG[0]?.versao ?? '');

  const versaoAtual = CHANGELOG.find((v) => v.versao === versaoAtiva) ?? CHANGELOG[0];
  const totalItens = versaoAtual?.categorias?.reduce((n, c) => n + c.itens.length, 0) ?? 0;

  return (
    <div className="novidades-backdrop" onClick={onFechar}>
      <div className="novidades-card" onClick={(e) => e.stopPropagation()}>

        <div className="novidades-header">
          <div className="novidades-header-left">
            <div className="novidades-logo-box">
              <img src="/logo-eops.png" alt="E-Ops" className="novidades-logo-img" />
            </div>
            <div>
              <div className="novidades-title">Novidades</div>
              <div className="novidades-subtitle">O que mudou no E-Ops</div>
            </div>
          </div>
          <button className="novidades-close" onClick={onFechar} aria-label="Fechar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <div className="novidades-tabs">
          {CHANGELOG.map((v) => (
            <button
              key={v.versao}
              className={`novidades-tab${v.versao === versaoAtiva ? ' ativa' : ''}`}
              onClick={() => setVersaoAtiva(v.versao)}
            >
              {v.versao}
            </button>
          ))}
        </div>

        <div className="novidades-conteudo">
          {versaoAtual?.categorias?.map((cat) => (
            <div key={cat.nome} className="novidades-categoria">
              <div className="novidades-categoria-titulo">
                <span className="novidades-categoria-ponto" style={{ background: cat.cor }} />
                {cat.nome}
              </div>
              <ul className="novidades-lista">
                {cat.itens.map((item, i) => (
                  <li key={i}>
                    <svg
                      width="14" height="14" viewBox="0 0 24 24" fill="none"
                      stroke={cat.cor} strokeWidth="2.6"
                      strokeLinecap="round" strokeLinejoin="round"
                    >
                      <path d="M5 13l4 4L19 7" />
                    </svg>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="novidades-footer">
          <span>{totalItens} {totalItens === 1 ? 'item' : 'itens'} nesta versão</span>
          <span>E-Ops</span>
        </div>

      </div>
    </div>
  );
}
