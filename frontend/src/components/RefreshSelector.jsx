import './RefreshSelector.css';

const OPCOES = [
  { label: '5s', valor: 5000 },
  { label: '30s', valor: 30000 },
  { label: '1min', valor: 60000 },
  { label: '30min', valor: 1800000 },
  { label: '1h', valor: 3600000 },
];

function RefreshSelector({ intervaloAtual, onChange }) {
  return (
    <div className="refresh-selector">
      <span className="refresh-selector-label">Atualizar a cada:</span>
      <div className="refresh-selector-options">
        {OPCOES.map((opcao) => (
          <button
            key={opcao.valor}
            className={`refresh-option ${intervaloAtual === opcao.valor ? 'active' : ''}`}
            onClick={() => onChange(opcao.valor)}
          >
            {opcao.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default RefreshSelector;
