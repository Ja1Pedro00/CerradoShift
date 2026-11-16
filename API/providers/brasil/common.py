"""Utilitários para serviços HTTP; não inventa valores quando a fonte falha."""
import httpx


async def get_json(url: str, *, params: dict | None = None,
                   headers: dict | None = None, timeout: float = 12):
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()


def status(source: str, state: str, *, data=None, warning=None, **extra):
    result = {"source": source, "status": state, "data": data, **extra}
    if warning:
        result["warning"] = str(warning)
    return result


def safe_error(source: str, exc: Exception):
    return status(source, "error", warning=f"{type(exc).__name__}: {exc}")
