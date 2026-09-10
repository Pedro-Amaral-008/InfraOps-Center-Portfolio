import asyncio
import re
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, case
from app.config import settings
from app.models import ProtheusStatus
from app.agent_alerts import enviar_telegram

INTERVALO_SEGUNDOS = 15
QUANTIDADE_PINGS = 5
REFERENCIA_IP = "8.8.8.8"  # Google DNS, usado so pra comparacao/validacao

PFSENSE_SSH_USER = "infraops-readonly"
PFSENSE_SSH_KEY = "/home/appuser/.ssh/pfsense_readonly"
MINUTOS_PARA_ALERTA_CONFIRMADO = 5


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


def _extrair_perda_e_latencia(saida: str):
    """Extrai (perda_percentual, latencia_ms) de uma saida de `ping`. Retorna
    (None, None) quando nao encontra o padrao de 'packet loss' - sinal de que
    o ping nem chegou a rodar direito (ex: comando falhou antes de imprimir
    as estatisticas)."""
    match_perda = re.search(r"(\d+(?:\.\d+)?)% packet loss", saida)
    if match_perda is None:
        return None, None
    perda = float(match_perda.group(1))
    match_latencia = re.search(r"= [\d.]+/([\d.]+)/", saida)
    latencia = float(match_latencia.group(1)) if match_latencia else None
    return perda, latencia


async def fazer_ping_duplo_via_pfsense(ip1: str, ip2: str, quantidade: int = QUANTIDADE_PINGS):
    """Roda dois pings (Protheus e Google) numa unica conexao SSH pro
    pfSense, pra comparar as duas origens vistas de la - se so o Protheus
    cair e o Google nao, o problema e especifico dele; se os dois carem
    juntos, o problema e da rede/rota do pfSense ate a internet.

    Retorna ((perda1, latencia1), (perda2, latencia2)). Se o proprio SSH
    falhar/travar (nao conseguiu nem conectar no pfSense), retorna
    (None, None) pros dois - assim a gente nao confunde "SSH deu problema"
    com "Protheus (ou Google) caiu", o que geraria falso alarme."""
    separador = "___SEPARADOR_PING___"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-i", PFSENSE_SSH_KEY,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            "-o", "BatchMode=yes",
            f"{PFSENSE_SSH_USER}@{settings.pfsense_host}",
            f"ping -c {quantidade} {ip1}; echo {separador}; ping -c {quantidade} {ip2}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=quantidade * 2 * 3 + 15)
        saida = stdout.decode(errors="ignore")

        if separador not in saida:
            erro = stderr.decode(errors="ignore").strip()[:200]
            print(f"AVISO pfSense SSH: nao conseguiu executar os pings (stderr: {erro})")
            return (None, None), (None, None)

        saida1, saida2 = saida.split(separador, 1)
        return _extrair_perda_e_latencia(saida1), _extrair_perda_e_latencia(saida2)
    except Exception as e:
        print(f"AVISO pfSense SSH: excecao ao executar pings ({e})")
        return (None, None), (None, None)


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


_confirmado_offline_desde = None
_alerta_confirmado_enviado = False


async def verificar_protheus(db):
    global _confirmado_offline_desde, _alerta_confirmado_enviado

    (perda, latencia), (perda_ref, latencia_ref), ((perda_pfsense, latencia_pfsense), (perda_pfsense_ref, latencia_pfsense_ref)) = await asyncio.gather(
        fazer_ping(settings.protheus_ip),
        fazer_ping(REFERENCIA_IP),
        fazer_ping_duplo_via_pfsense(settings.protheus_ip, REFERENCIA_IP),
    )
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
        # "Nossa rede ok" agora considera tanto o status de link/AP quanto
        # se o proprio Google tambem perdeu pacote no mesmo instante - um
        # sinal bem mais direto de problema de internet geral vs isolado.
        problema_local = await houve_problema_na_rede_local() or perda_ref >= 50
        rede_ok = not problema_local

    db.add(ProtheusStatus(
        estado=novo_estado,
        latencia_ms=latencia,
        perda_pacotes_percentual=perda,
        rede_ok=rede_ok,
        referencia_perda_percentual=perda_ref,
        pfsense_perda_percentual=perda_pfsense,
        pfsense_latencia_ms=latencia_pfsense,
        pfsense_referencia_perda_percentual=perda_pfsense_ref,
        pfsense_referencia_latencia_ms=latencia_pfsense_ref,
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
        marco_diferente = result.scalar_one_or_none()

        inicio_do_estado = None
        if marco_diferente:
            result = await db.execute(
                select(func.min(ProtheusStatus.verificado_em))
                .where(ProtheusStatus.estado == estado_anterior, ProtheusStatus.verificado_em > marco_diferente)
            )
            inicio_do_estado = result.scalar_one_or_none()

        duracao_str = _formatar_duracao((agora - inicio_do_estado).total_seconds()) if inicio_do_estado else "algum tempo"

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
        msg += f"📡 *Perda pro Google (8.8.8.8) no mesmo instante:* {perda_ref:.0f}%\n"
        msg += f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        msg += f"*Estado da nossa rede no momento:*\n{resumo_rede}"

        await enviar_telegram(msg)

    # Alerta separado dos dois de cima: dispara so quando as DUAS origens
    # (E-Ops e pfSense) confirmarem o Protheus offline ao mesmo tempo, por
    # mais de N minutos seguidos - independente do cooldown/horario fixo.
    confirmado_offline_agora = (
        classificar_estado(perda) == "offline"
        and perda_pfsense is not None
        and classificar_estado(perda_pfsense) == "offline"
    )

    if confirmado_offline_agora:
        if _confirmado_offline_desde is None:
            _confirmado_offline_desde = agora
            _alerta_confirmado_enviado = False

        duracao_confirmada = (agora - _confirmado_offline_desde).total_seconds()

        if duracao_confirmada >= MINUTOS_PARA_ALERTA_CONFIRMADO * 60 and not _alerta_confirmado_enviado:
            msg_confirmado = (
                f"🔴🔴 *InfraOps Center — QUEDA CONFIRMADA DO PROTHEUS*\n\n"
                f"🖥️ *Servidor:* Protheus ({settings.protheus_hostname})\n"
                f"⏱️ *Offline há mais de {MINUTOS_PARA_ALERTA_CONFIRMADO} minutos*, confirmado por *E-Ops* e *pfSense* ao mesmo tempo\n"
                f"📉 *Perda (E-Ops):* {perda:.0f}% | *Perda (pfSense):* {perda_pfsense:.0f}%\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                f"_Este alerta é independente dos resumos das 08h/18h — dispara só quando confirmado por duas origens._"
            )
            await enviar_telegram(msg_confirmado)
            _alerta_confirmado_enviado = True
    else:
        _confirmado_offline_desde = None
        _alerta_confirmado_enviado = False


_ultimo_resumo_protheus_enviado = None  # (data, hora) do ultimo resumo ja mandado


def _agrupar_quedas(registros, obter_perda, fim):
    """Agrupa uma serie de leituras em segmentos continuos do mesmo estado,
    a partir de uma funcao que extrai a perda de pacotes de cada linha.
    Retorna so os segmentos que nao sao "online"."""
    eventos = []
    atual = None
    for r in registros:
        perda_r = obter_perda(r)
        estado_r = classificar_estado(perda_r) if perda_r is not None else "desconhecido"
        if atual is None or estado_r != atual["estado"]:
            if atual is not None:
                atual["fim"] = r.verificado_em
                atual["duracao_segundos"] = (atual["fim"] - atual["inicio"]).total_seconds()
                eventos.append(atual)
            atual = {"estado": estado_r, "inicio": r.verificado_em, "fim": None, "duracao_segundos": None}
    if atual is not None:
        atual["fim"] = fim
        atual["duracao_segundos"] = (atual["fim"] - atual["inicio"]).total_seconds()
        eventos.append(atual)
    return [e for e in eventos if e["estado"] not in ("online", "desconhecido")]


def _media_perda_no_intervalo(registros, obter_perda, inicio, fim):
    """Media da perda de pacotes (de uma origem qualquer) dentro de uma janela
    de tempo - usado pra parear a queda do Protheus com o que o Google mediu
    no mesmo instante."""
    valores = [
        obter_perda(r) for r in registros
        if inicio <= r.verificado_em < fim and obter_perda(r) is not None
    ]
    return sum(valores) / len(valores) if valores else None


def _formatar_lista_quedas(quedas, max_listadas=15):
    linhas = []
    for q in quedas[:max_listadas]:
        linha = (
            f"• {q['inicio'].astimezone().strftime('%H:%M:%S')} → "
            f"{q['fim'].astimezone().strftime('%H:%M:%S')} "
            f"({_formatar_duracao(q['duracao_segundos'])})"
        )
        if q.get("google_pct") is not None:
            linha += f" | Google no mesmo instante: {q['google_pct']:.0f}% perda"
        linhas.append(linha)
    if len(quedas) > max_listadas:
        linhas.append(f"_(+ {len(quedas) - max_listadas} outra(s) queda(s) não listada(s))_")
    return "\n".join(linhas)


async def gerar_resumo_periodico_protheus(db, inicio, fim, rotulo):
    """Monta e manda o resumo do periodo [inicio, fim): quedas vistas pelo
    E-Ops e pelo pfSense (uma embaixo da outra, pra comparar), tempo total
    de cada origem, e se alguma coincidiu com problema na nossa rede."""
    result = await db.execute(
        select(ProtheusStatus)
        .where(ProtheusStatus.verificado_em >= inicio, ProtheusStatus.verificado_em < fim)
        .order_by(ProtheusStatus.verificado_em)
    )
    registros = result.scalars().all()

    quedas_eops = _agrupar_quedas(registros, lambda r: r.perda_pacotes_percentual, fim)
    quedas_pfsense = _agrupar_quedas(registros, lambda r: r.pfsense_perda_percentual, fim)

    for q in quedas_eops:
        q["google_pct"] = _media_perda_no_intervalo(
            registros, lambda r: r.referencia_perda_percentual, q["inicio"], q["fim"]
        )

    for q in quedas_pfsense:
        q["google_pct"] = _media_perda_no_intervalo(
            registros, lambda r: r.pfsense_referencia_perda_percentual, q["inicio"], q["fim"]
        )

    # Correlacao com rede/AP e com o Google, so faz sentido do lado do E-Ops
    # (e o unico que tem essas duas checagens extras).
    mapa_correlacao = {}
    for r in registros:
        if r.rede_ok is not None or r.referencia_perda_percentual is not None:
            mapa_correlacao[r.verificado_em] = (r.rede_ok, r.referencia_perda_percentual)

    def _coincidiu_eops(q):
        for r in registros:
            if q["inicio"] <= r.verificado_em < q["fim"]:
                rede_ok, ref_perda = mapa_correlacao.get(r.verificado_em, (None, None))
                if rede_ok is False or (ref_perda or 0) >= 50:
                    return True
        return False

    tempo_total_eops = sum(q["duracao_segundos"] for q in quedas_eops)
    tempo_total_pfsense = sum(q["duracao_segundos"] for q in quedas_pfsense)
    coincidiu_com_rede = any(_coincidiu_eops(q) for q in quedas_eops)

    status_atual = await get_protheus_status_atual(db)

    msg = f"🔔 *InfraOps Center — Resumo Protheus ({rotulo})*\n\n"
    msg += f"📅 *Período:* {inicio.astimezone().strftime('%d/%m %H:%M')} → {fim.astimezone().strftime('%d/%m %H:%M')}\n\n"

    if not quedas_eops and not quedas_pfsense:
        msg += "✅ *Nenhuma queda registrada por nenhuma das origens — 100% online no período*\n"
    else:
        msg += f"📍 *E-Ops — {len(quedas_eops)} queda(s):*\n"
        if quedas_eops:
            msg += _formatar_lista_quedas(quedas_eops) + "\n"
            msg += f"⏱️ Tempo total (E-Ops): {_formatar_duracao(tempo_total_eops)}\n"
        else:
            msg += "✅ Nenhuma queda vista pelo E-Ops\n"

        msg += f"\n📍 *pfSense — {len(quedas_pfsense)} queda(s):*\n"
        if quedas_pfsense:
            msg += _formatar_lista_quedas(quedas_pfsense) + "\n"
            msg += f"⏱️ Tempo total (pfSense): {_formatar_duracao(tempo_total_pfsense)}\n"
        else:
            msg += "✅ Nenhuma queda vista pelo pfSense\n"

        msg += "\n"
        if coincidiu_com_rede:
            msg += "🌐 *Atenção: pelo menos uma queda do E-Ops coincidiu com problema na nossa rede/AP ou perda pro Google*\n"
        else:
            msg += "🌐 Nenhuma queda coincidiu com problema na nossa rede\n"

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
