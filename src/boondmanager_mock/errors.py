"""Enveloppe d'erreur — la forme exacte de la vraie API.

    {"errors": [{"code": "422", "detail": "…"}]}

Le client d'ophelie lit `errors[0].detail || errors[0].title` pour composer son
message ; s'écarter de cette forme rendrait les erreurs illisibles côté
consommateur sans que rien n'échoue franchement.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse


def error(status_code: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"errors": [{"code": str(status_code), "detail": detail}]},
        headers=headers or {},
    )
