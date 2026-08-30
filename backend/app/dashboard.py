import httpx
from datetime import datetime, timedelta

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


INSTANCIAS_REMOVIDAS = ["192.168.1.71:445", "192.168.1.71"]
async def get_uptime_por_job(job: str, dias: int = 30):
    """Calcula o uptime percentual de cada instance de um job, usando o
    historico armazenado pelo proprio Prometheus (avg_over_time)."""
    query = f'avg_over_time(probe_success{{job=~"{job}"}}[{dias}d]) * 100'
    resultados = await query_prometheus(query)
    uptime = []
    for r in resultados:
        metric = r.get("metric", {})
        if metric.get("instance", "") in INSTANCIAS_REMOVIDAS:
            continue
        valor = r.get("value", [None, None])[1]
        uptime.append({
            "nome": metric.get("nome", metric.get("instance", "")),
            "instance": metric.get("instance", ""),
            "uptime_percent": round(float(valor), 2) if valor is not None else None,
        })
    return uptime
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
            "ecam": "Backup E-CAM",
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




async def get_backups_uptime(db, dias: int = 30):
    from sqlalchemy import select, func as sqlfunc
    from datetime import datetime, timedelta, timedelta, timezone
    from app.models import BackupExecution

    nomes_amigaveis = {
        "servidor_arquivos": "Backup Servidor de Arquivos",
        "servidor_impressao": "Backup Servidor de Impressão",
        "ecam": "Backup E-CAM",
        "eops": "Backup E-Ops",
    }

    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    result = await db.execute(
        select(BackupExecution).where(BackupExecution.executado_em >= limite)
    )
    execucoes = result.scalars().all()

    # Agrupa por (instance, backup_type). Quando so existe um tipo de backup
    # para a instancia (ex: E-CAM, que so faz Dump PostgreSQL), o resultado
    # continua sendo uma linha unica - o agrupamento nao cria divisao artificial.
    por_grupo = {}
    for e in execucoes:
        chave = (e.instance, e.backup_type or "")
        if chave not in por_grupo:
            por_grupo[chave] = {"total": 0, "sucesso": 0}
        por_grupo[chave]["total"] += 1
        if e.status in ("Success", "Warning", "sucesso"):
            por_grupo[chave]["sucesso"] += 1

    resultado = []
    for (instance, backup_type), dados in por_grupo.items():
        uptime = round((dados["sucesso"] / dados["total"]) * 100, 1) if dados["total"] > 0 else None
        nome_base = nomes_amigaveis.get(instance, instance)
        # So adiciona o sufixo do tipo se essa instancia tiver mais de um tipo distinto.
        tipos_da_instancia = {t for (i, t) in por_grupo.keys() if i == instance}
        if len(tipos_da_instancia) > 1 and backup_type:
            tipo_curto = "Full" if "Full" in backup_type else ("Incremental" if "Incremental" in backup_type else backup_type)
            nome_exibido = f"{nome_base} — {tipo_curto}"
        else:
            nome_exibido = nome_base
        resultado.append({
            "nome": nome_exibido,
            "instance": instance,
            "backup_type": backup_type,
            "total_execucoes": dados["total"],
            "execucoes_com_sucesso": dados["sucesso"],
            "uptime_percent": uptime,
        })
    resultado.sort(key=lambda x: x["nome"])
    return resultado


async def get_backups_detalhado(db=None):
    from sqlalchemy import select, func as sqlfunc
    from app.models import BackupExecution

    nomes_amigaveis = {
        "servidor_arquivos": "Backup Servidor de Arquivos",
        "servidor_impressao": "Backup Servidor de Impressão",
        "ecam": "Backup E-CAM",
        "eops": "Backup E-Ops",
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


async def get_vpn_vlan_uptime(db, tipo: str, dias: int = 30):
    from sqlalchemy import select
    from datetime import datetime, timedelta, timedelta, timezone
    from app.models import PfsenseVpnVlanStatus

    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    result = await db.execute(
        select(PfsenseVpnVlanStatus).where(
            (PfsenseVpnVlanStatus.tipo == tipo) & (PfsenseVpnVlanStatus.verificado_em >= limite)
        )
    )
    registros = result.scalars().all()

    por_nome = {}
    for r in registros:
        if r.nome not in por_nome:
            por_nome[r.nome] = {"total": 0, "online": 0}
        por_nome[r.nome]["total"] += 1
        if r.online:
            por_nome[r.nome]["online"] += 1

    resultado = []
    for nome, dados in por_nome.items():
        uptime = round((dados["online"] / dados["total"]) * 100, 2) if dados["total"] > 0 else None
        resultado.append({"nome": nome, "uptime_percent": uptime})
    return resultado


async def get_tendencia_saude_24h():
    """Retorna a % de equipamentos saudaveis (online) a cada hora, nas ultimas 24h,
    combinando servidores, access points, links, e impressoras (via Prometheus)."""
    query = (
        '('
        'sum(probe_success{job=~"blackbox-servidores-tcp|blackbox-servidor-backup-principal|'
        'blackbox-access-points|blackbox-impressoras"}) '
        'or vector(0)'
        ') / ('
        'count(probe_success{job=~"blackbox-servidores-tcp|blackbox-servidor-backup-principal|'
        'blackbox-access-points|blackbox-impressoras"}) '
        'or vector(1)'
        ') * 100'
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": query,
                    "start": (datetime.now() - timedelta(hours=24)).timestamp(),
                    "end": datetime.now().timestamp(),
                    "step": "1h",
                }
            )
            response.raise_for_status()
            data = response.json()
            resultados = data.get("data", {}).get("result", [])
            if not resultados:
                return []
            pontos = resultados[0].get("values", [])
            return [
                {"timestamp": int(float(p[0]) * 1000), "valor": round(float(p[1]), 1)}
                for p in pontos
            ]
        except Exception:
            return []


async def get_estabilidade_semanal(db):
    """Retorna o uptime medio diario (ultimos 7 dias) de cada categoria monitorada
    via Prometheus (servidores, access_points, links) e do banco (backups)."""
    from datetime import timezone

    categorias_prometheus = {
        "servidores": "blackbox-servidores-tcp|blackbox-servidor-backup-principal",
        "access_points": "blackbox-access-points",
    }

    resultado = {}

    for chave, job in categorias_prometheus.items():
        # avg() agrega todas as instancias da categoria numa unica serie de media,
        # em vez de pegar so a primeira instancia retornada (bug anterior).
        query = f'avg(avg_over_time(probe_success{{job=~"{job}"}}[1d])) * 100'
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": query,
                        "start": (datetime.now() - timedelta(days=7)).timestamp(),
                        "end": datetime.now().timestamp(),
                        "step": "1d",
                    }
                )
                response.raise_for_status()
                data = response.json()
                resultados = data.get("data", {}).get("result", [])
                if resultados:
                    valores = [round(float(v[1]), 1) for v in resultados[0].get("values", [])]
                else:
                    valores = []
            except Exception:
                valores = []
        resultado[chave] = valores

    # Impressoras: uptime considerando SO o horario comercial (seg-sex, 8h-18h local),
    # ja que muitas entram em modo standby fora desse horario e isso nao deve contar como "queda".
    query_impressoras = 'avg(probe_success{job="blackbox-impressoras"}) * 100'
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": query_impressoras,
                    "start": (datetime.now() - timedelta(days=7)).timestamp(),
                    "end": datetime.now().timestamp(),
                    "step": "15m",
                }
            )
            response.raise_for_status()
            data = response.json()
            resultados_imp = data.get("data", {}).get("result", [])
            pontos_imp = resultados_imp[0].get("values", []) if resultados_imp else []
        except Exception:
            pontos_imp = []

    from datetime import timezone as tz_utc, timedelta as td
    fuso_local = tz_utc(td(hours=-3))
    por_dia_imp = {}
    for ts_str, valor_str in pontos_imp:
        momento_utc = datetime.fromtimestamp(float(ts_str), tz=tz_utc.utc)
        momento_local = momento_utc.astimezone(fuso_local)
        # so conta segunda(0) a sexta(4), das 8h as 18h
        if momento_local.weekday() <= 4 and 8 <= momento_local.hour < 18:
            dia = momento_local.date().isoformat()
            por_dia_imp.setdefault(dia, []).append(float(valor_str))

    dias_imp_ordenados = sorted(por_dia_imp.keys())
    resultado["impressoras"] = [
        round(sum(por_dia_imp[d]) / len(por_dia_imp[d]), 1) if por_dia_imp[d] else None
        for d in dias_imp_ordenados
    ]

    # Links de Internet: calcula uptime diario a partir do historico salvo (pfsense_link_status)
    from sqlalchemy import select
    from app.models import PfsenseLinkStatus
    limite_links = datetime.now(timezone.utc) - timedelta(days=7)
    result_links = await db.execute(
        select(PfsenseLinkStatus).where(PfsenseLinkStatus.verificado_em >= limite_links)
    )
    registros_links = result_links.scalars().all()
    por_dia_links = {}
    for r in registros_links:
        dia = r.verificado_em.date().isoformat()
        if dia not in por_dia_links:
            por_dia_links[dia] = {"total": 0, "online": 0}
        por_dia_links[dia]["total"] += 1
        if r.online:
            por_dia_links[dia]["online"] += 1
    dias_links_ordenados = sorted(por_dia_links.keys())
    resultado["links"] = [
        round((por_dia_links[d]["online"] / por_dia_links[d]["total"]) * 100, 1) if por_dia_links[d]["total"] > 0 else None
        for d in dias_links_ordenados
    ]

    # Backups: calcula uptime diario dos ultimos 7 dias a partir do historico salvo
    from sqlalchemy import select
    from app.models import BackupExecution
    limite = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(BackupExecution).where(BackupExecution.executado_em >= limite)
    )
    execucoes = result.scalars().all()
    por_dia = {}
    for e in execucoes:
        dia = e.executado_em.date().isoformat()
        if dia not in por_dia:
            por_dia[dia] = {"total": 0, "sucesso": 0}
        por_dia[dia]["total"] += 1
        if e.status in ("Success", "Warning", "sucesso"):
            por_dia[dia]["sucesso"] += 1

    dias_ordenados = sorted(por_dia.keys())
    resultado["backups"] = [
        round((por_dia[d]["sucesso"] / por_dia[d]["total"]) * 100, 1) if por_dia[d]["total"] > 0 else None
        for d in dias_ordenados
    ]

    # Reordena na ordem oficial das categorias (mesma ordem dos cards do topo)
    ordem = ["servidores", "access_points", "links", "backups", "impressoras"]
    resultado_ordenado = {chave: resultado[chave] for chave in ordem if chave in resultado}
    return resultado_ordenado
