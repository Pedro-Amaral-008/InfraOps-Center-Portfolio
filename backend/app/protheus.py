import asyncio
import re
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, case
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


async def houve_problema_na_rede_local() -> bool:
    """True se algum link WAN ou AP nosso estiver com problema agora. Usado
    pra decidir se uma queda do Protheus merece alerta na hora (coincidiu
    com algo nosso) ou pode esperar o resumo periodico."""
    try:
        from app.pfsense import get_status_links
        links = await get_status_links()
        if any(l["status"] != "online" for l in links):
            return True
    except Exception:
        pass

    try:
        from app.unifi import get_aps_com_clientes
        aps = await get_aps_com_clientes()
        if any(str(a.get("status", "")).upper() != "ONLINE" for a in aps):
            return True
    except Exception:
        pass

    return False


async def verificar_protheus(db):
    perda, latencia = await fazer_ping(settings.protheus_ip)
    novo_estado = classificar_estado(perda)
    agora = datetime.now(timezone.utc)

    result = await db.execute(
        select(ProtheusStatus).order_by(ProtheusStatus.verificado_em.desc()).limit(1)
    )
    ultima = result.scalar_one_or_none()
    estado_anterior = ultima.estado if ultima else None

    mudou_estado = estado_anterior is not None and novo_estado != estado_anterior

    rede_ok = None
    if mudou_estado:
        rede_ok = not await houve_problema_na_rede_local()

    db.add(ProtheusStatus(
        estado=novo_estado,
        latencia_ms=latencia,
        perda_pacotes_percentual=perda,
        rede_ok=rede_ok,
    ))
    await db.commit()

    if mudou_estado and not rede_ok:
        # So alerta na hora quando a queda coincide com problema na nossa
        # propria rede/AP. Sem isso, fica so registrado e entra no resumo
        # periodico das 08h/18h.
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
            f"*PROTHEUS MUDOU DE ESTADO* {emojis.get(novo_estado, '⚪')} _(coincide com instabilidade na nossa rede)_\n\n"
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


_ultimo_resumo_protheus_enviado = None  # (data, hora) do ultimo resumo ja mandado


async def gerar_resumo_periodico_protheus(db, inicio, fim, rotulo):
    """Monta e manda o resumo do periodo [inicio, fim): quantas quedas,
    tempo total offline/intermitente, a pior queda, e se alguma coincidiu
    com problema na nossa rede."""
    result = await db.execute(
        select(ProtheusStatus)
        .where(ProtheusStatus.verificado_em >= inicio, ProtheusStatus.verificado_em < fim)
        .order_by(ProtheusStatus.verificado_em)
    )
    registros = result.scalars().all()

    eventos = []
    atual = None
    for r in registros:
        if atual is None or r.estado != atual["estado"]:
            if atual is not None:
                atual["fim"] = r.verificado_em
                atual["duracao_segundos"] = (atual["fim"] - atual["inicio"]).total_seconds()
                eventos.append(atual)
            atual = {
                "estado": r.estado,
                "inicio": r.verificado_em,
                "fim": None,
                "duracao_segundos": None,
                "rede_ok": r.rede_ok,
            }
    if atual is not None:
        atual["fim"] = fim
        atual["duracao_segundos"] = (atual["fim"] - atual["inicio"]).total_seconds()
        eventos.append(atual)

    quedas = [e for e in eventos if e["estado"] != "online"]
    total_quedas = len(quedas)
    tempo_total_offline = sum(e["duracao_segundos"] for e in quedas)
    coincidiu_com_rede = any(e["rede_ok"] is False for e in quedas)

    status_atual = await get_protheus_status_atual(db)

    msg = f"🔔 *InfraOps Center — Resumo Protheus ({rotulo})*\n\n"
    msg += f"📅 *Período:* {inicio.astimezone().strftime('%d/%m %H:%M')} → {fim.astimezone().strftime('%d/%m %H:%M')}\n\n"

    if total_quedas == 0:
        msg += "✅ *Nenhuma queda registrada — 100% online no período*\n"
    else:
        pior = max(quedas, key=lambda e: e["duracao_segundos"])
        msg += f"🔴 *{total_quedas} queda(s) registrada(s)*\n"
        msg += f"⏱️ *Tempo total offline/intermitente:* {_formatar_duracao(tempo_total_offline)}\n"
        msg += f"📉 *Maior queda:* {_formatar_duracao(pior['duracao_segundos'])} (às {pior['inicio'].astimezone().strftime('%H:%M')})\n"
        if coincidiu_com_rede:
            msg += "🌐 *Atenção: pelo menos uma queda coincidiu com problema na nossa rede/AP*\n"
        else:
            msg += "🌐 Nenhuma coincidiu com problema na nossa rede\n"

    estado_txt = {"online": "Online", "intermitente": "Intermitente", "offline": "Offline"}.get(status_atual["estado"], status_atual["estado"])
    lat_txt = f" ({status_atual['latencia_ms']:.1f}ms)" if status_atual["latencia_ms"] is not None else ""
    msg += f"\n✅ *Status atual:* {estado_txt}{lat_txt}"

    await enviar_telegram(msg)


async def loop_resumo_periodico_protheus():
    global _ultimo_resumo_protheus_enviado
    from app.database import AsyncSessionLocal
    while True:
        try:
            agora_local = datetime.now()
            marcador = (agora_local.date(), agora_local.hour)

            if agora_local.hour in (8, 18) and _ultimo_resumo_protheus_enviado != marcador:
                fim = datetime.now(timezone.utc)
                if agora_local.hour == 8:
                    inicio = fim - timedelta(hours=14)  # 18h de ontem -> 8h de hoje
                    rotulo = "madrugada"
                else:
                    inicio = fim - timedelta(hours=10)  # 8h de hoje -> 18h de hoje
                    rotulo = "dia"

                async with AsyncSessionLocal() as db:
                    await gerar_resumo_periodico_protheus(db, inicio, fim, rotulo)

                _ultimo_resumo_protheus_enviado = marcador
        except Exception as e:
            print(f"ERRO no loop_resumo_periodico_protheus: {e}")
        await asyncio.sleep(300)


async def loop_protheus_icmp():
    from app.database import AsyncSessionLocal
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await verificar_protheus(db)
        except Exception as e:
            print(f"ERRO no loop_protheus_icmp: {e}")
        await asyncio.sleep(INTERVALO_SEGUNDOS)


async def get_protheus_status_atual(db):
    """Estado mais recente, ha quanto tempo esta nesse estado, e uptime% em
    3 janelas (24h/7d/30d), tudo calculado a partir do historico salvo."""
    result = await db.execute(
        select(ProtheusStatus).order_by(ProtheusStatus.verificado_em.desc()).limit(1)
    )
    ultima = result.scalar_one_or_none()
    if not ultima:
        return {
            "estado": "desconhecido", "latencia_ms": None, "perda_pacotes_percentual": None,
            "desde": None, "uptime_24h": None, "uptime_7d": None, "uptime_30d": None,
        }

    result = await db.execute(
        select(ProtheusStatus.verificado_em)
        .where(ProtheusStatus.estado != ultima.estado, ProtheusStatus.verificado_em < ultima.verificado_em)
        .order_by(ProtheusStatus.verificado_em.desc())
        .limit(1)
    )
    marco = result.scalar_one_or_none()
    desde = marco if marco else ultima.verificado_em

    async def uptime_em(dias):
        limite = datetime.now(timezone.utc) - timedelta(days=dias)
        result = await db.execute(
            select(
                func.count(),
                func.sum(case((ProtheusStatus.estado == "online", 1), else_=0)),
            ).where(ProtheusStatus.verificado_em >= limite)
        )
        total, online = result.one()
        online = online or 0
        return round((online / total) * 100, 2) if total else None

    return {
        "estado": ultima.estado,
        "latencia_ms": float(ultima.latencia_ms) if ultima.latencia_ms is not None else None,
        "perda_pacotes_percentual": float(ultima.perda_pacotes_percentual),
        "desde": desde,
        "uptime_24h": await uptime_em(1),
        "uptime_7d": await uptime_em(7),
        "uptime_30d": await uptime_em(30),
    }


async def get_protheus_historico(db, horas: float = 24):
    """Serie temporal de latencia/perda pra montar o grafico."""
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    result = await db.execute(
        select(ProtheusStatus)
        .where(ProtheusStatus.verificado_em >= limite)
        .order_by(ProtheusStatus.verificado_em)
    )
    registros = result.scalars().all()
    return [
        {
            "verificado_em": r.verificado_em,
            "estado": r.estado,
            "latencia_ms": float(r.latencia_ms) if r.latencia_ms is not None else None,
            "perda_pacotes_percentual": float(r.perda_pacotes_percentual),
        }
        for r in registros
    ]


async def get_protheus_eventos(db, dias: int = 30):
    """Agrupa o historico bruto em segmentos continuos do mesmo estado
    (ex: 'offline das 14:02 as 14:15'), mais recente primeiro."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    result = await db.execute(
        select(ProtheusStatus)
        .where(ProtheusStatus.verificado_em >= limite)
        .order_by(ProtheusStatus.verificado_em)
    )
    registros = result.scalars().all()

    eventos = []
    atual = None
    for r in registros:
        if atual is None or r.estado != atual["estado"]:
            if atual is not None:
                atual["fim"] = r.verificado_em
                atual["duracao_segundos"] = int((atual["fim"] - atual["inicio"]).total_seconds())
                eventos.append(atual)
            atual = {"estado": r.estado, "inicio": r.verificado_em, "fim": None, "duracao_segundos": None}
    if atual is not None:
        eventos.append(atual)

    eventos.reverse()
    return eventos
