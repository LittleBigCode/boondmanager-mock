"""Enveloppe d'erreur — la forme exacte relevée sur la vraie API (9.1.78.1).

Une erreur réelle porte TOUJOURS le `meta` (version, isLogged, language,
timestamp…), puis des entrées `{status, code, detail, title | source}` :

    401/403/404/405 : {"status": "404", "code": "404",
                       "detail": "HTTP 404 (GET /api/resources/999999999)",
                       "title": "404"}
    422 JWT         : {"status": "422", "code": "422",
                       "detail": "422 - Signature verification failed",
                       "source": {"parameter": "xJwtClient"}}
    422 métier      : {"status": "422", "code": "1017",
                       "detail": "1017 - Missing required attribute",
                       "source": {"parameter": "endMonth"}}

Détail clé du dialecte : quand la requête n'est pas authentifiée (401, JWT
invalide) ou que la ROUTE n'existe pas (404/405 — le routage précède l'auth),
le meta rend `isLogged: false` et `language: "en"`, sans `login` ni `customer`.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def entree_erreur(
    status_code: int,
    detail: str,
    *,
    code: str | None = None,
    source: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Une entrée du tableau `errors` — `title` OU `source`, jamais les deux."""
    entree: dict[str, Any] = {
        "status": str(status_code),
        "code": code or str(status_code),
        "detail": detail,
    }
    if source is not None:
        entree["source"] = source
    else:
        entree["title"] = str(status_code)
    return entree


def reponse_erreurs(
    status_code: int,
    entrees: list[dict[str, Any]],
    *,
    connecte: bool = True,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """L'enveloppe complète : meta (selon l'état d'authentification) + errors."""
    from .envelope import meta_erreur

    return JSONResponse(
        status_code=status_code,
        content={"meta": meta_erreur(connecte), "errors": entrees},
        headers=headers or {},
    )


def detail_generique(status_code: int, request: Request) -> str:
    """`"HTTP 404 (GET /api/resources/12?maxResults=2)"` — le format réel."""
    cible = request.url.path
    if request.url.query:
        cible = f"{cible}?{request.url.query}"
    return f"HTTP {status_code} ({request.method} {cible})"


def error(
    status_code: int,
    detail: str | None = None,
    *,
    request: Request | None = None,
    code: str | None = None,
    source: dict[str, str] | None = None,
    connecte: bool = True,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Une erreur à entrée unique. Sans `detail`, le message générique réel est
    construit depuis la requête (`HTTP {code} ({méthode} {chemin})`)."""
    if detail is None:
        if request is None:
            detail = f"HTTP {status_code}"
        else:
            detail = detail_generique(status_code, request)
    return reponse_erreurs(
        status_code,
        [entree_erreur(status_code, detail, code=code, source=source)],
        connecte=connecte,
        headers=headers,
    )
