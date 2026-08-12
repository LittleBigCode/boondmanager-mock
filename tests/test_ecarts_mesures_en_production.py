"""Quatre endroits où le mock racontait autre chose que le fournisseur.

┌─ CE QUE CES TESTS DÉFENDENT ────────────────────────────────────────────────┐
│ Ce dépôt existe pour qu'un consommateur puisse développer sans toucher      │
│ l'API réelle. Cette promesse ne tient QUE si ce qu'il émet est ce que le    │
│ fournisseur émet — un mock plus généreux que la vraie API ne rend pas       │
│ service : il déplace la découverte du défaut vers la production, là où      │
│ elle coûte le plus cher.                                                    │
│                                                                             │
│ Les quatre écarts ci-dessous ont été mesurés le 2026-08-12 contre un tenant │
│ de production, en LECTURE SEULE (une page par collection, les dix-huit      │
│ interrogées). Chacun avait déjà cassé la chaîne insights360 en production   │
│ pendant que la CI restait verte — c'est-à-dire au pire moment, et pour la   │
│ pire raison : parce qu'on avait cru le mock.                                │
│                                                                             │
│ Ces tests ne vérifient donc pas un choix de conception, mais un RELEVÉ. Ils │
│ ne doivent bouger que si une nouvelle sonde montre autre chose.             │
└─────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from tests.conftest import ADMIN, JWT

# Les dix-huit collections sondées, par leur chemin d'API.
COLLECTIONS = [
    "resources",
    "agencies",
    "companies",
    "contacts",
    "projects",
    "times",
    "actions",
    "opportunities",
    "poles",
    "candidates",
    "orders",
    "purchases",
    "business-units",
    "absences",
    "invoices",
    "expenses",
    "payments",
]


def _premiers(client, collection: str, **params) -> list[dict]:
    requete = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/{collection}" + (f"?{requete}" if requete else "")
    reponse = client.get(url, headers=JWT)
    assert reponse.status_code == 200, f"{collection}: {reponse.status_code}"
    return reponse.json()["data"]


# ── 1. `isDeleted` n'est pas un champ du fournisseur ─────────────────────────


def test_aucune_collection_ne_sert_isdeleted_par_defaut(client):
    """Absent des DIX-HUIT collections réelles — il doit l'être ici aussi.

    C'est l'écart qui a coûté le plus cher : dix-sept modèles de staging bâtis
    sur `where not is_deleted`, tous verts contre ce mock, tous cassés au
    premier run de production.
    """
    fautives = []
    for collection in COLLECTIONS:
        lignes = _premiers(client, collection, maxResults=5)
        if any("isDeleted" in (ligne.get("attributes") or {}) for ligne in lignes):
            fautives.append(collection)

    assert not fautives, (
        "isDeleted servi par défaut sur : "
        + ", ".join(fautives)
        + " — le fournisseur ne l'expose sur AUCUNE collection."
    )


def test_le_drapeau_reste_disponible_apres_une_suppression_explicite(client):
    """L'affordance n'est pas supprimée : elle cesse d'être un DÉFAUT.

    `/__admin/delete` doit continuer à poser le drapeau, sinon on perd le seul
    moyen d'exercer la gestion des suppressions chez le consommateur. Ce qui
    change, c'est qu'il faut le DEMANDER — et une charge par défaut ressemble
    alors à celle du fournisseur.
    """
    client.post("/__admin/delete", headers=ADMIN, json={"collection": "resources", "id": "8"})
    lignes = _premiers(client, "resources", maxResults=500)
    marquee = next(ligne for ligne in lignes if ligne["id"] == "8")
    assert marquee["attributes"]["isDeleted"] is True

    autres = [ligne for ligne in lignes if ligne["id"] != "8"]
    assert all("isDeleted" not in ligne["attributes"] for ligne in autres), (
        "seul l'enregistrement explicitement supprimé porte le drapeau"
    )


# ── 2. `/orders` ne porte pas d'horodatage de mise à jour ────────────────────


def test_les_commandes_n_ont_ni_updatedate_ni_creationdate(client):
    """`/orders` ne porte AUCUN des deux horodatages.

    `updateDate` d'abord : il porte la stratégie d'extraction, et le servir fait
    déclarer la collection incrémentale — le curseur casse alors en réel.

    `creationDate` ensuite, et c'est une erreur qu'il vaut la peine de garder
    sous test : 0.6.0 l'avait maintenu au motif qu'« il ne pilote aucune
    stratégie, donc le servir ne coûte rien ». C'était faux — un modèle qui LIT
    une colonne a besoin qu'elle EXISTE, et `stg_commande` est tombé sur
    « column o.creation_date does not exist » au run suivant.

    D'où la forme de ce test : la règle n'admet pas d'exception « inoffensive ».
    """
    for ligne in _premiers(client, "orders", maxResults=10):
        attributs = ligne["attributes"]
        for champ in ("updateDate", "creationDate"):
            assert champ not in attributs, f"le fournisseur ne rend pas `{champ}` sur les commandes"
        assert "date" in attributs, (
            "`date` (la date de commande) est bien rendue en réel — ne pas la retirer"
        )


def test_les_autres_collections_gardent_leur_updatedate(client):
    """Le garde inverse : ne pas « corriger » au-delà de ce qui a été mesuré."""
    for collection in ("resources", "companies", "projects", "invoices"):
        lignes = _premiers(client, collection, maxResults=5)
        assert all("updateDate" in ligne["attributes"] for ligne in lignes), (
            f"{collection} doit garder son updateDate — il est bien rendu en réel"
        )


# ── 3. `/actions` ignore `maxResults` ────────────────────────────────────────


def test_les_actions_ignorent_maxresults(client):
    """`GET /actions?maxResults=500` rend 30 lignes, pas 500.

    Le paramètre est ACCEPTÉ — pas de 422 — et silencieusement ignoré. Un
    consommateur qui croit tenir 500 lignes par page sous-estime son nombre de
    pages d'un facteur 16.
    """
    reponse = client.get("/api/actions?maxResults=500", headers=JWT)
    assert reponse.status_code == 200, "le paramètre est accepté, jamais rejeté"

    corps = reponse.json()
    total = corps["meta"]["totals"]["rows"]
    assert len(corps["data"]) == min(30, total)


def test_les_autres_collections_honorent_maxresults(client):
    """Sans ce garde, on aurait « corrigé » tout le monde au lieu d'/actions."""
    for collection in ("contacts", "candidates", "times"):
        lignes = _premiers(client, collection, maxResults=100)
        total = client.get(f"/api/{collection}", headers=JWT).json()["meta"]["totals"]["rows"]
        attendu = min(100, total)
        assert len(lignes) == attendu, (
            f"{collection} doit honorer maxResults ({len(lignes)} au lieu de {attendu})"
        )


# ── 4. `availability` d'un CANDIDAT est un code, pas une date ────────────────


def test_la_disponibilite_d_un_candidat_est_un_code_entier(client):
    """Relevé sur 26 814 candidats réels : des entiers, `-1` sur 24 289.

    Le mock servait une date ISO, et le consommateur la castait en date.
    """
    for ligne in _premiers(client, "candidates", maxResults=20):
        valeur = ligne["attributes"]["availability"]
        assert isinstance(valeur, int), (
            f"availability = {valeur!r} ({type(valeur).__name__}) — attendu un code entier"
        )


def test_la_disponibilite_d_une_ressource_reste_une_date(client):
    """Même nom, autre entité, autre type — et c'est le fournisseur qui le dit.

    Sur une RESSOURCE, `availability` est bien une date (ou « immediate »).
    Aligner les deux serait lisser un écart que le mock doit justement porter.
    """
    for ligne in _premiers(client, "resources", maxResults=20):
        valeur = ligne["attributes"]["availability"]
        assert isinstance(valeur, str), (
            f"availability = {valeur!r} — sur une ressource, c'est une date ou « immediate »"
        )
