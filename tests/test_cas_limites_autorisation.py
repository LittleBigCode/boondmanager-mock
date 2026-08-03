"""Les cas limites que le jeu `realiste` porte pour les modèles d'autorisation.

Ces trois propriétés ne servent pas la vraisemblance du jeu de données : elles
servent à ce qu'un modèle d'autorisation construit dessus PUISSE échouer. Un
jeu uniforme rend un test de visibilité vrai par vacuité — il passe aussi bien
avec un modèle correct qu'avec un modèle cassé.

Elles sont donc assertées ICI, dans le dépôt du mock, et non seulement chez le
consommateur : un refactor du générateur qui les ferait disparaître doit casser
un test visible, pas dégrader silencieusement la couverture d'un autre dépôt.
"""

from __future__ import annotations

import random
from collections import Counter

from boondmanager_mock.dataset.realiste import (
    _AGENCE_AVANT_MUTATION,
    _ID_MUTATION,
    _IDS_HOMONYMES,
    _IDS_SORTIS,
    _MOIS_MUTATION,
    _MOIS_SORTIE,
    MOIS_ACTIVITE,
    _cras,
    _ressources,
)


def _jeu() -> tuple[list[dict], list[dict]]:
    ressources = _ressources(random.Random(42))
    cras, _ = _cras(ressources, random.Random(42))
    return ressources, cras


def test_deux_homonymes_avec_des_adresses_distinctes() -> None:
    """Même prénom + même nom, adresses DIFFÉRENTES, agences DIFFÉRENTES.

    C'est le cas le plus dangereux du lot. Un consommateur qui dérive un
    identifiant d'annuaire du seul « prénom.nom » attribue la même identité aux
    deux et FUSIONNE leurs périmètres de visibilité — une escalade de privilège
    silencieuse, pas un défaut cosmétique.

    Les agences distinctes ne sont pas un détail : homonymes dans la même
    agence, une fusion d'identité ne changerait aucun périmètre et le test du
    consommateur resterait vert à tort.
    """
    ressources, _ = _jeu()
    par_id = {r["id"]: r for r in ressources}
    a, b = (par_id[str(i)] for i in _IDS_HOMONYMES)

    assert (a["attributes"]["firstName"], a["attributes"]["lastName"]) == (
        b["attributes"]["firstName"],
        b["attributes"]["lastName"],
    ), "les homonymes doivent porter EXACTEMENT la même identité nominale"

    assert a["attributes"]["email1"] != b["attributes"]["email1"], (
        "des adresses identiques feraient du cas un doublon, pas un homonyme"
    )
    assert (
        a["relationships"]["agency"]["data"]["id"] != b["relationships"]["agency"]["data"]["id"]
    ), "sans agences distinctes, le cas ne discrimine rien"

    # …et ils doivent rester les SEULS : un second couple d'homonymes non
    # intentionnel rendrait tout diagnostic ambigu chez le consommateur.
    noms = Counter((r["attributes"]["firstName"], r["attributes"]["lastName"]) for r in ressources)
    assert [n for n, c in noms.items() if c > 1] == [
        (a["attributes"]["firstName"], a["attributes"]["lastName"])
    ]


def test_une_mutation_laisse_les_faits_anterieurs_sur_l_ancienne_agence() -> None:
    """Les CRA antérieurs à la mutation portent l'ANCIENNE agence.

    Un modèle qui rattache les faits au collaborateur plutôt qu'à la ligne de
    fait réécrit rétroactivement l'historique dès qu'un collaborateur bouge —
    et ça reste invisible tant que personne ne bouge.
    """
    ressources, cras = _jeu()
    courante = next(r for r in ressources if r["id"] == str(_ID_MUTATION))
    agence_courante = courante["relationships"]["agency"]["data"]["id"]

    par_terme = {
        c["attributes"]["term"]: c["relationships"]["agency"]["data"]["id"]
        for c in cras
        if c["relationships"]["resource"]["data"]["id"] == str(_ID_MUTATION)
    }
    assert par_terme, "la ressource mutée doit avoir des CRA"

    avant = {t: a for t, a in par_terme.items() if int(t.split("-")[1]) < _MOIS_MUTATION}
    apres = {t: a for t, a in par_terme.items() if int(t.split("-")[1]) >= _MOIS_MUTATION}
    assert avant and apres, (
        "la mutation doit tomber DANS MOIS_ACTIVITE, sinon un des deux côtés est vide "
        "et le cas n'existe pas"
    )
    assert set(avant.values()) == {str(_AGENCE_AVANT_MUTATION)}
    assert set(apres.values()) == {agence_courante}
    assert str(_AGENCE_AVANT_MUTATION) != agence_courante


def test_un_sorti_conserve_son_historique_et_rien_apres() -> None:
    """Un partant garde ses faits produits, et n'en produit plus après.

    Deux propriétés distinctes, et les confondre est exactement ce qui fait
    qu'un partant conserve des droits — ou qu'on perd la trace de ce qu'il a
    produit. Sans CRA du tout, le second risque devient invérifiable chez le
    consommateur.
    """
    _, cras = _jeu()
    mois_max = max(m for _, m in MOIS_ACTIVITE)
    assert mois_max > _MOIS_SORTIE, (
        "une sortie au dernier mois d'activité ne prouve rien : il n'y aurait aucun "
        "mois APRÈS où constater l'absence"
    )

    for rid in _IDS_SORTIS:
        termes = sorted(
            c["attributes"]["term"]
            for c in cras
            if c["relationships"]["resource"]["data"]["id"] == str(rid)
        )
        assert termes, f"la ressource sortie {rid} doit conserver un historique"
        assert all(int(t.split("-")[1]) <= _MOIS_SORTIE for t in termes), (
            f"la ressource sortie {rid} produit des faits APRÈS son départ : {termes}"
        )
