import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AgentMetric, AgentAlertState
from app.config import settings

LIMITE_CPU = 90
LIMITE_RAM = 90
LIMITE_DISCO = 90

COOLDOWN_HORAS = 24


async def enviar_telegram(mensagem: str):
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(url, json={
                "chat_id": settings.telegram_chat_id,
                "text": mensagem,
                "parse_mode": "Markdown",
            })
        except Exception:
            pass


async def obter_estado(db: AsyncSession, instance: str, recurso: str):
    result = await db.execute(
        select(AgentAlertState).where(
            AgentAlertState.instance == instance,
            AgentAlertState.recurso == recurso,
        )
    )
    return result.scalar_one_or_none()


async def definir_estado(db: AsyncSession, instance: str, recurso: str, em_alerta: bool):
    registro = await obter_estado(db, instance, recurso)
    if registro:
        registro.em_alerta = em_alerta
    else:
        registro = AgentAlertState(instance=instance, recurso=recurso, em_alerta=em_alerta)
        db.add(registro)
    await db.commit()


async def processar_recurso(db: AsyncSession, hostname: str, instance: str, nome_recurso: str, valor, limite, emoji):
    if valor is None:
        return

    registro = await obter_estado(db, instance, nome_recurso)
    estava_em_alerta = registro.em_alerta if registro else False
    esta_em_alerta = valor >= limite

    if esta_em_alerta and not estava_em_alerta:
        agora = datetime.now(timezone.utc)
        ja_avisado_recentemente = False
        if registro and registro.atualizado_em:
            ja_avisado_recentemente = (agora - registro.atualizado_em) < timedelta(hours=COOLDOWN_HORAS)

        if not ja_avisado_recentemente:
            msg = (
                f"🔔 *Monitoramento InfraOps Center*\n\n"
                f"*USO ELEVADO* ⚠️:\n\n"
                f"{emoji} *Servidor:* {hostname}\n"
                f"📊 *{nome_recurso}* {valor}%\n"
                f"🌐 *Instância:* {instance}\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"⚠️ *Ação:* Verificar uso de {nome_recurso.lower()} imediatamente\n\n"
                f"_Próximo alerta deste tipo, se persistir, em até {COOLDOWN_HORAS}h._"
            )
            await enviar_telegram(msg)

        await definir_estado(db, instance, nome_recurso, True)

    elif not esta_em_alerta and estava_em_alerta:
        msg = (
            f"🔔 *Monitoramento InfraOps Center*\n\n"
            f"*USO NORMALIZADO* ✅:\n\n"
            f"{emoji} *Servidor:* {hostname}\n"
            f"📊 *{nome_recurso}* {valor}%\n"
            f"🌐 *Instância:* {instance}\n"
            f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        await enviar_telegram(msg)
        await definir_estado(db, instance, nome_recurso, False)


async def verificar_limites_agentes(db: AsyncSession):
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

    for m in metricas:
        await processar_recurso(db, m.hostname, m.instance, "CPU", m.cpu_percent, LIMITE_CPU, "🖥️")
        await processar_recurso(db, m.hostname, m.instance, "RAM", m.ram_percent, LIMITE_RAM, "🧠")

        if m.discos_json:
            for disco in m.discos_json:
                drive = disco.get("drive", "?")
                percent = disco.get("percent")
                nome_recurso = f"Disco {drive}"
                await processar_recurso(db, m.hostname, m.instance, nome_recurso, percent, LIMITE_DISCO, "💾")
        else:
            await processar_recurso(db, m.hostname, m.instance, "Disco", m.disco_percent, LIMITE_DISCO, "💾")


async def verificar_failover_srv_arquivos(db: AsyncSession):
    from datetime import timezone, timedelta
    from sqlalchemy import select
    from app.models import AgentMetric, ConfiguracaoSistema, AutomationJob

    LIMITE_MINUTOS_QUEDA = 5

    result = await db.execute(
        select(AgentMetric)
        .where(AgentMetric.instance == "srv-arq")
        .order_by(AgentMetric.coletado_em.desc())
        .limit(1)
    )
    ultima_coleta = result.scalar_one_or_none()

    if not ultima_coleta:
        return

    agora = datetime.now(timezone.utc)
    tempo_sem_reportar = agora - ultima_coleta.coletado_em

    if tempo_sem_reportar < timedelta(minutes=LIMITE_MINUTOS_QUEDA):
        return

    result = await db.execute(select(AutomationJob).where(
        AutomationJob.alvo == "srvarqred",
        AutomationJob.status.in_(["pendente", "executando"])
    ))
    if result.scalar_one_or_none():
        return

    result = await db.execute(select(AutomationJob).where(
        AutomationJob.alvo == "srvarqred",
        AutomationJob.tipo == "failover_srv_arquivos"
    ).order_by(AutomationJob.criado_em.desc()).limit(1))
    ultimo_job = result.scalar_one_or_none()
    if ultimo_job and (agora - ultimo_job.criado_em) < timedelta(hours=1):
        return

    result = await db.execute(select(ConfiguracaoSistema).where(ConfiguracaoSistema.chave == "failover_automatico"))
    config = result.scalar_one_or_none()
    automatico_ativo = config.valor == "ligado" if config else False

    minutos_sem_reportar = int(tempo_sem_reportar.total_seconds() / 60)

    if automatico_ativo:
        job = AutomationJob(
            tipo="failover_srv_arquivos",
            alvo="srvarqred",
            status="pendente",
            solicitado_por="sistema (deteccao automatica)",
        )
        db.add(job)
        await db.commit()

        msg = (
            f"🔔 *Monitoramento InfraOps Center*\n\n"
            f"*QUEDA DETECTADA — FAILOVER AUTOMÁTICO ACIONADO* 🔴\n\n"
            f"🖥️ *Servidor:* SRV-ARQ\n"
            f"⏱️ *Sem resposta há:* {minutos_sem_reportar} minutos\n"
            f"🔄 *Ação:* Failover automático iniciado para SrvArqRed\n"
            f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
    else:
        msg = (
            f"🔔 *Monitoramento InfraOps Center*\n\n"
            f"*QUEDA DETECTADA — FAILOVER AUTOMÁTICO DESLIGADO* ⚠️\n\n"
            f"🖥️ *Servidor:* SRV-ARQ\n"
            f"⏱️ *Sem resposta há:* {minutos_sem_reportar} minutos\n"
            f"⚠️ *Ação:* Failover automático está desativado. Use o botão manual no painel se necessário.\n"
            f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )

    await enviar_telegram(msg)


LIMITE_MINUTOS_SEM_COLETA = 5


async def verificar_disponibilidade_agentes(db: AsyncSession):
    from datetime import timezone, timedelta
    from sqlalchemy import select, func
    from app.models import AgentMetric

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

    agora = datetime.now(timezone.utc)
    limite = timedelta(minutes=LIMITE_MINUTOS_SEM_COLETA)

    for m in metricas:
        atraso = agora - m.coletado_em
        offline = atraso > limite

        registro = await obter_estado(db, m.instance, "Disponibilidade")
        estava_offline = registro.em_alerta if registro else False

        if offline and not estava_offline:
            msg = (
                f"🔔 *Monitoramento InfraOps Center*\n\n"
                f"*SERVIDOR SEM RESPOSTA* ❌:\n\n"
                f"🖥️ *Servidor:* {m.hostname}\n"
                f"🌐 *Instância:* {m.instance}\n"
                f"⏱️ *Última coleta há:* {int(atraso.total_seconds() / 60)} minutos\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"⚠️ *Ação:* Verificar conectividade e status do servidor"
            )
            await enviar_telegram(msg)
            await definir_estado(db, m.instance, "Disponibilidade", True)

        elif not offline and estava_offline:
            msg = (
                f"🔔 *Monitoramento InfraOps Center*\n\n"
                f"*SERVIDOR RESPONDENDO NOVAMENTE* ✅:\n\n"
                f"🖥️ *Servidor:* {m.hostname}\n"
                f"🌐 *Instância:* {m.instance}\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            await enviar_telegram(msg)
            await definir_estado(db, m.instance, "Disponibilidade", False)
