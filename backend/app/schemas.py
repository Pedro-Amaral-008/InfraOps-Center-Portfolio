from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    nome_completo: str
    role: str
    deve_trocar_senha: bool


class TrocarSenhaRequest(BaseModel):
    senha_atual: str
    nova_senha: str
class SolicitacaoAcessoCreate(BaseModel):
    nome_completo: str
    email: str
    username: str
    password: str
class SolicitacaoAcessoResponse(BaseModel):
    id: int
    nome_completo: str
    email: str
    username: str
    status: str
    solicitado_em: str
class SolicitacaoAcessoAprovar(BaseModel):
    role: str
class EsqueciSenhaRequest(BaseModel):
    email: str
class RedefinirSenhaRequest(BaseModel):
    token: str
    nova_senha: str


class BackupExecutionCreate(BaseModel):
    job_name: str
    instance: str
    backup_type: str | None = None
    status: str
    tamanho_transferido_bytes: int = 0
    tamanho_processado_bytes: int = 0
    tamanho_lido_bytes: int = 0
    executado_em: str


class DiscoInfo(BaseModel):
    drive: str
    total_gb: int
    percent: int


class AgentMetricCreate(BaseModel):
    hostname: str
    instance: str
    cpu_percent: int | None = None
    ram_percent: int | None = None
    ram_total_gb: int | None = None
    disco_percent: int | None = None
    disco_total_gb: int | None = None
    uptime_horas: int | None = None
    coletado_em: str
    discos: list[DiscoInfo] | None = None
    latencia_ms: int | None = None


class UsuarioCreate(BaseModel):
    username: str
    nome_completo: str
    role: str


class UsuarioResponse(BaseModel):
    id: int
    username: str
    nome_completo: str
    role: str
    ativo: bool
    deve_trocar_senha: bool

    class Config:
        from_attributes = True


class UsuarioRoleUpdate(BaseModel):
    role: str


class SenhaResetResponse(BaseModel):
    username: str
    senha_temporaria: str
