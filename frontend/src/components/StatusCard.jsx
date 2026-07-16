import './StatusCard.css';

function StatusCard({ title, value, status, subtitle }) {
  return (
    <div className={`status-card status-${status}`}>
      <div className="status-card-header">
        <span className="status-dot"></span>
        <span className="status-card-title">{title}</span>
      </div>
      <div className="status-card-value">{value}</div>
      {subtitle && <div className="status-card-subtitle">{subtitle}</div>}
    </div>
  );
}

export default StatusCard;
