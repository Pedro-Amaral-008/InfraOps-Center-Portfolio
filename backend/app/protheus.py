import asyncio
import re
from datetime import datetime, timezone
from sqlalchemy import select
from app.config import settings
from app.models import ProtheusStatus
from app.agent_alerts import enviar_telegram

INTERVALO_SEGUNDOS = 15
QUANTIDADE_PINGS = 5


async def fazer_ping(ip: str, quantidade: int = QUANTIDADE_PINGS):
    """Manda um mini-lote de pings ICMP pro IP informado e retorna
    (perda_percentual, latencia_media_ms). Se o comando falhar por completo
    (ex: binario ausente, sem permissao), assume 100% de perda."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", str(quantidade), "-W", "1", ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=quantidade * 2 + 5)
        saida = stdout.decode(errors="ignore")

        match_perda = re.search(r"(\d+(?:\.\d+)?)% packet loss", saida)
        perda = float(match_perda.group(1)) if match_perda else 100.0

        match_latencia = re.search(r"= [\d.]+/([\d.]+)/", saida)
        latencia = float(match_latencia.group(1)) if match_latencia else None

        return perda, latencia
    except Exception:
        return 100.0, None


def classificar_estado(perda_percentual: float) -> str:
    if perda_percentual >= 100:
        return "offline"
    if perda_percentual <= 0:
        return "online"
    return "intermitente"


def _formatar_duracao(segundos: float) -> str:
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos}s"
    minutos, segundos = divmod(segundos, 60)
    if minutos < 60:
        return f"{minutos}min{segundos:02d}s"
    horas, minutos = divmod(minutos, 60)
    return f"{horas}h{minutos:02d}min"


async def formatar_resumo_rede() -> str:
    """Resumo curto do estado atual dos links WAN e APs, incluido no alerta
    do Protheus pra ajudar a diferenciar se o problema e do lado deles ou da
    nossa propria internet/rede."""
    linhas = []

    try:
        from app.pfsense import get_status_links
        links = await get_status_links()
        problemas = [l["nome"] for l in links if l["status"] != "online"]
        if problemas:
            linhas.append(f"🔴 Links WAN com problema: {', '.join(problemas)}")
        else:
            linhas.append("🟢 Links WAN: todos online")
    except Exception:
        linhas.append("⚪ Links WAN: não foi possível checar agora")

    try:
        from app.unifi import get_aps_com_clientes
        aps = await get_aps_com_clientes()
        problemas = [a["nome"] for a in aps if str(a.get("status", "")).upper() != "ONLINE"]
        if problemas:
            linhas.append(f"🔴 APs com problema: {', '.join(problemas)}")
        else:
            linhas.append("🟢 Access Points: todos online")
    except Exception:
        linhas.append("⚪ Access Points: não foi possível checar agora")

    return "\n".join(linhas)


async def verificar_protheus(db):
    perda, latencia = await fazer_ping(settings.protheus_ip)
    novo_estado = classificar_estado(perda)
    agora = datetime.now(timezone.utc)

    result = await db.execute(
        select(ProtheusStatus).order_by(ProtheusStatus.verificado_em.desc()).limit(1)
    )
    ultima = result.scalar_one_or_none()
    estado_anterior = ultima.estado if ultima else None

    db.add(ProtheusStatus(
        estado=novo_estado,
        latencia_ms=latencia,
        perda_pacotes_percentual=perda,
    ))
    await db.commit()

    if estado_anterior is not None and novo_estado != estado_anterior:
        result = await db.execute(
            select(ProtheusStatus.verificado_em)
            .where(ProtheusStatus.estado != estado_anterior, ProtheusStatus.verificado_em < agora)
            .order_by(ProtheusStatus.verificado_em.desc())
            .limit(1)
        )
        marco_anterior = result.scalar_one_or_none()
        duracao_str = _formatar_duracao((agora - marco_anterior).total_seconds()) if marco_anterior else "algum tempo"

        emojis = {"online": "🟢", "intermitente": "🟡", "offline": "🔴"}

        resumo_rede = await formatar_resumo_rede()

        msg = (
            f"🔔 *Monitoramento InfraOps Center*\n\n"
            f"*PROTHEUS MUDOU DE ESTADO* {emojis.get(novo_estado, '⚪')}\n\n"
            f"🖥️ *Servidor:* Protheus ({settings.protheus_hostname})\n"
            f"🔁 *{estado_anterior.upper()} → {novo_estado.upper()}*\n"
            f"⏱️ *Ficou {estado_anterior} por:* {duracao_str}\n"
        )
        if latencia is not None:
            msg += f"📶 *Latência atual:* {latencia:.1f}ms\n"
        msg += f"📉 *Perda de pacotes:* {perda:.0f}%\n"
        msg += f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        msg += f"*Estado da nossa rede no momento:*\n{resumo_rede}"

        await enviar_telegram(msg)


async def loop_protheus_icmp():
    from app.database import AsyncSessionLocal
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await verificar_protheus(db)
        except Exception as e:
            print(f"ERRO no loop_protheus_icmp: {e}")
        await asyncio.sleep(INTERVALO_SEGUNDOS)
