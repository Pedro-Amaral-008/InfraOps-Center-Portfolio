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
