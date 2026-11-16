from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx


class CachedHTTP:
    """Cliente HTTP com cache em disco e retry.

    Motivação: as fontes são lentas (ISRIC chega a 12 s, POWER ~1 s) e algumas
    têm limite de requisições. O cache também permite mostrar a demo mesmo se
    a internet do evento oscilar. O cache é por URL+parâmetros, com TTL.
    """

    def __init__(
        self,
        *,
        timeout: float,
        cache_dir: Path,
        ttl: int,
        retries: int = 2,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={"User-Agent": "nasa-agro-api/0.1 (hackathon)"},
            follow_redirects=True,
        )
        self._cache_dir = cache_dir
        self._default_ttl = ttl
        self._retries = max(0, retries)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ API

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        ttl: int | None = None,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any, bool]:
        """Retorna (json, veio_do_cache)."""
        return await self._request(
            "GET", url, params=params, ttl=ttl, timeout=timeout, headers=headers
        )

    async def post_json(
        self,
        url: str,
        *,
        body: Any = None,
        params: dict[str, Any] | None = None,
        ttl: int | None = None,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any, bool]:
        return await self._request(
            "POST", url, params=params, body=body, ttl=ttl, timeout=timeout, headers=headers
        )

    # -------------------------------------------------------------- interno

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        body: Any = None,
        ttl: int | None = None,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any, bool]:
        key = self._cache_key(method, url, params, body)
        path = self._cache_dir / f"{key}.json"

        cached = self._read_cache(path, self._default_ttl if ttl is None else ttl)
        if cached is not None:
            return cached, True

        extra: dict[str, Any] = {}
        if timeout is not None:
            extra["timeout"] = httpx.Timeout(timeout)

        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=params,
                    json=body,
                    headers=headers,
                    **extra,
                )
                response.raise_for_status()
                data = response.json()
                self._write_cache(path, data)
                return data, False
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self._retries:
                    await asyncio.sleep(0.4 * (attempt + 1))

        raise last_error if last_error else RuntimeError(f"falha ao chamar {url}")

    def _cache_key(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        body: Any,
    ) -> str:
        payload = json.dumps(
            {"method": method, "url": url, "params": params, "body": body},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]

    def _read_cache(self, path: Path, ttl: int) -> Any | None:
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - envelope["stored_at"] > ttl:
                return None
            return envelope["data"]
        except (OSError, ValueError, KeyError):
            return None

    def _write_cache(self, path: Path, data: Any) -> None:
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps({"stored_at": time.time(), "data": data}, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(path)
        except OSError:
            tmp.unlink(missing_ok=True)
