import os
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request
from app.config import settings
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, desc, func
from datetime import datetime, timedelta, timezone
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.database import get_db
from app.dashboard import get_dashboard_summary
from app.metrics import get_metricas_host
from app.models import User, BackupExecution, AuditLog
from app.schemas import LoginRequest, LoginResponse, TrocarSenhaRequest, BackupExecutionCreate
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

    result = await db.execute(select(User).where(User.username == dados.username))
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


@app.get("/dashboard/backups")
async def dashboard_backups(usuario: User = Depends(get_current_user)):
    from app.dashboard import get_backups_detalhado
    return await get_backups_detalhado()


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
from app.pfsense import registrar_status_links, registrar_trafego
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
                await registrar_status_links(db)
            except Exception as e:
                print(f"ERRO em registrar_status_links: {e}")

        await asyncio.sleep(120)

@app.on_event("startup")
async def iniciar_verificacao_agentes():
    asyncio.create_task(loop_verificacao_agentes())
    asyncio.create_task(loop_trafego_pfsense())
    asyncio.create_task(loop_resumo_diario())


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

    def extrair_valor(resultado):
        if resultado and len(resultado) > 0:
            return float(resultado[0].get("value", [None, "0"])[1])
        return 0

    return {
        "hostname": "InfraOps Controller",
        "instance": "raspberry-pi-controller",
        "cpu_percent": round(extrair_valor(cpu)),
        "ram_percent": round(extrair_valor(ram)),
        "ram_total_gb": round(extrair_valor(ram_total) / (1024**3)),
        "disco_percent": round(extrair_valor(disco)),
        "disco_total_gb": round(extrair_valor(disco_total) / (1024**3)),
        "temperatura_celsius": round(extrair_valor(temperatura), 1),
        "uptime_horas": None,
    }


@app.get("/dashboard/unifi/aps")
async def dashboard_unifi_aps(
    usuario: User = Depends(get_current_user),
):
    from app.unifi import get_aps_com_clientes
    return await get_aps_com_clientes()


@app.get("/dashboard/pfsense/links")
async def dashboard_pfsense_links(
    usuario: User = Depends(get_current_user),
):
    from app.pfsense import get_status_links
    return await get_status_links()


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


@app.get("/dashboard/metrics/latencia-agentes")
async def dashboard_metrics_latencia_agentes(
    minutos: int = 60,
    usuario: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timezone
    limite = datetime.now(timezone.utc) - timedelta(minutes=minutos)

    result = await db.execute(
        select(AgentMetric)
        .where(AgentMetric.instance == "srvfrotas", AgentMetric.coletado_em >= limite)
        .order_by(AgentMetric.coletado_em)
    )
    registros = result.scalars().all()

    return [
        {
            "nome": "SRV-FLUIG",
            "instance": "srvfrotas",
            "pontos": [
                {"timestamp": int(r.coletado_em.timestamp() * 1000), "valor": r.latencia_ms}
                for r in registros if r.latencia_ms is not None
            ],
        }
    ]


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

    return {"status": "solicitado", "job_id": job.id}
