from __future__ import annotations

from datetime import date, timedelta
import httpx

from formula_engine.core.evapotranspiration import wind_10m_to_2m
from formula_engine.core.schemas import DailyWeather

POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMETERS = (
    "T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR,T2MDEW"
)


async def fetch_nasa_power_daily(
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
    timeout_seconds: float = 45.0,
) -> list[DailyWeather]:
    """Busca dados diários POWER para um ponto e os converte para o schema interno.

    POWER usa parâmetros diários de resolução nativa da fonte e oferece LST/UTC;
    pedimos UTC explicitamente para a série temporal ser reproduzível.
    Consulte a documentação do POWER antes de alterar parâmetros/unidades.
    """
    if start_date > end_date:
        raise ValueError("start_date não pode ser posterior a end_date.")
    params = {
        "parameters": POWER_PARAMETERS,
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(POWER_DAILY_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    try:
        parameter_data = payload["properties"]["parameter"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Resposta NASA POWER sem properties.parameter.") from exc

    # NASA POWER codifica datas como YYYYMMDD; -999/-999.0 é valor ausente.
    required = ["T2M_MAX", "T2M_MIN", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "PRECTOTCORR"]
    missing = [name for name in required if name not in parameter_data]
    if missing:
        raise ValueError(f"Parâmetros ausentes na resposta POWER: {missing}")

    date_keys = sorted(parameter_data[required[0]].keys())
    output: list[DailyWeather] = []
    for key in date_keys:
        values: dict[str, float | None] = {}
        for name in required + ["T2MDEW"]:
            raw = parameter_data.get(name, {}).get(key)
            try:
                value = float(raw) if raw is not None else None
            except (TypeError, ValueError):
                value = None
            if value is not None and value <= -900:
                value = None
            values[name] = value

        # Não inventar valor ausente: o modelo precisa dos seis campos para ET0.
        if any(values[name] is None for name in required):
            continue
        day = date(int(key[:4]), int(key[4:6]), int(key[6:8]))
        dewpoint = values["T2MDEW"]
        output.append(DailyWeather(
            day=day,
            tmax_c=float(values["T2M_MAX"]),
            tmin_c=float(values["T2M_MIN"]),
            rh_mean_pct=float(values["RH2M"]),
            wind_2m_m_s=float(values["WS2M"]),
            solar_radiation_mj_m2_day=float(values["ALLSKY_SFC_SW_DWN"]),
            precipitation_mm_day=float(values["PRECTOTCORR"]),
            dew_point_c=float(dewpoint) if dewpoint is not None else None,
        ))
    if not output:
        raise ValueError("NASA POWER não retornou dias completos para os parâmetros solicitados.")
    found = {row.day for row in output}
    expected = set()
    cursor = start_date
    while cursor <= end_date:
        expected.add(cursor)
        cursor += timedelta(days=1)
    missing_dates = sorted(expected - found)
    if missing_dates:
        sample = ", ".join(day.isoformat() for day in missing_dates[:8])
        raise ValueError(f"NASA POWER não forneceu todos os dias do período. Dias ausentes (amostra): {sample}. Ajuste o intervalo ou complemente com estação local.")
    return output
