"""Assemblage de l'application FastAPI.

Un SEUL point de dispatch pour les pannes (`_dispatch_injections`), évalué avant
l'authentification pour que `auth_reject` puisse préempter. Toute route de
collection passe par lui : il ne peut donc pas y avoir de route « oubliée » où
les pannes ne s'appliqueraient pas.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
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
from .models import (
    REPONSES_ERREUR,
    Agence,
    Compte,
    Contact,
    Cra,
    DonneesTechniques,
    ItemEnvelope,
    ListEnvelope,
    Mission,
    Projet,
    Ressource,
    Societe,
)
from .settings import settings
from .state import state


@dataclass(frozen=True)
class CollectionSpec:
    """Ce qu'il faut savoir d'une collection pour la servir ET la documenter.

    La fabrique de routes lit cette table : ajouter une collection, c'est une
    entrée ici plus une clé dans le jeu de données. Le `modele` est ce qui fait
    passer le contrat OpenAPI de « liste de chemins » à contrat véritable.
    """

    chemin: str  # segment d'URL — `times-reports` porte un tiret
    cle_dataset: str  # clé dans le dict du jeu de données
    modele: type  # modèle pydantic de l'élément
    singulier: str  # pour le message 404


COLLECTIONS: tuple[CollectionSpec, ...] = (
    CollectionSpec("resources", "resources", Ressource, "resource"),
    CollectionSpec("companies", "companies", Societe, "company"),
    CollectionSpec("contacts", "contacts", Contact, "contact"),
    CollectionSpec("projects", "projects", Projet, "project"),
    CollectionSpec("agencies", "agencies", Agence, "agency"),
    CollectionSpec("deliveries", "deliveries", Mission, "delivery"),
    CollectionSpec("times-reports", "times_reports", Cra, "timesReport"),
)


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


def _paginated(request: Request, spec: CollectionSpec) -> JSONResponse:
    path_name, dataset_key = spec.chemin, spec.cle_dataset
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


def _detail(request: Request, spec: CollectionSpec, item_id: str) -> JSONResponse:
    path_name, dataset_key = spec.chemin, spec.cle_dataset
    params = dict(request.query_params)
    if (injected := _dispatch_injections(f"/api/{path_name}/{item_id}", params)) is not None:
        return injected
    if (denied := _check_auth(request)) is not None:
        return denied
    for item in _collection_items(dataset_key):
        if item["id"] == item_id:
            return JSONResponse({"data": item})
    # Le singulier vient de la spec, plus d'un `[:-1]` sur le chemin : ce
    # découpage donnait « timesReport » → « times-report » sur la collection à
    # tiret. Les messages des collections historiques sont inchangés.
    return error(404, f"{spec.singulier} {item_id} not found")


def _register(spec: CollectionSpec) -> None:
    """Fabrique de routes.

    La fonction existe pour lier `spec` À CHAQUE ITÉRATION : sans elle, la
    fermeture capturerait la variable de boucle et toutes les routes serviraient
    la dernière collection. C'est le même garde-fou que dans le mock d'origine.

    `response_model` est déclaré mais les handlers rendent une `JSONResponse` :
    FastAPI documente alors la forme SANS revalider la sortie. C'est délibéré —
    un mock doit pouvoir servir des charges volontairement anormales (dérive de
    pagination, champs manquants) sans que sa propre validation l'en empêche.
    Le contrat décrit le cas nominal ; les pannes restent injectables.
    """

    @api.get(
        f"/{spec.chemin}",
        name=f"list_{spec.cle_dataset}",
        response_model=ListEnvelope[spec.modele],  # type: ignore[valid-type]
        responses=REPONSES_ERREUR,
        summary=f"Liste paginée : {spec.chemin}",
    )
    def _list(request: Request) -> JSONResponse:
        return _paginated(request, spec)

    @api.get(
        f"/{spec.chemin}/{{item_id}}",
        name=f"get_{spec.cle_dataset}",
        response_model=ItemEnvelope[spec.modele],  # type: ignore[valid-type]
        responses=REPONSES_ERREUR,
        summary=f"Détail : {spec.singulier}",
    )
    def _get(request: Request, item_id: str) -> JSONResponse:
        return _detail(request, spec, item_id)


for _spec in COLLECTIONS:
    _register(_spec)


@api.get(
    "/resources/{item_id}/technical-data",
    response_model=ItemEnvelope[DonneesTechniques],
    responses=REPONSES_ERREUR,
    summary="Onglet CV — seul endroit où vivent les références",
)
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


@api.get(
    "/application/current-user",
    response_model=ItemEnvelope[Compte],
    responses=REPONSES_ERREUR,
    summary="Vérification d'identité — test de fumée des identifiants",
)
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


# ─────────────────────────────────────────────────────────────────────────────
#  Le contrat
# ─────────────────────────────────────────────────────────────────────────────


def contrat_openapi() -> dict[str, Any]:
    """Le contrat OpenAPI — le DIALECTE BoondManager, et lui seul.

    Les chemins `/__admin` (plan de contrôle des pannes) et `/__fixtures`
    (rémunération, servie hors de /api faute d'endpoint fournisseur attesté)
    sont RETIRÉS. Deux raisons :

      • ce sont des affordances du mock, pas du fournisseur. Les publier au
        contrat ferait passer pour du BoondManager ce qui n'en est pas — et un
        consommateur pourrait s'y adosser ;

      • `/__admin` n'est monté que si `BOOND_MOCK_ADMIN_ENABLED` est vrai. Le
        contrat dépendrait alors de l'environnement de génération, et le test
        anti-dérive échouerait selon la façon dont on l'a lancé.

    Elles restent documentées — dans le README et dans docs/adr/0002 — mais hors
    du contrat.
    """
    spec = app.openapi()
    spec["paths"] = {
        chemin: op
        for chemin, op in spec["paths"].items()
        if not chemin.startswith(("/__admin", "/__fixtures"))
    }
    _elaguer_schemas_orphelins(spec)
    return spec


def _elaguer_schemas_orphelins(spec: dict[str, Any]) -> None:
    """Retire les schémas que plus aucun chemin ne référence.

    Retirer des chemins laisse leurs schémas derrière eux. Le symptôme est
    déroutant : le contrat contient `HTTPValidationError` et `ValidationError`
    UNIQUEMENT quand `/__admin` était monté au moment de la génération — donc le
    fichier committé diffère selon la valeur d'une variable d'environnement, et
    le test anti-dérive échoue sans que rien de significatif n'ait changé.

    On résout les `$ref` de façon transitive : un schéma gardé peut en
    référencer un autre.
    """
    schemas = spec.get("components", {}).get("schemas", {})
    if not schemas:
        return

    def refs(noeud: Any) -> set[str]:
        trouves: set[str] = set()
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                if cle == "$ref" and isinstance(valeur, str):
                    trouves.add(valeur.rsplit("/", 1)[-1])
                else:
                    trouves |= refs(valeur)
        elif isinstance(noeud, list):
            for element in noeud:
                trouves |= refs(element)
        return trouves

    gardes = refs(spec["paths"])
    # Fermeture transitive : un schéma gardé peut en référencer d'autres.
    a_explorer = set(gardes)
    while a_explorer:
        nom = a_explorer.pop()
        for suivant in refs(schemas.get(nom, {})):
            if suivant not in gardes:
                gardes.add(suivant)
                a_explorer.add(suivant)

    spec["components"]["schemas"] = {n: c for n, c in schemas.items() if n in gardes}
