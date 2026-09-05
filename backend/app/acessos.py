import asyncio
import ipaddress
import json
from datetime import datetime, timedelta, timezone

import paramiko
import re
from sqlalchemy import delete, func, select, update

from app.config import settings
from app.models import AcessoDominio, SuricataFlowSni, SuricataSyncEstado

PFSENSE_SSH_USER = "infraops-readonly"
PFSENSE_SSH_KEY_PATH = "/home/appuser/.ssh/pfsense_readonly"
EVE_JSON_REMOTE_PATH = "/var/log/suricata/suricata_igc046238/eve.json"

LAN_CIDRS = [ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("10.0.0.0/8")]
OPENVPN_LOG_REMOTE_PATH = "/var/log/openvpn.log"
_cache_ip_dinamico_excluido = {"ip": None}

# Nao filtra nada - todo dominio capturado e gravado do mesmo jeito. Isso so
# decide o rotulo amigavel (campo "categoria") usado pra agrupar visualmente
# no grafico de top sites. O que nao bate com nada aqui cai em "Outros", mas
# continua gravado com o dominio real.
CATEGORIAS = [
    # --- Google / infraestrutura Google ---
    (["youtube.com", "googlevideo.com", "ytimg.com", "youtu.be"], "YouTube"),
    (["gmail.com", "mail.google.com"], "Gmail"),
    (["drive.google.com", "docs.google.com"], "Google Drive/Docs"),
    (["doubleclick.net", "googlesyndication.com", "googleadservices.com",
      "googletagmanager.com", "google-analytics.com"], "Google Ads/Analytics"),
    (["googleapis.com", "gstatic.com", "googleusercontent.com", "google.com",
      "google.com.br", "1e100.net"], "Google (geral)"),

    # --- Microsoft ---
    (["office365.com", "office.com", "office.net", "microsoftonline.com", "live.com",
      "outlook.com", "outlook.office365.com"], "Microsoft 365 / Outlook"),
    (["sharepoint.com", "onedrive.com"], "SharePoint / OneDrive"),
    (["teams.microsoft.com", "teams.live.com"], "Microsoft Teams"),
    (["windowsupdate.com", "update.microsoft.com", "delivery.mp.microsoft.com"], "Windows Update"),
    (["microsoft.com", "msn.com", "bing.com", "azure.com", "azureedge.net", "static.microsoft", "wns.windows.com"], "Microsoft (geral)"),

    # --- Redes sociais / mensageria ---
    (["whatsapp.com", "whatsapp.net"], "WhatsApp"),
    (["instagram.com", "cdninstagram.com"], "Instagram"),
    (["facebook.com", "fbcdn.net", "fbsbx.com", "messenger.com"], "Facebook / Messenger"),
    (["tiktok.com", "tiktokcdn.com", "tiktokv.com", "byteoversea.com", "musical.ly", "ttwstatic.com"], "TikTok"),
    (["twitter.com", "x.com", "twimg.com"], "X (Twitter)"),
    (["linkedin.com", "licdn.com"], "LinkedIn"),
    (["telegram.org", "t.me", "telegram.me"], "Telegram"),
    (["discord.com", "discord.gg", "discordapp.com", "discordapp.net"], "Discord"),
    (["snapchat.com", "sc-cdn.net"], "Snapchat"),
    (["pinterest.com", "pinimg.com"], "Pinterest"),
    (["reddit.com", "redd.it", "redditstatic.com"], "Reddit"),

    # --- Streaming / video / musica ---
    (["netflix.com", "nflxvideo.net", "nflximg.net"], "Netflix"),
    (["twitch.tv", "ttvnw.net", "jtvnw.net"], "Twitch"),
    (["spotify.com", "spotifycdn.com", "scdn.co"], "Spotify"),
    (["disneyplus.com", "disney-plus.net", "bamgrid.com"], "Disney+"),
    (["primevideo.com", "amazonvideo.com"], "Prime Video"),
    (["globoplay.globo.com", "globo.com", "glbimg.com"], "Globo / Globoplay"),
    (["deezer.com"], "Deezer"),

    # --- Videoconferencia ---
    (["zoom.us", "zoomgov.com"], "Zoom"),
    (["meet.google.com"], "Google Meet"),
    (["webex.com"], "Webex"),

    # --- Nuvem / dev / infraestrutura ---
    (["github.com", "githubusercontent.com", "githubassets.com"], "GitHub"),
    (["gitlab.com"], "GitLab"),
    (["amazonaws.com", "aws.amazon.com", "cloudfront.net"], "Amazon AWS"),
    (["cloudflare.com", "cloudflare.net", "cloudflareinsights.com"], "Cloudflare (CDN)"),
    (["akamai.net", "akamaiedge.net", "akamaitechnologies.com"], "Akamai (CDN)"),
    (["fastly.net"], "Fastly (CDN)"),
    (["dropbox.com", "dropboxusercontent.com"], "Dropbox"),
    (["icloud.com", "apple.com", "mzstatic.com", "apple-dns.net"], "Apple / iCloud"),

    # --- Antivirus / atualizacoes ---
    (["avast.com", "avg.com"], "Antivirus (Avast/AVG)"),
    (["kaspersky.com"], "Antivirus (Kaspersky)"),
    (["adobe.com", "adobedtm.com"], "Adobe"),

    # --- E-commerce ---
    (["mercadolivre.com", "mercadolibre.com", "mlstatic.com"], "Mercado Livre"),
    (["amazon.com", "amazon.com.br"], "Amazon (loja)"),
    (["shopee.com.br", "shopee.com"], "Shopee"),
    (["magazineluiza.com.br", "magalu.com"], "Magazine Luiza"),
    (["aliexpress.com", "alicdn.com"], "AliExpress"),

    # --- Bancos / pagamentos (BR) ---
    (["bb.com.br"], "Banco do Brasil"),
    (["itau.com.br"], "Itaú"),
    (["bradesco.com.br", "bradesconetempresa.b.br"], "Bradesco"),
    (["caixa.gov.br"], "Caixa"),
    (["santander.com.br"], "Santander"),
    (["nubank.com.br", "nu.com.br"], "Nubank"),
    (["pagseguro.uol.com.br", "pagbank.com.br"], "PagSeguro/PagBank"),
    (["paypal.com"], "PayPal"),
    (["mercadopago.com", "mercadopago.com.br"], "Mercado Pago"),

    # --- Apostas / jogos de azar ---
    (["bet365.com", "betano.com", "sportingbet.com", "blaze.com", "stake.com",
      "pixbet.com", "kto.com", "betfair.com", "betnacional.com", "1xbet.com",
      "vaidebet.com", "betsson.com", "rivalo.com", "esportesdasorte.bet"], "Apostas / Jogos de azar"),

    # --- Conteudo adulto ---
    (["pornhub.com", "xvideos.com", "xnxx.com", "redtube.com", "youporn.com",
      "xhamster.com", "brazzers.com", "onlyfans.com"], "Conteúdo adulto"),

    # --- Jogos ---
    (["steampowered.com", "steamcontent.com", "steamstatic.com"], "Steam"),
    (["epicgames.com", "unrealengine.com"], "Epic Games"),
    (["playstation.com", "playstation.net"], "PlayStation Network"),
    (["xbox.com", "xboxlive.com"], "Xbox Live"),

    # --- Noticias / portais BR ---
    (["uol.com.br"], "UOL"),
    (["g1.globo.com"], "G1"),
    (["terra.com.br"], "Terra"),

    # --- Sistemas corporativos (TOTVS) - ajustar quando virem os dominios reais ---
    (["fluig", "totvs.com.br", "totvs.com", "totvs.io"], "Fluig / TOTVS"),
    (["protheus"], "Protheus"),

    # --- Ferramentas de terceiros usadas na empresa ---
    (["pythonhosted.org", "pypi.org"], "Python / PyPI (dev)"),
    (["ituran.com.br"], "Ituran (rastreamento veicular)"),
    (["uipath.com"], "UiPath (RPA)"),
    (["tiendanube.com"], "Tiendanube"),
    (["ilovepdf.com"], "iLovePDF (ferramenta online)"),
    (["mcafee.com"], "McAfee (antivirus)"),
    (["docker.io"], "Docker Hub (dev)"),
    (["analysis.windows.net"], "Power BI (Microsoft)"),
    (["skype.com"], "Skype (Microsoft)"),
    (["core.windows.net", "sfx.ms", "cloud.microsoft"], "Microsoft (geral)"),
    (["santandernetibe.com.br"], "Santander"),
    (["gvt2.com"], "Google (Ads/Analytics)"),
    (["we-stats.com"], "TikTok"),
    (["telemetry.mozilla.org", "browser-intake-datadoghq.com", "dc.services.visualstudio.com", "opera-api.com"], "Telemetria / Diagnostico de apps"),
    (["sistemapenalidadeselcop-production.up.railway.app", "elcop-ejourney.up.railway.app"], "Sistemas internos Elcop"),

    # --- Infraestrutura interna da Elcop - por ultimo de proposito, so pega
    # o que sobrar e nao bateu em nenhuma categoria mais especifica acima ---
    (["elcop.eng"], "Sistemas internos Elcop"),
]


def categorizar_dominio(dominio: str) -> str:
    d = (dominio or "").lower()
    for termos, nome in CATEGORIAS:
        if any(t in d for t in termos):
            return nome
    return "Outros"


def _eh_ip_lan(ip: str) -> bool:
    try:
        endereco = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(endereco in rede for rede in LAN_CIDRS)


def _parse_timestamp(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S.%f%z")
    except (ValueError, TypeError):
        return None


def _puxar_novas_linhas_sync(offset: int):
    """Conecta via SSH no pfSense e retorna (bytes_novos, novo_offset, tamanho_atual).
    E sincrono (paramiko) - rodar sempre via asyncio.to_thread."""
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cliente.connect(
        hostname=settings.pfsense_host,
        username=PFSENSE_SSH_USER,
        key_filename=PFSENSE_SSH_KEY_PATH,
        timeout=10,
    )
    try:
        _, stdout, _ = cliente.exec_command(f"wc -c < {EVE_JSON_REMOTE_PATH}")
        tamanho_atual = int((stdout.read().decode().strip() or "0"))

        offset_efetivo = offset
        if tamanho_atual < offset:
            offset_efetivo = 0

        if tamanho_atual <= offset_efetivo:
            return b"", offset_efetivo, tamanho_atual

        _, stdout, _ = cliente.exec_command(f"tail -c +{offset_efetivo + 1} {EVE_JSON_REMOTE_PATH}")
        dados = stdout.read()
        return dados, offset_efetivo + len(dados), tamanho_atual
    finally:
        cliente.close()


def _buscar_ip_dinamico_excluido_sync(identificador: str):
    """Consulta via SSH o log do servico de VPN pra descobrir o IP atualmente
    associado a um identificador especifico. Sincrono (paramiko) - rodar via
    asyncio.to_thread. Retorna None se nao encontrar nada (ex: sem conexao ativa)."""
    if not identificador:
        return None
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cliente.connect(
        hostname=settings.pfsense_host,
        username=PFSENSE_SSH_USER,
        key_filename=PFSENSE_SSH_KEY_PATH,
        timeout=10,
    )
    try:
        comando = (
            f"grep -a {identificador!r} {OPENVPN_LOG_REMOTE_PATH} | "
            f"grep -a 'MULTI_sva' | tail -1"
        )
        _, stdout, _ = cliente.exec_command(comando)
        linha = stdout.read().decode(errors="ignore").strip()
        if not linha:
            return None
        match = re.search(r"IPv4=([0-9.]+)", linha)
        return match.group(1) if match else None
    finally:
        cliente.close()


async def _obter_ips_excluidos() -> set:
    """Monta o conjunto de IPs ignorados na captura: uma lista estatica (config)
    mais uma resolucao dinamica (via log de VPN), cacheada e so atualizada
    quando a consulta remota tiver sucesso (evita perder a exclusao se a
    consulta falhar num ciclo)."""
    ips = set()
    if settings.acessos_ips_excluidos:
        ips.update(ip.strip() for ip in settings.acessos_ips_excluidos.split(",") if ip.strip())

    if settings.acessos_cn_vpn_excluido:
        try:
            ip_dinamico = await asyncio.to_thread(
                _buscar_ip_dinamico_excluido_sync, settings.acessos_cn_vpn_excluido
            )
            if ip_dinamico:
                _cache_ip_dinamico_excluido["ip"] = ip_dinamico
        except Exception:
            pass
        if _cache_ip_dinamico_excluido["ip"]:
            ips.add(_cache_ip_dinamico_excluido["ip"])

    return ips


def _buscar_cn_por_ip_sync(ip: str):
    """Consulta via SSH o log da VPN pra descobrir qual Common Name (nome do
    certificado) esta associado a um IP virtual da VPN num dado momento.
    Sincrono (paramiko) - rodar via asyncio.to_thread. Retorna None se nao
    achar nada (ex: IP nao e de VPN, ou sem conexao recente o suficiente)."""
    if not ip:
        return None
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cliente.connect(
        hostname=settings.pfsense_host,
        username=PFSENSE_SSH_USER,
        key_filename=PFSENSE_SSH_KEY_PATH,
        timeout=10,
    )
    try:
        padrao_busca = f"IPv4={ip},"
        comando = f"grep -a {padrao_busca!r} {OPENVPN_LOG_REMOTE_PATH} | tail -1"
        _, stdout, _ = cliente.exec_command(comando)
        linha = stdout.read().decode(errors="ignore").strip()
        if not linha:
            return None
        match = re.search(r"\]: ([^/\s]+)/\S+ MULTI_sva: pool returned IPv4=", linha)
        return match.group(1) if match else None
    finally:
        cliente.close()


async def buscar_nome_vpn_por_ip(ip: str):
    """Versao assincrona, com protecao contra falha na consulta remota."""
    try:
        return await asyncio.to_thread(_buscar_cn_por_ip_sync, ip)
    except Exception:
        return None


async def recategorizar_dominios_outros(db) -> int:
    """Reprocessa as linhas gravadas como 'Outros' aplicando as regras atuais
    de categorizar_dominio() - util pois a categoria e calculada uma unica vez
    no momento da captura, entao dominios adicionados depois (novas regras)
    nao retroagem sozinhos. Roda automaticamente 1x por dia. Retorna quantas
    linhas foram atualizadas."""
    resultado = await db.execute(
        select(AcessoDominio.id, AcessoDominio.dominio, AcessoDominio.categoria)
        .where(AcessoDominio.categoria == "Outros")
    )
    linhas = resultado.all()
    atualizados = 0
    for id_, dominio, categoria_atual in linhas:
        nova = categorizar_dominio(dominio)
        if nova != categoria_atual:
            await db.execute(
                update(AcessoDominio).where(AcessoDominio.id == id_).values(categoria=nova)
            )
            atualizados += 1
    await db.commit()
    return atualizados


async def _obter_estado(db) -> SuricataSyncEstado:
    resultado = await db.execute(select(SuricataSyncEstado).where(SuricataSyncEstado.id == 1))
    estado = resultado.scalar_one_or_none()
    if estado is None:
        estado = SuricataSyncEstado(id=1, offset_bytes=0)
        db.add(estado)
        await db.commit()
        await db.refresh(estado)
    return estado


async def sincronizar_acessos_suricata(db):
    """Roda periodicamente: puxa via SSH as linhas novas do eve.json do pfSense,
    casa eventos TLS (SNI) com eventos de flow (que trazem duracao e volume) pelo
    flow_id, resolve o dispositivo (mac/hostname) pelo IP via UniFi, categoriza o
    dominio, grava em AcessoDominio e aplica a retencao de 60 dias."""
    from app.unifi import get_todos_clientes

    estado = await _obter_estado(db)
    dados, novo_offset, _tamanho_atual = await asyncio.to_thread(_puxar_novas_linhas_sync, estado.offset_bytes)

    if not dados:
        estado.offset_bytes = novo_offset
        await db.commit()
        return

    resultado_cache = await db.execute(select(SuricataFlowSni))
    cache_sni = {linha.flow_id: linha.sni for linha in resultado_cache.scalars().all()}
    novos_no_cache = {}
    flow_ids_consumidos = set()

    clientes = await get_todos_clientes()
    mapa_clientes = {c["ip"]: c for c in clientes if c.get("ip")}
    ips_excluidos = await _obter_ips_excluidos()

    eventos_para_gravar = []

    for linha in dados.decode("utf-8", errors="ignore").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError:
            continue

        tipo = evento.get("event_type")
        flow_id = evento.get("flow_id")
        if flow_id is None:
            continue
        flow_id = str(flow_id)

        if tipo == "tls":
            sni = evento.get("tls", {}).get("sni")
            if sni:
                cache_sni[flow_id] = sni
                novos_no_cache[flow_id] = sni
            continue

        if tipo != "flow":
            continue

        sni = cache_sni.get(flow_id)
        if not sni:
            continue

        flow_info = evento.get("flow") or {}
        inicio = _parse_timestamp(flow_info.get("start"))
        fim = _parse_timestamp(flow_info.get("end"))
        if not inicio or not fim:
            continue

        src_ip = evento.get("src_ip", "")
        dest_ip = evento.get("dest_ip", "")
        bytes_toserver = flow_info.get("bytes_toserver", 0) or 0
        bytes_toclient = flow_info.get("bytes_toclient", 0) or 0

        if _eh_ip_lan(src_ip):
            ip_dispositivo = src_ip
            bytes_upload, bytes_download = bytes_toserver, bytes_toclient
        elif _eh_ip_lan(dest_ip):
            ip_dispositivo = dest_ip
            bytes_upload, bytes_download = bytes_toclient, bytes_toserver
        else:
            flow_ids_consumidos.add(flow_id)
            continue

        if ip_dispositivo in ips_excluidos:
            flow_ids_consumidos.add(flow_id)
            continue
        cliente = mapa_clientes.get(ip_dispositivo)
        mac = cliente["mac"] if cliente and cliente.get("mac") else f"desconhecido-{ip_dispositivo}"
        hostname = cliente["hostname"] if cliente else "Desconhecido"
        ap = cliente.get("ap") if cliente else None

        eventos_para_gravar.append(AcessoDominio(
            mac=mac,
            ip=ip_dispositivo,
            hostname=hostname,
            ap=ap,
            dominio=sni,
            categoria=categorizar_dominio(sni),
            inicio=inicio,
            fim=fim,
            duracao_segundos=max(0, round((fim - inicio).total_seconds())),
            bytes_download=bytes_download,
            bytes_upload=bytes_upload,
        ))
        flow_ids_consumidos.add(flow_id)

    for evento in eventos_para_gravar:
        db.add(evento)

    for flow_id in flow_ids_consumidos:
        await db.execute(delete(SuricataFlowSni).where(SuricataFlowSni.flow_id == flow_id))
        novos_no_cache.pop(flow_id, None)

    for flow_id, sni in novos_no_cache.items():
        db.add(SuricataFlowSni(flow_id=flow_id, sni=sni))

    limite_cache = datetime.now(timezone.utc) - timedelta(hours=2)
    await db.execute(delete(SuricataFlowSni).where(SuricataFlowSni.criado_em < limite_cache))

    limite_retencao = datetime.now(timezone.utc) - timedelta(days=60)
    await db.execute(delete(AcessoDominio).where(AcessoDominio.inicio < limite_retencao))

    estado.offset_bytes = novo_offset
    await db.commit()


GAP_SESSAO_SEGUNDOS = 300  # flows do mesmo dispositivo+servico com menos que isso entre eles viram uma sessao so


def _fechar_sessao(s):
    duracao = max(0, round((s["fim_dt"] - s["inicio_dt"]).total_seconds()))
    return {
        "mac": s["mac"],
        "hostname": s["hostname"],
        "ip": s["ip"],
        "ap": s["ap"],
        "categoria": s["categoria"] or "Outros",
        "dominio_principal": sorted(s["dominios"])[0],
        "dominios": sorted(s["dominios"]),
        "inicio": s["inicio_dt"].isoformat(),
        "fim": s["fim_dt"].isoformat(),
        "duracao_segundos": duracao,
        "bytes_download": s["bytes_download"],
        "bytes_upload": s["bytes_upload"],
    }


async def get_sessoes_acesso(db, horas: float = 1440, mac: str = None, gap_segundos: int = GAP_SESSAO_SEGUNDOS):
    """Agrupa os flows brutos de AcessoDominio (cada um dura fracoes de segundo)
    em 'sessoes' continuas por mac+categoria: flows do mesmo dispositivo pro
    mesmo servico com menos de gap_segundos de intervalo entre eles viram uma
    sessao so, somando bytes e calculando a duracao real (inicio da primeira
    conexao ate o fim da ultima). Essa e a fonte usada tanto pela linha do
    tempo quanto pelo ranking de duracao por site."""
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    query = select(AcessoDominio).where(AcessoDominio.inicio >= desde)
    if mac:
        query = query.where(AcessoDominio.mac == mac)
    query = query.order_by(AcessoDominio.mac, AcessoDominio.categoria, AcessoDominio.inicio)

    resultado = await db.execute(query)
    linhas = resultado.scalars().all()

    sessoes = []
    atual = None
    for linha in linhas:
        chave = (linha.mac, linha.categoria)
        if atual and atual["_chave"] == chave and (linha.inicio - atual["fim_dt"]).total_seconds() <= gap_segundos:
            atual["fim_dt"] = max(atual["fim_dt"], linha.fim)
            atual["bytes_download"] += linha.bytes_download
            atual["bytes_upload"] += linha.bytes_upload
            atual["dominios"].add(linha.dominio)
        else:
            if atual:
                sessoes.append(_fechar_sessao(atual))
            atual = {
                "_chave": chave,
                "mac": linha.mac,
                "hostname": linha.hostname,
                "ip": linha.ip,
                "ap": linha.ap,
                "categoria": linha.categoria,
                "dominios": {linha.dominio},
                "inicio_dt": linha.inicio,
                "fim_dt": linha.fim,
                "bytes_download": linha.bytes_download,
                "bytes_upload": linha.bytes_upload,
            }
    if atual:
        sessoes.append(_fechar_sessao(atual))

    sessoes.sort(key=lambda s: s["inicio"], reverse=True)
    return sessoes


async def get_atividade_por_hora(db, mac: str, horas: float = 1440):
    """Agrupa as sessoes de um dispositivo por hora do dia (0-23, horario de
    Brasilia), somando duracao e volume - serve pra ver em que horario do dia
    o dispositivo mais acessa a internet."""
    from zoneinfo import ZoneInfo
    fuso_local = ZoneInfo("America/Sao_Paulo")

    sessoes = await get_sessoes_acesso(db, horas=horas, mac=mac)

    baldes = {h: {"hora": h, "acessos": 0, "duracao_segundos": 0, "bytes_total": 0} for h in range(24)}
    for sessao in sessoes:
        inicio_dt = datetime.fromisoformat(sessao["inicio"])
        inicio_local = inicio_dt.astimezone(fuso_local)
        h = inicio_local.hour
        baldes[h]["acessos"] += 1
        baldes[h]["duracao_segundos"] += sessao["duracao_segundos"]
        baldes[h]["bytes_total"] += sessao["bytes_download"] + sessao["bytes_upload"]

    return [baldes[h] for h in range(24)]


async def get_dispositivos_acessos(db, horas: float = 1440):
    """Lista de dispositivos com acessos no periodo, com contagem de sites
    diferentes, volume total e ultima atividade - alimenta a tela de lista
    da aba Acessos."""
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)

    agregados = await db.execute(
        select(
            AcessoDominio.mac,
            func.count(func.distinct(AcessoDominio.dominio)).label("sites_diferentes"),
            func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).label("volume_bytes"),
            func.max(AcessoDominio.fim).label("ultima_atividade"),
        )
        .where(AcessoDominio.inicio >= desde)
        .group_by(AcessoDominio.mac)
    )
    mapa_agregados = {linha.mac: linha for linha in agregados.all()}

    ultimos = await db.execute(
        select(AcessoDominio.mac, AcessoDominio.hostname, AcessoDominio.ip, AcessoDominio.ap)
        .distinct(AcessoDominio.mac)
        .where(AcessoDominio.inicio >= desde)
        .order_by(AcessoDominio.mac, AcessoDominio.inicio.desc())
    )
    mapa_info = {linha.mac: linha for linha in ultimos.all()}

    agora = datetime.now(timezone.utc)
    resultado = []
    for mac, agg in mapa_agregados.items():
        info = mapa_info.get(mac)
        segundos_desde_ultima = (agora - agg.ultima_atividade).total_seconds() if agg.ultima_atividade else None
        resultado.append({
            "mac": mac,
            "hostname": info.hostname if info else "Desconhecido",
            "ip": info.ip if info else "",
            "ap": info.ap if info else None,
            "sites_diferentes": agg.sites_diferentes,
            "volume_bytes": int(agg.volume_bytes or 0),
            "ultima_atividade": agg.ultima_atividade.isoformat() if agg.ultima_atividade else None,
            "ativo_agora": segundos_desde_ultima is not None and segundos_desde_ultima <= 600,
        })
    resultado.sort(key=lambda d: d["volume_bytes"], reverse=True)
    return resultado


async def get_top_sites_rede(db, horas: float = 1440, limite: int = 8):
    """Top categorias/servicos acessados por toda a rede (todos os dispositivos
    somados) no periodo - alimenta o donut da tela de lista."""
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    resultado = await db.execute(
        select(
            AcessoDominio.categoria,
            func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).label("volume_bytes"),
        )
        .where(AcessoDominio.inicio >= desde)
        .group_by(AcessoDominio.categoria)
        .order_by(func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).desc())
        .limit(limite)
    )
    linhas = resultado.all()
    total = sum(l.volume_bytes or 0 for l in linhas)
    return [
        {
            "categoria": l.categoria or "Outros",
            "volume_bytes": int(l.volume_bytes or 0),
            "percentual": round((l.volume_bytes or 0) / total * 100, 1) if total else 0,
        }
        for l in linhas
    ]


# Categorias consideradas "nao corporativas" (lazer/uso pessoal) para fins de
# relatorio - lista heuristica e editavel, usada so pra destacar quem mais
# consome esse tipo de conteudo. Bancos, pagamentos e ferramentas de trabalho
# ficam de fora de proposito por ambiguidade (podem ser uso corporativo real).
CATEGORIAS_NAO_CORPORATIVAS = {
    "Instagram", "Facebook / Messenger", "TikTok", "X (Twitter)", "Telegram",
    "Discord", "Snapchat", "Pinterest", "Reddit",
    "Netflix", "Twitch", "Spotify", "Disney+", "Prime Video", "Globo / Globoplay", "Deezer",
    "Apostas / Jogos de azar", "Conteúdo adulto",
    "Steam", "Epic Games", "PlayStation Network", "Xbox Live",
    "UOL", "G1", "Terra",
    "Mercado Livre", "Amazon (loja)", "Shopee", "Magazine Luiza", "AliExpress",
}


async def get_relatorio_acessos(db, dias: int = 15) -> dict:
    """Monta o resumo de Acessos (internet) pro modulo de relatorios: resumo
    geral (volume total, categoria mais acessada, dispositivos monitorados),
    top sites da rede, ranking de dispositivos por volume total e ranking de
    dispositivos por uso de categorias nao-corporativas (lazer)."""
    horas = dias * 24
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)

    resultado_resumo = await db.execute(
        select(
            func.count(func.distinct(AcessoDominio.mac)),
            func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload),
        ).where(AcessoDominio.inicio >= desde)
    )
    dispositivos_monitorados, volume_total = resultado_resumo.one()
    volume_total = int(volume_total or 0)

    top_sites = await get_top_sites_rede(db, horas=horas, limite=8)
    categoria_mais_acessada = top_sites[0]["categoria"] if top_sites else None

    async def _ranking_por_filtro(filtro_categoria=None):
        condicoes = [AcessoDominio.inicio >= desde]
        if filtro_categoria is not None:
            condicoes.append(AcessoDominio.categoria.in_(filtro_categoria))
        resultado = await db.execute(
            select(
                AcessoDominio.mac,
                func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).label("volume"),
            )
            .where(*condicoes)
            .group_by(AcessoDominio.mac)
            .order_by(func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).desc())
            .limit(10)
        )
        return resultado.all()

    ranking_geral_bruto = await _ranking_por_filtro()
    ranking_pessoal_bruto = await _ranking_por_filtro(CATEGORIAS_NAO_CORPORATIVAS)

    macs_necessarios = {m for m, _ in ranking_geral_bruto} | {m for m, _ in ranking_pessoal_bruto}
    mapa_dispositivo = {}
    if macs_necessarios:
        subq = (
            select(AcessoDominio.mac, AcessoDominio.hostname, AcessoDominio.ip)
            .where(AcessoDominio.mac.in_(macs_necessarios))
            .distinct(AcessoDominio.mac)
            .order_by(AcessoDominio.mac, AcessoDominio.inicio.desc())
        )
        resultado_nomes = await db.execute(subq)
        for mac, hostname, ip in resultado_nomes.all():
            mapa_dispositivo[mac] = {"hostname": hostname, "ip": ip}

    def _montar_linha(mac, volume):
        info = mapa_dispositivo.get(mac, {})
        return {
            "mac": mac,
            "hostname": info.get("hostname") or "Desconhecido",
            "ip": info.get("ip"),
            "volume_bytes": int(volume or 0),
        }

    ranking_geral = [_montar_linha(m, v) for m, v in ranking_geral_bruto]
    ranking_pessoal = [_montar_linha(m, v) for m, v in ranking_pessoal_bruto]

    for linha in ranking_geral:
        resultado_top_cat_geral = await db.execute(
            select(
                AcessoDominio.categoria,
                func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).label("v"),
            )
            .where(
                AcessoDominio.inicio >= desde,
                AcessoDominio.mac == linha["mac"],
            )
            .group_by(AcessoDominio.categoria)
            .order_by(func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).desc())
            .limit(1)
        )
        linha_top_geral = resultado_top_cat_geral.first()
        linha["categoria_principal"] = linha_top_geral[0] if linha_top_geral else None

    for linha in ranking_pessoal:
        resultado_top_cat = await db.execute(
            select(
                AcessoDominio.categoria,
                func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).label("v"),
            )
            .where(
                AcessoDominio.inicio >= desde,
                AcessoDominio.mac == linha["mac"],
                AcessoDominio.categoria.in_(CATEGORIAS_NAO_CORPORATIVAS),
            )
            .group_by(AcessoDominio.categoria)
            .order_by(func.sum(AcessoDominio.bytes_download + AcessoDominio.bytes_upload).desc())
            .limit(1)
        )
        linha_top = resultado_top_cat.first()
        linha["categoria_principal"] = linha_top[0] if linha_top else None

    return {
        "resumo": {
            "volume_total_bytes": volume_total,
            "categoria_mais_acessada": categoria_mais_acessada,
            "dispositivos_monitorados": dispositivos_monitorados or 0,
        },
        "top_sites": top_sites,
        "ranking_geral": ranking_geral,
        "ranking_pessoal": ranking_pessoal,
    }


async def get_detalhe_dispositivo(db, mac: str, horas: float = 1440):
    """Detalhe de um dispositivo: stats gerais, top sites (categoria) por
    volume/duracao e a linha do tempo (sessoes) - alimenta a tela de detalhe
    da aba Acessos."""
    sessoes = await get_sessoes_acesso(db, horas=horas, mac=mac)

    duracao_por_categoria = {}
    volume_por_categoria = {}
    dominios_distintos = set()
    volume_total = 0
    ultima_atividade = None
    hostname = ip = ap = None

    for s in sessoes:
        cat = s["categoria"]
        duracao_por_categoria[cat] = duracao_por_categoria.get(cat, 0) + s["duracao_segundos"]
        vol = s["bytes_download"] + s["bytes_upload"]
        volume_por_categoria[cat] = volume_por_categoria.get(cat, 0) + vol
        volume_total += vol
        dominios_distintos.update(s["dominios"])
        fim_dt = datetime.fromisoformat(s["fim"])
        if ultima_atividade is None or fim_dt > ultima_atividade:
            ultima_atividade = fim_dt
            hostname, ip, ap = s["hostname"], s["ip"], s["ap"]

    top_sites = sorted(
        [
            {
                "categoria": c,
                "duracao_segundos": duracao_por_categoria[c],
                "volume_bytes": volume_por_categoria[c],
            }
            for c in volume_por_categoria
        ],
        key=lambda x: x["volume_bytes"], reverse=True,
    )
    for item in top_sites:
        item["percentual"] = round(item["volume_bytes"] / volume_total * 100, 1) if volume_total else 0

    return {
        "mac": mac,
        "hostname": hostname,
        "ip": ip,
        "ap": ap,
        "sites_diferentes": len(dominios_distintos),
        "volume_total_bytes": volume_total,
        "ultima_atividade": ultima_atividade.isoformat() if ultima_atividade else None,
        "top_sites": top_sites,
        "linha_do_tempo": sessoes[:200],
    }
