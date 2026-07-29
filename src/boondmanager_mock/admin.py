"""Plan de contrôle `/__admin` — piloter les pannes par HTTP.

Pourquoi il existe : le mock d'origine ne s'injectait des pannes qu'en mutant un
`set` Python depuis le même processus. Cela marche quand les tests montent
l'application en process (le cas d'ophelie), et pas du tout quand le mock tourne
en conteneur — le cas d'insights360, en docker compose comme en sidecar Tekton.

Deux décisions de conception :

  • le préfixe `/__admin` est HORS de `/api`. D'une part aucune collision n'est
    possible avec un vrai chemin BoondManager ; d'autre part une NetworkPolicy
    ou une règle d'ingress peut le bloquer en bloc, sans connaître les routes ;

  • le routeur n'est PAS MONTÉ quand `BOOND_MOCK_ADMIN_ENABLED` est faux. Pas
    « monté puis interdit » : absent. Le déploiement d'ophelie le laisse à
    false, donc la surface n'existe simplement pas sur le cluster.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from .errors import error
from .injection import engine
from .settings import settings
from .state import state

router = APIRouter(prefix="/__admin", tags=["admin"])


def _authorized(token: str | None) -> bool:
    return bool(token) and token == settings.admin_token


def _guard(token: str | None) -> JSONResponse | None:
    if not _authorized(token):
        return error(401, "invalid or missing X-Mock-Admin-Token")
    return None


@router.post("/reset")
async def reset(
    request: Request,
    x_mock_admin_token: str | None = Header(default=None),
) -> JSONResponse:
    """Reconstruit le jeu de données et remet les compteurs à zéro.

    Les règles d'injection reviennent à la LIGNE DE BASE déclarée par
    l'environnement, pas à vide — cf. state.MockState.reset.
    """
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    body: dict[str, Any] = {}
    if request.headers.get("content-length") not in (None, "0"):
        body = await request.json()
    seed = body.get("seed", request.query_params.get("seed"))
    profile = body.get("profile", request.query_params.get("profile"))
    state.reset(seed=int(seed) if seed is not None else None, profile=profile)
    return JSONResponse({"status": "reset", "seed": state.seed, "profile": state.profile})


@router.get("/state")
def get_state(x_mock_admin_token: str | None = Header(default=None)) -> JSONResponse:
    """Ce que le mock a vu et ce qu'il fera.

    `last_query_params` est la partie porteuse : c'est ce qui permet à un
    consommateur de PROUVER qu'il a envoyé son paramètre incrémental et son
    tri, au lieu de simplement tolérer leur absence. Un pipeline qui aurait
    oublié son curseur passerait sinon tous ses tests d'incrémentalité.
    """
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    return JSONResponse(
        {
            "seed": state.seed,
            "profile": state.profile,
            "totals": state.totals(),
            "request_counts_by_path": dict(engine.request_counts),
            "last_query_params_by_path": dict(engine.last_query_params),
            "injections": engine.snapshot(),
            "fail_collections": sorted(state.fail_collections),
            "clock_offset": engine.clock_offset,
        }
    )


@router.post("/inject")
async def inject(
    request: Request,
    x_mock_admin_token: str | None = Header(default=None),
) -> JSONResponse:
    """Ajoute une règle d'injection.

    Corps : union discriminée sur `kind` —
      {"kind":"rate_limit","scope":"/api/resources","after_requests":10,"retry_after_seconds":2}
      {"kind":"status","scope":"/api/times-reports","status":503,"times":2}
      {"kind":"latency","scope":"*","seconds":2.5,"times":1}
      {"kind":"page_drift","scope":"/api/resources","after_page":1,"mode":"insert"}
      {"kind":"auth_reject","scope":"*","status":401}
      {"kind":"stable_order","scope":"*"}
    """
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    body = await request.json()
    kind = body.pop("kind", None)
    if kind not in {
        "rate_limit",
        "status",
        "latency",
        "page_drift",
        "auth_reject",
        "stable_order",
    }:
        return error(422, f"unknown injection kind: {kind!r}")
    try:
        rule = engine.add(kind=kind, **body)
    except TypeError as exc:
        return error(422, f"invalid injection payload: {exc}")
    return JSONResponse({"rule_id": rule.id, "kind": rule.kind, "scope": rule.scope})


@router.delete("/inject/{rule_id}")
def delete_inject(
    rule_id: str, x_mock_admin_token: str | None = Header(default=None)
) -> JSONResponse:
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    if not engine.remove(rule_id):
        return error(404, f"rule {rule_id} not found")
    return JSONResponse({"status": "removed", "rule_id": rule_id})


@router.post("/inject/clear")
def clear_inject(x_mock_admin_token: str | None = Header(default=None)) -> JSONResponse:
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    engine.clear()
    return JSONResponse({"status": "cleared"})


@router.post("/mutate")
async def mutate(
    request: Request,
    x_mock_admin_token: str | None = Header(default=None),
) -> JSONResponse:
    """Modifie un enregistrement et avance son `updateDate`.

    INDISPENSABLE au test d'incrémentalité : « after a run, modifying one record
    in the mock and re-running updates exactly one row and touches no others ».
    Une fois le mock en conteneur, c'est la seule voie pour simuler un
    changement à la source.

    Corps : {"collection": "resources", "id": "3", "attributes": {...}}
    """
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    body = await request.json()
    collection = body.get("collection")
    item_id = str(body.get("id"))
    patch = body.get("attributes", {})

    items = state.dataset.get(collection)
    if not isinstance(items, list):
        return error(404, f"collection {collection!r} not found")
    for item in items:
        if item["id"] == item_id:
            item.setdefault("attributes", {}).update(patch)
            # L'avancée de l'horodatage n'est pas cosmétique : sans elle, le
            # curseur incrémental ne reverrait jamais l'enregistrement modifié,
            # et le test d'incrémentalité passerait en ne testant rien.
            item["attributes"][_UPDATED_AT] = _bump(item["attributes"].get(_UPDATED_AT))
            return JSONResponse({"status": "mutated", "id": item_id})
    return error(404, f"{collection}/{item_id} not found")


@router.post("/delete")
async def soft_delete(
    request: Request,
    x_mock_admin_token: str | None = Header(default=None),
) -> JSONResponse:
    """Suppression LOGIQUE — drapeau + avancée de l'horodatage.

    Jamais de suppression physique, et c'est une décision, pas une facilité :
    un pipeline incrémental en stratégie `merge` ne PEUT PAS observer une
    suppression physique sans rafraîchissement complet. Prétendre le contraire
    est exactement comment les tables ACL continuent d'accorder l'accès à des
    partants — ce que le test négatif « un employé sorti ne conserve aucune
    visibilité » cherche précisément à empêcher.
    """
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    body = await request.json()
    collection = body.get("collection")
    item_id = str(body.get("id"))
    items = state.dataset.get(collection)
    if not isinstance(items, list):
        return error(404, f"collection {collection!r} not found")
    for item in items:
        if item["id"] == item_id:
            item.setdefault("attributes", {})["isDeleted"] = True
            item["attributes"][_UPDATED_AT] = _bump(item["attributes"].get(_UPDATED_AT))
            return JSONResponse({"status": "soft-deleted", "id": item_id})
    return error(404, f"{collection}/{item_id} not found")


@router.post("/clock")
async def clock(
    request: Request,
    x_mock_admin_token: str | None = Header(default=None),
) -> JSONResponse:
    """Avance l'horloge virtuelle — des fenêtres temporelles sans `sleep`."""
    if (denied := _guard(x_mock_admin_token)) is not None:
        return denied
    body = await request.json()
    engine.clock_offset += float(body.get("advance_seconds", 0))
    return JSONResponse({"clock_offset": engine.clock_offset})


_UPDATED_AT = "updateDate"


def _bump(current: str | None) -> str:
    """Avance l'horodatage d'une seconde, de façon déterministe.

    Pas de `datetime.now()` : le jeu de données doit rester reproductible d'un
    run à l'autre, sinon le test « deux exécutions produisent un `raw`
    identique » devient impossible à écrire.
    """
    import contextlib
    from datetime import datetime, timedelta

    base = datetime(2026, 1, 1, tzinfo=UTC)
    if current:
        # Un horodatage illisible retombe sur la base fixe plutôt que de faire
        # échouer la mutation : le mock doit rester utilisable même si un test a
        # écrit n'importe quoi dans le champ.
        with contextlib.suppress(ValueError):
            base = datetime.fromisoformat(current.replace("Z", "+00:00"))
    return (base + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
