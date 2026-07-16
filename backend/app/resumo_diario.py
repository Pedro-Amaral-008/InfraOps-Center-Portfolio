from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from app.models import AgentMetric
from app.agent_alerts import enviar_telegram, obter_estado, COOLDOWN_HORAS

LIMITE_CPU = 90
LIMITE_RAM = 90
LIMITE_DISCO = 90


async def _ja_notificado_recentemente(db, instance, nome_recurso):
    registro = await obter_estado(db, instance, nome_recurso)
    if not registro or not registro.em_alerta or not registro.atualizado_em:
        return False
    agora = datetime.now(timezone.utc)
    return (agora - registro.atualizado_em) < timedelta(hours=COOLDOWN_HORAS)


async def gerar_resumo_diario(db):
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

    problemas = []
    for m in metricas:
        if m.cpu_percent is not None and m.cpu_percent >= LIMITE_CPU:
            if not await _ja_notificado_recentemente(db, m.instance, "CPU"):
                problemas.append(f"🖥️ *{m.hostname}* — CPU: {m.cpu_percent}%")

        if m.ram_percent is not None and m.ram_percent >= LIMITE_RAM:
            if not await _ja_notificado_recentemente(db, m.instance, "RAM"):
                problemas.append(f"🧠 *{m.hostname}* — RAM: {m.ram_percent}%")

        if m.discos_json:
            for disco in m.discos_json:
                if disco.get("percent", 0) >= LIMITE_DISCO:
                    nome_recurso = f"Disco {disco.get('drive')}"
                    if not await _ja_notificado_recentemente(db, m.instance, nome_recurso):
                        problemas.append(f"💾 *{m.hostname}* — Disco {disco.get('drive')} {disco.get('percent')}%")
        elif m.disco_percent is not None and m.disco_percent >= LIMITE_DISCO:
            if not await _ja_notificado_recentemente(db, m.instance, "Disco"):
                problemas.append(f"💾 *{m.hostname}* — Disco: {m.disco_percent}%")

    if not problemas:
        return

    agora = datetime.now().strftime('%d/%m/%Y %H:%M')
    msg = (
        f"🔔 *Monitoramento InfraOps Center*\n\n"
        f"*RESUMO DIÁRIO — 05:00* ⚠️\n\n"
        f"Os seguintes recursos estão acima de {LIMITE_CPU}% (sem alerta nas últimas {COOLDOWN_HORAS}h):\n\n"
        + "\n".join(problemas) +
        f"\n\n🕐 *Verificado em:* {agora}"
    )
    await enviar_telegram(msg)
