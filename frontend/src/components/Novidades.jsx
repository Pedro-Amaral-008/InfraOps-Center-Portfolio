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
          padding: '32px',
          maxWidth: '680px',
          width: '90%',
          maxHeight: '75vh',
          overflowY: 'auto',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ margin: 0, fontSize: '22px' }}>Novidades</h2>
          <button
            onClick={onFechar}
            style={{ background: 'none', border: 'none', fontSize: '26px', cursor: 'pointer', color: 'inherit' }}
          >
            ×
          </button>
        </div>
        {CHANGELOG.map((entrada) => (
          <div key={entrada.versao} style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '16px', marginBottom: '10px' }}>{entrada.versao}</h3>
            <ul style={{ margin: 0, paddingLeft: '22px', fontSize: '14.5px', lineHeight: '1.7' }}>
              {entrada.itens.map((item, idx) => (
                <li key={idx} style={{ marginBottom: '4px' }}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
export default Novidades;
