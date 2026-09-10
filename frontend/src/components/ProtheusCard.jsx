import StatusServidor from './StatusServidor';
import './ProtheusCard.css';

function ProtheusCard({ status, historico, eventos }) {
  if (!status) {
    return (
      <div className="protheus-card">
        <div className="protheus-header">
          <span className="protheus-name">Protheus (ERP)</span>
        </div>
        <div className="protheus-loading">Carregando...</div>
      </div>
    );
  }

  return (
    <div className="protheus-card">
      <div className="protheus-header">
        <div className="protheus-title-group">
          <span className="protheus-name">Protheus (ERP)</span>
          <span className="protheus-hostname">protheus.elcop.eng.br</span>
        </div>
        <span className="protheus-badge">Monitorado via ICMP — sem agente</span>
      </div>

      <StatusServidor status={status} historico={historico} eventos={eventos} />
    </div>
  );
}

export default ProtheusCard;
