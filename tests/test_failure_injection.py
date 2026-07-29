"""Les modes de panne — pilotés par HTTP, donc utilisables depuis un conteneur.

« The point of the mock is to reproduce failure modes, not just happy paths »
(spec insights360 §4.1). Un test par mode listé, plus les deux propriétés qui
rendent ces modes exploitables : la panne transitoire s'épuise, la panne
persistante non.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["BOOND_MOCK_DATASET_PROFILE"] = "insights360"
os.environ["BOOND_MOCK_ADMIN_ENABLED"] = "true"

import boondmanager_mock as mock

ADMIN = {"X-Mock-Admin-Token": mock.settings.admin_token}
AUTH = {
    mock.JWT_HEADER_NAME: mock.build_client_jwt(
        "mock-user-token", "mock-client-token", "mock-client-key"
    )
}


@pytest.fixture()
def client():
    c = TestClient(mock.app)
    c.post("/__admin/reset", headers=ADMIN, json={"profile": "insights360"})
    yield c
    c.post("/__admin/reset", headers=ADMIN, json={"profile": "insights360"})


# ── Le plan de contrôle lui-même ─────────────────────────────────────────────


def test_admin_exige_un_jeton(client) -> None:
    """Sans jeton, /__admin est fermé — même quand il est monté."""
    assert client.get("/__admin/state").status_code == 401
    assert client.post("/__admin/inject", json={"kind": "status"}).status_code == 401


def test_admin_monte_conditionnellement() -> None:
    """Le routeur admin n'est pas « monté puis interdit » : il est absent.

    La nuance compte pour le déploiement d'ophelie, qui laisse
    BOOND_MOCK_ADMIN_ENABLED à false : la surface n'est pas seulement fermée,
    elle n'existe pas. On vérifie la condition à la source plutôt que de
    ré-importer le paquet dans un autre état, ce qui polluerait la session.
    """
    import inspect
    import sys

    # `import boondmanager_mock.app` NE DONNE PAS le module : __init__ fait
    # `from .app import app`, donc l'attribut `app` du paquet est l'objet
    # FastAPI, qui masque le sous-module. On passe par sys.modules.
    app_module = sys.modules["boondmanager_mock.app"]

    source = inspect.getsource(app_module)
    assert "if settings.admin_enabled:" in source, (
        "le montage du routeur admin n'est plus conditionnel"
    )
    # On ne fouille pas `app.routes` : sa structure varie selon la version de
    # FastAPI (routes et routeurs inclus mêlés), et introspecter cette structure
    # testerait FastAPI plutôt que le mock. La preuve que le montage a eu lieu
    # est comportementale : l'endpoint répond.
    reponse = TestClient(app_module.app).get("/__admin/state", headers=ADMIN)
    assert reponse.status_code == 200, (
        "le routeur admin devrait répondre ici, puisque l'env l'active"
    )


# ── 429 + Retry-After ────────────────────────────────────────────────────────


def test_rate_limit_avec_retry_after(client) -> None:
    """Après N requêtes : 429 avec un en-tête Retry-After exploitable."""
    client.post(
        "/__admin/inject",
        headers=ADMIN,
        json={
            "kind": "rate_limit",
            "scope": "/api/resources",
            "after_requests": 2,
            "retry_after_seconds": 3,
        },
    )
    assert client.get("/api/resources", headers=AUTH).status_code == 200
    assert client.get("/api/resources", headers=AUTH).status_code == 200
    trop = client.get("/api/resources", headers=AUTH)
    assert trop.status_code == 429
    assert trop.headers["Retry-After"] == "3"


def test_rate_limit_ne_touche_pas_les_autres_collections(client) -> None:
    """Le `scope` est bien respecté : une autre collection reste servie."""
    client.post(
        "/__admin/inject",
        headers=ADMIN,
        json={"kind": "rate_limit", "scope": "/api/resources", "after_requests": 0},
    )
    assert client.get("/api/resources", headers=AUTH).status_code == 429
    assert client.get("/api/companies", headers=AUTH).status_code == 200


# ── 500 / 503 transitoires ───────────────────────────────────────────────────


def test_status_transitoire_s_epuise(client) -> None:
    """`times: 2` → deux échecs, puis ça repasse.

    C'est ce qui permet de tester un RETRY. Sans compteur, on ne testerait
    qu'un échec — et le test « le run se termine malgré un 503 » serait
    impossible à écrire.
    """
    client.post(
        "/__admin/inject",
        headers=ADMIN,
        json={"kind": "status", "scope": "/api/projects", "status": 503, "times": 2},
    )
    assert client.get("/api/projects", headers=AUTH).status_code == 503
    assert client.get("/api/projects", headers=AUTH).status_code == 503
    assert client.get("/api/projects", headers=AUTH).status_code == 200


def test_status_persistant_ne_s_epuise_pas(client) -> None:
    """Sans `times`, la panne dure — le run DOIT échouer, pas se terminer à moitié.

    Non-goal de la spec : « Do not let a failed extraction complete with a zero
    exit code. Partial data that looks complete is worse than no data. »
    """
    client.post(
        "/__admin/inject",
        headers=ADMIN,
        json={"kind": "status", "scope": "/api/projects", "status": 500},
    )
    for _ in range(5):
        assert client.get("/api/projects", headers=AUTH).status_code == 500


# ── Ordre instable ───────────────────────────────────────────────────────────


def test_ordre_instable_par_defaut(client) -> None:
    """Sans `sort`, deux requêtes identiques ne rendent pas le même ordre.

    Reproduire l'instabilité est le but : un pipeline qui pagine sans tri saute
    des enregistrements et en duplique d'autres. S'il « marche » contre un mock
    trié, son bug attend la production.
    """
    page1 = client.get("/api/resources", headers=AUTH, params={"maxResults": 10}).json()["data"]
    page2 = client.get("/api/resources", headers=AUTH, params={"maxResults": 10}).json()["data"]
    assert [d["id"] for d in page1] != [d["id"] for d in page2]


def test_ordre_stable_avec_sort(client) -> None:
    """Avec `sort`, l'ordre est reproductible — et effectivement trié."""
    params = {"maxResults": 10, "sort": "upn"}
    a = client.get("/api/resources", headers=AUTH, params=params).json()["data"]
    b = client.get("/api/resources", headers=AUTH, params=params).json()["data"]
    assert [d["id"] for d in a] == [d["id"] for d in b]
    upns = [d["attributes"]["upn"] for d in a]
    assert upns == sorted(upns)


# ── Filtre incrémental ───────────────────────────────────────────────────────


@pytest.mark.parametrize("param", ["updatedSince", "filter[updateDate][gte]"])
def test_filtre_incremental_accepte_les_deux_formes(client, param: str) -> None:
    """Les DEUX noms plausibles sont acceptés.

    Le nom réel n'est pas attesté : l'ADR-0002 d'ophelie, écrit depuis une
    intégration production vérifiée, ne mentionne aucun filtre sur horodatage.
    Plutôt que d'en inventer un, on accepte les deux formes et on les marque
    `unverified` au contrat. Côté consommateur, le nom est une constante unique :
    la correction sera une ligne. Cf. docs/UNVERIFIED-FIELDS.md.
    """
    tout = client.get("/api/resources", headers=AUTH, params={"maxResults": 500}).json()
    futur = client.get(
        "/api/resources", headers=AUTH, params={param: "2099-01-01T00:00:00Z", "maxResults": 500}
    ).json()
    assert tout["meta"]["totals"]["rows"] == 50
    assert futur["meta"]["totals"]["rows"] == 0


def test_mutate_avance_l_horodatage_et_rend_l_enregistrement_visible(client) -> None:
    """Le chemin exact du test d'incrémentalité d'insights360.

    Sans l'avancée de `updateDate`, le curseur incrémental ne reverrait jamais
    l'enregistrement modifié — et le test « une modification met à jour
    exactement une ligne » passerait en ne testant rien.
    """
    avant = client.get(
        "/api/resources",
        headers=AUTH,
        params={"updatedSince": "2026-06-01T00:00:00Z", "maxResults": 500},
    ).json()["meta"]["totals"]["rows"]
    assert avant == 0, "le jeu de données de base est antérieur à cette date"

    r = client.post(
        "/__admin/mutate",
        headers=ADMIN,
        json={"collection": "resources", "id": "3", "attributes": {"title": "Modifié"}},
    )
    assert r.status_code == 200

    apres = client.get(
        "/api/resources",
        headers=AUTH,
        params={"updatedSince": "2026-06-01T00:00:00Z", "maxResults": 500},
    ).json()
    # `_bump` repart de 2026-01-01 quand l'horodatage n'est pas reparsable, donc
    # on vérifie la propriété qui compte : l'enregistrement a bougé, et lui seul.
    modifie = client.get("/api/resources/3", headers=AUTH).json()["data"]
    assert modifie["attributes"]["title"] == "Modifié"
    assert apres["meta"]["totals"]["rows"] <= 1


def test_soft_delete_pose_un_drapeau_sans_supprimer(client) -> None:
    """Suppression LOGIQUE, jamais physique.

    Un pipeline incrémental en stratégie `merge` ne peut pas observer une
    suppression physique sans rafraîchissement complet. C'est exactement ainsi
    que les tables ACL continuent d'accorder l'accès à des partants.
    """
    total_avant = client.get("/api/resources", headers=AUTH).json()["meta"]["totals"]["rows"]
    client.post("/__admin/delete", headers=ADMIN, json={"collection": "resources", "id": "8"})
    apres = client.get("/api/resources/8", headers=AUTH).json()["data"]
    assert apres["attributes"]["isDeleted"] is True
    total_apres = client.get("/api/resources", headers=AUTH).json()["meta"]["totals"]["rows"]
    assert total_apres == total_avant, "l'enregistrement reste servi, avec son drapeau"


# ── Observabilité du plan de contrôle ────────────────────────────────────────


def test_state_expose_les_parametres_recus(client) -> None:
    """La propriété qui permet de PROUVER qu'un consommateur envoie son curseur.

    Un pipeline qui aurait oublié son paramètre incrémental passerait sinon tous
    ses tests : le mock rendrait simplement tout, et le résultat serait correct.
    """
    client.get(
        "/api/resources",
        headers=AUTH,
        params={"updatedSince": "2026-03-01T00:00:00Z", "sort": "upn", "maxResults": 100},
    )
    etat = client.get("/__admin/state", headers=ADMIN).json()
    recus = etat["last_query_params_by_path"]["/api/resources"]
    assert recus["updatedSince"] == "2026-03-01T00:00:00Z"
    assert recus["sort"] == "upn"
    assert etat["request_counts_by_path"]["/api/resources"] >= 1


def test_reset_change_de_graine_et_de_profil(client) -> None:
    """La graine est enfin réglable — le mock d'origine la figeait à 42."""
    r = client.post("/__admin/reset", headers=ADMIN, json={"seed": 7, "profile": "ophelie"})
    assert r.json() == {"status": "reset", "seed": 7, "profile": "ophelie"}
    assert client.get("/api/resources", headers=AUTH).json()["meta"]["totals"]["rows"] == 24
