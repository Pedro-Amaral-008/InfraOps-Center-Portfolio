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
PROTHEUS_PORTA_SERVICO = 443  # HTTPS - porta do servico/portal do Protheus


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


async def testar_porta_protheus(host: str, porta: int = PROTHEUS_PORTA_SERVICO, timeout: float = 5.0):
    """Testa se a porta do servico Protheus aceita conexao TCP - mais preciso
    que ICMP pra saber se o SERVICO esta de pe: ICMP pode estar bloqueado ou
    deprorizado pelo servidor mesmo com o servico normal, e vice-versa (o
    servidor pode responder ping e o servico estar travado). Retorna True se
    conectou, False se recusou/deu timeout - nunca None, porque aqui a falta
    de resposta ja significa que ninguem atendeu a conexao."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, porta), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def fazer_traceroute(ip: str, max_saltos: int = 20, timeout: float = 40.0) -> str:
    """Roda um traceroute ate o IP informado e retorna a saida bruta (ou uma
    mensagem de erro/aviso). So e chamado quando uma queda ja foi confirmada
    (nao a cada ciclo, seria pesado demais) - a ideia e dar uma pista de ate
    onde a rota chega antes de parar: se parar logo no nosso proprio
    roteador, o problema e local; se passar varios saltos e so parar perto
    do IP final, o problema esta mais perto do lado do Protheus."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "traceroute", "-n", "-w", "2", "-q", "1", "-m", str(max_saltos), ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        saida = stdout.decode(errors="ignore").strip()
        return saida if saida else "traceroute nao retornou nenhuma saida"
    except FileNotFoundError:
        return "traceroute nao esta instalado no container"
    except asyncio.TimeoutError:
        return "traceroute nao terminou a tempo (timeout)"
    except Exception as e:
        return f"erro ao rodar traceroute: {e}"


def diagnosticar_traceroute(saida: str, ip_destino: str) -> str:
    """Interpreta a saida do traceroute pra apontar de que lado esta o
    problema: se a rota chega ate o IP do Protheus (mesmo sem ele responder
    ping/porta), a internet ate la esta OK e o problema tende a ser do lado
    dele; se a rota para logo nos primeiros saltos, tende a ser nosso; se
    avanca bastante mas nao chega, o problema esta no meio do caminho, mais
    perto do lado do Protheus do que do nosso."""
    linhas = [l for l in saida.strip().splitlines() if l.strip()]
    hops = []
    for linha in linhas:
        partes = linha.strip().split()
        if not partes or not partes[0].isdigit():
            continue
        numero = int(partes[0])
        ip_hop = partes[1] if len(partes) > 1 and partes[1] != "*" else None
        hops.append((numero, ip_hop))

    if not hops:
        return "⚪ Não deu pra interpretar o traceroute (saída vazia ou em formato inesperado)."

    total_saltos = len(hops)
    chegou_no_destino = any(ip_hop == ip_destino for _, ip_hop in hops)
    ultimo_respondeu = max((n for n, ip_hop in hops if ip_hop), default=0)

    if chegou_no_destino:
        return (
            "🔴 *Culpa provável: Protheus.* A rota chegou até o IP dele pelo "
            "traceroute — a internet até lá está OK, então o problema tende a ser "
            "do lado do Protheus (rede ou servidor deles), não da nossa rede."
        )

    if ultimo_respondeu <= 2:
        return (
            f"🟡 *Culpa provável: nossa rede.* A rota parou de responder logo no "
            f"início (só foi até o salto {ultimo_respondeu} de {total_saltos}) — "
            f"isso aponta pra um problema perto de nós (roteador/provedor nosso)."
        )

    return (
        f"🟠 *Culpa provável: lado do Protheus / trânsito da internet.* A rota "
        f"avançou bastante (salto {ultimo_respondeu} de {total_saltos}) sem "
        f"alcançar o destino — parou no meio do caminho, mais perto do lado do "
        f"Protheus do que do nosso."
    )


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


def _fmt_ping(perda, latencia):
    """Formata um resultado de ping pra mensagem: '12% perda (14.5ms)' ou
    'sem dado (SSH falhou)' quando a origem nem conseguiu medir."""
    if perda is None:
        return "sem dado (SSH falhou)"
    texto = f"{perda:.0f}% perda"
    if latencia is not None:
        texto += f" ({latencia:.1f}ms)"
    return texto


_confirmado_offline_desde = None
_alerta_confirmado_enviado = False


async def verificar_protheus(db):
    global _confirmado_offline_desde, _alerta_confirmado_enviado

    (
        (perda, latencia),
        (perda_ref, latencia_ref),
        ((perda_pfsense, latencia_pfsense), (perda_pfsense_ref, latencia_pfsense_ref)),
        porta_servico_ok,
    ) = await asyncio.gather(
        fazer_ping(settings.protheus_ip),
        fazer_ping(REFERENCIA_IP),
        fazer_ping_duplo_via_pfsense(settings.protheus_ip, REFERENCIA_IP),
        testar_porta_protheus(settings.protheus_ip),
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
        porta_servico_ok=porta_servico_ok,
    ))
    await db.commit()

    # Alertas instantaneos por "mudou de estado" foram removidos de proposito.
    # Toda queda isolada (mesmo as que coincidem com nossa rede) fica so
    # registrada no banco (campo rede_ok) e aparece no resumo das 08h/18h.
    # O unico alerta que dispara na hora, fora desses horarios, e o de queda
    # confirmada por duas origens ao mesmo tempo, logo abaixo - e ele traz o
    # detalhamento completo (Google e Protheus, pelas duas origens).

    # Alerta separado dos dois de cima: dispara so quando as DUAS origens
    # (E-Ops e pfSense) confirmarem o Protheus offline ao mesmo tempo, por
    # mais de N minutos seguidos - independente do cooldown/horario fixo.
    confirmado_offline_agora = (
        classificar_estado(perda) == "offline"
        and perda_pfsense is not None
        and classificar_estado(perda_pfsense) == "offline"
        and porta_servico_ok is False
    )

    if confirmado_offline_agora:
        if _confirmado_offline_desde is None:
            _confirmado_offline_desde = agora
            _alerta_confirmado_enviado = False

        duracao_confirmada = (agora - _confirmado_offline_desde).total_seconds()

        if duracao_confirmada >= MINUTOS_PARA_ALERTA_CONFIRMADO * 60 and not _alerta_confirmado_enviado:
            traceroute_saida = await fazer_traceroute(settings.protheus_ip)
            diagnostico = diagnosticar_traceroute(traceroute_saida, settings.protheus_ip)

            google_pi_ok = perda_ref < 50
            google_pfsense_ok = perda_pfsense_ref is not None and perda_pfsense_ref < 50

            if not google_pi_ok or not google_pfsense_ok:
                nota_google = (
                    "⚠️ Nota: o Google também está com perda agora (medido por nós "
                    "e/ou pelo pfSense) — sinal extra de instabilidade geral."
                )
            else:
                nota_google = "✅ Nota: Google respondendo normal nos dois lados (E-Ops e pfSense)."

            msg_confirmado = (
                f"🔴🔴 *InfraOps Center — QUEDA CONFIRMADA DO PROTHEUS*\n\n"
                f"🖥️ *Servidor:* Protheus ({settings.protheus_hostname})\n"
                f"⏱️ *Offline há mais de {MINUTOS_PARA_ALERTA_CONFIRMADO} minutos*, confirmado por *E-Ops*, *pfSense* e *porta do serviço* ao mesmo tempo\n\n"
                f"*Pings no momento da confirmação:*\n"
                f"📍 E-Ops → Protheus: {_fmt_ping(perda, latencia)}\n"
                f"📍 E-Ops → Google: {_fmt_ping(perda_ref, latencia_ref)}\n"
                f"📍 pfSense → Protheus: {_fmt_ping(perda_pfsense, latencia_pfsense)}\n"
                f"📍 pfSense → Google: {_fmt_ping(perda_pfsense_ref, latencia_pfsense_ref)}\n"
                f"🔌 Porta {PROTHEUS_PORTA_SERVICO} (serviço): {'aberta' if porta_servico_ok else 'FECHADA/recusada'}\n\n"
                f"*Diagnóstico (baseado no traceroute):*\n{diagnostico}\n\n"
                f"{nota_google}\n\n"
                f"*Traceroute até o Protheus:*\n"
                f"```\n{traceroute_saida[:1500]}\n```\n\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                f"_Este alerta é independente dos resumos das 08h/18h — dispara só quando confirmado por duas origens._"
            )
            await enviar_telegram(msg_confirmado)
            _alerta_confirmado_enviado = True
    else:
        if _alerta_confirmado_enviado:
            duracao_total_str = (
                _formatar_duracao((agora - _confirmado_offline_desde).total_seconds())
                if _confirmado_offline_desde else "tempo desconhecido"
            )
            msg_recuperado = (
                f"🟢 *InfraOps Center — Protheus voltou*\n\n"
                f"🖥️ *Servidor:* Protheus ({settings.protheus_hostname})\n"
                f"✅ Voltou a responder, confirmado por *E-Ops*, *pfSense* e *porta do serviço*\n"
                f"⏱️ *Ficou offline por:* {duracao_total_str} (queda confirmada por duas origens)\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            await enviar_telegram(msg_recuperado)
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
            culpa = "Protheus" if q["google_pct"] < 50 else "rede/internet"
            linha += f" | Google: {q['google_pct']:.0f}% perda → culpa provável: {culpa}"
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

    checagens_porta = [r.porta_servico_ok for r in registros if r.porta_servico_ok is not None]
    falhas_porta = sum(1 for ok in checagens_porta if not ok)

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

        if checagens_porta:
            msg += f"\n🔌 *Porta {PROTHEUS_PORTA_SERVICO} (serviço):* falhou em {falhas_porta}/{len(checagens_porta)} verificações no período\n"

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
