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

    backups = await query_prometheus('veeam_backup_success')
    backups_ok, backups_falharam = count_by_value(backups)

    impressoras = await query_prometheus('probe_success{job="blackbox-impressoras"}')
    impressoras_online, impressoras_offline = count_by_value(impressoras)

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
        "impressoras_online": impressoras_online,
        "impressoras_offline": impressoras_offline,
        "impressoras_detalhe": to_device_list(impressoras),
        "atualizado_em": datetime.now().isoformat(),
    }


async def get_backups_detalhado():
    sucesso = await query_prometheus('veeam_backup_success')
    timestamps = await query_prometheus('veeam_backup_last_run_timestamp')
    tamanhos = await query_prometheus('veeam_backup_size_bytes')

    def indexar(resultados):
        indice = {}
        for r in resultados:
            instance = r.get("metric", {}).get("instance", "")
            valor = r.get("value", [None, None])[1]
            indice[instance] = valor
        return indice

    idx_sucesso = indexar(sucesso)
    idx_timestamp = indexar(timestamps)
    idx_tamanho = indexar(tamanhos)

    nomes_amigaveis = {
        "servidor_arquivos": "Backup Servidor de Arquivos",
        "servidor_impressao": "Backup Servidor de Impressão",
    }

    backups = []
    for instance in idx_sucesso.keys():
        tamanho_bytes = float(idx_tamanho.get(instance, 0))
        tamanho_gb = round(tamanho_bytes / (1024**3), 2)

        ultimo_ts = idx_timestamp.get(instance)
        ultima_execucao = None
        if ultimo_ts:
            ultima_execucao = datetime.fromtimestamp(float(ultimo_ts)).isoformat()

        backups.append({
            "nome": nomes_amigaveis.get(instance, instance),
            "tamanho_transferido_gb": tamanho_gb,
            "instance": instance,
            "sucesso": idx_sucesso.get(instance) == "1",
            "tamanho_gb": tamanho_gb,
            "ultima_execucao": ultima_execucao,
        })

    return backups
