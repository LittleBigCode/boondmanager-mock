"""Assemblage de l'application FastAPI.

Un SEUL point de dispatch pour les pannes (`_dispatch_injections`), évalué avant
l'authentification pour que `auth_reject` puisse préempter. Toute route de
collection passe par lui : il ne peut donc pas y avoir de route « oubliée » où
les pannes ne s'appliqueraient pas.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .auth import basic_is_valid, jwt_is_valid
from .envelope import (
    apply_incremental,
    apply_keywords,
    apply_order,
    apply_page_drift,
    envelope,
    extract_since,
    paginate,
)
from .errors import error
from .injection import engine
from .settings import settings
from .state import state

# Les collections servies. Ajouter une collection = une entrée ici plus une clé
# dans le jeu de données. `deliveries` et `times_reports` sont les deux ajouts
# demandés par insights360 (missions et CRA).
#
# Le chemin d'URL n'est pas toujours la clé du dataset : BoondManager expose
# `times-reports` avec un tiret.
COLLECTIONS: dict[str, str] = {
    "resources": "resources",
    "companies": "companies",
    "contacts": "contacts",
    "projects": "projects",
    "agencies": "agencies",
    "deliveries": "deliveries",
    "times-reports": "times_reports",
}


def _check_auth(request: Request) -> JSONResponse | None:
    """401 sans identifiants, **422** avec un JWT invalide — comme la vraie API."""
    jwt_token = request.headers.get("X-Jwt-Client-Boondmanager")
    if jwt_token is not None:
        if jwt_is_valid(jwt_token):
            return None
        return error(422, "Signature verification failed")
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Basic ") and basic_is_valid(authorization[6:]):
        return None
    return error(401, "Authentication required")


def _dispatch_injections(path: str, params: dict[str, str]) -> JSONResponse | None:
    """Le point de dispatch unique. Rend une réponse si une panne se déclenche.

    Ordre significatif :
      1. auth_reject  — doit préempter l'authentification réelle ;
      2. latency      — s'applique même quand la requête finit par réussir ;
      3. rate_limit   — dépend du compteur, donc après l'observation ;
      4. status       — la panne franche.
    """
    index = engine.observe(path, params)

    if (rule := engine.first("auth_reject", path)) is not None and rule.consume():
        return error(rule.status or 401, "Authentication required")

    if (rule := engine.first("latency", path)) is not None and rule.consume():
        # Un vrai `sleep` : c'est le seul moyen d'éprouver un timeout côté
        # client. L'horloge virtuelle sert aux fenêtres temporelles, pas ici.
        time.sleep(rule.seconds)

    if (
        (rule := engine.first("rate_limit", path)) is not None
        and index > rule.after_requests
        and rule.consume()
    ):
        # `Retry-After` en secondes, comme la vraie API. Un client qui l'ignore
        # et retente immédiatement doit continuer à recevoir des 429 — c'est ce
        # que teste insights360.
        return error(
            429,
            "Too many requests",
            headers={"Retry-After": str(rule.retry_after_seconds)},
        )

    if (rule := engine.first("status", path)) is not None and rule.consume():
        return error(rule.status, f"mock: injected {rule.status} on {path}")

    return None


def _collection_items(dataset_key: str) -> list[dict[str, Any]]:
    return state.dataset.get(dataset_key, [])


# ─────────────────────────────────────────────────────────────────────────────
#  Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="BoondManager mock", version="0.1.0", docs_url="/docs")
api = APIRouter(prefix="/api")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Non authentifié — c'est une sonde, pas une ressource."""
    return {"status": "ok", "service": "boondmanager-mock"}


def _paginated(request: Request, path_name: str, dataset_key: str) -> JSONResponse:
    params = dict(request.query_params)
    path = f"/api/{path_name}"

    if (injected := _dispatch_injections(path, params)) is not None:
        return injected
    if (denied := _check_auth(request)) is not None:
        return denied
    # Levier d'injection historique, conservé pour la suite de tests d'ophelie.
    if dataset_key in state.fail_collections or path_name in state.fail_collections:
        return error(500, f"mock: simulated outage on /{path_name}")

    items = _collection_items(dataset_key)
    items = apply_keywords(items, params.get("keywords", ""))
    items = apply_incremental(items, extract_since(params))

    total = len(items)
    items = apply_order(items, params, engine.request_counts.get(path, 1))

    paged = paginate(items, params)
    if paged is None:
        return error(422, "Wrong or missing attribute: page/maxResults")
    slice_, page, page_size = paged
    slice_ = apply_page_drift(slice_, page, page_size, path)

    return JSONResponse(envelope(slice_, total))


def _detail(request: Request, path_name: str, dataset_key: str, item_id: str) -> JSONResponse:
    params = dict(request.query_params)
    if (injected := _dispatch_injections(f"/api/{path_name}/{item_id}", params)) is not None:
        return injected
    if (denied := _check_auth(request)) is not None:
        return denied
    for item in _collection_items(dataset_key):
        if item["id"] == item_id:
            return JSONResponse({"data": item})
    # Le singulier est obtenu en retirant le `s` final — comportement du mock
    # d'origine, conservé parce que des tests s'appuient sur le message.
    return error(404, f"{path_name[:-1]} {item_id} not found")


def _register(path_name: str, dataset_key: str) -> None:
    """Fabrique de routes.

    La fonction existe pour lier `path_name`/`dataset_key` À CHAQUE ITÉRATION :
    sans elle, la fermeture capturerait la variable de boucle et toutes les
    routes serviraient la dernière collection. C'est le même garde-fou que dans
    le mock d'origine.
    """

    @api.get(f"/{path_name}", name=f"list_{dataset_key}")
    def _list(request: Request) -> JSONResponse:
        return _paginated(request, path_name, dataset_key)

    @api.get(f"/{path_name}/{{item_id}}", name=f"get_{dataset_key}")
    def _get(request: Request, item_id: str) -> JSONResponse:
        return _detail(request, path_name, dataset_key, item_id)


for _path_name, _dataset_key in COLLECTIONS.items():
    _register(_path_name, _dataset_key)


@api.get("/resources/{item_id}/technical-data")
def technical_data(request: Request, item_id: str) -> JSONResponse:
    """L'onglet CV — seul endroit où vivent les `references[]`."""
    if (
        injected := _dispatch_injections(
            "/api/resources/technical-data", dict(request.query_params)
        )
    ) is not None:
        return injected
    if (denied := _check_auth(request)) is not None:
        return denied
    if "technical-data" in state.fail_collections:
        return error(500, "mock: simulated outage on /resources/{id}/technical-data")
    data = state.dataset["technical_data"].get(item_id)
    if data is None:
        return error(404, f"resource {item_id} not found")
    return JSONResponse({"data": data})


@api.get("/application/current-user")
def current_user(request: Request) -> JSONResponse:
    """Vérification d'identité — utilisé comme test de fumée des identifiants."""
    if (denied := _check_auth(request)) is not None:
        return denied
    return JSONResponse(
        {
            "data": {
                "id": "1",
                "type": "account",
                "attributes": {
                    "firstName": "Mock",
                    "lastName": "Sync",
                    "email": settings.basic_user,
                },
            }
        }
    )


app.include_router(api)

# Le plan de contrôle n'est pas « monté puis interdit » : quand il est
# désactivé, la surface n'existe pas. C'est la configuration du déploiement
# d'ophelie sur le cluster.
if settings.admin_enabled:
    from .admin import router as admin_router

    app.include_router(admin_router)


# ─────────────────────────────────────────────────────────────────────────────
#  Rémunération — DÉLIBÉRÉMENT HORS DE /api
# ─────────────────────────────────────────────────────────────────────────────
#
# Aucun endpoint de rémunération par ressource n'est attesté chez BoondManager.
# L'ADR-0002 d'ophelie, écrit depuis une intégration production vérifiée,
# énumère resources / companies / contacts / projects / agencies et le
# sous-onglet technical-data — rien d'autre. Le seul champ monétaire par
# ressource est `averageDailyPriceExcludingTax`, qui est un tarif de vente.
#
# La spec d'insights360 en a pourtant besoin (`fct_remuneration` est la table la
# plus sensible du modèle et toute sa suite de tests négatifs en dépend), et
# elle interdit explicitement d'inventer un champ fournisseur.
#
# Résolution : la rémunération est servie comme un FICHIER, hors de `/api`, pour
# que personne ne puisse la prendre pour un endpoint BoondManager. C'est
# probablement aussi la vérité métier — une rémunération vit dans une paie ou un
# SIRH, pas dans l'ERP commercial. Cf. docs/adr/0004.


# `response_model=None` : le type de retour est une union de deux Response, que
# FastAPI tenterait sinon d'interpréter comme un modèle Pydantic.
@app.get("/__fixtures/remuneration.csv", response_class=PlainTextResponse, response_model=None)
def remuneration_csv(request: Request) -> PlainTextResponse | JSONResponse:
    if settings.compensation_mode == "absent":
        return error(404, "compensation fixture disabled (BOOND_MOCK_COMPENSATION_MODE=absent)")
    if (denied := _check_auth(request)) is not None:
        return denied
    lignes = ["collaborateur_id,upn,entite,periode,montant_brut_annuel"]
    for row in state.dataset.get("remuneration", []):
        lignes.append(
            f"{row['collaborateur_id']},{row['upn']},{row['entite']},"
            f"{row['periode']},{row['montant_brut_annuel']}"
        )
    return PlainTextResponse("\n".join(lignes) + "\n", media_type="text/csv")
