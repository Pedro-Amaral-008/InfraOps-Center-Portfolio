import asyncio
import re
import socket
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
PATIO2_SSH_USER = "e-ops-readonly"  # mesma chave SSH, usuario criado no pfSense do Patio 2
MINUTOS_PARA_ALERTA_CONFIRMADO = 2
MINUTOS_PARA_ALERTA_APP = 2  # quanto tempo a aplicacao (HTTP) pode ficar sem responder OK antes de alertar
PROTHEUS_PORTA_SERVICO = 1000  # porta real do webapp do Protheus (nao a 443)
PROTHEUS_SITE_HOST = "protheus.elcop.eng.br"
PROTHEUS_SITE_CAMINHO = "/webapp/"


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


async def fazer_ping_duplo_via_pfsense(ip1: str, ip2: str, quantidade: int = QUANTIDADE_PINGS,
                                        host: str = None, usuario: str = None, apelido: str = "pfSense"):
    """Roda dois pings (Protheus e Google) numa unica conexao SSH num
    pfSense, pra comparar as duas origens vistas de la - se so o Protheus
    cair e o Google nao, o problema e especifico dele; se os dois carem
    juntos, o problema e da rede/rota desse pfSense ate a internet.

    Por padrao usa o pfSense da matriz; passe host/usuario pra rodar contra
    outro (ex: o do Patio 2).

    Retorna ((perda1, latencia1), (perda2, latencia2)). Se o proprio SSH
    falhar/travar (nao conseguiu nem conectar), retorna (None, None) pros
    dois - assim a gente nao confunde "SSH deu problema" com "Protheus (ou
    Google) caiu", o que geraria falso alarme."""
    host = host or settings.pfsense_host
    usuario = usuario or PFSENSE_SSH_USER
    separador = "___SEPARADOR_PING___"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-i", PFSENSE_SSH_KEY,
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            "-o", "BatchMode=yes",
            f"{usuario}@{host}",
            f"ping -c {quantidade} {ip1}; echo {separador}; ping -c {quantidade} {ip2}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=quantidade * 2 * 3 + 15)
        saida = stdout.decode(errors="ignore")

        if separador not in saida:
            erro = stderr.decode(errors="ignore").strip()[:200]
            print(f"AVISO {apelido} SSH: nao conseguiu executar os pings (stderr: {erro})")
            return (None, None), (None, None)

        saida1, saida2 = saida.split(separador, 1)
        return _extrair_perda_e_latencia(saida1), _extrair_perda_e_latencia(saida2)
    except Exception as e:
        print(f"AVISO {apelido} SSH: excecao ao executar pings ({e})")
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


async def testar_site_protheus(timeout: float = 8.0) -> str:
    """Faz uma requisicao HTTPS de verdade no site do Protheus (nao so abre a
    porta) - confirma que o servico web responde de fato. So e chamado no
    momento de confirmar uma queda, nao a cada ciclo. Retorna uma string
    pronta pra mensagem, com check/X visual."""
    import ssl
    try:
        contexto = ssl.create_default_context()
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(PROTHEUS_SITE_HOST, PROTHEUS_PORTA_SERVICO, ssl=contexto),
            timeout=timeout,
        )
        pedido = (
            f"GET {PROTHEUS_SITE_CAMINHO} HTTP/1.1\r\n"
            f"Host: {PROTHEUS_SITE_HOST}\r\nConnection: close\r\n\r\n"
        )
        writer.write(pedido.encode())
        await writer.drain()
        resposta = await asyncio.wait_for(reader.read(200), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        primeira_linha = resposta.decode(errors="ignore").splitlines()[0] if resposta else ""
        if primeira_linha.startswith("HTTP/"):
            partes = primeira_linha.split(" ")
            codigo = partes[1] if len(partes) > 1 else "?"
            return f"✅ Site respondeu (HTTP {codigo})"
        return "❌ Site não respondeu com um HTTP válido"
    except Exception as e:
        return f"❌ Site não respondeu ({type(e).__name__})"


async def verificar_saude_app_protheus(timeout: float = 8.0):
    """Faz uma requisicao HTTPS real no site do Protheus e considera saudavel
    so quando a resposta vem com um HTTP 2xx/3xx. Detecta quedas da
    APLICACAO (ex: manutencao, erro interno) mesmo quando rede, ping e porta
    TCP continuam OK - o que o teste de ping/porta sozinho nao pega."""
    import ssl
    CRLF = chr(13) + chr(10)
    try:
        contexto = ssl.create_default_context()
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(PROTHEUS_SITE_HOST, PROTHEUS_PORTA_SERVICO, ssl=contexto),
            timeout=timeout,
        )
        pedido = (
            "GET " + PROTHEUS_SITE_CAMINHO + " HTTP/1.1" + CRLF
            + "Host: " + PROTHEUS_SITE_HOST + CRLF + "Connection: close" + CRLF + CRLF
        )
        writer.write(pedido.encode())
        await writer.drain()
        resposta = await asyncio.wait_for(reader.read(200), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        primeira_linha = resposta.decode(errors="ignore").splitlines()[0] if resposta else ""
        if primeira_linha.startswith("HTTP/"):
            partes = primeira_linha.split(" ")
            codigo = partes[1] if len(partes) > 1 else "?"
            if codigo.isdigit() and 200 <= int(codigo) < 400:
                return True, "HTTP " + codigo
            return False, "HTTP " + codigo
        return False, "resposta sem HTTP valido"
    except Exception as e:
        return False, type(e).__name__


def _analisar_traceroute(saida: str, ip_destino: str):
    """Extrai do traceroute: se chegou no destino, ate qual salto respondeu,
    e o IP desse ultimo salto (usado pra identificar o equipamento/provedor
    onde a rota parou). Usado tanto pro diagnostico curto quanto pro completo."""
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
        return None

    total_saltos = len(hops)
    chegou_no_destino = any(ip_hop == ip_destino for _, ip_hop in hops)
    hops_com_resposta = [(n, ip_hop) for n, ip_hop in hops if ip_hop]
    ultimo_respondeu = max((n for n, _ in hops_com_resposta), default=0)
    ip_ultimo_respondeu = next((ip_hop for n, ip_hop in hops_com_resposta if n == ultimo_respondeu), None)
    return chegou_no_destino, ultimo_respondeu, total_saltos, ip_ultimo_respondeu


def resumir_culpa_traceroute(saida: str, ip_destino: str) -> str:
    """Frase curta de culpa, pra usar logo no comeco do alerta."""
    analise = _analisar_traceroute(saida, ip_destino)
    if analise is None:
        return "não foi possível identificar de onde vem o problema"
    chegou_no_destino, ultimo_respondeu, total_saltos, _ip_ultimo = analise
    if chegou_no_destino:
        return "Problema Protheus"
    if ultimo_respondeu <= 2:
        return "Problema rede interna"
    return "Problema no trajeto"


def diagnosticar_traceroute(saida: str, ip_destino: str) -> str:
    """Texto completo do diagnostico, pra secao 'Diagnostico' do alerta."""
    analise = _analisar_traceroute(saida, ip_destino)
    if analise is None:
        return "⚪ Não deu pra interpretar o traceroute (saída vazia ou em formato inesperado)."
    chegou_no_destino, ultimo_respondeu, total_saltos, _ip_ultimo = analise

    if chegou_no_destino:
        return (
            "🔴 Problema Protheus — rede até lá está OK, a falha é no "
            "servidor/aplicação deles."
        )
    if ultimo_respondeu <= 2:
        return (
            f"🟡 Problema rede interna — a conexão já falha logo no início "
            f"(salto {ultimo_respondeu} de {total_saltos}), do nosso lado "
            f"(rede ou provedor daqui)."
        )
    return (
        f"🟠 Problema no trajeto — a rota avança bastante (salto "
        f"{ultimo_respondeu} de {total_saltos}) mas não chega no destino, "
        f"indicando falha no meio do caminho da internet, mais perto do "
        f"lado do Protheus."
    )


def _nome_equipamento_conhecido(ip: str):
    """Se o IP for um equipamento nosso conhecido (firewalls), retorna o
    nome amigavel. Senao, None."""
    if not ip:
        return None
    if ip == getattr(settings, "pfsense_host", None):
        return "Firewall Matriz"
    if ip == getattr(settings, "pfsense2_host", None):
        return "Firewall Pátio 2"
    return None


async def _resolver_nome_ip(ip: str) -> str:
    """Da um nome amigavel pro IP de um salto do traceroute: equipamento
    nosso conhecido (Firewall Matriz/Pátio 2), ou reverse DNS (PTR) pra
    tentar identificar o provedor de internet quando o salto e externo.
    Se nada funcionar, devolve o proprio IP."""
    if not ip:
        return "ponto desconhecido"

    nome_conhecido = _nome_equipamento_conhecido(ip)
    if nome_conhecido:
        return f"{nome_conhecido} ({ip})"

    try:
        hostname = await asyncio.wait_for(
            asyncio.to_thread(socket.gethostbyaddr, ip), timeout=3.0
        )
        ptr = hostname[0].lower()
        provedores = {
            "vivo": "Vivo", "telefonica": "Vivo", "claro": "Claro", "embratel": "Claro",
            "oi.net": "Oi", "veloxzone": "Oi", "tim": "TIM", "algar": "Algar",
            "brasiltelecom": "Oi",
        }
        for chave, nome_provedor in provedores.items():
            if chave in ptr:
                return f"{nome_provedor} ({ip})"
        return f"{ptr} ({ip})"
    except Exception:
        return ip


async def montar_causa_evento(saida_traceroute: str, ip_destino: str):
    """Monta a causa de uma queda pro texto do resumo/alerta. Retorna
    (tipo, texto) onde tipo e um de 'protheus'/'rede_interna'/'trajeto'/
    'desconhecido', pra permitir contar por categoria no resumo."""
    analise = _analisar_traceroute(saida_traceroute, ip_destino)
    if analise is None:
        return "desconhecido", "não foi possível identificar a causa (traceroute sem dados)"

    chegou_no_destino, ultimo_respondeu, total_saltos, ip_ultimo_respondeu = analise

    if chegou_no_destino:
        return "protheus", f"Protheus não respondeu (servidor {ip_destino})"

    nome_ponto = await _resolver_nome_ip(ip_ultimo_respondeu)

    if ultimo_respondeu <= 2:
        return "rede_interna", f"rede interna — {nome_ponto} não respondeu"

    return "trajeto", f"{nome_ponto} — caminho entre rede interna e Protheus"


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
_porta_fechada_vista_na_janela = False
_confirmacao_externa_vista_na_janela = False
_app_offline_desde = None
_alerta_app_confirmado_enviado = False


async def verificar_protheus(db):
    global _confirmado_offline_desde, _alerta_confirmado_enviado
    global _porta_fechada_vista_na_janela, _confirmacao_externa_vista_na_janela
    global _app_offline_desde, _alerta_app_confirmado_enviado

    (
        (perda, latencia),
        (perda_ref, latencia_ref),
        ((perda_pfsense, latencia_pfsense), (perda_pfsense_ref, latencia_pfsense_ref)),
        ((perda_patio2, latencia_patio2), (perda_patio2_ref, latencia_patio2_ref)),
        porta_servico_ok,
    ) = await asyncio.gather(
        fazer_ping(settings.protheus_ip),
        fazer_ping(REFERENCIA_IP),
        fazer_ping_duplo_via_pfsense(settings.protheus_ip, REFERENCIA_IP),
        fazer_ping_duplo_via_pfsense(
            settings.protheus_ip, REFERENCIA_IP,
            host=settings.pfsense2_host, usuario=PATIO2_SSH_USER, apelido="Patio2",
        ),
        testar_porta_protheus(settings.protheus_ip),
    )
    estado_pelo_ping = classificar_estado(perda)
    if estado_pelo_ping != "online" and porta_servico_ok:
        # Ping falhou mas a porta do servico respondeu - isso e sinal de ICMP
        # instavel/deprorizado, nao de queda real. Nao conta como offline.
        novo_estado = "online"
    else:
        novo_estado = estado_pelo_ping
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

    causa_tipo = None
    causa_detalhe = None
    if mudou_estado and estado_anterior == "online" and novo_estado != "online":
        try:
            traceroute_saida_evento = await fazer_traceroute(settings.protheus_ip)
            causa_tipo, causa_detalhe = await montar_causa_evento(traceroute_saida_evento, settings.protheus_ip)
        except Exception as e:
            print(f"AVISO: falha ao calcular causa da queda ({e})")

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
        patio2_perda_percentual=perda_patio2,
        patio2_latencia_ms=latencia_patio2,
        patio2_referencia_perda_percentual=perda_patio2_ref,
        patio2_referencia_latencia_ms=latencia_patio2_ref,
        causa_tipo=causa_tipo,
        causa_detalhe=causa_detalhe,
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
    confirmacao_externa = (
        (perda_pfsense is not None and classificar_estado(perda_pfsense) == "offline")
        or (perda_patio2 is not None and classificar_estado(perda_patio2) == "offline")
    )
    eops_offline_agora = classificar_estado(perda) == "offline"

    if eops_offline_agora:
        if _confirmado_offline_desde is None:
            _confirmado_offline_desde = agora
            _alerta_confirmado_enviado = False
            _porta_fechada_vista_na_janela = False
            _confirmacao_externa_vista_na_janela = False

        if porta_servico_ok is False:
            _porta_fechada_vista_na_janela = True
        if confirmacao_externa:
            _confirmacao_externa_vista_na_janela = True

        duracao_confirmada = (agora - _confirmado_offline_desde).total_seconds()

        if (
            duracao_confirmada >= MINUTOS_PARA_ALERTA_CONFIRMADO * 60
            and _porta_fechada_vista_na_janela
            and _confirmacao_externa_vista_na_janela
            and not _alerta_confirmado_enviado
        ):
            traceroute_saida = await fazer_traceroute(settings.protheus_ip)
            causa_tipo_alerta, causa_detalhe_alerta = await montar_causa_evento(traceroute_saida, settings.protheus_ip)
            site_status = await testar_site_protheus()

            origens_confirmando = []
            if perda_pfsense is not None and classificar_estado(perda_pfsense) == "offline":
                origens_confirmando.append("Firewall Matriz")
            if perda_patio2 is not None and classificar_estado(perda_patio2) == "offline":
                origens_confirmando.append("Firewall Pátio 2")
            texto_origens = " e ".join(origens_confirmando) if origens_confirmando else "nenhuma origem externa disponível"

            google_pi_ok = perda_ref < 50
            google_pfsense_ok = perda_pfsense_ref is not None and perda_pfsense_ref < 50
            google_patio2_ok = perda_patio2_ref is not None and perda_patio2_ref < 50

            if not google_pi_ok or not google_pfsense_ok or (perda_patio2_ref is not None and not google_patio2_ok):
                nota_google = (
                    "⚠️ O Google também está com perda em pelo menos uma origem agora "
                    "— sinal extra de instabilidade geral."
                )
            else:
                nota_google = "✅ Google respondendo normal em todas as origens — nossa internet está OK."

            msg_confirmado = (
                f"🔴🔴 *InfraOps Center — QUEDA CONFIRMADA DO PROTHEUS*\n\n"
                f"🖥️ *Protheus offline há {MINUTOS_PARA_ALERTA_CONFIRMADO}+ min*\n"
                f"Rota parou em: {causa_detalhe_alerta}\n"
                f"Confirmado por: E-Ops, porta do serviço, {texto_origens}\n\n"
                f"{nota_google}\n\n"
                f"*Pings no momento da confirmação:*\n"
                f"📍 E-Ops → Protheus: {_fmt_ping(perda, latencia)}\n"
                f"📍 E-Ops → Google: {_fmt_ping(perda_ref, latencia_ref)}\n"
                f"📍 Firewall Matriz → Protheus: {_fmt_ping(perda_pfsense, latencia_pfsense)}\n"
                f"📍 Firewall Matriz → Google: {_fmt_ping(perda_pfsense_ref, latencia_pfsense_ref)}\n"
                f"📍 Firewall Pátio 2 → Protheus: {_fmt_ping(perda_patio2, latencia_patio2)}\n"
                f"📍 Firewall Pátio 2 → Google: {_fmt_ping(perda_patio2_ref, latencia_patio2_ref)}\n"
                f"🔌 Porta {PROTHEUS_PORTA_SERVICO} (webapp): {'aberta' if porta_servico_ok else 'FECHADA/recusada'}\n"
                f"🌐 Acesso ao site: {site_status}\n\n"
                f"*Traceroute até o Protheus:*\n"
                f"```\n{traceroute_saida[:1500]}\n```\n\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
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
                f"🟢 *Protheus voltou* — ficou offline por {duracao_total_str}\n"
                f"Confirmado por: E-Ops voltando a responder\n\n"
                f"🕐 *Horário:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            await enviar_telegram(msg_recuperado)
        _confirmado_offline_desde = None
        _alerta_confirmado_enviado = False
        _porta_fechada_vista_na_janela = False
        _confirmacao_externa_vista_na_janela = False

    # --- Verificacao separada: saude da APLICACAO Protheus via HTTP ---
    # Roda em paralelo a checagem de rede acima. Cobre o caso em que rede,
    # porta TCP e ping estao todos OK mas o webapp em si nao responde certo
    # (erro 5xx, manutencao, timeout na aplicacao) - isso a checagem de rede
    # sozinha nunca detecta.
    app_ok, app_detalhe = await verificar_saude_app_protheus()

    if not app_ok:
        if _app_offline_desde is None:
            _app_offline_desde = agora

        duracao_app = (agora - _app_offline_desde).total_seconds()

        if duracao_app >= MINUTOS_PARA_ALERTA_APP * 60 and not _alerta_app_confirmado_enviado:
            msg_app = (
                "🟠 *InfraOps Center — PROTHEUS (APLICAÇÃO) INDISPONÍVEL*" + '\n\n' +
                "🖥️ Site/webapp do Protheus não responde corretamente há " + str(MINUTOS_PARA_ALERTA_APP) + "+ min" + '\n' +
                "Detalhe: " + app_detalhe + '\n\n' +
                "✅ Rede, porta " + str(PROTHEUS_PORTA_SERVICO) + " e ping continuam OK — o problema é na aplicação (ex: manutenção, erro interno), não na rede/infraestrutura." + '\n\n' +
                "🕐 *Horário:* " + datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            )
            await enviar_telegram(msg_app)
            _alerta_app_confirmado_enviado = True
    else:
        if _alerta_app_confirmado_enviado:
            duracao_app_total_str = (
                _formatar_duracao((agora - _app_offline_desde).total_seconds())
                if _app_offline_desde else "tempo desconhecido"
            )
            msg_app_recuperado = (
                "🟢 *Protheus (aplicação) voltou* — ficou indisponível por " + duracao_app_total_str + '\n\n' +
                "🕐 *Horário:* " + datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            )
            await enviar_telegram(msg_app_recuperado)
        _app_offline_desde = None
        _alerta_app_confirmado_enviado = False


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
            atual = {
                "estado": estado_r, "inicio": r.verificado_em, "fim": None,
                "duracao_segundos": None, "causa_tipo": None, "causa_detalhe": None,
            }
        if atual.get("causa_tipo") is None and getattr(r, "causa_tipo", None):
            atual["causa_tipo"] = r.causa_tipo
            atual["causa_detalhe"] = r.causa_detalhe
    if atual is not None:
        atual["fim"] = fim
        atual["duracao_segundos"] = (atual["fim"] - atual["inicio"]).total_seconds()
        eventos.append(atual)
    resultado = [e for e in eventos if e["estado"] not in ("online", "desconhecido")]
    # quedas coladas uma na outra (mesmo evento na pratica, so dividido por
    # causa da classificacao de estado mudar no meio) herdam a causa da vizinha
    for i, seg in enumerate(resultado):
        if seg["causa_tipo"] is not None:
            continue
        if i > 0 and resultado[i - 1]["fim"] == seg["inicio"] and resultado[i - 1]["causa_tipo"] is not None:
            seg["causa_tipo"] = resultado[i - 1]["causa_tipo"]
            seg["causa_detalhe"] = resultado[i - 1]["causa_detalhe"]
            continue
        if i < len(resultado) - 1 and resultado[i + 1]["inicio"] == seg["fim"] and resultado[i + 1]["causa_tipo"] is not None:
            seg["causa_tipo"] = resultado[i + 1]["causa_tipo"]
            seg["causa_detalhe"] = resultado[i + 1]["causa_detalhe"]
    return resultado


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
        if q.get("causa_detalhe"):
            linha += f"\n  Rota parou em: {q['causa_detalhe']}"
        elif q.get("google_pct") is not None:
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
    quedas_patio2 = _agrupar_quedas(registros, lambda r: r.patio2_perda_percentual, fim)

    for q in quedas_eops:
        q["google_pct"] = _media_perda_no_intervalo(
            registros, lambda r: r.referencia_perda_percentual, q["inicio"], q["fim"]
        )

    for q in quedas_pfsense:
        q["google_pct"] = _media_perda_no_intervalo(
            registros, lambda r: r.pfsense_referencia_perda_percentual, q["inicio"], q["fim"]
        )

    for q in quedas_patio2:
        q["google_pct"] = _media_perda_no_intervalo(
            registros, lambda r: r.patio2_referencia_perda_percentual, q["inicio"], q["fim"]
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
    tempo_total_patio2 = sum(q["duracao_segundos"] for q in quedas_patio2)
    coincidiu_com_rede = any(_coincidiu_eops(q) for q in quedas_eops)

    checagens_porta = [r.porta_servico_ok for r in registros if r.porta_servico_ok is not None]
    falhas_porta = sum(1 for ok in checagens_porta if not ok)

    status_atual = await get_protheus_status_atual(db)

    msg = f"🔔 *InfraOps Center — Resumo Protheus ({rotulo})*\n\n"
    msg += f"📅 *Período:* {inicio.astimezone().strftime('%d/%m %H:%M')} → {fim.astimezone().strftime('%d/%m %H:%M')}\n\n"

    if not quedas_eops and not quedas_pfsense and not quedas_patio2:
        msg += "✅ *Nenhuma queda registrada por nenhuma das origens — 100% online no período*\n"
    else:
        msg += f"📍 *E-Ops — {len(quedas_eops)} queda(s):*\n"
        if quedas_eops:
            msg += _formatar_lista_quedas(quedas_eops) + "\n"
            msg += f"⏱️ Tempo total (E-Ops): {_formatar_duracao(tempo_total_eops)}\n"
        else:
            msg += "✅ Nenhuma queda vista pelo E-Ops\n"

        msg += f"\n📍 *Firewall Matriz — {len(quedas_pfsense)} queda(s):*\n"
        if quedas_pfsense:
            msg += _formatar_lista_quedas(quedas_pfsense) + "\n"
            msg += f"⏱️ Tempo total (Firewall Matriz): {_formatar_duracao(tempo_total_pfsense)}\n"
        else:
            msg += "✅ Nenhuma queda vista pelo Firewall Matriz\n"

        msg += f"\n📍 *Firewall Pátio 2 — {len(quedas_patio2)} queda(s):*\n"
        if quedas_patio2:
            msg += _formatar_lista_quedas(quedas_patio2) + "\n"
            msg += f"⏱️ Tempo total (Firewall Pátio 2): {_formatar_duracao(tempo_total_patio2)}\n"
        else:
            msg += "✅ Nenhuma queda vista pelo Firewall Pátio 2\n"

        if checagens_porta:
            msg += f"\n🔌 *Porta {PROTHEUS_PORTA_SERVICO} (serviço):* falhou em {falhas_porta}/{len(checagens_porta)} verificações no período\n"

        msg += "\n"
        if coincidiu_com_rede:
            msg += "🌐 *Atenção: pelo menos uma queda do E-Ops coincidiu com problema na nossa rede/AP ou perda pro Google*\n"
        else:
            msg += "🌐 Nenhuma queda coincidiu com problema na nossa rede\n"

        contagem_causas = {}
        for q in quedas_eops:
            tipo = q.get("causa_tipo") or "desconhecido"
            contagem_causas[tipo] = contagem_causas.get(tipo, 0) + 1
        total_causas = sum(contagem_causas.values())
        if total_causas:
            rotulos_causa = {
                "protheus": "🔴 Protheus",
                "rede_interna": "🏢 Rede interna",
                "trajeto": "🌎 Rota/ambiente Protheus",
                "desconhecido": "⚪ Não identificado",
            }
            msg += "\n📊 *Causas:*\n"
            for tipo, qtd in sorted(contagem_causas.items(), key=lambda x: -x[1]):
                pct = (qtd / total_causas) * 100
                msg += f"{rotulos_causa.get(tipo, tipo)} ...... {qtd} ({pct:.0f}%)\n"

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

            if agora_local.hour in (7, 22) and _ultimo_resumo_protheus_enviado != marcador:
                fim = datetime.now(timezone.utc)
                if agora_local.hour == 7:
                    inicio = fim - timedelta(hours=9)  # 22h de ontem -> 7h de hoje
                    rotulo = "madrugada"
                else:
                    inicio = fim - timedelta(hours=15)  # 7h de hoje -> 22h de hoje
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
