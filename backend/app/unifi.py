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
                _estado_consumo_alto[mac] = {"desde": agora, "avisado": False}
            segundos_acima = agora - _estado_consumo_alto[mac]["desde"]

        resultado.append({
            "hostname": c.get("hostname") or c.get("name") or "Desconhecido",
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
            db.add(EventoSistema(
                tipo="atencao",
                mensagem=f"Consumo de rede {hostname} ficou acima de {LIMITE_MBPS_CONSUMO} Mbps por {_formatar_duracao(duracao_total)}",
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
