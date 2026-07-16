import httpx
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentAlertState
from app.config import settings

LIMITE_CPU = 90
LIMITE_RAM = 90
LIMITE_DISCO = 90

PROMETHEUS_URL = "http://prometheus:9090"


async def consultar_metrica(query: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": query}
            )
            response.raise_for_status()
            data = response.json()
            resultado = data.get("data", {}).get("result", [])
            if resultado:
                return float(resultado[0]["value"][1])
            return None
        except Exception:
            return None


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


async def obter_estado(db: AsyncSession, instance: str, recurso: str) -> bool:
    result = await db.execute(
        select(AgentAlertState).where(
            AgentAlertState.instance == instance,
            AgentAlertState.recurso == recurso,
        )
    )
    registro = result.scalar_one_or_none()
    return registro.em_alerta if registro else False


async def definir_estado(db: AsyncSession, instance: str, recurso: str, em_alerta: bool):
    result = await db.execute(
        select(AgentAlertState).where(
            AgentAlertState.instance == instance,
            AgentAlertState.recurso == recurso,
        )
    )
    registro = result.scalar_one_or_none()

    if registro:
        registro.em_alerta = em_alerta
    else:
        registro = AgentAlertState(instance=instance, recurso=recurso, em_alerta=em_alerta)
        db.add(registro)

    await db.commit()


async def verificar_limites_controller(db: AsyncSession):
    instance = "raspberry-pi-controller"
    hostname = "InfraOps Controller"

    cpu = await consultar_metrica('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)')
    ram = await consultar_metrica('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
    disco = await consultar_metrica('100 - ((node_filesystem_avail_bytes{mountpoint="/"} * 100) / node_filesystem_size_bytes{mountpoint="/"})')

    recursos = [
        ("CPU", cpu, LIMITE_CPU, "🖥️"),
        ("RAM", ram, LIMITE_RAM, "🧠"),
        ("Disco", disco, LIMITE_DISCO, "💾"),
    ]

    for nome_recurso, valor, limite, emoji in recursos:
        if valor is None:
            continue

        valor = round(valor)
        estava_em_alerta = await obter_estado(db, instance, nome_recurso)
        esta_em_alerta = valor >= limite

        if esta_em_alerta and not estava_em_alerta:
            msg = (
                f"🔔 *Monitoramento InfraOps Center*\n\n"
                f"*USO ELEVADO* ⚠️:\n\n"
                f"{emoji} *Servidor: {hostname}*\n"
                f"📊 {nome_recurso}: {valor}%\n"
                f"🕐 Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"⚠️ Ação: Verificar uso de {nome_recurso.lower()} imediatamente"
            )
            await enviar_telegram(msg)
            await definir_estado(db, instance, nome_recurso, True)

        elif not esta_em_alerta and estava_em_alerta:
            msg = (
                f"🔔 *Monitoramento InfraOps Center*\n\n"
                f"*USO NORMALIZADO* ✅:\n\n"
                f"{emoji} *Servidor: {hostname}*\n"
                f"📊 {nome_recurso}: {valor}%\n"
                f"🕐 Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            await enviar_telegram(msg)
            await definir_estado(db, instance, nome_recurso, False)
