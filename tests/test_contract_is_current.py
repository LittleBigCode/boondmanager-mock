"""Le contrat committé dit-il la vérité ?

Deux propriétés, et la seconde est celle qui compte vraiment.

**Le contrat ne dérive pas.** `contracts/boondmanager.openapi.yaml` est généré
depuis l'application, mais il est COMMITTÉ — c'est la seule disposition où le
fichier est à la fois relisible dans un diff de PR et garanti exact. Généré au
moment du build, il serait exact et invisible ; écrit à la main, il serait
visible et faux.

**L'inventaire d'honnêteté est complet.** La spécification d'insights360 est
formelle : « Do not invent BoondManager API fields. Mark unknowns TODO in the
contract and raise them rather than guessing. » Marquer ne suffit pas — un
marqueur que personne ne relève est un commentaire. Ce test exige que TOUT champ
`x-boond-confidence: unverified` figure dans `docs/UNVERIFIED-FIELDS.md`.

L'honnêteté devient ainsi une contrainte de build, pas une bonne intention.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

os.environ.setdefault("BOOND_MOCK_DATASET_PROFILE", "insights360")

import boondmanager_mock as mock

RACINE = Path(__file__).resolve().parents[1]
CONTRAT = RACINE / "contracts" / "boondmanager.openapi.yaml"
REGISTRE = RACINE / "docs" / "UNVERIFIED-FIELDS.md"


def _champs_marques(schemas: dict[str, Any], marqueur: str) -> dict[str, str]:
    """Rend {nom_de_champ: note} pour tous les champs portant ce niveau de confiance."""
    trouves: dict[str, str] = {}
    for schema in schemas.values():
        for nom, prop in (schema.get("properties") or {}).items():
            if prop.get("x-boond-confidence") == marqueur:
                trouves[nom] = prop.get("x-boond-note", "")
    return trouves


@pytest.fixture(scope="module")
def genere() -> dict[str, Any]:
    # `contrat_openapi()` et non `app.openapi()` : le contrat décrit le dialecte
    # BoondManager. Comparer à l'application brute échouerait selon que
    # BOOND_MOCK_ADMIN_ENABLED est vrai ou non au moment du run — le test
    # dépendrait de l'environnement au lieu de tester le contrat.
    return mock.contrat_openapi()


def test_le_contrat_committe_est_a_jour(genere: dict[str, Any]) -> None:
    """Le fichier committé == ce que l'application produit."""
    assert CONTRAT.exists(), f"{CONTRAT} absent — lancer `make contract`"
    committe = yaml.safe_load(CONTRAT.read_text(encoding="utf-8"))
    assert committe == genere, (
        "Le contrat committé a dérivé de l'application. Lancer `make contract`, "
        "RELIRE le diff — une forme de réponse qui change est un changement de "
        "contrat pour les consommateurs — puis committer."
    )


def test_le_contrat_porte_de_vraies_formes(genere: dict[str, Any]) -> None:
    """Un contrat sans schémas n'est pas un contrat.

    C'était l'état de départ : des handlers `(Request) -> JSONResponse`, donc un
    `/docs` qui listait des chemins et rien d'autre. Ce test empêche d'y revenir
    par inadvertance — en ajoutant une route non typée, par exemple.
    """
    schemas = genere.get("components", {}).get("schemas", {})
    assert len(schemas) > 20, f"seulement {len(schemas)} schémas — les routes sont-elles typées ?"

    for chemin in ("/api/resources", "/api/deliveries", "/api/times-reports"):
        contenu = genere["paths"][chemin]["get"]["responses"]["200"]["content"]
        schema = contenu["application/json"]["schema"]
        assert "$ref" in schema or "allOf" in schema, (
            f"{chemin} ne déclare pas de forme de réponse exploitable : {schema}"
        )


def test_le_contrat_ne_publie_pas_les_affordances_du_mock(genere: dict[str, Any]) -> None:
    """Ni `/__admin` ni `/__fixtures` ne sont du BoondManager.

    Les publier ferait passer pour du fournisseur ce qui n'en est pas, et un
    consommateur pourrait s'y adosser — le plan de contrôle des pannes, en
    particulier, n'existe pas en production.
    """
    intrus = [c for c in genere["paths"] if c.startswith(("/__admin", "/__fixtures"))]
    assert not intrus, (
        f"le contrat publie des affordances du mock : {intrus}. "
        "Elles sont documentées dans le README, pas dans le contrat."
    )


@pytest.mark.parametrize("code", ["401", "422", "429"])
def test_les_erreurs_sont_documentees(genere: dict[str, Any], code: str) -> None:
    """Les codes d'erreur font partie du contrat.

    Ils ne passent PAS par `response_model` (qui ne décrit que le cas nominal) :
    sans déclaration explicite, un consommateur ne saurait pas qu'un 422 est
    l'échec d'authentification attendu, ni qu'un 429 porte un `Retry-After`.
    """
    reponses = genere["paths"]["/api/resources"]["get"]["responses"]
    assert code in reponses, f"le code {code} n'est pas documenté sur /api/resources"


def test_tout_champ_non_verifie_est_inscrit_au_registre(genere: dict[str, Any]) -> None:
    """LE test qui rend l'honnêteté vérifiable.

    Marquer un champ `unverified` sans l'inscrire au registre revient à écrire un
    commentaire : personne ne le relèvera, et il partira en production comme une
    certitude. Ce test transforme l'inventaire en contrainte de build.
    """
    schemas = genere.get("components", {}).get("schemas", {})
    marques = _champs_marques(schemas, "unverified")
    assert marques, (
        "AUCUN champ marqué `unverified`. Ce serait une bonne nouvelle si le "
        "dialecte était intégralement attesté — il ne l'est pas (updateDate, "
        "upn, deliveries, times-reports…). Le marquage a-t-il été retiré ?"
    )

    registre = REGISTRE.read_text(encoding="utf-8")
    absents = sorted(nom for nom in marques if nom not in registre)
    assert not absents, (
        "Champs marqués `unverified` mais ABSENTS de docs/UNVERIFIED-FIELDS.md :\n  "
        + "\n  ".join(f"{n} — {marques[n]}" for n in absents)
        + "\n\nUn marqueur que personne ne relève est un commentaire. Inscrire "
        "chaque champ au registre, avec ce qu'il faudrait faire pour lever le doute."
    )


def test_les_champs_inventes_sont_signales_comme_tels(genere: dict[str, Any]) -> None:
    """`invented` est plus grave qu'`unverified` et doit rester exceptionnel.

    `unverified` dit « plausible, non prouvé ». `invented` dit « nous savons que
    ça n'existe pas ». Le second ne doit jamais s'installer discrètement : s'il
    apparaît, il doit être au registre, avec sa justification.
    """
    schemas = genere.get("components", {}).get("schemas", {})
    inventes = _champs_marques(schemas, "invented")
    if not inventes:
        return
    registre = REGISTRE.read_text(encoding="utf-8")
    absents = sorted(nom for nom in inventes if nom not in registre)
    assert not absents, f"champs INVENTÉS absents du registre : {absents}"
