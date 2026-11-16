"""ANA HidroWebService: cliente configurável após credenciamento.

As rotas e formato de autenticação devem seguir o Swagger/manual oficial.
Nenhum token ou estação é inventado.
"""
import os
from .common import get_json, safe_error, status


async def consultar_serie(codigo_estacao: str, inicio: str, fim: str):
    template = os.getenv("ANA_ENDPOINT_TEMPLATE", "").strip()
    token = os.getenv("ANA_ACCESS_TOKEN", "").strip()
    if not template:
        return status("ANA HidroWebService", "not_configured",
                      warning="Configure ANA_ENDPOINT_TEMPLATE após obter acesso e verificar o Swagger oficial.")
    if not codigo_estacao.isdigit() or "{station}" not in template:
        return status("ANA HidroWebService", "invalid_request", warning="Estação numérica e {station} no template são obrigatórios")
    if not token:
        return status("ANA HidroWebService", "not_configured", warning="ANA_ACCESS_TOKEN ausente")
    headers = {"Authorization": f"Bearer {token}"}  # Ajustar conforme autenticação autorizada
    try:
        raw = await get_json(template.replace("{station}", codigo_estacao),
                             params={"start": inicio, "end": fim}, headers=headers)
        return status("ANA HidroWebService", "ok", data=raw,
                      warning="Conferir nomes dos parâmetros e esquema de auth no Swagger; não usar dados brutos sem controle de qualidade.")
    except Exception as exc:
        return safe_error("ANA HidroWebService", exc)
