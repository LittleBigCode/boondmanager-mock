"""Les endroits où l'API RÉELLE diverge de sa propre documentation.

Un mock a deux fidélités possibles, et elles s'opposent : être fidèle à la
DOCUMENTATION, ou fidèle au COMPORTEMENT OBSERVÉ. Ce dépôt choisit le second,
sans exception.

La raison est concrète. Un mock qui « fait bien » là où le fournisseur ne le
fait pas rend son consommateur vert sur un comportement qui n'existe pas : le
dimensionnement, la cadence d'extraction et la charge imposée à l'API se
calculent alors sur une fiction. C'est exactement ce qui s'est produit pour
insights360 — sa cadence horaire supposait un filtre incrémental sur /times,
et représentait en réalité ~25 000 appels par jour chez le fournisseur.

Chaque écart consigné ici a été MESURÉ contre ui.boondmanager.com, avec une
date et des chiffres. Aucun n'est déduit de la documentation.
"""

from __future__ import annotations

from typing import Any

from boondmanager_mock.app import COLLECTIONS
from tests.conftest import JWT


def _total(reponse: Any) -> int:
    return int(reponse.json()["meta"]["totals"]["rows"])


def test_times_ignore_le_filtre_de_periode_comme_l_api_reelle(client: Any) -> None:
    """`/times` accepte `period`/`startDate`/`endDate` et les IGNORE.

    Mesuré le 2026-08-04 contre ui.boondmanager.com, sur un tenant de
    production à 106 976 lignes de temps :

        sans filtre                    → 106 976
        startDate + endDate            → 106 976
        startMonth + endMonth          → 106 976
        period=updated + startDate     → 106 976

    Les quatre formes rendent le même total. Aucune n'est rejetée — c'est le
    point important : un 422 aurait au moins signalé quelque chose. Ici l'API
    accepte silencieusement un filtre qu'elle n'applique pas.

    Ce test échouera le jour où BoondManager corrigera son API. C'est
    souhaitable : la correction devra alors être constatée, pas devinée.
    """
    h = JWT

    reference = _total(client.get("/api/times", params={"maxResults": 1}, headers=h))
    assert reference > 0, "le jeu de référence doit contenir des lignes de temps"

    for filtre in (
        {"startDate": "2026-07-01", "endDate": "2026-07-31"},
        {"startMonth": "2026-07", "endMonth": "2026-07"},
        {"period": "updated", "startDate": "2026-07-01"},
        {"period": "created", "startDate": "2026-07-01", "endDate": "2026-07-31"},
    ):
        p = dict(filtre)
        p["maxResults"] = "1"
        reponse = client.get("/api/times", params=p, headers=h)
        assert reponse.status_code == 200, (
            f"{filtre} doit être ACCEPTÉ, pas rejeté — l'API réelle ne renvoie "
            f"aucune erreur sur ces paramètres (reçu {reponse.status_code})"
        )
        assert _total(reponse) == reference, (
            f"{filtre} a filtré {reference - _total(reponse)} ligne(s). L'API "
            "réelle n'en filtre aucune : le mock doit reproduire le "
            "comportement observé, pas la documentation."
        )


def test_les_autres_collections_honorent_bien_le_filtre(client: Any) -> None:
    """L'écart est LOCAL à `/times` — pas une propriété du mock entier.

    Sans cette contre-épreuve, `filtre_periode=False` posé par erreur sur une
    autre collection passerait inaperçu : le test précédent resterait vert, et
    un consommateur perdrait silencieusement son incrémentalité.
    """
    sans_filtre = [s.chemin for s in COLLECTIONS if not s.filtre_periode]
    assert sans_filtre == ["times"], (
        f"seule /times est concernée par l'écart mesuré ; trouvé : {sans_filtre}. "
        "Ajouter une collection ici exige une MESURE contre l'API réelle, "
        "documentée dans docs/comparisons/."
    )

    h = JWT
    # `/actions` porte `creationDate` et honore le filtre — contre-épreuve sur
    # une collection au comportement conforme à la documentation.
    total = _total(client.get("/api/actions", params={"maxResults": 1}, headers=h))
    filtre = _total(
        client.get(
            "/api/actions",
            params={"maxResults": 1, "period": "created", "endDate": "1900-01-01"},
            headers=h,
        )
    )
    assert filtre < total, (
        "une fenêtre fermée en 1900 doit vider /actions ; si elle ne le fait "
        "pas, le filtre de période est cassé pour TOUTES les collections"
    )
