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


async def get_top_consumo_clientes(limite: int = 50):
    """Retorna os clientes que mais consomem banda AGORA (taxa em tempo real),
    usando a API classica (session-based) do UniFi, que traz esse dado -
    diferente da API oficial nova, que so tem dados de conectividade."""
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

    resultado = []
    for c in clientes:
        taxa_total = c.get("bytes-r", 0) or 0
        if taxa_total <= 0:
            continue
        ip_cliente = c.get("ip") or c.get("last_ip", "")
        if ip_cliente in IPS_EXCLUIDOS:
            continue
        resultado.append({
            "hostname": c.get("hostname") or c.get("name") or "Desconhecido",
            "ip": c.get("ip") or c.get("last_ip", ""),
            "mac": c.get("mac", ""),
            "download_mbps": round((c.get("rx_bytes-r", 0) or 0) * 8 / 1_000_000, 2),
            "upload_mbps": round((c.get("tx_bytes-r", 0) or 0) * 8 / 1_000_000, 2),
            "total_mbps": round(taxa_total * 8 / 1_000_000, 2),
        })

    resultado.sort(key=lambda x: x["total_mbps"], reverse=True)
    return resultado[:limite]


LIMITE_MBPS_CONSUMO = 20
DURACAO_MINIMA_SEGUNDOS = 40

_estado_consumo_alto = {}  # mac -> {"desde": timestamp, "avisado": bool}


async def verificar_consumo_excessivo(db):
    """Roda com frequencia (a cada ~20s) verificando se algum cliente esta
    consumindo acima do limite (download OU upload) de forma SUSTENTADA por
    pelo menos DURACAO_MINIMA_SEGUNDOS. Quando confirma, registra um evento
    no Feed do Dashboard (sem Telegram)."""
    import time
    from app.models import EventoSistema

    agora = time.time()
    clientes = await get_top_consumo_clientes(limite=50)
    macs_atuais_acima = set()

    for c in clientes:
        acima_limite = c["download_mbps"] >= LIMITE_MBPS_CONSUMO or c["upload_mbps"] >= LIMITE_MBPS_CONSUMO
        if not acima_limite:
            continue

        mac = c["mac"]
        macs_atuais_acima.add(mac)

        if mac not in _estado_consumo_alto:
            _estado_consumo_alto[mac] = {"desde": agora, "avisado": False}
            continue

        registro = _estado_consumo_alto[mac]
        duracao = agora - registro["desde"]

        if duracao >= DURACAO_MINIMA_SEGUNDOS and not registro["avisado"]:
            registro["avisado"] = True
            direcao = "download" if c["download_mbps"] >= LIMITE_MBPS_CONSUMO else "upload"
            valor = max(c["download_mbps"], c["upload_mbps"])
            db.add(EventoSistema(
                tipo="atencao",
                mensagem=f"Consumo de rede {c['hostname']} acima de {LIMITE_MBPS_CONSUMO} Mbps ({direcao}: {valor:.1f} Mbps)",
                detalhes=f"{c['ip']} · sustentado por mais de {DURACAO_MINIMA_SEGUNDOS}s",
            ))
            await db.commit()

    # Limpa clientes que normalizaram (nao aparecem mais acima do limite)
    for mac in list(_estado_consumo_alto.keys()):
        if mac not in macs_atuais_acima:
            del _estado_consumo_alto[mac]
