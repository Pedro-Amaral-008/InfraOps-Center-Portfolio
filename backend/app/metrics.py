import httpx
import time

PROMETHEUS_URL = "http://prometheus:9090"


async def query_range(query: str, minutos: int = 60, step: str = "30s"):
    fim = int(time.time())
    inicio = fim - (minutos * 60)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": query,
                    "start": inicio,
                    "end": fim,
                    "step": step,
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("result", [])
        except Exception:
            return []


def formatar_serie(resultado):
    if not resultado:
        return []
    valores = resultado[0].get("values", [])
    return [
        {"timestamp": int(v[0]) * 1000, "valor": round(float(v[1]), 2)}
        for v in valores
    ]


async def get_metricas_host(minutos: int = 60):
    step = "15s" if minutos <= 30 else ("30s" if minutos <= 120 else "5m")

    cpu = await query_range(
        '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)',
        minutos, step
    )

    ram = await query_range(
        '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
        minutos, step
    )

    disco = await query_range(
        '100 - ((node_filesystem_avail_bytes{mountpoint="/"} * 100) / node_filesystem_size_bytes{mountpoint="/"})',
        minutos, step
    )

    rede_rx = await query_range(
        'rate(node_network_receive_bytes_total{device!="lo"}[2m]) * 8 / 1024',
        minutos, step
    )

    rede_tx = await query_range(
        'rate(node_network_transmit_bytes_total{device!="lo"}[2m]) * 8 / 1024',
        minutos, step
    )

    return {
        "cpu": formatar_serie(cpu),
        "ram": formatar_serie(ram),
        "disco": formatar_serie(disco),
        "rede_rx_kbps": formatar_serie(rede_rx),
        "rede_tx_kbps": formatar_serie(rede_tx),
    }


async def query_instant_by_instance(query: str):
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


async def get_latencia_por_categoria(job: str, minutos: int = 60):
    step = "30s" if minutos <= 60 else "5m"

    resultado = await query_range(
        f'probe_duration_seconds{{job=~"{job}"}} * 1000',
        minutos, step
    )

    series = []
    for r in resultado:
        metric = r.get("metric", {})
        valores = r.get("values", [])
        series.append({
            "nome": metric.get("nome", metric.get("instance", "desconhecido")),
            "instance": metric.get("instance", ""),
            "pontos": [
                {"timestamp": int(v[0]) * 1000, "valor": round(float(v[1]), 1)}
                for v in valores
            ],
        })

    return series
