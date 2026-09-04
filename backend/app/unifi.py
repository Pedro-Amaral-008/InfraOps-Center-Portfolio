import httpx
from app.config import settings

SITE_ID = "88f7af54-98f8-306a-a1c7-c9349722b1f6"


async def consultar_unifi(endpoint: str, params: dict = None):
    url = f"{settings.unifi_controller_url}/proxy/network/integration/v1/sites/{SITE_ID}/{endpoint}"
    headers = {"X-API-KEY": settings.unifi_api_key}

    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        try:
            response = await client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


async def get_aps_com_clientes():
    devices_data = await consultar_unifi("devices")
    if not devices_data:
        return []

    aps = devices_data.get("data", [])

    todos_clientes = []
    offset = 0
    limit = 200
    while True:
        clientes_data = await consultar_unifi("clients", {"offset": offset, "limit": limit})
        if not clientes_data:
            break
        todos_clientes.extend(clientes_data.get("data", []))
        total = clientes_data.get("totalCount", 0)
        offset += limit
        if offset >= total:
            break

    contagem_por_ap = {}
    for c in todos_clientes:
        if c.get("type") == "WIRELESS":
            uplink = c.get("uplinkDeviceId")
            contagem_por_ap[uplink] = contagem_por_ap.get(uplink, 0) + 1

    resultado = []
    for ap in aps:
        ap_id = ap.get("id")
        resultado.append({
            "nome": ap.get("name", "Desconhecido"),
            "modelo": ap.get("model", ""),
            "status": ap.get("state", "UNKNOWN"),
            "ip": ap.get("ipAddress", ""),
            "mac": ap.get("macAddress", ""),
            "clientes_conectados": contagem_por_ap.get(ap_id, 0),
            "uptime_segundos": ap.get("uptime", 0),
        })

    return resultado


_sessao_unifi = {"cookie": None, "expira_em": 0}


async def _obter_cookie_sessao():
    """Faz login classico (UniFi OS) e guarda o cookie de sessao em cache,
    reaproveitando por ate 1 hora antes de logar de novo."""
    import time
    agora = time.time()
    if _sessao_unifi["cookie"] and agora < _sessao_unifi["expira_em"]:
        return _sessao_unifi["cookie"]

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        try:
            resp = await client.post(
                f"{settings.unifi_controller_url}/api/auth/login",
                json={"username": settings.unifi_username, "password": settings.unifi_password},
            )
            resp.raise_for_status()
            cookie_valor = resp.cookies.get("TOKEN")
            if cookie_valor:
                _sessao_unifi["cookie"] = cookie_valor
                _sessao_unifi["expira_em"] = agora + 3600
                return cookie_valor
        except Exception:
            pass
    return None




LIMITE_MBPS_CONSUMO = 60
DURACAO_MINIMA_SEGUNDOS = 60

_estado_consumo_alto = {}  # mac -> {"desde": timestamp, "avisado": bool}


async def get_top_consumo_clientes(limite: int = 50):
    """Retorna os clientes que mais consomem banda AGORA (taxa em tempo real),
    usando a API classica (session-based) do UniFi. Tambem calcula, por
    cliente, ha quanto tempo ele esta continuamente acima do limite
    (segundos_acima / sustentado), reaproveitado tanto pela tela quanto
    pela checagem de alerta."""
    import time

    cookie = await _obter_cookie_sessao()
    if not cookie:
        return []

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        try:
            resp = await client.get(
                f"{settings.unifi_controller_url}/proxy/network/api/s/default/stat/sta",
                cookies={"TOKEN": cookie},
            )
            resp.raise_for_status()
            clientes = resp.json().get("data", [])
        except Exception:
            return []

    IPS_EXCLUIDOS = {ip.strip() for ip in settings.ips_excluidos_consumo.split(",") if ip.strip()}
    agora = time.time()
    macs_atuais_acima = set()

    resultado = []
    for c in clientes:
        taxa_total = c.get("bytes-r", 0) or 0
        if taxa_total <= 0:
            continue
        ip_cliente = c.get("ip") or c.get("last_ip", "")
        if ip_cliente in IPS_EXCLUIDOS:
            continue

        mac = c.get("mac", "")
        download_mbps = round((c.get("rx_bytes-r", 0) or 0) * 8 / 1_000_000, 2)
        upload_mbps = round((c.get("tx_bytes-r", 0) or 0) * 8 / 1_000_000, 2)
        total_mbps = round(taxa_total * 8 / 1_000_000, 2)

        acima_limite = download_mbps >= LIMITE_MBPS_CONSUMO or upload_mbps >= LIMITE_MBPS_CONSUMO
        segundos_acima = 0
        if acima_limite:
            macs_atuais_acima.add(mac)
            if mac not in _estado_consumo_alto:
                _estado_consumo_alto[mac] = {"desde": agora, "avisado": False, "pico_download": download_mbps, "pico_upload": upload_mbps}
            else:
                _r = _estado_consumo_alto[mac]
                _r["pico_download"] = max(_r["pico_download"], download_mbps)
                _r["pico_upload"] = max(_r["pico_upload"], upload_mbps)
            segundos_acima = agora - _estado_consumo_alto[mac]["desde"]

        resultado.append({
            "hostname": c.get("hostname") or c.get("name") or "Desconhecido",
            "ap": (c.get("last_uplink_name") or "").strip() or None,
            "ip": c.get("ip") or c.get("last_ip", ""),
            "mac": mac,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "total_mbps": total_mbps,
            "segundos_acima": round(segundos_acima),
            "sustentado": segundos_acima >= DURACAO_MINIMA_SEGUNDOS,
        })

    resultado.sort(key=lambda x: x["total_mbps"], reverse=True)
    return resultado[:limite], macs_atuais_acima


def _formatar_duracao(segundos):
    minutos = round(segundos / 60)
    if minutos < 1:
        return f"{round(segundos)} segundos"
    if minutos == 1:
        return "1 minuto"
    return f"{minutos} minutos"


async def verificar_consumo_excessivo(db):
    """Roda com frequencia (a cada ~20s): grava uma amostra de cada cliente
    (para o historico/top semanal) e registra um evento no Feed do Dashboard
    quando um cliente NORMALIZA depois de ter ficado sustentado acima do
    limite - a mensagem entao informa o tempo TOTAL que ele ficou acima,
    nao so o instante em que cruzou o limiar minimo."""
    import time
    from app.models import EventoSistema, ConsumoRedeAmostra

    clientes, macs_atuais_acima = await get_top_consumo_clientes(limite=50)

    for c in clientes:
        db.add(ConsumoRedeAmostra(
            mac=c["mac"], hostname=c["hostname"], ip=c["ip"],
            download_mbps=c["download_mbps"], upload_mbps=c["upload_mbps"],
            ap=c.get("ap"),
        ))
    await db.commit()

    info_por_mac = {c["mac"]: c for c in clientes}
    agora = time.time()

    for mac in list(_estado_consumo_alto.keys()):
        if mac in macs_atuais_acima:
            continue

        # Esse cliente estava sendo rastreado e agora normalizou - se ficou
        # tempo suficiente acima do limite, registra o evento com a duracao real.
        registro = _estado_consumo_alto[mac]
        duracao_total = agora - registro["desde"]
        if duracao_total >= DURACAO_MINIMA_SEGUNDOS:
            c = info_por_mac.get(mac)
            hostname = c["hostname"] if c else mac
            ip = c["ip"] if c else ""
            pico_download = registro.get("pico_download", 0)
            pico_upload = registro.get("pico_upload", 0)
            direcao = "download" if pico_download >= pico_upload else "upload"
            pico_maior = max(pico_download, pico_upload)
            db.add(EventoSistema(
                tipo="atencao",
                mensagem=f"Consumo de rede {hostname} ficou acima de {LIMITE_MBPS_CONSUMO} Mbps por {_formatar_duracao(duracao_total)} (pico {direcao}: {pico_maior:.1f} Mbps)",
                detalhes=f"{ip}" if ip else None,
            ))
            await db.commit()

        del _estado_consumo_alto[mac]


async def get_top_consumo_semanal(db, dias: int = 7, minimo: int = 5):
    """Agrega as amostras coletadas nos ultimos N dias, retornando os
    dispositivos que mais consumiram banda no periodo (media de download +
    upload, em Mbps). Util pra ver quem consome mais 'no geral', nao so
    o instante atual."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, func as sqlfunc
    from app.models import ConsumoRedeAmostra

    limite_data = datetime.now(timezone.utc) - timedelta(days=dias)

    result = await db.execute(
        select(
            ConsumoRedeAmostra.mac,
            sqlfunc.max(ConsumoRedeAmostra.hostname).label("hostname"),
            sqlfunc.max(ConsumoRedeAmostra.ip).label("ip"),
            sqlfunc.avg(ConsumoRedeAmostra.download_mbps).label("download_medio"),
            sqlfunc.avg(ConsumoRedeAmostra.upload_mbps).label("upload_medio"),
            sqlfunc.max(ConsumoRedeAmostra.download_mbps).label("download_pico"),
            sqlfunc.max(ConsumoRedeAmostra.upload_mbps).label("upload_pico"),
            sqlfunc.count(ConsumoRedeAmostra.id).label("amostras"),
        )
        .where(ConsumoRedeAmostra.coletado_em >= limite_data)
        .group_by(ConsumoRedeAmostra.mac)
        .order_by((sqlfunc.avg(ConsumoRedeAmostra.download_mbps) + sqlfunc.avg(ConsumoRedeAmostra.upload_mbps)).desc())
    )
    linhas = result.all()

    resultado = [
        {
            "mac": r.mac,
            "hostname": r.hostname,
            "ip": r.ip,
            "download_medio_mbps": round(r.download_medio, 2),
            "upload_medio_mbps": round(r.upload_medio, 2),
            "download_pico_mbps": round(r.download_pico, 2),
            "upload_pico_mbps": round(r.upload_pico, 2),
            "total_medio_mbps": round(r.download_medio + r.upload_medio, 2),
            "amostras": r.amostras,
        }
        for r in linhas
    ]

    return resultado[:max(minimo, len(resultado))] if len(resultado) >= minimo else resultado


async def get_historico_consumo_agregado(db, minutos: float = 60, num_baldes: int = 150):
    """Agrega as amostras do periodo em ate 'num_baldes' pontos no tempo.

    IMPORTANTE: o "total da rede" de cada ponto e a MEDIA das rodadas de
    coleta dentro daquele intervalo, nao a SOMA de todas as leituras -
    somar leituras ao longo do tempo infla o numero artificialmente (uma
    janela de 24h teria centenas de leituras somadas, um valor sem
    significado real). Uma "rodada de coleta" e o conjunto de amostras de
    todos os dispositivos, coletadas quase no mesmo instante (arredondado
    pro intervalo de coleta mais proximo) - a soma DENTRO da rodada da o
    consumo real da rede naquele instante; a MEDIA dessas rodadas dentro
    do balde de tempo da o valor comparavel ao grafico.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.models import ConsumoRedeAmostra

    limite_data = datetime.now(timezone.utc) - timedelta(minutes=minutos)

    result = await db.execute(
        select(ConsumoRedeAmostra)
        .where(ConsumoRedeAmostra.coletado_em >= limite_data)
        .order_by(ConsumoRedeAmostra.coletado_em)
    )
    amostras = result.scalars().all()

    if not amostras:
        return []

    rodadas = {}
    for a in amostras:
        chave_rodada = int(a.coletado_em.timestamp() // 15)
        if chave_rodada not in rodadas:
            rodadas[chave_rodada] = {"total": 0.0, "timestamp": a.coletado_em, "maior_individual": 0.0, "maior_hostname": None, "maior_ap": None, "maior_mac": None, "maior_download": 0.0, "maior_upload": 0.0}
        r = rodadas[chave_rodada]
        total_amostra = a.download_mbps + a.upload_mbps
        r["total"] += total_amostra
        if total_amostra > r["maior_individual"]:
            r["maior_individual"] = total_amostra
            r["maior_hostname"] = a.hostname
            r["maior_ap"] = a.ap
            r["maior_mac"] = a.mac
            r["maior_download"] = a.download_mbps
            r["maior_upload"] = a.upload_mbps

    rodadas_ordenadas = [rodadas[k] for k in sorted(rodadas.keys())]

    inicio = rodadas_ordenadas[0]["timestamp"]
    fim = rodadas_ordenadas[-1]["timestamp"]
    duracao_total = (fim - inicio).total_seconds() or 1
    tamanho_balde = max(duracao_total / num_baldes, 1)

    baldes = {}
    for r in rodadas_ordenadas:
        indice_balde = int((r["timestamp"] - inicio).total_seconds() / tamanho_balde)
        if indice_balde not in baldes:
            baldes[indice_balde] = {
                "somatorio_total": 0.0, "contagem": 0, "maior_individual": 0.0,
                "maior_hostname": None, "maior_ap": None, "maior_mac": None,
                "maior_download": 0.0, "maior_upload": 0.0, "timestamp": r["timestamp"],
            }
        b = baldes[indice_balde]
        b["somatorio_total"] += r["total"]
        b["contagem"] += 1
        if r["maior_individual"] > b["maior_individual"]:
            b["maior_individual"] = r["maior_individual"]
            b["maior_hostname"] = r["maior_hostname"]
            b["maior_ap"] = r["maior_ap"]
            b["maior_mac"] = r["maior_mac"]
            b["maior_download"] = r["maior_download"]
            b["maior_upload"] = r["maior_upload"]
        b["timestamp"] = r["timestamp"]

    resultado = [
        {
            "timestamp": v["timestamp"].isoformat(),
            "total_mbps": round(v["somatorio_total"] / v["contagem"], 2),
            "pico_hostname": v["maior_hostname"],
            "pico_mbps": round(v["maior_individual"], 2),
            "pico_ap": v["maior_ap"],
            "pico_mac": v["maior_mac"],
            "pico_download_mbps": round(v["maior_download"], 2),
            "pico_upload_mbps": round(v["maior_upload"], 2),
        }
        for k, v in sorted(baldes.items())
    ]
    return resultado


async def get_picos_sustentados(db, minutos: float = 60, limiar_mbps: float = 60, duracao_minima_segundos: int = 60):
    """Analisa o historico POR DISPOSITIVO (nao a rede toda somada) e
    encontra trechos onde o download OU o upload de UM UNICO dispositivo
    ficou >= limiar_mbps de forma continua por pelo menos
    duracao_minima_segundos. Retorna uma lista de eventos, cada um com
    inicio, fim, duracao, hostname/mac/ap e o valor de pico atingido."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.models import ConsumoRedeAmostra

    limite_data = datetime.now(timezone.utc) - timedelta(minutes=minutos)

    result = await db.execute(
        select(ConsumoRedeAmostra)
        .where(ConsumoRedeAmostra.coletado_em >= limite_data)
        .order_by(ConsumoRedeAmostra.mac, ConsumoRedeAmostra.coletado_em)
    )
    amostras = result.scalars().all()

    por_mac = {}
    for a in amostras:
        por_mac.setdefault(a.mac, []).append(a)

    eventos = []
    for mac, lista in por_mac.items():
        trecho_inicio = None
        trecho_pico = 0.0
        trecho_direcao = None

        def fechar_trecho(fim_amostra):
            nonlocal trecho_inicio, trecho_pico, trecho_direcao
            if trecho_inicio is None:
                return
            duracao = (fim_amostra.coletado_em - trecho_inicio.coletado_em).total_seconds()
            if duracao >= duracao_minima_segundos:
                eventos.append({
                    "mac": mac,
                    "hostname": trecho_inicio.hostname,
                    "ap": trecho_inicio.ap,
                    "direcao": trecho_direcao,
                    "pico_mbps": round(trecho_pico, 2),
                    "inicio": trecho_inicio.coletado_em.isoformat(),
                    "fim": fim_amostra.coletado_em.isoformat(),
                    "duracao_segundos": round(duracao),
                })
            trecho_inicio = None
            trecho_pico = 0.0
            trecho_direcao = None

        anterior = None
        for a in lista:
            acima_download = a.download_mbps >= limiar_mbps
            acima_upload = a.upload_mbps >= limiar_mbps
            acima = acima_download or acima_upload

            if acima:
                if trecho_inicio is None:
                    trecho_inicio = a
                valor_atual = max(a.download_mbps, a.upload_mbps)
                if valor_atual > trecho_pico:
                    trecho_pico = valor_atual
                    trecho_direcao = "download" if acima_download and a.download_mbps >= a.upload_mbps else "upload"
            else:
                if trecho_inicio is not None and anterior is not None:
                    fechar_trecho(anterior)

            anterior = a

        if trecho_inicio is not None and anterior is not None:
            fechar_trecho(anterior)

    eventos.sort(key=lambda e: e["inicio"])
    return eventos
