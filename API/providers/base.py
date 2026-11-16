from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    """Resultado padronizado de uma fonte externa.

    Todas as rotas devolvem isso (ou uma lista disso) para que o app consiga
    mostrar na tela "o que respondeu, o que falhou e por quê" — em hackathon
    isso vale ouro na hora da demo.
    """

    name: str
    ok: bool = True
    data: Any = None
    cached: bool = False
    warnings: list[str] = field(default_factory=list)
    detail: str | None = None
    ms: int = 0

    def as_source(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": "ok" if self.ok else "error",
            "cached": self.cached,
            "latency_ms": self.ms,
            "detail": self.detail,
        }


async def guard(
    name: str,
    factory: Callable[[], Awaitable[ProviderResult]],
) -> ProviderResult:
    """Executa um provider isolando falhas: uma fonte fora do ar nunca derruba
    a resposta inteira."""
    started = time.perf_counter()
    try:
        result = await factory()
    except Exception as exc:  # noqa: BLE001 - queremos capturar tudo aqui
        return ProviderResult(
            name=name,
            ok=False,
            detail=f"{type(exc).__name__}: {exc}"[:400],
            ms=int((time.perf_counter() - started) * 1000),
        )
    result.ms = int((time.perf_counter() - started) * 1000)
    return result
