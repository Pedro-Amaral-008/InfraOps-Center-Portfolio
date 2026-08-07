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


NOMES_AMIGAVEIS = {
    "WAN_G8GW": "WAN_G8",
    "VIVO_DEDICADO_GATEWAY": "WAN_Vivo",
    "WAN_OI_DHCP": "WAN_Nio",
}

async def get_status_links():
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-i", "/root/.ssh/pfsense_readonly",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            f"USUARIO_SSH_AQUI@{settings.pfsense_host}",
            "pfSsh.php playback gatewaystatus",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        linhas = stdout.decode().strip().split("\n")
        resultado = []
        for linha in linhas[1:]:
            partes = linha.split()
            if len(partes) < 7:
                continue
            nome_gw = partes[0]
            status = partes[6]
            nome_amigavel = NOMES_AMIGAVEIS.get(nome_gw, nome_gw)
            resultado.append({
                "nome": nome_amigavel,
                "status": "online" if status == "online" else "offline",
            })
        return resultado
    except Exception:
        return [{"nome": nome, "status": "desconhecido"} for nome in INTERFACES.values()]


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



_ultima_leitura_trafego = {}


async def get_trafego_links():
    import time
    global _ultima_leitura_trafego

    resultado = []
    agora = time.time()

    for indice, nome in INTERFACES.items():
        in_octets = await consultar_oid(f"1.3.6.1.2.1.2.2.1.10.{indice}")
        out_octets = await consultar_oid(f"1.3.6.1.2.1.2.2.1.16.{indice}")
        in_atual = int(in_octets) if in_octets is not None else 0
        out_atual = int(out_octets) if out_octets is not None else 0

        anterior = _ultima_leitura_trafego.get(indice)

        if anterior is not None:
            tempo_decorrido = agora - anterior["tempo"]
            if tempo_decorrido > 0:
                diff_in = (in_atual - anterior["in"]) if in_atual >= anterior["in"] else 0
                diff_out = (out_atual - anterior["out"]) if out_atual >= anterior["out"] else 0
                download_mbps = round((diff_in * 8) / tempo_decorrido / 1_000_000, 2)
                upload_mbps = round((diff_out * 8) / tempo_decorrido / 1_000_000, 2)
            else:
                download_mbps = 0
                upload_mbps = 0
        else:
            download_mbps = 0
            upload_mbps = 0

        _ultima_leitura_trafego[indice] = {"in": in_atual, "out": out_atual, "tempo": agora}

        resultado.append({
            "nome": nome,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
        })

    return resultado




async def verificar_alertas_links(db):
    from datetime import datetime
    from app.agent_alerts import obter_estado, definir_estado, enviar_telegram

    links = await get_status_links()
    for link in links:
        nome = link["nome"]
        offline = link["status"] == "offline"

        registro = await obter_estado(db, "pfsense", nome)
        estava_offline = registro.em_alerta if registro else False

        if offline and not estava_offline:
            msg = (
                f"🔔 <b>Monitoramento InfraOps Center</b>\n\n"
                f"<b>LINK DE REDE OFFLINE</b> ❌:\n\n"
                f"🌐 <b>Link:</b> {nome}\n"
                f"🕐 <b>Horário:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"⚠️ <b>Ação:</b> Verificar conectividade do link imediatamente"
            )
            await enviar_telegram(msg, parse_mode="HTML")
            await definir_estado(db, "pfsense", nome, True, notificacao_enviada=True)
        elif not offline and estava_offline:
            notificacao_foi_enviada = registro.notificacao_enviada if registro else False
            if notificacao_foi_enviada:
                msg = (
                    f"🔔 <b>Monitoramento InfraOps Center</b>\n\n"
                    f"<b>LINK DE REDE NORMALIZADO</b> ✅:\n\n"
                    f"🌐 <b>Link:</b> {nome}\n"
                    f"🕐 <b>Horário:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                )
                await enviar_telegram(msg, parse_mode="HTML")
            await definir_estado(db, "pfsense", nome, False, notificacao_enviada=False)
