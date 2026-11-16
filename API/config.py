from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Configuração lida de variáveis de ambiente (.env).

    Nenhuma chave é obrigatória para subir a API: as fontes abertas
    (POWER, SDA, Open-Meteo, STAC, USGS) funcionam sem cadastro.
    """

    def __init__(self) -> None:
        self.cache_dir = Path(os.getenv("CACHE_DIR") or (BASE_DIR / ".cache"))
        self.cache_ttl_seconds = _int("CACHE_TTL_SECONDS", 6 * 3600)
        self.http_timeout_seconds = _float("HTTP_TIMEOUT_SECONDS", 25.0)
        self.http_retries = _int("HTTP_RETRIES", 2)
        self.cors_origins = _list("CORS_ORIGINS", "*")

        # Serviço de fórmulas (CerradoShift). A base é a raiz da API deles.
        # Ex.: FORMULAS_BASE_URL=http://localhost:8000
        self.formulas_base_url = (os.getenv("FORMULAS_BASE_URL") or "").strip().rstrip("/") or None
        self.formulas_field_path = (
            os.getenv("FORMULAS_FIELD_PATH") or "/api/v1/assessments/field"
        ).strip()
        self.formulas_transition_path = (
            os.getenv("FORMULAS_TRANSITION_PATH")
            or "/api/v1/assessments/cerrado-transition-options"
        ).strip()
        self.formulas_timeout_seconds = _float("FORMULAS_TIMEOUT_SECONDS", 30.0)

        # Credenciais opcionais (fontes que hoje estão bloqueadas sem conta).
        self.earthdata_username = (os.getenv("EARTHDATA_USERNAME") or "").strip() or None
        self.earthdata_password = (os.getenv("EARTHDATA_PASSWORD") or "").strip() or None
        self.nass_api_key = (os.getenv("NASS_API_KEY") or "").strip() or None
        self.ams_api_key = (os.getenv("AMS_API_KEY") or "").strip() or None
        self.openet_api_key = (os.getenv("OPENET_API_KEY") or "").strip() or None
        self.cdsapi_url = (os.getenv("CDSAPI_URL") or "").strip() or None
        self.cdsapi_key = (os.getenv("CDSAPI_KEY") or "").strip() or None

    @property
    def earthdata_configured(self) -> bool:
        return bool(self.earthdata_username and self.earthdata_password)

    def formulas_url(self, path: str) -> str | None:
        if not self.formulas_base_url:
            return None
        return f"{self.formulas_base_url}{path}"


settings = Settings()
