import httpx
from datetime import datetime

PROMETHEUS_URL = "http://prometheus:9090"


async def query_prometheus(query: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": query}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("result", [])
        except Exception:
            return []


def count_by_value(results, target_value="1"):
    online = 0
    offline = 0
    for r in results:
        value = r.get("value", [None, None])[1]
        if value == target_value:
            online += 1
        else:
            offline += 1
    return online, offline


def to_device_list(results):
    devices = []
    for r in results:
        metric = r.get("metric", {})
        value = r.get("value", [None, None])[1]
        devices.append({
            "nome": metric.get("nome", metric.get("instance", "desconhecido")),
            "instance": metric.get("instance", ""),
            "status": "online" if value == "1" else "offline",
        })
    devices.sort(key=lambda d: (d["status"] != "offline", d["nome"]))
    return devices


async def get_dashboard_summary(db=None):
    servidores = await query_prometheus(
        'probe_success{job=~"blackbox-servidores-tcp|blackbox-servidor-backup-principal"}'
    )
    servidores_online, servidores_offline = count_by_value(servidores)
    servidores_detalhe_extra = []

    if db is not None:
        from datetime import timezone, timedelta
        from sqlalchemy import select
        from app.models import AgentMetric

        result = await db.execute(
            select(AgentMetric).where(AgentMetric.instance == "srvfrotas")
            .order_by(AgentMetric.coletado_em.desc()).limit(1)
        )
        fluig = result.scalar_one_or_none()

        if fluig:
            agora = datetime.now(timezone.utc)
            offline = (agora - fluig.coletado_em) > timedelta(minutes=5)
            if offline:
                servidores_offline += 1
            else:
                servidores_online += 1
            servidores_detalhe_extra.append({
                "nome": fluig.hostname,
                "instance": fluig.instance,
                "status": "offline" if offline else "online",
            })

    aps = await query_prometheus('probe_success{job="blackbox-access-points"}')
    aps_online, aps_offline = count_by_value(aps)

    unifi = await query_prometheus('probe_success{job="blackbox-unifi-controller"}')
    unifi_status = "online" if unifi and unifi[0].get("value", [None, "0"])[1] == "1" else "offline"

    from sqlalchemy import select, func as sqlfunc
    from datetime import timezone, timedelta
    from app.models import BackupExecution

    backups_ok = 0
    backups_falharam = 0
    backups_detalhe = []
    if db is not None:
        limite = datetime.now(timezone.utc) - timedelta(hours=48)
        subquery_backup = (
            select(
                BackupExecution.job_name,
                sqlfunc.max(BackupExecution.executado_em).label("max_executado")
            )
            .where(BackupExecution.executado_em >= limite)
            .group_by(BackupExecution.job_name)
            .subquery()
        )
        result_backups = await db.execute(
            select(BackupExecution)
            .join(
                subquery_backup,
                (BackupExecution.job_name == subquery_backup.c.job_name) &
                (BackupExecution.executado_em == subquery_backup.c.max_executado)
            )
        )
        ultimas_execucoes = result_backups.scalars().all()
        nomes_amigaveis_backup = {
            "servidor_arquivos": "Backup Servidor de Arquivos",
            "servidor_impressao": "Backup Servidor de Impressão",
        }
        for execucao in ultimas_execucoes:
            ok = execucao.status in ("Success", "Warning")
            if ok:
                backups_ok += 1
            else:
                backups_falharam += 1
            backups_detalhe.append({
                "nome": nomes_amigaveis_backup.get(execucao.instance, execucao.instance),
                "instance": execucao.backup_type or "-",
                "status": "online" if ok else "offline",
            })

    impressoras = await query_prometheus('probe_success{job="blackbox-impressoras"}')
    impressoras_online, impressoras_offline = count_by_value(impressoras)

    from app.pfsense import get_status_links
    links_wan = await get_status_links()
    links_online = sum(1 for l in links_wan if l["status"] == "online")
    links_offline = sum(1 for l in links_wan if l["status"] == "offline")
    links_detalhe = [{"nome": l["nome"], "instance": l["nome"], "status": l["status"]} for l in links_wan]

    return {
        "servidores_online": servidores_online,
        "servidores_offline": servidores_offline,
        "servidores_detalhe": to_device_list(servidores) + servidores_detalhe_extra,
        "access_points_online": aps_online,
        "access_points_offline": aps_offline,
        "access_points_detalhe": to_device_list(aps),
        "painel_unifi": unifi_status,
        "backups_ok": backups_ok,
        "backups_falharam": backups_falharam,
        "backups_detalhe": backups_detalhe,
        "impressoras_online": impressoras_online,
        "impressoras_offline": impressoras_offline,
        "links_online": links_online,
        "links_offline": links_offline,
        "links_detalhe": links_detalhe,
        "impressoras_detalhe": to_device_list(impressoras),
        "atualizado_em": datetime.now().isoformat(),
    }




async def get_backups_detalhado(db=None):
    from sqlalchemy import select, func as sqlfunc
    from app.models import BackupExecution

    nomes_amigaveis = {
        "servidor_arquivos": "Backup Servidor de Arquivos",
        "servidor_impressao": "Backup Servidor de Impressão",
    }

    if db is None:
        return []

    subquery = (
        select(
            BackupExecution.instance,
            sqlfunc.max(BackupExecution.executado_em).label("max_executado")
        )
        .group_by(BackupExecution.instance)
        .subquery()
    )
    result = await db.execute(
        select(BackupExecution)
        .join(
            subquery,
            (BackupExecution.instance == subquery.c.instance) &
            (BackupExecution.executado_em == subquery.c.max_executado)
        )
    )
    ultimas_execucoes = result.scalars().all()

    backups = []
    for execucao in ultimas_execucoes:
        tamanho_gb = round((execucao.tamanho_transferido_bytes or 0) / (1024**3), 2)
        backups.append({
            "nome": nomes_amigaveis.get(execucao.instance, execucao.instance),
            "tamanho_transferido_gb": tamanho_gb,
            "instance": execucao.instance,
            "sucesso": execucao.status in ("Success", "Warning"),
            "tamanho_gb": tamanho_gb,
            "ultima_execucao": execucao.executado_em.isoformat() if execucao.executado_em else None,
        })
    return backups
