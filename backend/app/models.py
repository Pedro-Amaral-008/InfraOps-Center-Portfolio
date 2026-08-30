from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, JSON, Numeric
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    nome_completo = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="operador")
    deve_trocar_senha = Column(Boolean, default=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())


class SolicitacaoAcesso(Base):
    __tablename__ = "solicitacoes_acesso"

    id = Column(Integer, primary_key=True, index=True)
    nome_completo = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pendente")
    solicitado_em = Column(DateTime(timezone=True), server_default=func.now())
    revisado_em = Column(DateTime(timezone=True), nullable=True)
    revisado_por = Column(String, nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    usado = Column(Boolean, default=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())


class BackupExecution(Base):
    __tablename__ = "backup_executions"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, nullable=False)
    instance = Column(String, nullable=False, index=True)
    backup_type = Column(String, nullable=True)
    status = Column(String, nullable=False)
    tamanho_transferido_bytes = Column(BigInteger, default=0)
    tamanho_processado_bytes = Column(BigInteger, default=0)
    tamanho_lido_bytes = Column(BigInteger, default=0)
    executado_em = Column(DateTime(timezone=True), nullable=False)
    registrado_em = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    acao = Column(String, nullable=False)
    detalhes = Column(String, nullable=True)
    resultado = Column(String, nullable=False)
    ip_origem = Column(String, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AgentMetric(Base):
    __tablename__ = "agent_metrics"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, nullable=False, index=True)
    instance = Column(String, nullable=False, index=True)
    cpu_percent = Column(Integer, nullable=True)
    ram_percent = Column(Integer, nullable=True)
    ram_total_gb = Column(Integer, nullable=True)
    disco_percent = Column(Integer, nullable=True)
    disco_total_gb = Column(Integer, nullable=True)
    uptime_horas = Column(Integer, nullable=True)
    discos_json = Column(JSON, nullable=True)
    latencia_ms = Column(Integer, nullable=True)
    coletado_em = Column(DateTime(timezone=True), nullable=False, index=True)
    registrado_em = Column(DateTime(timezone=True), server_default=func.now())


class AgentAlertState(Base):
    __tablename__ = "agent_alert_state"

    id = Column(Integer, primary_key=True, index=True)
    instance = Column(String, nullable=False, index=True)
    recurso = Column(String, nullable=False)
    notificacao_enviada = Column(Boolean, default=False)
    em_alerta = Column(Boolean, default=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PfsenseLinkStatus(Base):
    __tablename__ = "pfsense_link_status"

    id = Column(Integer, primary_key=True, index=True)
    nome_link = Column(String, nullable=False, index=True)
    online = Column(Boolean, nullable=False)
    verificado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class PfsenseTrafego(Base):
    __tablename__ = "pfsense_trafego"

    id = Column(Integer, primary_key=True, index=True)
    nome_link = Column(String, nullable=False, index=True)
    download_mbps = Column(Numeric(10, 3), nullable=True)
    upload_mbps = Column(Numeric(10, 3), nullable=True)
    registrado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)
    alvo = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pendente")
    solicitado_por = Column(String, nullable=False)
    resultado = Column(String, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    concluido_em = Column(DateTime(timezone=True), nullable=True)


class ConfiguracaoSistema(Base):
    __tablename__ = "configuracao_sistema"

    id = Column(Integer, primary_key=True, index=True)
    chave = Column(String, nullable=False, unique=True, index=True)
    valor = Column(String, nullable=False)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PfsenseVpnVlanStatus(Base):
    __tablename__ = "pfsense_vpn_vlan_status"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)
    nome = Column(String, nullable=False, index=True)
    online = Column(Boolean, nullable=False)
    verificado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class EventoSistema(Base):
    __tablename__ = "eventos_sistema"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)
    mensagem = Column(String, nullable=False)
    detalhes = Column(String, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)
