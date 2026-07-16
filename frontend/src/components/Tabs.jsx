import './Tabs.css';

function Tabs({ abas, abaAtiva, onChange }) {
  return (
    <div className="tabs-container">
      {abas.map((aba) => (
        <button
          key={aba.id}
          className={`tab-item ${abaAtiva === aba.id ? 'active' : ''}`}
          onClick={() => onChange(aba.id)}
        >
          {aba.label}
        </button>
      ))}
    </div>
  );
}

export default Tabs;
