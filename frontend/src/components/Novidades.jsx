import CHANGELOG from '../changelog';

function Novidades({ onFechar }) {
  return (
    <div
      onClick={onFechar}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-secondary, #1c1c1c)',
          borderRadius: '16px',
          padding: '24px',
          maxWidth: '480px',
          width: '90%',
          maxHeight: '70vh',
          overflowY: 'auto',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ margin: 0, fontSize: '18px' }}>Novidades</h2>
          <button
            onClick={onFechar}
            style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: 'inherit' }}
          >
            ×
          </button>
        </div>
        {CHANGELOG.map((entrada) => (
          <div key={entrada.versao} style={{ marginBottom: '20px' }}>
            <h3 style={{ fontSize: '14px', marginBottom: '8px' }}>{entrada.versao}</h3>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', lineHeight: '1.6' }}>
              {entrada.itens.map((item, idx) => (
                <li key={idx}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Novidades;
