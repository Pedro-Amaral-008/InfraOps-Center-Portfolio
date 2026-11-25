"""Módulo de clima - integração OpenWeatherMap + alertas Telegram."""
import httpx
import json
import os
from datetime import datetime, timezone, timedelta
from app.config import settings

LAT = -16.6933
LON = -49.2373
FUSO = timezone(timedelta(hours=-3))

ICONES = {
    "01d": "☀️", "01n": "🌙",
    "02d": "🌤️", "02n": "🌙",
    "03d": "☁️", "03n": "☁️",
    "04d": "☁️", "04n": "☁️",
    "09d": "🌧️", "09n": "🌧️",
    "10d": "🌦️", "10n": "🌦️",
    "11d": "⛈️", "11n": "⛈️",
    "13d": "❄️", "13n": "❄️",
    "50d": "🌫️", "50n": "🌫️",
}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "dados", "clima_telegram_config.json")

DEFAULT_CONFIG = {
    "chuva_leve": False,
    "chuva_moderada": True,
    "chuva_forte": True,
    "chuva_severa": True,
    "calor_intenso": True,
    "vento_forte": True,
}


def ler_config_telegram():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()


def salvar_config_telegram(config: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


async def buscar_clima_atual():
    api_key = settings.openweather_api_key
    if not api_key:
        return None

    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={LAT}&lon={LON}&appid={api_key}&units=metric&lang=pt_br"
    )

    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

    rain_1h = data.get("rain", {}).get("1h", 0) or 0

    # Usa o maior valor entre rain.1h real e estimativa pelo weather code
    # O rain.1h do OpenWeatherMap e impreciso em Goiania (ex: 0.15mm pra trovoada forte)
    weather_id = data["weather"][0]["id"]
    estimativas_por_codigo = {
        200: 1.0, 201: 3.0, 202: 8.0,
        210: 0.5, 211: 1.0, 212: 4.0, 221: 2.0,
        230: 0.5, 231: 1.0, 232: 2.0,
        300: 0.3, 301: 0.5, 302: 1.0,
        310: 0.5, 311: 1.0, 312: 2.0, 313: 2.0, 314: 3.0, 321: 1.0,
        500: 1.5, 501: 4.0, 502: 10.0, 503: 30.0, 504: 50.0,
        511: 2.0, 520: 3.0, 521: 5.0, 522: 10.0, 531: 5.0,
        600: 0.5, 601: 2.0, 602: 5.0,
        611: 1.0, 612: 1.0, 613: 2.0, 615: 1.0, 616: 2.0,
        620: 1.0, 621: 3.0, 622: 5.0,
    }
    if 200 <= weather_id <= 622:
        estimado = estimativas_por_codigo.get(weather_id, 1.0)
        rain_1h = max(rain_1h, estimado)

    return {
        "temperatura": data["main"]["temp"],
        "sensacao": data["main"]["feels_like"],
        "umidade": data["main"]["humidity"],
        "pressao": data["main"]["pressure"],
        "vento_kmh": round(data["wind"]["speed"] * 3.6, 1),
        "vento_direcao": data["wind"].get("deg"),
        "precipitacao_mm": rain_1h,
        "weather_id": weather_id,
        "visibilidade_m": data.get("visibility", 10000),
        "nuvens": data["clouds"]["all"],
        "descricao": data["weather"][0]["description"],
        "icone": ICONES.get(data["weather"][0]["icon"], "🌤️"),
    }


async def buscar_previsao_horas():
    api_key = settings.openweather_api_key
    if not api_key:
        return []

    url = (
        f"https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={LAT}&lon={LON}&appid={api_key}&units=metric&lang=pt_br&cnt=12"
    )

    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

    resultado = []
    for item in data.get("list", []):
        dt = datetime.fromtimestamp(item["dt"], tz=FUSO)
        rain_3h = item.get("rain", {}).get("3h", 0) or 0
        pop = item.get("pop", 0) * 100

        resultado.append({
            "hora": dt.strftime("%Hh"),
            "temperatura": item["main"]["temp"],
            "probabilidade_chuva": round(pop),
            "precipitacao_mm": rain_3h,
            "icone": ICONES.get(item["weather"][0]["icon"], "🌤️"),
            "descricao": item["weather"][0]["description"],
        })

    return resultado


def gerar_alertas(dados_atuais, previsao):
    alertas = []
    agora = datetime.now(FUSO).isoformat()

    if not dados_atuais:
        return alertas

    precip = dados_atuais.get("precipitacao_mm", 0)
    temp = dados_atuais.get("temperatura", 0)
    vento = dados_atuais.get("vento_kmh", 0)
    umidade = dados_atuais.get("umidade", 0)

    if precip >= 50:
        alertas.append({"tipo": "critical", "mensagem": f"Chuva severa: {precip:.1f} mm/h", "hora": agora})
    elif precip >= 7.5:
        alertas.append({"tipo": "critical", "mensagem": f"Chuva forte: {precip:.1f} mm/h", "hora": agora})
    elif precip >= 2.5:
        alertas.append({"tipo": "warning", "mensagem": f"Chuva moderada: {precip:.1f} mm/h", "hora": agora})
    elif precip > 0:
        alertas.append({"tipo": "info", "mensagem": f"Chuva leve: {precip:.1f} mm/h", "hora": agora})

    if temp >= 38:
        alertas.append({"tipo": "critical", "mensagem": f"Calor intenso: {temp:.1f}°C", "hora": agora})
    elif temp >= 35:
        alertas.append({"tipo": "warning", "mensagem": f"Temperatura elevada: {temp:.1f}°C", "hora": agora})

    if vento >= 60:
        alertas.append({"tipo": "critical", "mensagem": f"Vento forte: {vento:.1f} km/h", "hora": agora})
    elif vento >= 40:
        alertas.append({"tipo": "warning", "mensagem": f"Vento moderado: {vento:.1f} km/h", "hora": agora})

    if umidade < 20:
        alertas.append({"tipo": "critical", "mensagem": f"Umidade crítica: {umidade}%", "hora": agora})
    elif umidade < 30:
        alertas.append({"tipo": "warning", "mensagem": f"Umidade baixa: {umidade}%", "hora": agora})

    for h in previsao[:4]:
        if h.get("probabilidade_chuva", 0) >= 70:
            alertas.append({
                "tipo": "warning",
                "mensagem": f"Chuva prevista às {h['hora']} ({h['probabilidade_chuva']}%)",
                "hora": agora,
            })
            break

    if not alertas:
        alertas.append({"tipo": "ok", "mensagem": "Nenhum alerta meteorológico ativo no momento.", "hora": agora})

    return alertas


async def enviar_alerta_telegram(mensagem: str):
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}

    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
    except Exception:
        pass


async def verificar_e_alertar_telegram(dados, previsao):
    config = ler_config_telegram()
    if not dados:
        return

    precip = dados.get("precipitacao_mm", 0)
    temp = dados.get("temperatura", 0)
    vento = dados.get("vento_kmh", 0)
    msgs = []

    if precip >= 50 and config.get("chuva_severa"):
        msgs.append(f"🌊 <b>CHUVA SEVERA</b>\nPrecipitação: {precip:.1f} mm/h")
    elif precip >= 7.5 and config.get("chuva_forte"):
        msgs.append(f"⛈️ <b>CHUVA FORTE</b>\nPrecipitação: {precip:.1f} mm/h")
    elif precip >= 2.5 and config.get("chuva_moderada"):
        msgs.append(f"🌧️ <b>CHUVA MODERADA</b>\nPrecipitação: {precip:.1f} mm/h")
    elif precip > 0 and config.get("chuva_leve"):
        msgs.append(f"🌦️ <b>Chuva Leve</b>\nPrecipitação: {precip:.1f} mm/h")

    if temp >= 38 and config.get("calor_intenso"):
        msgs.append(f"🌡️ <b>CALOR INTENSO</b>\nTemperatura: {temp:.1f}°C")

    if vento >= 60 and config.get("vento_forte"):
        msgs.append(f"💨 <b>VENTO FORTE</b>\nVelocidade: {vento:.1f} km/h")

    for h in previsao[:4]:
        if h.get("probabilidade_chuva", 0) >= 80 and h.get("precipitacao_mm", 0) >= 2.5:
            if config.get("chuva_moderada") or config.get("chuva_forte"):
                msgs.append(f"⚠️ <b>PREVISÃO DE CHUVA</b>\nÀs {h['hora']}: {h['probabilidade_chuva']}% de probabilidade")
                break

    if not msgs:
        return

    hora = datetime.now(FUSO).strftime("%H:%M")
    umidade = dados.get("umidade", 0)
    nuvens = dados.get("nuvens", 0)
    descricao = dados.get("descricao", "")

    # Montar previsao proximas horas
    prev_texto = ""
    for h in previsao[:3]:
        prob = h.get("probabilidade_chuva", 0)
        p_mm = h.get("precipitacao_mm", 0)
        prev_texto += f"  {h['hora']} — {prob}% chance, {p_mm:.1f} mm/h\n"

    for msg in msgs:
        texto = (
            f"🌤️ <b>E-Ops Clima — Goiânia</b>\n"
            f"📍 Região da Elcop — Jardim Goiás\n\n"
            f"{msg}\n\n"
            f"🌡️ Temp: {temp:.1f}°C | 💧 Umidade: {umidade}%\n"
            f"💨 Vento: {vento:.1f} km/h | ☁️ Nuvens: {nuvens}%\n"
            f"📝 {descricao.capitalize()}\n\n"
        )
        if prev_texto:
            texto += f"📊 <b>Próximas horas:</b>\n{prev_texto}\n"
        texto += (
            f"⚠️ <b>Atenção:</b> Verificar se há infiltração de água na sala do CPD, "
            f"entrada de água pelo cabo dos APs, estado dos nobreaks "
            f"e estabilidade dos links de internet.\n\n"
            f"🕐 {hora}\n\n📡 Fonte: OpenWeatherMap"
        )
        await enviar_alerta_telegram(texto)
