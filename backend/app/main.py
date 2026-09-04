import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request
from app.config import settings
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, desc, func, case
from datetime import datetime, timedelta, timezone
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.database import get_db
from app.dashboard import get_dashboard_summary
from app.metrics import get_metricas_host
from app.models import User, BackupExecution, AuditLog, SolicitacaoAcesso, PasswordResetToken
from app.schemas import LoginRequest, LoginResponse, TrocarSenhaRequest, BackupExecutionCreate, UsuarioCreate, UsuarioResponse, UsuarioRoleUpdate, SenhaResetResponse, SolicitacaoAcessoCreate, SolicitacaoAcessoResponse, SolicitacaoAcessoAprovar, EsqueciSenhaRequest, RedefinirSenhaRequest
from app.auth import verificar_senha, criar_token, hash_senha
from app.deps import get_current_user, exigir_papel
from app.audit import registrar_log

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="InfraOps Center API",
    description="API central de observabilidade, automação e inventário de infraestrutura",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "InfraOps Center API", "status": "online"}


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {
        "api": "healthy",
        "database": db_status,
    }


@app.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, dados: LoginRequest, db: AsyncSession = Depends(get_db)):
    ip_cliente = request.client.host if request.client else None

    result = await db.execute(
        select(User).where(
            (User.username == dados.username) | (User.email == dados.username)
        )
    )
    usuario = result.scalar_one_or_none()

    if usuario is None or not usuario.ativo or not verificar_senha(dados.password, usuario.password_hash):
        await registrar_log(
            db, dados.username, "login", "falha",
            detalhes="Usuario ou senha invalidos", ip_origem=ip_cliente,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario ou senha invalidos",
        )

    token = criar_token({"sub": usuario.username, "role": usuario.role})

    await registrar_log(db, usuario.username, "login", "sucesso", ip_origem=ip_cliente)

    return LoginResponse(
        access_token=token,
        username=usuario.username,
        nome_completo=usuario.nome_completo,
        role=usuario.role,
        deve_trocar_senha=usuario.deve_trocar_senha,
    )


DOMINIO_EMAIL_PERMITIDO = "@elcop.eng.br"


@app.post("/auth/solicitar-acesso")
@limiter.limit("3/hour")
async def solicitar_acesso(request: Request, dados: SolicitacaoAcessoCreate, db: AsyncSession = Depends(get_db)):
    from app.email_service import enviar_email_confirmacao_solicitacao

    if not dados.email.lower().endswith(DOMINIO_EMAIL_PERMITIDO):
        raise HTTPException(status_code=400, detail=f"Use um e-mail corporativo ({DOMINIO_EMAIL_PERMITIDO})")

    result = await db.execute(select(User).where((User.username == dados.username) | (User.email == dados.email)))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Usuario ou e-mail ja cadastrado")

    result = await db.execute(
        select(SolicitacaoAcesso).where(
            ((SolicitacaoAcesso.username == dados.username) | (SolicitacaoAcesso.email == dados.email))
            & (SolicitacaoAcesso.status == "pendente")
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ja existe uma solicitacao pendente para esse usuario ou e-mail")

    solicitacao = SolicitacaoAcesso(
        nome_completo=dados.nome_completo,
        email=dados.email,
        username=dados.username,
        password_hash=hash_senha(dados.password),
    )
    db.add(solicitacao)
    await db.commit()
    enviar_email_confirmacao_solicitacao(dados.email, dados.nome_completo)
    return {"status": "solicitacao enviada, aguardando aprovacao"}


@app.get("/auth/solicitacoes", response_model=list[SolicitacaoAcessoResponse])
async def listar_solicitacoes(
    usuario: User = Depends(exigir_papel("admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SolicitacaoAcesso).where(SolicitacaoAcesso.status == "pendente").order_by(SolicitacaoAcesso.solicitado_em)
    )
    solicitacoes = result.scalars().all()
    return [
        SolicitacaoAcessoResponse(
            id=s.id, nome_completo=s.nome_completo, email=s.email,
            username=s.username, status=s.status,
            solicitado_em=s.solicitado_em.isoformat(),
        )
        for s in solicitacoes
    ]


@app.post("/auth/solicitacoes/{solicitacao_id}/aprovar")
async def aprovar_solicitacao(
    solicitacao_id: int,
    dados: SolicitacaoAcessoAprovar,
    usuario: User = Depends(exigir_papel("admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.email_service import enviar_email_acesso_aprovado

    if dados.role not in ("operador", "admin"):
        raise HTTPException(status_code=400, detail="Role invalido, use operador ou admin")

    result = await db.execute(select(SolicitacaoAcesso).where(SolicitacaoAcesso.id == solicitacao_id))
    solicitacao = result.scalar_one_or_none()
    if not solicitacao or solicitacao.status != "pendente":
        raise HTTPException(status_code=404, detail="Solicitacao nao encontrada ou ja processada")

    novo_usuario = User(
        username=solicitacao.username,
        email=solicitacao.email,
        nome_completo=solicitacao.nome_completo,
        password_hash=solicitacao.password_hash,
        role=dados.role,
        deve_trocar_senha=False,
    )
    db.add(novo_usuario)
    solicitacao.status = "aprovada"
    solicitacao.revisado_em = datetime.now(timezone.utc)
    solicitacao.revisado_por = usuario.username
    await db.commit()
    enviar_email_acesso_aprovado(solicitacao.email, solicitacao.nome_completo, solicitacao.username)
    return {"status": "aprovado"}


@app.post("/auth/solicitacoes/{solicitacao_id}/rejeitar")
async def rejeitar_solicitacao(
    solicitacao_id: int,
    usuario: User = Depends(exigir_papel("admin", "super_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SolicitacaoAcesso).where(SolicitacaoAcesso.id == solicitacao_id))
    solicitacao = result.scalar_one_or_none()
    if not solicitacao or solicitacao.status != "pendente":
        raise HTTPException(status_code=404, detail="Solicitacao nao encontrada ou ja processada")
    solicitacao.status = "rejeitada"
    solicitacao.revisado_em = datetime.now(timezone.utc)
    solicitacao.revisado_por = usuario.username
    await db.commit()
    return {"status": "rejeitado"}


@app.post("/auth/esqueci-senha")
@limiter.limit("3/hour")
async def esqueci_senha(request: Request, dados: EsqueciSenhaRequest, db: AsyncSession = Depends(get_db)):
    from app.email_service import enviar_email_recuperacao_senha

    result = await db.execute(select(User).where(User.email == dados.email))
    usuario = result.scalar_one_or_none()

    if usuario and usuario.ativo:
        token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            username=usuario.username,
            token=token,
            expira_em=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset)
        await db.commit()
        enviar_email_recuperacao_senha(usuario.email, usuario.nome_completo, token)

    return {"status": "se o e-mail existir, um link de redefinicao foi enviado"}


@app.post("/auth/redefinir-senha")
async def redefinir_senha(dados: RedefinirSenhaRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == dados.token))
    reset = result.scalar_one_or_none()

    if not reset or reset.usado or reset.expira_em < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token invalido ou expirado")

    result = await db.execute(select(User).where(User.username == reset.username))
    usuario = result.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    usuario.password_hash = hash_senha(dados.nova_senha)
    usuario.deve_trocar_senha = False
    reset.usado = True
    await db.commit()
    return {"status": "senha redefinida com sucesso"}


@app.post("/auth/trocar-senha")
async def trocar_senha(
    dados: TrocarSenhaRequest,
    request: Request,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip_cliente = request.client.host if request.client else None

    if not verificar_senha(dados.senha_atual, usuario.password_hash):
        await registrar_log(
            db, usuario.username, "trocar_senha", "falha",
            detalhes="Senha atual incorreta", ip_origem=ip_cliente,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha atual incorreta",
        )

    if len(dados.nova_senha) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ter no minimo 8 caracteres",
        )

    usuario.password_hash = hash_senha(dados.nova_senha)
    usuario.deve_trocar_senha = False
    await db.commit()

    await registrar_log(db, usuario.username, "trocar_senha", "sucesso", ip_origem=ip_cliente)

    return {"status": "senha alterada com sucesso"}


@app.get("/auth/me")
async def me(usuario: User = Depends(get_current_user)):
    return {
        "username": usuario.username,
        "nome_completo": usuario.nome_completo,
        "role": usuario.role,
    }


@app.get("/dashboard/summary")
async def dashboard_summary(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_dashboard_summary(db)
@app.post("/webhooks/alertmanager")
async def webhook_alertmanager(request: Request, db: AsyncSession = Depends(get_db)):
    from app.models import EventoSistema

    NOMES_ALERTA = {
        "AccessPointOffline": ("Access Point", "offline"),
        "ServidorOffline": ("Servidor", "offline"),
        "ServidorArquivosOffline": ("Servidor", "offline"),
        "ImpressoraOffline": ("Impressora", "offline"),
        "PainelWebOffline": ("Painel Web", "offline"),
        "InstanciaOffline": ("Equipamento", "offline"),
        "DiscoAcimaDe90": ("Servidor", "disco_alto"),
        "MemoriaAlta": ("Servidor", "memoria_alta"),
        "VeeamBackupFalhou": ("Backup", "falhou"),
        "VeeamBackupAtrasado": ("Backup", "atrasado"),
    }

    try:
        payload = await request.json()
        for alerta in payload.get("alerts", []):
            labels = alerta.get("labels", {})
            status_alerta = alerta.get("status", "")
            alertname = labels.get("alertname", "")
            categoria, situacao = NOMES_ALERTA.get(alertname, ("Equipamento", "offline"))
            nome_equip = labels.get("nome") or labels.get("instance", "")

            textos_firing = {
                "offline": f"{categoria} {nome_equip} ficou offline",
                "disco_alto": f"{categoria} {nome_equip} com disco acima de 90%",
                "memoria_alta": f"{categoria} {nome_equip} com uso de memória elevado",
                "falhou": f"Backup de {nome_equip} falhou",
                "atrasado": f"Backup de {nome_equip} está atrasado",
            }
            textos_resolvido = {
                "offline": f"{categoria} {nome_equip} voltou online",
                "disco_alto": f"{categoria} {nome_equip} com uso de disco normalizado",
                "memoria_alta": f"{categoria} {nome_equip} com uso de memória normalizado",
                "falhou": f"Backup de {nome_equip} normalizado",
                "atrasado": f"Backup de {nome_equip} normalizado",
            }

            if status_alerta == "firing":
                tipo = "critico" if situacao in ("offline", "falhou") else "atencao"
                texto = textos_firing.get(situacao, f"{categoria} {nome_equip} em alerta")
            else:
                tipo = "bom"
                texto = textos_resolvido.get(situacao, f"{categoria} {nome_equip} normalizado")

            db.add(EventoSistema(
                tipo=tipo,
                mensagem=texto[:300],
                detalhes=labels.get("instance", "")[:300],
            ))
        await db.commit()
    except Exception:
        pass

    return {"status": "ok"}
@app.get("/dashboard/eventos/recentes")
async def dashboard_eventos_recentes(
    limite: int = 8,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import EventoSistema
    result = await db.execute(
        select(EventoSistema).order_by(desc(EventoSistema.criado_em)).limit(limite)
    )
    eventos = result.scalars().all()
    return [
        {
            "id": e.id,
            "tipo": e.tipo,
            "mensagem": e.mensagem,
            "detalhes": e.detalhes,
            "criado_em": e.criado_em.isoformat(),
        }
        for e in eventos
    ]
@app.get("/dashboard/eventos/contagem-24h")
async def dashboard_eventos_contagem_24h(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import EventoSistema
    from datetime import timezone
    limite = datetime.now(timezone.utc) - timedelta(hours=24)
    result = await db.execute(
        select(func.count()).select_from(EventoSistema).where(EventoSistema.criado_em >= limite)
    )
    total = result.scalar_one()
    return {"total_24h": total}
@app.get("/dashboard/tendencia-24h")
async def dashboard_tendencia_24h(
    usuario: User = Depends(get_current_user),
):
    from app.dashboard import get_tendencia_saude_24h
    return await get_tendencia_saude_24h()
@app.get("/dashboard/estabilidade-semanal")
async def dashboard_estabilidade_semanal(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_estabilidade_semanal
    return await get_estabilidade_semanal(db)
@app.get("/dashboard/estabilidade-com-variacao")
async def dashboard_estabilidade_com_variacao(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_estabilidade_com_variacao
    return await get_estabilidade_com_variacao(db)
@app.get("/dashboard/estabilidade-14-dias")
async def dashboard_estabilidade_14_dias(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_estabilidade_14_dias
    return await get_estabilidade_14_dias(db)
@app.get("/dashboard/relatorio")
async def dashboard_relatorio(
    dias: int = 15,
    categorias: str = "",
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_dados_relatorio
    lista_categorias = [c.strip() for c in categorias.split(",") if c.strip()] if categorias else None
    return await get_dados_relatorio(db, dias, lista_categorias)
@app.get("/dashboard/relatorio/pdf")
async def dashboard_relatorio_pdf(
    dias: int = 15,
    categorias: str = "",
    periodo_label: str = "",
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_dados_relatorio, gerar_html_relatorio_pdf
    from weasyprint import HTML
    import io

    lista_categorias = [c.strip() for c in categorias.split(",") if c.strip()] if categorias else None
    dados = await get_dados_relatorio(db, dias, lista_categorias)
    html_str = gerar_html_relatorio_pdf(dados, periodo_label or f"Últimos {dias} dias")

    pdf_bytes = HTML(string=html_str).write_pdf()
    buffer = io.BytesIO(pdf_bytes)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=relatorio-eops.pdf"},
    )
@app.post("/dashboard/alertas-ativos-duracao")
async def dashboard_alertas_ativos_duracao(
    request: Request,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_alertas_ativos_com_duracao
    payload = await request.json()
    nomes = payload.get("nomes", [])
    return await get_alertas_ativos_com_duracao(db, nomes)
@app.get("/dashboard/pior-desempenho-semana")
async def dashboard_pior_desempenho_semana(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_estabilidade_semanal, get_pior_desempenho_semana
    estabilidade = await get_estabilidade_semanal(db)
    return await get_pior_desempenho_semana(db, estabilidade)
@app.get("/dashboard/ocorrencias-semana/{nome_equipamento}")
async def dashboard_ocorrencias_semana(
    nome_equipamento: str,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import contar_ocorrencias_semana
    total = await contar_ocorrencias_semana(db, nome_equipamento)
    return {"total": total}


@app.get("/dashboard/metrics/host")
async def dashboard_metrics_host(
    minutos: int = 60,
    usuario: User = Depends(get_current_user),
):
    return await get_metricas_host(minutos)


@app.get("/dashboard/metrics/latencia/{categoria}")
async def dashboard_metrics_latencia(
    categoria: str,
    minutos: int = 60,
    usuario: User = Depends(get_current_user),
):
    from app.metrics import get_latencia_por_categoria

    jobs_permitidos = {
        "servidores": "blackbox-servidores-tcp|blackbox-servidor-backup-principal",
        "access_points": "blackbox-access-points",
        "impressoras": "blackbox-impressoras",
    }

    job = jobs_permitidos.get(categoria)
    if not job:
        raise HTTPException(status_code=404, detail="Categoria invalida")

    return await get_latencia_por_categoria(job, minutos)


@app.get("/dashboard/servidores/uptime")
async def dashboard_servidores_uptime(
    dias: int = 30,
    usuario: User = Depends(get_current_user),
):
    from app.dashboard import get_uptime_por_job
    return await get_uptime_por_job("blackbox-servidores-tcp|blackbox-servidor-backup-principal", dias)
@app.get("/dashboard/access-points/uptime")
async def dashboard_access_points_uptime(
    dias: int = 30,
    usuario: User = Depends(get_current_user),
):
    from app.dashboard import get_uptime_por_job
    return await get_uptime_por_job("blackbox-access-points", dias)
@app.get("/dashboard/backups")
async def dashboard_backups(usuario: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.dashboard import get_backups_detalhado
    return await get_backups_detalhado(db)
@app.get("/dashboard/backups/uptime")
async def dashboard_backups_uptime(
    dias: int = 30,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_backups_uptime
    return await get_backups_uptime(db, dias)


@app.post("/backups/registrar")
async def registrar_backup(
    dados: BackupExecutionCreate,
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if x_api_key != settings.backup_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key invalida")

    execucao = BackupExecution(
        job_name=dados.job_name,
        instance=dados.instance,
        backup_type=dados.backup_type,
        status=dados.status,
        tamanho_transferido_bytes=dados.tamanho_transferido_bytes,
        tamanho_processado_bytes=dados.tamanho_processado_bytes,
        tamanho_lido_bytes=dados.tamanho_lido_bytes,
        executado_em=datetime.fromisoformat(dados.executado_em),
    )
    db.add(execucao)
    await db.commit()

    from app.agent_alerts import obter_estado, definir_estado, enviar_telegram
    falhou = dados.status not in ("Success", "Warning", "sucesso")
    registro_alerta = await obter_estado(db, dados.instance, "Backup")
    estava_falhando = registro_alerta.em_alerta if registro_alerta else False

    if falhou and not estava_falhando:
        msg = (
            f"🔔 <b>Monitoramento InfraOps Center</b>\n\n"
            f"<b>FALHA NO BACKUP</b> ❌:\n\n"
            f"📦 <b>Job:</b> {dados.job_name}\n"
            f"🌐 <b>Instância:</b> {dados.instance}\n"
            f"🕐 <b>Horário:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"⚠️ <b>Ação:</b> Verificar log do backup imediatamente"
        )
        await enviar_telegram(msg, parse_mode="HTML")
        await definir_estado(db, dados.instance, "Backup", True, notificacao_enviada=True)
    elif not falhou and estava_falhando:
        notificacao_foi_enviada = registro_alerta.notificacao_enviada if registro_alerta else False
        if notificacao_foi_enviada:
            msg = (
                f"🟢 <b>Monitoramento InfraOps Center</b>\n\n"
                f"<b>Backup Realizado Com Sucesso</b> ✅:\n\n"
                f"📦 <b>Job Executado:</b> {dados.job_name}\n"
                f"🌐 <b>Instância:</b> {dados.instance}\n"
                f"🕐 <b>Horário:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            await enviar_telegram(msg, parse_mode="HTML")
        await definir_estado(db, dados.instance, "Backup", False, notificacao_enviada=False)

    return {"status": "registrado com sucesso"}


@app.get("/dashboard/backups/history")
async def dashboard_backups_history(
    dias: int = 30,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    limite = datetime.utcnow() - timedelta(days=dias)

    result = await db.execute(
        select(BackupExecution)
        .where(BackupExecution.executado_em >= limite)
        .order_by(desc(BackupExecution.executado_em))
    )
    execucoes = result.scalars().all()

    return [
        {
            "id": e.id,
            "job_name": e.job_name,
            "instance": e.instance,
            "backup_type": e.backup_type,
            "status": e.status,
            "tamanho_transferido_gb": round(e.tamanho_transferido_bytes / (1024**3), 2),
            "executado_em": e.executado_em.isoformat(),
        }
        for e in execucoes
    ]


@app.get("/audit/logs")
async def audit_logs(
    dias: int = 30,
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    limite = datetime.utcnow() - timedelta(days=dias)

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.criado_em >= limite)
        .order_by(desc(AuditLog.criado_em))
        .limit(500)
    )
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "username": log.username,
            "acao": log.acao,
            "detalhes": log.detalhes,
            "resultado": log.resultado,
            "ip_origem": log.ip_origem,
            "criado_em": log.criado_em.isoformat(),
        }
        for log in logs
    ]


from app.models import AgentMetric
from app.schemas import AgentMetricCreate


@app.post("/agents/metrics")
async def registrar_metrica_agente(
    dados: AgentMetricCreate,
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if x_api_key != settings.backup_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key invalida")

    discos_lista = [d.dict() for d in dados.discos] if dados.discos else None

    metrica = AgentMetric(
        hostname=dados.hostname,
        instance=dados.instance,
        cpu_percent=dados.cpu_percent,
        ram_percent=dados.ram_percent,
        ram_total_gb=dados.ram_total_gb,
        disco_percent=dados.disco_percent,
        disco_total_gb=dados.disco_total_gb,
        uptime_horas=dados.uptime_horas,
        discos_json=discos_lista,
        latencia_ms=dados.latencia_ms,
        coletado_em=datetime.fromisoformat(dados.coletado_em),
    )
    db.add(metrica)
    await db.commit()

    return {"status": "metrica registrada com sucesso"}


@app.get("/dashboard/agents")
async def dashboard_agents_latest(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subquery = (
        select(
            AgentMetric.instance,
            func.max(AgentMetric.coletado_em).label("max_coletado")
        )
        .group_by(AgentMetric.instance)
        .subquery()
    )

    result = await db.execute(
        select(AgentMetric)
        .join(
            subquery,
            (AgentMetric.instance == subquery.c.instance) &
            (AgentMetric.coletado_em == subquery.c.max_coletado)
        )
    )
    metricas = result.scalars().all()
    INSTANCIAS_REMOVIDAS = ["srv-bkp2"]

    return [
        {
            "hostname": m.hostname,
            "instance": m.instance,
            "cpu_percent": m.cpu_percent,
            "ram_percent": m.ram_percent,
            "ram_total_gb": m.ram_total_gb,
            "disco_percent": m.disco_percent,
            "disco_total_gb": m.disco_total_gb,
            "uptime_horas": m.uptime_horas,
            "discos": m.discos_json,
            "latencia_ms": m.latencia_ms,
            "coletado_em": m.coletado_em.isoformat(),
        }
        for m in metricas
        if m.instance not in INSTANCIAS_REMOVIDAS
    ]


@app.get("/dashboard/agents/{instance}/history")
async def dashboard_agent_history(
    instance: str,
    minutos: int = 60,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timezone
    limite = datetime.now(timezone.utc) - timedelta(minutes=minutos)

    result = await db.execute(
        select(AgentMetric)
        .where(AgentMetric.instance == instance, AgentMetric.coletado_em >= limite)
        .order_by(AgentMetric.coletado_em)
    )
    metricas = result.scalars().all()

    return {
        "cpu": [{"timestamp": int(m.coletado_em.timestamp() * 1000), "valor": m.cpu_percent} for m in metricas],
        "ram": [{"timestamp": int(m.coletado_em.timestamp() * 1000), "valor": m.ram_percent} for m in metricas],
        "disco": [{"timestamp": int(m.coletado_em.timestamp() * 1000), "valor": m.disco_percent} for m in metricas],
    }


import asyncio
from app.agent_alerts import verificar_limites_agentes, verificar_disponibilidade_agentes, verificar_failover_srv_arquivos
from app.controller_alerts import verificar_limites_controller
from app.pfsense import registrar_status_links, registrar_trafego, verificar_alertas_links, verificar_alertas_vpns_vlans, registrar_status_vpns_vlans
from app.database import AsyncSessionLocal


async def loop_verificacao_agentes():
    while True:
        async with AsyncSessionLocal() as db:
            try:
                await verificar_limites_agentes(db)
            except Exception as e:
                print(f"ERRO em verificar_limites_agentes: {e}")

            try:
                await verificar_disponibilidade_agentes(db)
            except Exception as e:
                print(f"ERRO em verificar_disponibilidade_agentes: {e}")

            try:
                await verificar_failover_srv_arquivos(db)
            except Exception as e:
                print(f"ERRO em verificar_failover_srv_arquivos: {e}")

            try:
                await verificar_limites_controller(db)
            except Exception as e:
                print(f"ERRO em verificar_limites_controller: {e}")

            try:
                await verificar_alertas_links(db)
            except Exception as e:
                print(f"ERRO em verificar_alertas_links: {e}")
            try:
                await verificar_alertas_vpns_vlans(db)
            except Exception as e:
                print(f"ERRO em verificar_alertas_vpns_vlans: {e}")

            try:
                await registrar_status_links(db)
            except Exception as e:
                print(f"ERRO em registrar_status_links: {e}")
            try:
                await registrar_status_vpns_vlans(db)
            except Exception as e:
                print(f"ERRO em registrar_status_vpns_vlans: {e}")

        await asyncio.sleep(120)

async def loop_consumo_rede():
    from app.unifi import verificar_consumo_excessivo
    while True:
        async with AsyncSessionLocal() as db:
            try:
                await verificar_consumo_excessivo(db)
            except Exception as e:
                print(f"ERRO em verificar_consumo_excessivo: {e}")
        await asyncio.sleep(20)
@app.on_event("startup")
async def iniciar_verificacao_agentes():
    asyncio.create_task(loop_verificacao_agentes())
    asyncio.create_task(loop_trafego_pfsense())
    asyncio.create_task(loop_resumo_diario())
    asyncio.create_task(loop_consumo_rede())


@app.get("/dashboard/controller/current")
async def dashboard_controller_current(
    usuario: User = Depends(get_current_user),
):
    from app.metrics import query_instant_by_instance as query_prometheus

    cpu = await query_prometheus('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)')
    ram = await query_prometheus('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
    disco = await query_prometheus('100 - ((node_filesystem_avail_bytes{mountpoint="/"} * 100) / node_filesystem_size_bytes{mountpoint="/"})')
    ram_total = await query_prometheus('node_memory_MemTotal_bytes')
    temperatura = await query_prometheus('node_thermal_zone_temp{type="cpu-thermal"}')
    disco_total = await query_prometheus('node_filesystem_size_bytes{mountpoint="/"}')
    disco_hd_percent = await query_prometheus('100 - ((node_filesystem_avail_bytes{mountpoint="/mnt/data"} * 100) / node_filesystem_size_bytes{mountpoint="/mnt/data"})')
    disco_hd_total = await query_prometheus('node_filesystem_size_bytes{mountpoint="/mnt/data"}')
    boot_time = await query_prometheus('node_boot_time_seconds')

    def extrair_valor(resultado):
        if resultado and len(resultado) > 0:
            return float(resultado[0].get("value", [None, "0"])[1])
        return 0

    discos_lista = [
        {"drive": "/", "total_gb": round(extrair_valor(disco_total) / (1024**3)), "percent": round(extrair_valor(disco))},
    ]
    if extrair_valor(disco_hd_total) > 0:
        discos_lista.append({
            "drive": "/mnt/data",
            "total_gb": round(extrair_valor(disco_hd_total) / (1024**3)),
            "percent": round(extrair_valor(disco_hd_percent)),
        })
    return {
        "hostname": "E-Ops Controller",
        "instance": "raspberry-pi-controller",
        "cpu_percent": round(extrair_valor(cpu)),
        "ram_percent": round(extrair_valor(ram)),
        "ram_total_gb": round(extrair_valor(ram_total) / (1024**3)),
        "disco_percent": round(extrair_valor(disco)),
        "disco_total_gb": round(extrair_valor(disco_total) / (1024**3)),
        "discos": discos_lista,
        "temperatura_celsius": round(extrair_valor(temperatura), 1),
        "uptime_horas": round((datetime.now(timezone.utc).timestamp() - extrair_valor(boot_time)) / 3600, 1) if extrair_valor(boot_time) > 0 else None,
    }


@app.get("/dashboard/unifi/aps")
async def dashboard_unifi_aps(
    usuario: User = Depends(get_current_user),
):
    from app.unifi import get_aps_com_clientes
    return await get_aps_com_clientes()
@app.get("/dashboard/unifi/top-consumo")
async def dashboard_unifi_top_consumo(
    limite: int = 15,
    usuario: User = Depends(get_current_user),
):
    from app.unifi import get_top_consumo_clientes
    clientes, _ = await get_top_consumo_clientes(limite)
    return clientes
@app.get("/dashboard/unifi/top-consumo-semanal")
async def dashboard_unifi_top_consumo_semanal(
    dias: int = 7,
    minimo: int = 5,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.unifi import get_top_consumo_semanal
    return await get_top_consumo_semanal(db, dias, minimo)
@app.get("/dashboard/unifi/consumo/historico")
async def dashboard_unifi_consumo_historico(
    minutos: float = 60,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.unifi import get_historico_consumo_agregado
    return await get_historico_consumo_agregado(db, minutos)
@app.get("/dashboard/unifi/consumo/picos")
async def dashboard_unifi_consumo_picos(
    minutos: float = 60,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.unifi import get_picos_sustentados
    return await get_picos_sustentados(db, minutos)


@app.get("/dashboard/pfsense/links")
async def dashboard_pfsense_links(
    usuario: User = Depends(get_current_user),
):
    from app.pfsense import get_status_links
    return await get_status_links()
@app.get("/dashboard/pfsense/vpns")
async def dashboard_pfsense_vpns(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.pfsense import get_vpns_status_trafego
    return await get_vpns_status_trafego(db)
@app.get("/dashboard/pfsense/vlans")
async def dashboard_pfsense_vlans(
    usuario: User = Depends(get_current_user),
):
    from app.pfsense import get_vlans_status_trafego
    return await get_vlans_status_trafego()
@app.get("/dashboard/pfsense/vpns/uptime")
async def dashboard_pfsense_vpns_uptime(
    dias: int = 30,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_vpn_vlan_uptime
    return await get_vpn_vlan_uptime(db, "vpn", dias)
@app.get("/dashboard/pfsense/vlans/uptime")
async def dashboard_pfsense_vlans_uptime(
    dias: int = 30,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.dashboard import get_vpn_vlan_uptime
    return await get_vpn_vlan_uptime(db, "vlan", dias)


@app.get("/dashboard/pfsense/links/uptime")
async def dashboard_pfsense_uptime(
    dias: int = 30,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import PfsenseLinkStatus

    limite = datetime.utcnow() - timedelta(days=dias)

    result = await db.execute(
        select(PfsenseLinkStatus).where(PfsenseLinkStatus.verificado_em >= limite)
    )
    registros = result.scalars().all()

    por_link = {}
    for r in registros:
        if r.nome_link not in por_link:
            por_link[r.nome_link] = {"total": 0, "online": 0}
        por_link[r.nome_link]["total"] += 1
        if r.online:
            por_link[r.nome_link]["online"] += 1

    resultado = []
    for nome, dados in por_link.items():
        uptime_pct = round((dados["online"] / dados["total"]) * 100, 2) if dados["total"] > 0 else 0
        resultado.append({
            "nome": nome,
            "uptime_percent": uptime_pct,
            "total_checagens": dados["total"],
        })

    return resultado


@app.get("/dashboard/pfsense/trafego/history")
async def dashboard_pfsense_trafego_history(
    minutos: int = 60,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import PfsenseTrafego

    from datetime import timezone
    limite = datetime.now(timezone.utc) - timedelta(minutes=minutos)

    result = await db.execute(
        select(PfsenseTrafego)
        .where(PfsenseTrafego.registrado_em >= limite)
        .order_by(PfsenseTrafego.registrado_em)
    )
    registros = result.scalars().all()

    por_link = {}
    for r in registros:
        if r.nome_link not in por_link:
            por_link[r.nome_link] = {"download": [], "upload": []}

        ts = int(r.registrado_em.timestamp() * 1000)
        por_link[r.nome_link]["download"].append({"timestamp": ts, "valor": r.download_mbps})
        por_link[r.nome_link]["upload"].append({"timestamp": ts, "valor": r.upload_mbps})

    return por_link


async def loop_trafego_pfsense():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await registrar_trafego(db)
        except Exception as e:
            print(f"ERRO NO LOOP DE TRAFEGO: {e}", flush=True)
        await asyncio.sleep(30)





from app.resumo_diario import gerar_resumo_diario

_ultimo_resumo_diario = None


async def loop_resumo_diario():
    global _ultimo_resumo_diario
    while True:
        try:
            agora = datetime.now()
            hoje = agora.date()

            if agora.hour == 5 and _ultimo_resumo_diario != hoje:
                async with AsyncSessionLocal() as db:
                    await gerar_resumo_diario(db)
                _ultimo_resumo_diario = hoje
        except Exception:
            pass
        await asyncio.sleep(300)


from app.models import AutomationJob


@app.post("/automations/restart-fluig")
async def solicitar_restart_fluig(
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutomationJob).where(
            AutomationJob.alvo == "srvfrotas",
            AutomationJob.status.in_(["pendente", "executando"])
        )
    )
    job_existente = result.scalar_one_or_none()

    if job_existente:
        raise HTTPException(status_code=400, detail="Ja existe um restart em andamento ou pendente para o Fluig")

    job = AutomationJob(
        tipo="restart_fluig",
        alvo="srvfrotas",
        status="pendente",
        solicitado_por=usuario.username,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await registrar_log(
        db, usuario.username, "restart_fluig", "solicitado",
        detalhes=f"Job ID {job.id}",
    )

    return {"status": "solicitado", "job_id": job.id}


@app.get("/automations/jobs/pendente")
async def consultar_job_pendente(
    alvo: str,
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if x_api_key != settings.backup_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key invalida")

    result = await db.execute(
        select(AutomationJob)
        .where(AutomationJob.alvo == alvo, AutomationJob.status == "pendente")
        .order_by(AutomationJob.criado_em)
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if not job:
        return {"tem_job": False}

    job.status = "executando"
    await db.commit()

    return {"tem_job": True, "job_id": job.id, "tipo": job.tipo}


@app.post("/automations/jobs/{job_id}/concluir")
async def concluir_job(
    job_id: int,
    resultado: str,
    detalhe: str = None,
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    if x_api_key != settings.backup_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key invalida")

    result = await db.execute(select(AutomationJob).where(AutomationJob.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")

    job.status = "concluido" if resultado == "sucesso" else "erro"
    job.resultado = resultado
    job.concluido_em = datetime.now(timezone.utc)
    await db.commit()

    await registrar_log(
        db, job.solicitado_por, job.tipo, resultado,
        detalhes=detalhe if detalhe else f"Job ID {job.id} - execucao concluida",
    )

    return {"status": "atualizado"}


@app.get("/automations/jobs/historico")
async def historico_jobs(
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutomationJob).order_by(desc(AutomationJob.criado_em)).limit(20)
    )
    jobs = result.scalars().all()

    return [
        {
            "id": j.id,
            "tipo": j.tipo,
            "alvo": j.alvo,
            "status": j.status,
            "solicitado_por": j.solicitado_por,
            "resultado": j.resultado,
            "criado_em": j.criado_em.isoformat(),
            "concluido_em": j.concluido_em.isoformat() if j.concluido_em else None,
        }
        for j in jobs
    ]


from app.models import ConfiguracaoSistema


@app.get("/automations/failover-automatico")
async def consultar_failover_automatico(
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ConfiguracaoSistema).where(ConfiguracaoSistema.chave == "failover_automatico"))
    config = result.scalar_one_or_none()
    ativo = config.valor == "ligado" if config else False
    return {"ativo": ativo}


@app.post("/automations/failover-automatico/alternar")
async def alternar_failover_automatico(
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ConfiguracaoSistema).where(ConfiguracaoSistema.chave == "failover_automatico"))
    config = result.scalar_one_or_none()

    if config:
        novo_valor = "desligado" if config.valor == "ligado" else "ligado"
        config.valor = novo_valor
    else:
        novo_valor = "ligado"
        config = ConfiguracaoSistema(chave="failover_automatico", valor=novo_valor)
        db.add(config)

    await db.commit()

    await registrar_log(
        db, usuario.username, "alternar_failover_automatico", "sucesso",
        detalhes=f"Failover automatico definido como: {novo_valor}",
    )

    return {"ativo": novo_valor == "ligado"}


@app.post("/automations/failover-srv-arquivos")
async def solicitar_failover_srv_arquivos(
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutomationJob).where(
            AutomationJob.alvo == "srvarqred",
            AutomationJob.status.in_(["pendente", "executando"])
        )
    )
    job_existente = result.scalar_one_or_none()
    if job_existente:
        raise HTTPException(status_code=400, detail="Ja existe um failover em andamento ou pendente")

    job = AutomationJob(
        tipo="failover_srv_arquivos",
        alvo="srvarqred",
        status="pendente",
        solicitado_por=usuario.username,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await registrar_log(
        db, usuario.username, "failover_srv_arquivos", "solicitado",
        detalhes=f"Job ID {job.id}",
    )



@app.post("/automations/desfazer-failover-srv-arquivos")
async def desfazer_failover_srv_arquivos(
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutomationJob).where(
            AutomationJob.alvo == "srvarqred",
            AutomationJob.status.in_(["pendente", "executando"])
        )
    )
    job_existente = result.scalar_one_or_none()
    if job_existente:
        raise HTTPException(status_code=400, detail="Ja existe uma operacao em andamento ou pendente")
    job = AutomationJob(
        tipo="desfazer_failover_srv_arquivos",
        alvo="srvarqred",
        status="pendente",
        solicitado_por=usuario.username,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await registrar_log(
        db, usuario.username, "desfazer_failover_srv_arquivos", "solicitado",
        detalhes=f"Job ID {job.id}",
    )
    return {"status": "solicitado", "job_id": job.id}


# ============================================
# GERENCIAMENTO DE USUARIOS (admin e super_admin)
# ============================================

def _pode_gerenciar(usuario: User, alvo_role: str | None = None) -> bool:
    if usuario.role == "super_admin":
        return True
    if usuario.role == "admin" and alvo_role != "super_admin":
        return True
    return False


@app.get("/usuarios", response_model=list[UsuarioResponse])
async def listar_usuarios(
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    ordem_role = case(
        (User.role == "super_admin", 1),
        (User.role == "admin", 2),
        (User.role == "operador", 3),
        else_=4,
    )
    result = await db.execute(select(User).order_by(ordem_role, User.username))
    return result.scalars().all()


@app.post("/usuarios", response_model=SenhaResetResponse)
async def criar_usuario(
    dados: UsuarioCreate,
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    if dados.role not in ("super_admin", "admin", "operador"):
        raise HTTPException(status_code=400, detail="Role invalido")

    if not _pode_gerenciar(usuario, dados.role):
        raise HTTPException(status_code=403, detail="Voce nao tem permissao para criar usuario com este papel")

    result = await db.execute(select(User).where(User.username == dados.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Nome de usuario ja existe")

    senha_temporaria = secrets.token_urlsafe(9)
    novo_usuario = User(
        username=dados.username,
        nome_completo=dados.nome_completo,
        password_hash=hash_senha(senha_temporaria),
        role=dados.role,
        deve_trocar_senha=True,
    )
    db.add(novo_usuario)
    await db.commit()

    await registrar_log(
        db, usuario.username, "criar_usuario", "sucesso",
        detalhes=f"Usuario criado: {dados.username} ({dados.role})",
    )

    return {"username": dados.username, "senha_temporaria": senha_temporaria}


@app.post("/usuarios/{username}/resetar-senha", response_model=SenhaResetResponse)
async def resetar_senha_usuario(
    username: str,
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == username))
    alvo = result.scalar_one_or_none()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if not _pode_gerenciar(usuario, alvo.role):
        raise HTTPException(status_code=403, detail="Voce nao tem permissao para gerenciar este usuario")

    senha_temporaria = secrets.token_urlsafe(9)
    alvo.password_hash = hash_senha(senha_temporaria)
    alvo.deve_trocar_senha = True
    await db.commit()

    await registrar_log(
        db, usuario.username, "resetar_senha", "sucesso",
        detalhes=f"Senha resetada para: {username}",
    )

    return {"username": username, "senha_temporaria": senha_temporaria}


@app.patch("/usuarios/{username}/role")
async def atualizar_role_usuario(
    username: str,
    dados: UsuarioRoleUpdate,
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    if dados.role not in ("super_admin", "admin", "operador"):
        raise HTTPException(status_code=400, detail="Role invalido")

    result = await db.execute(select(User).where(User.username == username))
    alvo = result.scalar_one_or_none()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if not _pode_gerenciar(usuario, alvo.role) or not _pode_gerenciar(usuario, dados.role):
        raise HTTPException(status_code=403, detail="Voce nao tem permissao para esta alteracao")

    if alvo.username == usuario.username and dados.role != usuario.role:
        raise HTTPException(status_code=400, detail="Voce nao pode alterar o proprio papel")

    alvo.role = dados.role
    await db.commit()

    await registrar_log(
        db, usuario.username, "atualizar_role", "sucesso",
        detalhes=f"Role de {username} alterado para {dados.role}",
    )

    return {"status": "atualizado"}


@app.delete("/usuarios/{username}")
async def desativar_usuario(
    username: str,
    usuario: User = Depends(exigir_papel("super_admin", "admin")),
    db: AsyncSession = Depends(get_db),
):
    if username == usuario.username:
        raise HTTPException(status_code=400, detail="Voce nao pode desativar seu proprio usuario")

    result = await db.execute(select(User).where(User.username == username))
    alvo = result.scalar_one_or_none()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if not _pode_gerenciar(usuario, alvo.role):
        raise HTTPException(status_code=403, detail="Voce nao tem permissao para desativar este usuario")

    alvo.ativo = False
    await db.commit()

    await registrar_log(
        db, usuario.username, "desativar_usuario", "sucesso",
        detalhes=f"Usuario desativado: {username}",
    )

    return {"status": "desativado"}
