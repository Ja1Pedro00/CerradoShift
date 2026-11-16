"""INMET: cliente configurável após liberação oficial de acesso à API.

Solicite acesso: api@inmet.gov.br. Defina URL exata da rota liberada,
parâmetros e autenticação conforme documentação recebida.
"""
import os
from .common import get_json, safe_error, status


async def consultar_estacao(codigo: str):
    template = os.getenv("INMET_ENDPOINT_TEMPLATE", "").strip()
    token = os.getenv("INMET_API_TOKEN", "").strip()
    if not template:
        return status("INMET", "not_configured",
                      warning="Solicite acesso oficial e configure INMET_ENDPOINT_TEMPLATE com {station}.")
    if "{station}" not in template or not codigo.isalnum():
        return status("INMET", "invalid_request", warning="Template deve incluir {station} e estação alfanumérica")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        raw = await get_json(template.replace("{station}", codigo), headers=headers)
        return status("INMET", "ok", data=raw,
                      warning="Validar campos, unidades, qualidade e fuso conforme contrato oficial.")
    except Exception as exc:
        return safe_error("INMET", exc)
