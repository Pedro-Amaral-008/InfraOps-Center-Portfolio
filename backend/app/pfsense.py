import asyncio
from app.config import settings

INTERFACES = {
    2: "WAN_G8",
    3: "WAN_Vivo",
    4: "WAN_Nio",
}


async def consultar_oid(oid: str):
    try:
        proc = await asyncio.create_subprocess_exec(
            "snmpget", "-v2c", "-c", settings.pfsense_snmp_community,
            "-Ovq", settings.pfsense_host, oid,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)

        if proc.returncode != 0:
            return None

        valor = stdout.decode().strip()
        return valor if valor else None
    except Exception:
        return None


async def get_status_links():
    resultado = []
    for indice, nome in INTERFACES.items():
        status_oid = f"1.3.6.1.2.1.2.2.1.8.{indice}"
        status = await consultar_oid(status_oid)
        online = str(status) == "1" if status is not None else None
        resultado.append({
            "nome": nome,
            "status": "online" if online else "offline" if online is False else "desconhecido",
        })
    return resultado


async def registrar_status_links(db):
    from app.models import PfsenseLinkStatus
    links = await get_status_links()
    for link in links:
        if link["status"] == "desconhecido":
            continue
        registro = PfsenseLinkStatus(
            nome_link=link["nome"],
            online=(link["status"] == "online"),
        )
        db.add(registro)
    await db.commit()


async def registrar_trafego(db):
    from app.models import PfsenseTrafego
    trafego = await get_trafego_links()
    for t in trafego:
        registro = PfsenseTrafego(
            nome_link=t["nome"],
            download_mbps=int(t["download_mbps"]),
            upload_mbps=int(t["upload_mbps"]),
        )
        db.add(registro)
    await db.commit()


async def get_trafego_links():
    resultado = []
    leitura1 = {}
    for indice in INTERFACES.keys():
        in_octets = await consultar_oid(f"1.3.6.1.2.1.2.2.1.10.{indice}")
        out_octets = await consultar_oid(f"1.3.6.1.2.1.2.2.1.16.{indice}")
        leitura1[indice] = {
            "in": int(in_octets) if in_octets is not None else 0,
            "out": int(out_octets) if out_octets is not None else 0,
        }
    await asyncio.sleep(1)
    for indice, nome in INTERFACES.items():
        in_octets = await consultar_oid(f"1.3.6.1.2.1.2.2.1.10.{indice}")
        out_octets = await consultar_oid(f"1.3.6.1.2.1.2.2.1.16.{indice}")
        in_atual = int(in_octets) if in_octets is not None else 0
        out_atual = int(out_octets) if out_octets is not None else 0
        in_anterior = leitura1[indice]["in"]
        out_anterior = leitura1[indice]["out"]
        diff_in = (in_atual - in_anterior) if in_atual >= in_anterior else 0
        diff_out = (out_atual - out_anterior) if out_atual >= out_anterior else 0
        download_mbps = round((diff_in * 8) / 1_000_000, 2)
        upload_mbps = round((diff_out * 8) / 1_000_000, 2)
        resultado.append({
            "nome": nome,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
        })
    return resultado
