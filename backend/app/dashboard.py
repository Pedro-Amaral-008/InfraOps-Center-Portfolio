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
                        "start": (datetime.now() - timedelta(days=6)).timestamp(),
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


async def get_alertas_ativos_com_duracao(db, itens_offline: list):
    """Para cada item offline (lista de nomes), busca o evento mais recente
    de 'ficou offline' no historico e calcula ha quanto tempo esta assim."""
    from sqlalchemy import select, desc
    from app.models import EventoSistema
    from datetime import timezone

    resultado = []
    agora = datetime.now(timezone.utc)

    for nome in itens_offline:
        result = await db.execute(
            select(EventoSistema)
            .where(EventoSistema.mensagem.like(f"%{nome}%ficou offline%"))
            .order_by(desc(EventoSistema.criado_em))
            .limit(1)
        )
        evento = result.scalar_one_or_none()

        if evento:
            criado_em = evento.criado_em
            if criado_em.tzinfo is None:
                criado_em = criado_em.replace(tzinfo=timezone.utc)
            diff = agora - criado_em
            horas = int(diff.total_seconds() // 3600)
            minutos = int((diff.total_seconds() % 3600) // 60)
            if horas > 0:
                duracao_texto = f"{horas}h {minutos}min"
            else:
                duracao_texto = f"{minutos}min"
        else:
            duracao_texto = "há pouco"

        resultado.append({"nome": nome, "duracaoTexto": duracao_texto})

    return resultado


async def contar_ocorrencias_semana(db, nome_equipamento: str) -> int:
    """Conta quantos eventos criticos ou de atencao esse equipamento teve
    nos ultimos 7 dias (para o selo 'Xa vez essa semana')."""
    from sqlalchemy import select, func as sqlfunc
    from app.models import EventoSistema
    from datetime import timezone

    limite = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(sqlfunc.count()).select_from(EventoSistema).where(
            EventoSistema.mensagem.like(f"%{nome_equipamento}%"),
            EventoSistema.tipo.in_(["critico", "atencao"]),
            EventoSistema.criado_em >= limite,
        )
    )
    return result.scalar_one()


async def get_pior_desempenho_semana(db, estabilidade: dict):
    """A partir dos dados ja calculados de estabilidade-semanal (semana atual),
    calcula tambem a semana anterior para comparar, e acha a categoria com
    pior media (ou melhor, se tudo estiver bem)."""
    from sqlalchemy import select
    from app.models import BackupExecution, PfsenseLinkStatus
    from datetime import timezone

    def media(valores):
        validos = [v for v in valores if v is not None]
        return sum(validos) / len(validos) if validos else 0

    medias_atuais = {cat: media(vals) for cat, vals in estabilidade.items() if vals}

    if not medias_atuais:
        return None

    pior_categoria = min(medias_atuais, key=medias_atuais.get)
    pior_media = medias_atuais[pior_categoria]

    # Calcula a media da semana ANTERIOR para a categoria pior, via Prometheus (servidores/access_points/impressoras)
    # ou historico salvo (links/backups), reaproveitando a mesma logica com offset de 7 dias.
    media_semana_passada = None
    if pior_categoria in ("servidores", "access_points"):
        job = "blackbox-servidores-tcp|blackbox-servidor-backup-principal" if pior_categoria == "servidores" else "blackbox-access-points"
        query = f'avg(avg_over_time(probe_success{{job=~"{job}"}}[7d])) * 100'
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={"query": query, "time": (datetime.now() - timedelta(days=7)).timestamp()}
                )
                data = response.json()
                resultados = data.get("data", {}).get("result", [])
                if resultados:
                    media_semana_passada = round(float(resultados[0]["value"][1]), 1)
            except Exception:
                pass

    delta = round(pior_media - media_semana_passada, 1) if media_semana_passada is not None else 0.0

    nomes_amigaveis_categoria = {
        "servidores": "Servidores",
        "access_points": "Access Points",
        "links": "Links de Rede",
        "backups": "Backups",
        "impressoras": "Impressoras",
    }

    quedas = len([v for v in estabilidade.get(pior_categoria, []) if v is not None and v < 99])

    return {
        "categoria": nomes_amigaveis_categoria.get(pior_categoria, pior_categoria),
        "quedas7dias": quedas,
        "percentSemana": round(pior_media, 1),
        "deltaVsSemanaPassada": delta,
    }


async def get_estabilidade_com_variacao(db):
    """Para cada categoria: os 7 dias de uptime (com null nos dias sem dado),
    a media da semana, e a variacao comparada com a semana anterior."""
    from datetime import timezone

    estabilidade = await get_estabilidade_semanal(db)

    categorias_prometheus_jobs = {
        "servidores": "blackbox-servidores-tcp|blackbox-servidor-backup-principal",
        "access_points": "blackbox-access-points",
    }

    async def media_periodo_prometheus(job: str, dias_atras_inicio: int, dias_atras_fim: int):
        query = f'avg(avg_over_time(probe_success{{job=~"{job}"}}[{dias_atras_inicio - dias_atras_fim}d])) * 100'
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={"query": query, "time": (datetime.now() - timedelta(days=dias_atras_fim)).timestamp()}
                )
                data = response.json()
                resultados = data.get("data", {}).get("result", [])
                if resultados:
                    return round(float(resultados[0]["value"][1]), 1)
            except Exception:
                pass
        return None

    resultado = {}
    for chave, valores in estabilidade.items():
        validos = [v for v in valores if v is not None]
        media = round(sum(validos) / len(validos), 1) if validos else 0.0

        media_semana_passada = None
        if chave in categorias_prometheus_jobs:
            media_semana_passada = await media_periodo_prometheus(categorias_prometheus_jobs[chave], 14, 7)

        if media_semana_passada is not None:
            delta = round(media - media_semana_passada, 1)
        else:
            delta = 0.0

        if abs(delta) < 0.5:
            sinal = "estavel"
        elif delta > 0:
            sinal = "alta"
        else:
            sinal = "baixa"

        resultado[chave] = {
            "dias": valores,
            "media": media,
            "variacao": abs(delta),
            "sinal": sinal,
        }

    return resultado


async def get_estabilidade_14_dias(db):
    """Retorna, para cada categoria, 14 valores diarios de uptime:
    os 7 dias anteriores seguidos dos 7 dias atuais. Isso permite ao
    frontend calcular tanto a media da semana atual quanto a variacao
    em relacao a semana passada, sempre a partir do MESMO array."""
    from datetime import timezone

    categorias_prometheus_jobs = {
        "servidores": "blackbox-servidores-tcp|blackbox-servidor-backup-principal",
        "access_points": "blackbox-access-points",
    }

    resultado = {}

    for chave, job in categorias_prometheus_jobs.items():
        query = f'avg(avg_over_time(probe_success{{job=~"{job}"}}[1d])) * 100'
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": query,
                        "start": (datetime.now() - timedelta(days=13)).timestamp(),
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

    # Impressoras: horario comercial, 14 dias uteis considerando seg-sex 8h-18h
    query_impressoras = 'avg(probe_success{job="blackbox-impressoras"}) * 100'
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": query_impressoras,
                    "start": (datetime.now() - timedelta(days=14)).timestamp(),
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

    fuso_local = timezone(timedelta(hours=-3))
    por_dia_imp = {}
    for ts_str, valor_str in pontos_imp:
        momento_utc = datetime.fromtimestamp(float(ts_str), tz=timezone.utc)
        momento_local = momento_utc.astimezone(fuso_local)
        if momento_local.weekday() <= 4 and 8 <= momento_local.hour < 18:
            dia = momento_local.date().isoformat()
            por_dia_imp.setdefault(dia, []).append(float(valor_str))
    dias_imp_ordenados = sorted(por_dia_imp.keys())
    resultado["impressoras"] = [
        round(sum(por_dia_imp[d]) / len(por_dia_imp[d]), 1) if por_dia_imp[d] else None
        for d in dias_imp_ordenados
    ]

    # Links: historico salvo (pfsense_link_status)
    from sqlalchemy import select
    from app.models import PfsenseLinkStatus
    limite_links = datetime.now(timezone.utc) - timedelta(days=14)
    result_links = await db.execute(
        select(PfsenseLinkStatus).where(PfsenseLinkStatus.verificado_em >= limite_links)
    )
    registros_links = result_links.scalars().all()
    por_dia_links = {}
    for r in registros_links:
        dia = r.verificado_em.date().isoformat()
        por_dia_links.setdefault(dia, {"total": 0, "online": 0})
        por_dia_links[dia]["total"] += 1
        if r.online:
            por_dia_links[dia]["online"] += 1
    dias_links_ordenados = sorted(por_dia_links.keys())
    resultado["links"] = [
        round((por_dia_links[d]["online"] / por_dia_links[d]["total"]) * 100, 1) if por_dia_links[d]["total"] > 0 else None
        for d in dias_links_ordenados
    ]

    # Backups: historico salvo (backup_executions)
    from app.models import BackupExecution
    limite_backups = datetime.now(timezone.utc) - timedelta(days=14)
    result_backups = await db.execute(
        select(BackupExecution).where(BackupExecution.executado_em >= limite_backups)
    )
    execucoes = result_backups.scalars().all()
    por_dia_bkp = {}
    for e in execucoes:
        dia = e.executado_em.date().isoformat()
        por_dia_bkp.setdefault(dia, {"total": 0, "sucesso": 0})
        por_dia_bkp[dia]["total"] += 1
        if e.status in ("Success", "Warning", "sucesso"):
            por_dia_bkp[dia]["sucesso"] += 1
    dias_bkp_ordenados = sorted(por_dia_bkp.keys())
    resultado["backups"] = [
        round((por_dia_bkp[d]["sucesso"] / por_dia_bkp[d]["total"]) * 100, 1) if por_dia_bkp[d]["total"] > 0 else None
        for d in dias_bkp_ordenados
    ]

    ordem = ["servidores", "access_points", "links", "backups", "impressoras"]
    return {chave: resultado[chave] for chave in ordem if chave in resultado}


async def get_dados_relatorio(db, dias: int, categorias_selecionadas: list = None):
    """Monta os dados completos de relatorio (uptime, eventos, ranking de
    equipamentos problematicos) para um periodo arbitrario de dias.
    categorias_selecionadas: lista de chaves (servidores, access_points, links,
    vpns, vlans, backups) ou None para todas. Impressoras ficam de fora por
    causa do modo standby, que distorce o uptime."""
    from datetime import timezone
    from sqlalchemy import select
    from app.models import EventoSistema, PfsenseLinkStatus, PfsenseVpnVlanStatus, BackupExecution

    todas_categorias = ["servidores", "access_points", "links", "vpns", "vlans", "backups"]
    categorias = categorias_selecionadas or todas_categorias
    nomes_amigaveis = {
        "servidores": "Servidores", "access_points": "Access Points",
        "links": "Links de Rede", "vpns": "VPNs", "vlans": "VLANs", "backups": "Backups",
    }

    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    limite_anterior = datetime.now(timezone.utc) - timedelta(days=dias * 2)

    resultado_categorias = {}

    jobs_prometheus = {
        "servidores": "blackbox-servidores-tcp|blackbox-servidor-backup-principal",
        "access_points": "blackbox-access-points",
    }

    passo = "1h" if dias <= 2 else "1d"

    for chave in categorias:
        if chave in jobs_prometheus:
            job = jobs_prometheus[chave]
            query_media = f'avg(avg_over_time(probe_success{{job=~"{job}"}}[{dias}d])) * 100'
            query_serie = f'avg(probe_success{{job=~"{job}"}}) * 100' if passo == "1h" else f'avg(avg_over_time(probe_success{{job=~"{job}"}}[1d])) * 100'

            media_atual = None
            media_anterior = None
            serie = []
            async with httpx.AsyncClient(timeout=20.0) as client:
                try:
                    r1 = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={
                        "query": query_media, "time": datetime.now().timestamp()
                    })
                    d1 = r1.json().get("data", {}).get("result", [])
                    if d1:
                        media_atual = round(float(d1[0]["value"][1]), 1)
                except Exception:
                    pass
                try:
                    r2 = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={
                        "query": query_media, "time": (datetime.now() - timedelta(days=dias)).timestamp()
                    })
                    d2 = r2.json().get("data", {}).get("result", [])
                    if d2:
                        media_anterior = round(float(d2[0]["value"][1]), 1)
                except Exception:
                    pass
                try:
                    r3 = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                        "query": query_serie,
                        "start": limite.timestamp(),
                        "end": datetime.now().timestamp(),
                        "step": passo,
                    })
                    d3 = r3.json().get("data", {}).get("result", [])
                    if d3:
                        serie = [{"t": int(float(p[0]) * 1000), "v": round(float(p[1]), 1)} for p in d3[0].get("values", [])]
                except Exception:
                    pass

            resultado_categorias[chave] = {
                "nome": nomes_amigaveis[chave],
                "media": media_atual if media_atual is not None else 0.0,
                "mediaAnterior": media_anterior,
                "serie": serie,
            }

        elif chave == "links":
            result = await db.execute(select(PfsenseLinkStatus).where(PfsenseLinkStatus.verificado_em >= limite))
            registros = result.scalars().all()
            total = len(registros)
            online = sum(1 for r in registros if r.online)
            media = round((online / total) * 100, 1) if total > 0 else 0.0

            result_ant = await db.execute(select(PfsenseLinkStatus).where(
                PfsenseLinkStatus.verificado_em >= limite_anterior, PfsenseLinkStatus.verificado_em < limite
            ))
            registros_ant = result_ant.scalars().all()
            total_ant = len(registros_ant)
            online_ant = sum(1 for r in registros_ant if r.online)
            media_ant = round((online_ant / total_ant) * 100, 1) if total_ant > 0 else None

            por_dia = {}
            for r in registros:
                dia = r.verificado_em.date().isoformat()
                por_dia.setdefault(dia, {"total": 0, "online": 0})
                por_dia[dia]["total"] += 1
                if r.online:
                    por_dia[dia]["online"] += 1
            serie = [
                {"t": d, "v": round((v["online"] / v["total"]) * 100, 1)}
                for d, v in sorted(por_dia.items())
            ]

            resultado_categorias[chave] = {
                "nome": nomes_amigaveis[chave], "media": media,
                "mediaAnterior": media_ant, "serie": serie,
            }

        elif chave in ("vpns", "vlans"):
            tipo_registro = "vpn" if chave == "vpns" else "vlan"
            result = await db.execute(select(PfsenseVpnVlanStatus).where(
                PfsenseVpnVlanStatus.tipo == tipo_registro,
                PfsenseVpnVlanStatus.verificado_em >= limite,
            ))
            registros = result.scalars().all()
            total = len(registros)
            online = sum(1 for r in registros if r.online)
            media = round((online / total) * 100, 1) if total > 0 else 0.0

            result_ant = await db.execute(select(PfsenseVpnVlanStatus).where(
                PfsenseVpnVlanStatus.tipo == tipo_registro,
                PfsenseVpnVlanStatus.verificado_em >= limite_anterior,
                PfsenseVpnVlanStatus.verificado_em < limite,
            ))
            registros_ant = result_ant.scalars().all()
            total_ant = len(registros_ant)
            online_ant = sum(1 for r in registros_ant if r.online)
            media_ant = round((online_ant / total_ant) * 100, 1) if total_ant > 0 else None

            por_dia = {}
            for r in registros:
                dia = r.verificado_em.date().isoformat()
                por_dia.setdefault(dia, {"total": 0, "online": 0})
                por_dia[dia]["total"] += 1
                if r.online:
                    por_dia[dia]["online"] += 1
            serie = [
                {"t": d, "v": round((v["online"] / v["total"]) * 100, 1)}
                for d, v in sorted(por_dia.items())
            ]

            resultado_categorias[chave] = {
                "nome": nomes_amigaveis[chave], "media": media,
                "mediaAnterior": media_ant, "serie": serie,
            }

        elif chave == "backups":
            result = await db.execute(select(BackupExecution).where(BackupExecution.executado_em >= limite))
            execucoes = result.scalars().all()
            total = len(execucoes)
            sucesso = sum(1 for e in execucoes if e.status in ("Success", "Warning", "sucesso"))
            media = round((sucesso / total) * 100, 1) if total > 0 else 0.0

            result_ant = await db.execute(select(BackupExecution).where(
                BackupExecution.executado_em >= limite_anterior, BackupExecution.executado_em < limite
            ))
            execucoes_ant = result_ant.scalars().all()
            total_ant = len(execucoes_ant)
            sucesso_ant = sum(1 for e in execucoes_ant if e.status in ("Success", "Warning", "sucesso"))
            media_ant = round((sucesso_ant / total_ant) * 100, 1) if total_ant > 0 else None

            por_dia = {}
            for e in execucoes:
                dia = e.executado_em.date().isoformat()
                por_dia.setdefault(dia, {"total": 0, "sucesso": 0})
                por_dia[dia]["total"] += 1
                if e.status in ("Success", "Warning", "sucesso"):
                    por_dia[dia]["sucesso"] += 1
            serie = [
                {"t": d, "v": round((v["sucesso"] / v["total"]) * 100, 1)}
                for d, v in sorted(por_dia.items())
            ]

            resultado_categorias[chave] = {
                "nome": nomes_amigaveis[chave], "media": media,
                "mediaAnterior": media_ant, "serie": serie,
            }

    result_eventos = await db.execute(
        select(EventoSistema).where(EventoSistema.criado_em >= limite).order_by(EventoSistema.criado_em.desc())
    )
    eventos = result_eventos.scalars().all()

    eventos_lista = [
        {
            "id": e.id,
            "tipo": e.tipo,
            "mensagem": e.mensagem,
            "detalhes": e.detalhes,
            "criado_em": e.criado_em.isoformat(),
        }
        for e in eventos
    ]

    contagem_severidade = {"critico": 0, "atencao": 0, "bom": 0}
    for e in eventos:
        if e.tipo in contagem_severidade:
            contagem_severidade[e.tipo] += 1

    ocorrencias_por_equipamento = {}
    for e in eventos:
        if e.tipo == "critico":
            palavras = e.mensagem.split()
            nome_equip = " ".join(palavras[:2]) if len(palavras) >= 2 else e.mensagem
            ocorrencias_por_equipamento[nome_equip] = ocorrencias_por_equipamento.get(nome_equip, 0) + 1
    ranking = sorted(ocorrencias_por_equipamento.items(), key=lambda x: x[1], reverse=True)[:5]
    ranking_formatado = [{"equipamento": nome, "ocorrencias": qtd} for nome, qtd in ranking]

    medias_validas = [c["media"] for c in resultado_categorias.values() if c["media"] > 0]
    uptime_geral = round(sum(medias_validas) / len(medias_validas), 1) if medias_validas else 0.0
    total_incidentes = contagem_severidade["critico"] + contagem_severidade["atencao"]
    categorias_saudaveis = sum(1 for c in resultado_categorias.values() if c["media"] >= 99)

    melhor_cat = max(resultado_categorias.items(), key=lambda x: x[1]["media"]) if resultado_categorias else None
    pior_cat = min(resultado_categorias.items(), key=lambda x: x[1]["media"]) if resultado_categorias else None

    return {
        "periodo_dias": dias,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "resumo": {
            "uptimeGeral": uptime_geral,
            "totalIncidentes": total_incidentes,
            "categoriasSaudaveis": categorias_saudaveis,
            "totalCategorias": len(resultado_categorias),
            "melhorCategoria": nomes_amigaveis.get(melhor_cat[0]) if melhor_cat else None,
            "melhorCategoriaValor": melhor_cat[1]["media"] if melhor_cat else None,
            "piorCategoria": nomes_amigaveis.get(pior_cat[0]) if pior_cat else None,
            "piorCategoriaValor": pior_cat[1]["media"] if pior_cat else None,
        },
        "categorias": resultado_categorias,
        "eventos": eventos_lista,
        "severidade": contagem_severidade,
        "ranking": ranking_formatado,
    }


def gerar_html_relatorio_pdf(dados: dict, periodo_label: str) -> str:
    """Monta o HTML completo do relatorio, com CSS compativel com WeasyPrint
    (sem color-mix(), sem CSS Grid - tudo em flexbox/bloco com larguras fixas
    em px, que o motor de renderizacao do WeasyPrint suporta de forma solida).
    Retorna uma string HTML pronta pra converter em PDF."""

    CORES = {
        "verde": "#22c55e", "verde_dim": "rgba(34,197,94,0.14)",
        "ambar": "#f59e0b", "ambar_dim": "rgba(245,158,11,0.14)",
        "vermelho": "#ef4444", "vermelho_dim": "rgba(239,68,68,0.14)",
        "marca": "#6172f3", "marca_dim": "rgba(97,114,243,0.14)",
        "fundo": "#151b24", "elevado": "#1b2330", "tinta": "#eef2f8",
        "suave": "#97a3b5", "fraca": "#64707f", "linha": "rgba(255,255,255,0.08)",
        "borda": "rgba(255,255,255,0.10)",
    }

    def cor_faixa(media):
        if media >= 99:
            return CORES["verde"]
        if media >= 90:
            return CORES["ambar"]
        return CORES["vermelho"]

    def classe_faixa(media):
        if media >= 99:
            return "bom"
        if media >= 90:
            return "mid"
        return "ruim"

    def escapar(texto):
        if texto is None:
            return ""
        return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def formatar_data_hora(iso_str):
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%d/%m %H:%M")
        except Exception:
            return iso_str

    def gerar_linha_svg(serie, cor):
        if not serie or len(serie) < 2:
            return ""
        valores = [p["v"] for p in serie]
        vmin, vmax = min(valores + [0]), max(valores + [100])
        faixa_v = (vmax - vmin) or 1
        x0, x1, y0, y1 = 10, 450, 20, 120
        passo_x = (x1 - x0) / (len(serie) - 1 or 1)
        pontos = []
        for i, p in enumerate(serie):
            x = x0 + i * passo_x
            y = y1 - ((p["v"] - vmin) / faixa_v) * (y1 - y0)
            pontos.append((x, y))
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pontos))
        area = f"{path} L{pontos[-1][0]:.1f},{y1} L{pontos[0][0]:.1f},{y1} Z"
        return f'''<svg viewBox="0 0 460 140" style="width:100%;display:block;">
            <line x1="10" y1="20" x2="450" y2="20" stroke="{CORES['linha']}" stroke-dasharray="2 4"/>
            <line x1="10" y1="70" x2="450" y2="70" stroke="{CORES['linha']}" stroke-dasharray="2 4"/>
            <path d="{area}" fill="{cor}" opacity="0.1"/>
            <path d="{path}" fill="none" stroke="{cor}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>'''

    def gerar_donut(itens, raio=42, rotulo_central="eventos", valor_central=None):
        total = sum(i["valor"] for i in itens) or 1
        circunferencia = 2 * 3.14159265 * raio
        acumulado = 0
        arcos = []
        for item in itens:
            proporcao = item["valor"] / total
            comprimento = proporcao * circunferencia
            offset = -acumulado
            acumulado += comprimento
            arcos.append((item["cor"], comprimento, circunferencia, offset))
        circulos = "".join(
            f'<circle cx="55" cy="55" r="{raio}" fill="none" stroke="{cor}" stroke-width="14" '
            f'stroke-dasharray="{comp:.2f} {circ:.2f}" stroke-dashoffset="{off:.2f}" '
            f'transform="rotate(-90 55 55)"/>'
            for cor, comp, circ, off in arcos
        )
        total_real = sum(i["valor"] for i in itens)
        texto_central_html = ""
        if rotulo_central:
            valor_exibido = valor_central if valor_central is not None else str(total_real)
            tamanho_valor = 18 if len(str(valor_exibido)) <= 3 else (14 if len(str(valor_exibido)) <= 7 else 11)
            texto_central_html = f'''<text x="55" y="51" text-anchor="middle" font-size="{tamanho_valor}" font-weight="700" fill="{CORES['tinta']}">{valor_exibido}</text>
            <text x="55" y="65" text-anchor="middle" font-size="7" fill="{CORES['suave']}">{rotulo_central}</text>'''
        return f'''<svg viewBox="0 0 110 110" style="width:100px;height:100px;flex-shrink:0;">
            <circle cx="55" cy="55" r="{raio}" fill="none" stroke="{CORES['linha']}" stroke-width="14"/>
            {circulos}
            {texto_central_html}
        </svg>'''

    css = f'''
    @page {{ margin: 14mm; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Arial, Helvetica, sans-serif; background: #0b0f16; color: {CORES['tinta']}; margin: 0; padding: 0; }}
    .pagina {{ background: {CORES['fundo']}; border: 1px solid {CORES['borda']}; border-radius: 14px; padding: 22px 26px; margin-bottom: 16px; page-break-inside: avoid; }}
    .titulo {{ font-size: 18px; font-weight: 800; margin: 0 0 4px; }}
    .sub {{ font-size: 11.5px; color: {CORES['suave']}; margin-bottom: 14px; }}
    .kpi-linha {{ display: flex; margin-bottom: 16px; }}
    .kpi-linha .kpi {{ margin-right: 10px; }}
    .kpi-linha .kpi:last-child {{ margin-right: 0; }}
    .kpi {{ background: {CORES['elevado']}; border: 1px solid {CORES['borda']}; border-radius: 10px; padding: 12px 14px; flex: 1; page-break-inside: avoid; }}
    .kpi .rot {{ font-size: 10.5px; color: {CORES['suave']}; margin-bottom: 6px; }}
    .kpi .val {{ font-size: 20px; font-weight: 800; }}
    .val.bom {{ color: {CORES['verde']}; }} .val.mid {{ color: {CORES['ambar']}; }} .val.ruim {{ color: {CORES['vermelho']}; }}
    .caixa {{ background: {CORES['elevado']}; border: 1px solid {CORES['borda']}; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; page-break-inside: avoid; }}
    .caixa-titulo {{ font-size: 11.5px; font-weight: 600; margin-bottom: 8px; }}
    .texto-auto {{ font-size: 12px; line-height: 1.5; color: {CORES['suave']}; background: {CORES['elevado']}; border: 1px solid {CORES['borda']}; border-left: 3px solid {CORES['marca']}; border-radius: 6px; padding: 10px 14px; margin: 12px 0; page-break-inside: avoid; }}
    .texto-auto b {{ color: {CORES['tinta']}; }}
    .cat-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid {CORES['linha']}; }}
    .cat-nome {{ font-size: 16px; font-weight: 800; flex: 1; }}
    .cat-media {{ text-align: right; }}
    .cat-media .num {{ font-size: 22px; font-weight: 800; }}
    .cat-media .rot {{ font-size: 10px; color: {CORES['suave']}; }}
    .donut-wrap {{ display: flex; align-items: center; }}
    .donut-wrap svg {{ margin-right: 14px; }}
    .donut-legenda {{ flex: 1; min-width: 0; }}
    .donut-legenda .item {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 11px; margin-bottom: 7px; }}
    .donut-legenda .item .dot {{ margin-right: 6px; flex-shrink: 0; }}
    .donut-legenda .item .nome {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 6px; }}
    .donut-legenda .item span:not(.dot):not(.nome) {{ margin-right: 6px; }}
    .donut-legenda .item b {{ flex-shrink: 0; white-space: nowrap; }}
    .dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
    table.anexo {{ width: 100%; border-collapse: collapse; font-size: 10.5px; }}
    table.anexo th {{ text-align: left; font-size: 9.5px; color: {CORES['fraca']}; padding: 6px 8px; border-bottom: 1px solid {CORES['borda']}; }}
    table.anexo td {{ padding: 6px 8px; border-bottom: 1px solid {CORES['linha']}; }}
    table.anexo tr {{ page-break-inside: avoid; }}
    '''
    total_eventos = len(dados["eventos"])
    resumo = dados["resumo"]

    # Delta geral: media das variacoes individuais das categorias que tem mediaAnterior
    deltas_validos = [
        info["media"] - info["mediaAnterior"]
        for info in dados["categorias"].values()
        if info.get("mediaAnterior") is not None
    ]
    delta_geral = sum(deltas_validos) / len(deltas_validos) if deltas_validos else None
    delta_geral_html = ""
    if delta_geral is not None:
        cor_delta = CORES["verde"] if delta_geral >= 0 else CORES["vermelho"]
        seta = "▲" if delta_geral >= 0 else "▼"
        delta_geral_html = f'<div style="font-size:10px;color:{cor_delta};margin-top:4px;">{seta} {abs(delta_geral):.1f}% vs. período anterior</div>'

    total_paginas = 2 + len(dados["categorias"]) + (2 if dados.get("acessos") else 0) + 1  # capa + resumo + categorias + acessos (2 paginas, opcional) + anexo

    kpis_html = f'''
    <div class="kpi-linha">
      <div class="kpi"><div class="rot">Uptime médio geral</div><div class="val {classe_faixa(resumo['uptimeGeral'])}">{resumo['uptimeGeral']}%</div>{delta_geral_html}</div>
      <div class="kpi"><div class="rot">Total de incidentes</div><div class="val">{resumo['totalIncidentes']}</div></div>
      <div class="kpi"><div class="rot">Total de eventos</div><div class="val">{total_eventos}</div></div>
      <div class="kpi"><div class="rot">Categorias saudáveis</div><div class="val mid">{resumo['categoriasSaudaveis']} de {resumo['totalCategorias']}</div></div>
    </div>'''

    donut_geral = gerar_donut([
        {"valor": dados["severidade"]["critico"], "cor": CORES["vermelho"]},
        {"valor": dados["severidade"]["atencao"], "cor": CORES["ambar"]},
        {"valor": dados["severidade"]["bom"], "cor": CORES["verde"]},
    ])

    equipamento_top = dados["ranking"][0] if dados["ranking"] else None

    cards_destaque_html = f'''
    <div class="kpi-linha">
      <div class="kpi">
        <div class="rot">Melhor desempenho</div>
        <div class="val bom" style="font-size:16px;">{escapar(resumo.get('melhorCategoria') or '—')}</div>
        <div style="font-size:11px;color:{CORES['suave']};margin-top:2px;">{resumo.get('melhorCategoriaValor') if resumo.get('melhorCategoriaValor') is not None else '—'}%</div>
      </div>
      <div class="kpi">
        <div class="rot">Pior desempenho</div>
        <div class="val ruim" style="font-size:16px;">{escapar(resumo.get('piorCategoria') or '—')}</div>
        <div style="font-size:11px;color:{CORES['suave']};margin-top:2px;">{resumo.get('piorCategoriaValor') if resumo.get('piorCategoriaValor') is not None else '—'}%</div>
      </div>
      <div class="kpi">
        <div class="rot">Equipamento mais problemático</div>
        <div class="val" style="font-size:16px;">{escapar(equipamento_top['equipamento']) if equipamento_top else '—'}</div>
        <div style="font-size:11px;color:{CORES['vermelho']};margin-top:2px;">{f"{equipamento_top['ocorrencias']}x ocorrências" if equipamento_top else '—'}</div>
      </div>
    </div>'''

    pagina_capa = f'''
    <div class="pagina" style="min-height: 620px; display:flex; flex-direction:column; justify-content:space-between;">
      <div style="font-weight:800; font-size:15px;">E-OPS · Elcop</div>
      <div>
        <div style="display:inline-block; font-size:11px; font-weight:700; color:{CORES['marca']}; background:{CORES['marca_dim']}; border-radius:6px; padding:4px 10px; margin-bottom:16px; text-transform:uppercase;">Relatório · {escapar(periodo_label)}</div>
        <div style="font-size:26px; font-weight:800; margin-bottom:10px;">Relatório de Disponibilidade e Incidentes</div>
        <div style="font-size:14px; color:{CORES['suave']}; margin-bottom:4px;">{escapar(periodo_label)}</div>
        <div style="font-size:12px; color:{CORES['fraca']};">{', '.join(info['nome'] for info in dados['categorias'].values())}</div>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:11px; color:{CORES['fraca']}; border-top:1px solid {CORES['linha']}; padding-top:14px;">
        <span>Gerado automaticamente pelo E-OPS</span>
        <span>Gerado em {formatar_data_hora(dados['gerado_em'])}</span>
      </div>
      <div style="text-align:right; font-size:9px; color:{CORES['fraca']}; margin-top:8px;">1 de {total_paginas}</div>
    </div>'''

    pagina_resumo = f'''
    <div class="pagina">
      <div class="titulo">Resumo geral</div>
      <div class="sub">Visão consolidada das categorias selecionadas no período</div>
      {kpis_html}
      {cards_destaque_html}
      <div class="caixa">
        <div class="caixa-titulo">Eventos por severidade — {total_eventos} no total</div>
        <div class="donut-wrap">
          {donut_geral}
          <div class="donut-legenda">
            <div class="item"><span class="dot" style="background:{CORES['vermelho']}"></span>Críticos<b>{dados['severidade']['critico']}</b></div>
            <div class="item"><span class="dot" style="background:{CORES['ambar']}"></span>Atenção<b>{dados['severidade']['atencao']}</b></div>
            <div class="item"><span class="dot" style="background:{CORES['verde']}"></span>Resolvidos<b>{dados['severidade']['bom']}</b></div>
          </div>
        </div>
      </div>
      <div class="texto-auto">
        No geral, as categorias selecionadas mantiveram <b>{resumo['uptimeGeral']}% de disponibilidade</b> no período.
        {f"O destaque negativo foi <b>{escapar(resumo['piorCategoria'])}</b>, com {resumo['piorCategoriaValor']}% de uptime." if resumo.get('piorCategoria') else ''}
      </div>
      <div style="text-align:right; font-size:9px; color:{CORES['fraca']}; margin-top:8px;">2 de {total_paginas}</div>
    </div>'''
    PALAVRA_CHAVE_POR_CATEGORIA = {
        "Servidores": "Servidor", "Access Points": "Access Point", "Links de Rede": "Link",
        "VPNs": "VPN", "VLANs": "VLAN", "Backups": "Backup",
    }

    paginas_categorias = []
    for chave, info in dados["categorias"].items():
        cor = cor_faixa(info["media"])
        delta = None
        if info.get("mediaAnterior") is not None:
            delta = info["media"] - info["mediaAnterior"]
        delta_texto = f" ({'melhora' if delta >= 0 else 'queda'} de {abs(delta):.1f} pontos vs. período anterior)" if delta is not None else ""
        grafico = gerar_linha_svg(info["serie"], cor) or f'<div style="color:{CORES["fraca"]};font-size:11px;">Sem dados suficientes no período.</div>'

        palavra_chave = PALAVRA_CHAVE_POR_CATEGORIA.get(info["nome"], info["nome"])
        eventos_cat = [e for e in dados["eventos"] if palavra_chave in e["mensagem"]]

        sev_cat = {"critico": 0, "atencao": 0, "bom": 0}
        for e in eventos_cat:
            if e["tipo"] in sev_cat:
                sev_cat[e["tipo"]] += 1
        donut_cat = gerar_donut([
            {"valor": sev_cat["critico"], "cor": CORES["vermelho"]},
            {"valor": sev_cat["atencao"], "cor": CORES["ambar"]},
            {"valor": sev_cat["bom"], "cor": CORES["verde"]},
        ], raio=34)

        contagem_equip = {}
        for e in eventos_cat:
            if e["tipo"] == "critico":
                nome_equip = " ".join(e["mensagem"].split()[:2])
                contagem_equip[nome_equip] = contagem_equip.get(nome_equip, 0) + 1
        ranking_cat = sorted(contagem_equip.items(), key=lambda x: x[1], reverse=True)[:5]
        ranking_html = "".join(
            f'<div style="display:flex;align-items:center;padding:5px 0;font-size:11px;border-bottom:1px solid {CORES["linha"]};">'
            f'<span style="width:16px;height:16px;margin-right:8px;border-radius:4px;background:{CORES["linha"]};color:{CORES["suave"]};font-size:9px;text-align:center;line-height:16px;flex-shrink:0;">{i+1}</span>'
            f'<span style="flex:1;margin-right:8px;">{escapar(nome)}</span>'
            f'<span style="color:{CORES["vermelho"]};font-weight:700;">{qtd}x</span></div>'
            for i, (nome, qtd) in enumerate(ranking_cat)
        ) or f'<div style="font-size:11px;color:{CORES["fraca"]};">Nenhuma ocorrência crítica nesta categoria.</div>'

        timeline_html = "".join(
            f'<div style="display:flex;padding:5px 0;border-bottom:1px solid {CORES["linha"]};font-size:10.5px;">'
            f'<span style="color:{CORES["suave"]};width:60px;margin-right:8px;flex-shrink:0;">{formatar_data_hora(e["criado_em"])}</span>'
            f'<span>{escapar(e["mensagem"])}</span></div>'
            for e in eventos_cat[:8]
        ) or f'<div style="font-size:11px;color:{CORES["fraca"]};">Nenhum evento nesta categoria.</div>'

        paginas_categorias.append(f'''
        <div class="pagina" style="border-left: 3px solid {cor};">
          <div class="cat-header">
            <div class="cat-nome">{escapar(info['nome'])}</div>
            <div class="cat-media"><div class="num" style="color:{cor}">{info['media']}%</div><div class="rot">uptime médio</div></div>
          </div>
          <div class="caixa"><div class="caixa-titulo">Evolução do uptime — {escapar(periodo_label)}</div>{grafico}</div>
          <div class="texto-auto">
            <b>{escapar(info['nome'])}</b> apresentou {info['media']}% de uptime no período{delta_texto}.
          </div>
          <div class="caixa">
            <div class="caixa-titulo">Distribuição de eventos nesta categoria</div>
            <div class="donut-wrap">
              {donut_cat}
              <div class="donut-legenda">
                <div class="item"><span class="dot" style="background:{CORES['vermelho']}"></span>Crítico<b>{sev_cat['critico']}</b></div>
                <div class="item"><span class="dot" style="background:{CORES['ambar']}"></span>Atenção<b>{sev_cat['atencao']}</b></div>
                <div class="item"><span class="dot" style="background:{CORES['verde']}"></span>Resolvido<b>{sev_cat['bom']}</b></div>
              </div>
            </div>
          </div>
          <div class="caixa"><div class="caixa-titulo">Ranking de equipamentos problemáticos</div>{ranking_html}</div>
          <div class="caixa"><div class="caixa-titulo">Linha do tempo de eventos</div>{timeline_html}</div>
        </div>''')


    ROTULO_SEVERIDADE = {"critico": "Crítico", "atencao": "Atenção", "bom": "Resolvido"}

    def badge_severidade(tipo):
        cor = CORES["vermelho"] if tipo == "critico" else CORES["ambar"] if tipo == "atencao" else CORES["verde"]
        cor_dim = CORES["vermelho_dim"] if tipo == "critico" else CORES["ambar_dim"] if tipo == "atencao" else CORES["verde_dim"]
        rotulo = ROTULO_SEVERIDADE.get(tipo, tipo)
        return f'<span style="display:inline-block;padding:2px 8px;border-radius:5px;font-size:9.5px;font-weight:700;color:{cor};background:{cor_dim};">{rotulo}</span>'

    linhas_anexo = "".join(
        f'''<tr>
          <td>{formatar_data_hora(ev['criado_em'])}</td>
          <td>{escapar(ev['mensagem'])}</td>
          <td>{escapar(ev.get('detalhes') or '—')}</td>
          <td>{badge_severidade(ev['tipo'])}</td>
        </tr>'''
        for ev in dados["eventos"][:150]
    )

    pagina_anexo = f'''
    <div class="pagina">
      <div class="titulo" style="font-size:15px;">Anexo — todos os eventos do período</div>
      <div class="sub">{total_eventos} eventos, ordenados cronologicamente</div>
      <table class="anexo">
        <thead><tr><th>Data/hora</th><th>Evento</th><th>Detalhes</th><th>Severidade</th></tr></thead>
        <tbody>{linhas_anexo}</tbody>
      </table>
    </div>'''

    def _fmt_bytes_relatorio(n):
        n = n or 0
        for unidade in ["B", "KB", "MB", "GB", "TB"]:
            if n < 1024:
                return f"{n:.1f} {unidade}"
            n /= 1024
        return f"{n:.1f} PB"

    pagina_acessos = ""
    if dados.get("acessos"):
        ac = dados["acessos"]
        paleta_ac = [CORES["marca"], CORES["verde"], CORES["ambar"], CORES["vermelho"], CORES["suave"]]
        top_sites_ac = ac.get("top_sites") or []
        donut_sites = gerar_donut([
            {"valor": s["volume_bytes"], "cor": paleta_ac[i % len(paleta_ac)]}
            for i, s in enumerate(top_sites_ac)
        ], raio=42, rotulo_central="tráfego", valor_central=_fmt_bytes_relatorio(ac['resumo']['volume_total_bytes'])) if top_sites_ac else ""
        legenda_sites = "".join(
            f'<div class="item"><span class="dot" style="background:{paleta_ac[i % len(paleta_ac)]}"></span><span class="nome">{escapar(s["categoria"])}</span><b>{s["percentual"]}%</b></div>'
            for i, s in enumerate(top_sites_ac)
        )

        def _linhas_ranking_ac(ranking):
            return "".join(
                f'''<tr>
                  <td>{escapar(r["hostname"])}</td>
                  <td>{_fmt_bytes_relatorio(r["volume_bytes"])}</td>
                  <td>{escapar(r.get("categoria_principal") or "—")}</td>
                </tr>'''
                for r in ranking
            )

        pagina_acessos = f'''
        <div class="pagina">
          <div class="titulo">Acessos à internet</div>
          <div class="sub">Resumo de navegação capturado no período</div>
          <div class="kpi-grade">
            <div class="kpi"><div class="rot">Volume total trafegado</div><div class="val" style="font-size:16px;">{_fmt_bytes_relatorio(ac['resumo']['volume_total_bytes'])}</div></div>
            <div class="kpi"><div class="rot">Categoria mais acessada</div><div class="val" style="font-size:16px;">{escapar(ac['resumo']['categoria_mais_acessada'] or '—')}</div></div>
            <div class="kpi"><div class="rot">Dispositivos monitorados</div><div class="val" style="font-size:16px;">{ac['resumo']['dispositivos_monitorados']}</div></div>
          </div>
          <div class="caixa">
            <div class="caixa-titulo">Top categorias acessadas na rede</div>
            <div class="donut-wrap">
              {donut_sites}
              <div class="donut-legenda">{legenda_sites}</div>
            </div>
          </div>
        </div>
        <div class="pagina">
          <div class="titulo" style="font-size:15px;">Acessos à internet — rankings</div>
          <div class="sub">Dispositivos com maior volume trafegado no período</div>
          <div>
            <div class="caixa-titulo" style="margin-bottom:6px;">Top 10 dispositivos por volume</div>
            <table class="anexo">
              <thead><tr><th>Dispositivo</th><th>Volume</th><th>Categoria principal</th></tr></thead>
              <tbody>{_linhas_ranking_ac(ac['ranking_geral'])}</tbody>
            </table>
          </div>
          <div style="margin-top:18px;">
            <div class="caixa-titulo" style="margin-bottom:6px;">Top 10 — uso não corporativo (lazer)</div>
            <table class="anexo">
              <thead><tr><th>Dispositivo</th><th>Volume</th><th>Categoria principal</th></tr></thead>
              <tbody>{_linhas_ranking_ac(ac['ranking_pessoal'])}</tbody>
            </table>
          </div>
        </div>'''

    html_final = f'''<!doctype html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>
{pagina_capa}
{pagina_resumo}
{''.join(paginas_categorias)}
{pagina_acessos}
{pagina_anexo}
</body></html>'''

    return html_final
