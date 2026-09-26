import asyncio
import re
import socket
from datetime import datetime, timedelta, timezone

import paramiko

from app.config import settings

PFSENSE_SSH_USER = "infraops-readonly"
PFSENSE_SSH_KEY_PATH = "/home/appuser/.ssh/pfsense_readonly"

# vpnid do OpenVPN (server1/2/3 no pfSense) por nome - confirmado cruzando a
# descricao no config.xml do pfSense com o ifDescr via SNMP (ovpnsN = vpnid
# N). So mapeamos as VPNs site-a-site aqui (tunel fixo entre unidades, deve
# sempre ter exatamente 1 peer conectado 24/7); "Elcop-Principal" e VPN de
# acesso de usuarios (logins esporadicos, "ninguem conectado" e normal fora
# do expediente) e continua usando o ifOperStatus, nao esse mapeamento.
VPNID_POR_NOME = {
    "Elcop-Matriz": 2,
    "VPN_MATRIZ_SP": 3,
}

INTERFACES = {
    3: "WAN_Vivo",
    4: "WAN_Nio",
}

VPNS = {
    12: "Elcop-Principal",
    11: "Elcop-Matriz",
    13: "VPN_MATRIZ_SP",
}

VLANS = {
    10: "VLAN_CELULARES",
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
    "VIVO_DEDICADO_GATEWAY": "WAN_Vivo",
    "WAN_OI_DHCP": "WAN_Nio",
}

async def get_status_links():
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-i", "/home/appuser/.ssh/pfsense_readonly",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=5",
            f"infraops-readonly@{settings.pfsense_host}",
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
        ordem = list(INTERFACES.values())
        resultado.sort(key=lambda x: ordem.index(x["nome"]) if x["nome"] in ordem else 99)
        return resultado
    except Exception:
        return [{"nome": nome, "status": "desconhecido"} for nome in INTERFACES.values()]


async def get_status_operstatus(indice: int):
    """Status via SNMP ifOperStatus (1=up, 2=down). Usado para VPNs e VLANs,
    que nao tem monitoramento de gateway como os links WAN."""
    valor = await consultar_oid(f"1.3.6.1.2.1.2.2.1.8.{indice}")
    if valor is None:
        return "desconhecido"
    return "online" if "1" in valor else "offline"


async def registrar_status_links(db, links=None):
    from app.models import PfsenseLinkStatus
    if links is None:
        links = await get_status_links()
    for link in links:
        if link["status"] == "desconhecido":
            # Nao conseguimos nem consultar o pfSense (SSH falhou/expirou) -
            # na pratica isso quase sempre significa que o roteador ou a rede
            # caiu de vez, nao que "nao sabemos". Antes isso pulava o
            # registro e a queda ficava invisivel pro uptime/relatorio -
            # agora conta como offline, pra refletir o que realmente
            # aconteceu em qualquer periodo que for selecionado depois.
            online = False
        else:
            online = (link["status"] == "online")
        registro = PfsenseLinkStatus(
            nome_link=link["nome"],
            online=online,
        )
        db.add(registro)
    await db.commit()


async def registrar_trafego(db):
    from app.models import PfsenseTrafego
    trafego = await get_trafego_links()
    vpns = await get_vpns_status_trafego(db)
    vlans = await get_vlans_status_trafego()
    for t in trafego + vpns + vlans:
        registro = PfsenseTrafego(
            nome_link=t["nome"],
            download_mbps=t["download_mbps"],
            upload_mbps=t["upload_mbps"],
        )
        db.add(registro)
    await db.commit()


_ultima_leitura_trafego = {}


async def get_trafego_por_indices(indices_nomes: dict):
    import time
    global _ultima_leitura_trafego

    resultado = []
    agora = time.time()

    for indice, nome in indices_nomes.items():
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
            "indice": indice,
            "nome": nome,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
        })

    return resultado


async def get_trafego_links():
    resultado = await get_trafego_por_indices(INTERFACES)
    for r in resultado:
        del r["indice"]
    return resultado


async def houve_trafego_recente(db, nome_link: str, minutos: int = 45) -> bool:
    """Confirma se um link teve QUALQUER trafego (download ou upload) nos
    ultimos N minutos, usando o historico ja salvo em pfsense_trafego.
    Um tunel VPN ponto-a-ponto realmente ativo sempre gera algum trafego
    (keepalive), mesmo sem uso ativo - ausencia total de trafego por varios
    minutos e sinal real de que nao ha peer conectado, mesmo que a interface
    apareca "up" localmente (ifOperStatus so reflete o lado local)."""
    if db is None:
        return True  # sem banco disponivel, nao aplica esse filtro extra
    from sqlalchemy import select
    from app.models import PfsenseTrafego
    limite = datetime.now(timezone.utc) - timedelta(minutes=minutos)
    result = await db.execute(
        select(PfsenseTrafego).where(
            PfsenseTrafego.nome_link == nome_link,
            PfsenseTrafego.registrado_em >= limite,
        )
    )
    registros = result.scalars().all()
    if not registros:
        return True  # sem historico suficiente ainda, nao penaliza
    total_trafego = sum((r.download_mbps or 0) + (r.upload_mbps or 0) for r in registros)
    return total_trafego > 0


def _consultar_clientes_conectados_openvpn_sync() -> dict:
    """Conecta via SSH no pfSense e roda (via sudo, permissao restrita a esse
    unico script) o script que le o socket de management de cada instancia
    OpenVPN site-a-site, retornando quem esta na CLIENT LIST de cada uma
    agora. Isso reflete se o peer remoto esta realmente conectado - diferente
    do ifOperStatus (so reflete o lado local da interface) e diferente de
    inferir por trafego (gera falso positivo num tunel ocioso mas realmente
    conectado). Sincrono (paramiko) - rodar via asyncio.to_thread.
    Retorna {vpnid: True/False}, ou {} se a consulta SSH falhar."""
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cliente.connect(
        hostname=settings.pfsense_host,
        username=PFSENSE_SSH_USER,
        key_filename=PFSENSE_SSH_KEY_PATH,
        timeout=10,
    )
    try:
        _, stdout, _ = cliente.exec_command("sudo /usr/local/bin/ler_status_openvpn.sh")
        stdout.channel.settimeout(15)
        try:
            saida = stdout.read().decode(errors="ignore")
        except socket.timeout:
            print("AVISO: leitura SSH do status OpenVPN excedeu 15s, abortando")
            return {}
    finally:
        cliente.close()

    conectado_por_vpnid = {}
    vpnid_atual = None
    dentro_client_list = False
    for linha in saida.splitlines():
        linha = linha.strip()
        m = re.match(r"===VPNID (\d+)===", linha)
        if m:
            vpnid_atual = int(m.group(1))
            conectado_por_vpnid[vpnid_atual] = False
            dentro_client_list = False
            continue
        if vpnid_atual is None:
            continue
        if linha == "OpenVPN CLIENT LIST":
            dentro_client_list = True
            continue
        if linha.startswith("ROUTING TABLE") or linha.startswith("GLOBAL STATS") or linha == "END":
            dentro_client_list = False
            continue
        if dentro_client_list and linha and not linha.startswith("Common Name") and not linha.startswith("Updated"):
            conectado_por_vpnid[vpnid_atual] = True

    return conectado_por_vpnid


async def get_vpns_status_trafego(db=None):
    trafego = await get_trafego_por_indices(VPNS)

    conectado_por_vpnid = None
    if any(t["nome"] in VPNID_POR_NOME for t in trafego):
        try:
            conectado_por_vpnid = await asyncio.to_thread(_consultar_clientes_conectados_openvpn_sync)
        except Exception as e:
            print(f"ERRO ao consultar status real do OpenVPN via SSH: {e}")
            conectado_por_vpnid = None

    resultado = []
    for t in trafego:
        vpnid = VPNID_POR_NOME.get(t["nome"])
        if vpnid is not None and conectado_por_vpnid is not None and vpnid in conectado_por_vpnid:
            # tunel site-a-site: status real, baseado em ter peer conectado
            # agora no socket de management do OpenVPN (nao em trafego)
            status = "online" if conectado_por_vpnid[vpnid] else "offline"
        else:
            # "Elcop-Principal" (VPN de usuarios) ou fallback se o SSH falhou:
            # usa o ifOperStatus (reflete o servico rodando, nao trafego)
            status = await get_status_operstatus(t["indice"])
        resultado.append({
            "nome": t["nome"],
            "status": status,
            "download_mbps": t["download_mbps"],
            "upload_mbps": t["upload_mbps"],
        })
    return resultado


async def get_vlans_status_trafego():
    trafego = await get_trafego_por_indices(VLANS)
    resultado = []
    for t in trafego:
        status = await get_status_operstatus(t["indice"])
        resultado.append({
            "nome": t["nome"],
            "status": status,
            "download_mbps": t["download_mbps"],
            "upload_mbps": t["upload_mbps"],
        })
    return resultado


async def verificar_alertas_links(db, links=None):
    from datetime import datetime
    from app.agent_alerts import obter_estado, definir_estado, enviar_telegram

    if links is None:
        links = await get_status_links()
    for link in links:
        nome = link["nome"]
        offline = link["status"] == "offline"

        registro = await obter_estado(db, "pfsense", nome)
        estava_offline = registro.em_alerta if registro else False
        # fecha a transacao de leitura antes de qualquer chamada de rede (Telegram),
        # pra nao deixar transacao "idle in transaction" aberta enquanto espera resposta
        await db.commit()

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


def _vpn_dentro_do_expediente() -> bool:
    from datetime import datetime, timezone, timedelta
    fuso_local = timezone(timedelta(hours=-3))
    agora_local = datetime.now(fuso_local)
    return agora_local.weekday() <= 4 and 8 <= agora_local.hour < 18


async def verificar_alertas_vpns_vlans(db):
    from datetime import datetime
    from app.agent_alerts import obter_estado, definir_estado, enviar_telegram

    categorias = [
        ("VPN", await get_vpns_status_trafego(db)),
        ("VLAN", await get_vlans_status_trafego()),
    ]

    for tipo, itens in categorias:
        for item in itens:
            nome = item["nome"]
            status = item["status"]
            if status == "desconhecido":
                continue
            offline = status == "offline"

            registro = await obter_estado(db, f"pfsense-{tipo.lower()}", nome)
            estava_offline = registro.em_alerta if registro else False
            notificacao_ja_enviada = registro.notificacao_enviada if registro else False
            pode_alertar = _vpn_dentro_do_expediente() if tipo == "VPN" else True
            # fecha a transacao de leitura antes de qualquer chamada de rede (Telegram),
            # pra nao deixar transacao "idle in transaction" aberta enquanto espera resposta
            await db.commit()

            if offline and not estava_offline:
                if pode_alertar:
                    msg = (
                        f"🔔 <b>Monitoramento InfraOps Center</b>\n\n"
                        f"❌ <b>{tipo} {nome} ficou offline</b>\n\n"
                        f"🕐 Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                        f"⚠️ Ação: Verificar conectividade imediatamente"
                    )
                    await enviar_telegram(msg, parse_mode="HTML")
                    await definir_estado(db, f"pfsense-{tipo.lower()}", nome, True, notificacao_enviada=True)
                else:
                    await definir_estado(db, f"pfsense-{tipo.lower()}", nome, True, notificacao_enviada=False)
            elif offline and estava_offline:
                if pode_alertar and not notificacao_ja_enviada:
                    msg = (
                        f"🔔 <b>Monitoramento InfraOps Center</b>\n\n"
                        f"❌ <b>{tipo} {nome} ainda offline</b>\n\n"
                        f"🕐 Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                        f"⚠️ Ação: Verificar conectividade imediatamente"
                    )
                    await enviar_telegram(msg, parse_mode="HTML")
                    await definir_estado(db, f"pfsense-{tipo.lower()}", nome, True, notificacao_enviada=True)
            elif not offline and estava_offline:
                if notificacao_ja_enviada and pode_alertar:
                    msg = (
                        f"🔔 <b>Monitoramento InfraOps Center</b>\n\n"
                        f"✅ <b>{tipo} {nome} voltou online</b>\n\n"
                        f"🕐 Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                    )
                    await enviar_telegram(msg, parse_mode="HTML")
                await definir_estado(db, f"pfsense-{tipo.lower()}", nome, False, notificacao_enviada=False)


async def registrar_status_vpns_vlans(db):
    from app.models import PfsenseVpnVlanStatus

    vpns = await get_vpns_status_trafego(db)
    for v in vpns:
        if v["status"] == "desconhecido":
            continue
        db.add(PfsenseVpnVlanStatus(tipo="vpn", nome=v["nome"], online=(v["status"] == "online")))

    vlans = await get_vlans_status_trafego()
    for v in vlans:
        if v["status"] == "desconhecido":
            continue
        db.add(PfsenseVpnVlanStatus(tipo="vlan", nome=v["nome"], online=(v["status"] == "online")))

    await db.commit()
