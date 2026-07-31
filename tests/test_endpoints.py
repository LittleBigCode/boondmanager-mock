"""Les 22 collections : dialecte, intégrité référentielle, cohérence métier.

C'est la suite qui prépare la comparaison avec la vraie API : chemins, `type`
JSON:API en minuscules, enveloppe `meta` complète, `included` résolu, détail
`/{id}` là où le fournisseur en a un — et NULLE PART ailleurs.
"""

from __future__ import annotations

import re

import pytest

from tests.conftest import JWT

# (chemin, type JSON:API, détail ?, included ?)
COLLECTIONS = [
    ("absences", "absence", False, False),
    ("actions", "action", True, True),
    ("agencies", "agency", True, False),
    ("banking-transactions", "bankingtransaction", True, True),
    ("business-units", "businessunit", True, True),
    ("candidates", "candidate", True, True),
    ("companies", "company", True, True),
    ("contacts", "contact", True, True),
    ("contracts", "contract", True, True),
    ("deliveries", "delivery", True, True),
    ("expenses", "expense", False, False),
    ("invoices", "invoice", True, True),
    ("opportunities", "opportunity", True, True),
    ("orders", "order", True, True),
    ("payments", "payment", True, True),
    ("poles", "pole", True, False),
    ("projects", "project", True, True),
    ("purchases", "purchase", True, True),
    ("resources", "resource", True, True),
    ("roles", "role", True, False),
    ("times", "time", False, True),
    ("times-reports", "timesreport", True, True),
]

ID_OFFICIEL = re.compile(r"^[1-9][0-9]*$")
#: Les ids de /times sont composites en réel : `regular_1`, `exceptional_3`…
ID_TEMPS = re.compile(r"^(regular|exceptional)_[1-9][0-9]*$")
#: Recherches absentes en réel (405) — les données passent par les détails.
SANS_LISTE = {"contracts", "deliveries"}
#: Paramètres obligatoires par collection (fenêtre de CRA).
PARAMS_OBLIGATOIRES = {"times-reports": {"startMonth": "2026-05", "endMonth": "2026-07"}}


def _cle_dataset(chemin: str) -> str:
    return chemin.replace("-", "_")


def _lister(client, chemin: str, **params):
    return client.get(
        f"/api/{chemin}",
        headers=JWT,
        params={**PARAMS_OBLIGATOIRES.get(chemin, {}), **params},
    )


@pytest.mark.parametrize(("chemin", "type_", "detail", "included"), COLLECTIONS)
def test_liste_dialecte(client, chemin, type_, detail, included):  # noqa: ARG001
    """200, enveloppe officielle, types minuscules, ids au format réel."""
    if chemin in SANS_LISTE:
        pytest.skip("recherche absente en réel (405) — couverte par test_dialecte")
    reponse = _lister(client, chemin)
    assert reponse.status_code == 200
    corps = reponse.json()

    meta = corps["meta"]
    assert meta["totals"]["rows"] >= 1, f"/{chemin} est vide — le jeu de données doit être complet"
    assert meta["isLogged"] is True
    assert meta["language"] == "fr"
    assert isinstance(meta["version"], str)

    motif = ID_TEMPS if chemin == "times" else ID_OFFICIEL
    assert corps["data"], f"/{chemin} ne rend aucune donnée"
    for item in corps["data"]:
        assert item["type"] == type_
        assert motif.match(item["id"]), f"id non conforme : {item['id']!r}"
        assert isinstance(item["attributes"], dict)

    if included:
        assert corps.get("included"), f"/{chemin} devrait porter un tableau included"
    else:
        assert "included" not in corps, f"/{chemin} ne doit pas porter d'included (schéma officiel)"


@pytest.mark.parametrize(("chemin", "type_"), [(c, t) for c, t, detail, _ in COLLECTIONS if detail])
def test_detail_et_404(client, boond_state, chemin, type_):
    premier = boond_state.dataset[_cle_dataset(chemin)][0]
    reponse = client.get(f"/api/{chemin}/{premier['id']}", headers=JWT)
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["data"]["id"] == premier["id"]
    assert corps["data"]["type"] == type_
    # Le détail porte le meta SANS totals — la forme des profils réels.
    assert "totals" not in corps["meta"]
    assert corps["meta"]["isLogged"] is True

    absent = client.get(f"/api/{chemin}/999999", headers=JWT)
    assert absent.status_code == 404
    erreur = absent.json()["errors"][0]
    assert erreur["code"] == "404"
    assert erreur["detail"] == f"HTTP 404 (GET /api/{chemin}/999999)"


@pytest.mark.parametrize("chemin", [c for c, _, detail, _ in COLLECTIONS if not detail])
def test_pas_de_detail_sur_les_collections_search_only(client, boond_state, chemin):
    """/absences, /expenses et /times n'ont pas de /{id} chez le fournisseur."""
    premier = boond_state.dataset[_cle_dataset(chemin)][0]
    reponse = client.get(f"/api/{chemin}/{premier['id']}", headers=JWT)
    assert reponse.status_code == 404
    assert reponse.json()["errors"][0]["title"] == "404"  # l'enveloppe, pas le 404 FastAPI


@pytest.mark.parametrize(
    "chemin", [c for c, _, _, included in COLLECTIONS if included and c not in SANS_LISTE]
)
def test_included_resout_les_relations_de_la_page(client, chemin):
    """Toute relation portée par la page a son entité dans `included`.

    C'est la propriété que les clients réels exploitent (afficher les libellés
    sans requête supplémentaire) — un included lacunaire passerait inaperçu
    jusqu'au premier rendu côté consommateur.
    """
    corps = _lister(client, chemin, maxResults=100).json()
    inclus = {(e["type"], e["id"]) for e in corps.get("included", [])}
    # schedule/batch : toujours nuls ici ; opportunityparsingjob : hors liste
    # blanche du module (comme en réel).
    IGNORES = {"schedule", "batch", "opportunityparsingjob"}
    for item in corps["data"]:
        for nom, relation in (item.get("relationships") or {}).items():
            data = relation.get("data")
            refs = data if isinstance(data, list) else ([data] if data else [])
            for ref in refs:
                if ref["type"] in IGNORES:
                    continue
                assert (ref["type"], ref["id"]) in inclus, (
                    f"/{chemin} item {item['id']} : relation {nom} → "
                    f"{ref['type']}/{ref['id']} absente d'included"
                )


def test_integrite_referentielle_du_dataset(boond_state):
    """Chaque référence {id, type} du jeu de données résout, sans exception."""
    dataset = boond_state.dataset
    collections = {k: v for k, v in dataset.items() if isinstance(v, list) and k != "remuneration"}
    index = {(item["type"], item["id"]) for items in collections.values() for item in items}
    for cle, items in collections.items():
        for item in items:
            for nom, relation in (item.get("relationships") or {}).items():
                data = relation.get("data")
                refs = data if isinstance(data, list) else ([data] if data else [])
                for ref in refs:
                    assert (ref["type"], ref["id"]) in index, (
                        f"{cle}/{item['id']} : {nom} → {ref['type']}/{ref['id']} cassée"
                    )


def test_coherence_facturation(boond_state):
    """Factures ↔ commandes ↔ projets : les cumuls se recoupent."""
    d = boond_state.dataset
    factures_par_commande: dict[str, float] = {}
    for f in d["invoices"]:
        if f["attributes"]["state"] > 0:
            cid = f["relationships"]["order"]["data"]["id"]
            factures_par_commande[cid] = round(
                factures_par_commande.get(cid, 0.0)
                + f["attributes"]["turnoverInvoicedExcludingTax"],
                2,
            )
    for commande in d["orders"]:
        attrs = commande["attributes"]
        assert attrs["turnoverInvoicedExcludingTax"] == factures_par_commande.get(
            commande["id"], 0.0
        )
        assert attrs["deltaInvoicedExcludingTax"] == round(
            attrs["turnoverOrderedExcludingTax"] - attrs["turnoverInvoicedExcludingTax"], 2
        )
        # TTC = HT x 1,20 sur chaque facture.
    for f in d["invoices"]:
        attrs = f["attributes"]
        assert attrs["turnoverInvoicedIncludingTax"] == round(
            attrs["turnoverInvoicedExcludingTax"] * 1.20, 2
        )


def test_coherence_activite(boond_state):
    """Temps ↔ CRA ↔ missions : les lignes tombent dans le bon mois et le bon CRA."""
    d = boond_state.dataset
    cras = {t["id"]: t for t in d["times_reports"]}
    missions = {m["id"]: m for m in d["deliveries"]}
    for temps in d["times"]:
        attrs = temps["attributes"]
        cra = cras[temps["relationships"]["timesReport"]["data"]["id"]]
        assert attrs["startDate"][:7] == cra["attributes"]["term"], (
            f"temps {temps['id']} hors du terme de son CRA"
        )
        ref_mission = temps["relationships"]["delivery"]["data"]
        if ref_mission is not None:
            mission = missions[ref_mission["id"]]
            assert (
                mission["relationships"]["dependsOn"]["data"]["id"]
                == (cra["relationships"]["resource"]["data"]["id"])
            ), f"temps {temps['id']} : le CRA n'appartient pas au consultant de la mission"
        assert attrs["workUnitType"]["activityType"] in (
            "production",
            "internal",
            "exceptionalTime",
        )


def test_coherence_absences_et_frais(boond_state):
    d = boond_state.dataset
    for absence in d["absences"]:
        attrs = absence["attributes"]
        assert attrs["workUnitType"]["activityType"] == "absence"
        assert attrs["startDate"] <= attrs["endDate"]
        assert attrs["absencesReport"]["resource"]["id"]
        assert attrs["duration"] >= 1
    for frais in d["expenses"]:
        attrs = frais["attributes"]
        assert attrs["expensesReport"]["term"] == attrs["startDate"][:7]
        if attrs["isKilometricExpense"]:
            bareme = attrs["expensesReport"]["ratePerKilometerType"]["amount"]
            assert attrs["amountIncludingTax"] == round(attrs["numberOfKilometers"] * bareme, 2)


def test_coherence_rh(boond_state):
    """Contrats ↔ ressources : chaque salarié a un contrat, chaînes CDD → CDI liées."""
    d = boond_state.dataset
    ressources = {r["id"]: r for r in d["resources"]}
    titulaires = set()
    for contrat in d["contracts"]:
        ref = contrat["relationships"]["dependsOn"]["data"]
        assert ref["type"] == "resource"
        titulaires.add(ref["id"])
        res = ressources[ref["id"]]
        assert res["attributes"]["typeOf"] == 0, "un sous-traitant n'a pas de contrat de travail"
        assert contrat["attributes"]["monthlySalary"] > 1500
        parent = contrat["relationships"]["parentContract"]
        if parent["data"] is not None:
            ids = {c["id"] for c in d["contracts"]}
            assert parent["data"]["id"] in ids
    salaries = {r["id"] for r in d["resources"] if r["attributes"]["typeOf"] == 0}
    assert salaries <= titulaires, "chaque salarié doit porter au moins un contrat"


def test_paiements_achats(boond_state):
    d = boond_state.dataset
    for achat in d["purchases"]:
        engages = round(
            sum(
                p["attributes"]["amountExcludingTax"]
                for p in d["payments"]
                if p["relationships"]["purchase"]["data"]["id"] == achat["id"]
            ),
            2,
        )
        assert achat["attributes"]["engagedPaymentsAmountExcludingTax"] == engages
