"""Pagination, tri, filtre incrémental — et les pannes qui les accompagnent.

Ce module concentre tout ce que la spec d'insights360 demande de reproduire
au-delà du chemin heureux :

  • pagination, dernière page plus courte que la taille de page ;
  • ordre INSTABLE sauf tri explicite ;
  • un enregistrement qui apparaît sur deux pages consécutives quand la donnée
    change en cours de pagination — la cause classique d'une duplication
    silencieuse ;
  • filtre incrémental sur l'horodatage de mise à jour.
"""

from __future__ import annotations

import json
from typing import Any

from .injection import engine
from .settings import settings

# ┌─ NOM DU PARAMÈTRE INCRÉMENTAL : NON ATTESTÉ ────────────────────────────────┐
# │ L'ADR-0002 d'ophelie documente le dialecte BoondManager depuis une          │
# │ intégration production VÉRIFIÉE, et ne mentionne AUCUN filtre sur           │
# │ horodatage — seulement `page`, `maxResults` et `keywords`.                  │
# │                                                                             │
# │ La spec d'insights360 est catégorique : « Do not invent BoondManager API    │
# │ fields. Mark unknowns TODO in the contract and raise them. » On ne devine   │
# │ donc pas : le mock accepte LES DEUX formes plausibles, toutes deux marquées │
# │ `unverified` au contrat et inscrites dans docs/UNVERIFIED-FIELDS.md.        │
# │                                                                             │
# │ Côté consommateur, le nom est une CONSTANTE UNIQUE                          │
# │ (insights360:extract/…/boondmanager/client.py::UPDATED_SINCE_PARAM), donc   │
# │ la correction, le jour où le fournisseur tranche, est une ligne.            │
# └─────────────────────────────────────────────────────────────────────────────┘
UPDATED_SINCE_PARAMS = ("updatedSince", "filter[updateDate][gte]")

UPDATED_AT_FIELD = "updateDate"


def apply_keywords(items: list[dict[str, Any]], keywords: str) -> list[dict[str, Any]]:
    """Recherche plein-texte grossière — comme le mock d'origine."""
    if not keywords:
        return items
    needle = keywords.strip().lower()
    return [i for i in items if needle in json.dumps(i, ensure_ascii=False).lower()]


def apply_incremental(items: list[dict[str, Any]], since: str | None) -> list[dict[str, Any]]:
    """Filtre sur l'horodatage de mise à jour.

    Comparaison lexicographique : les dates sont en ISO-8601, donc l'ordre
    lexicographique et l'ordre chronologique coïncident. Pas de parsing, donc
    pas de dépendance à un fuseau ni de mode de défaillance sur une date mal
    formée — c'est le mock, pas un moteur de dates.
    """
    if not since:
        return items
    return [i for i in items if str(i.get("attributes", {}).get(UPDATED_AT_FIELD, "")) >= since]


def extract_since(params: dict[str, str]) -> str | None:
    for name in UPDATED_SINCE_PARAMS:
        if (value := params.get(name)) is not None:
            return value
    return None


def apply_order(
    items: list[dict[str, Any]], params: dict[str, str], request_index: int
) -> list[dict[str, Any]]:
    """Ordre stable SI un tri est demandé, instable sinon.

    Reproduire l'instabilité est le but : une API qui rend ses pages dans un
    ordre non garanti fait sauter des enregistrements et en duplique d'autres
    dès qu'on pagine sans `ORDER BY`. Un pipeline qui « marche » contre un mock
    trié est un pipeline dont le bug attend la production.

    L'instabilité est DÉTERMINISTE dans un test donné — `hash((rang de requête,
    id))` — donc reproductible, tout en variant réellement d'une requête à
    l'autre.
    """
    sort_field = params.get("sort")
    if sort_field:
        reverse = params.get("order", "asc").lower() == "desc"
        return sorted(
            items,
            key=lambda i: str(i.get("attributes", {}).get(sort_field, "")),
            reverse=reverse,
        )

    # ┌─ LE PROFIL `ophelie` EST GELÉ, ORDRE COMPRIS ──────────────────────────┐
    # │ L'instabilité d'ordre est une PROPRIÉTÉ du profil `insights360`, pas du │
    # │ mock en général. Le profil `ophelie` reproduit le comportement          │
    # │ historique, et un profil « gelé » dont la sémantique de pagination      │
    # │ change n'est pas gelé — il casse simplement plus tard.                  │
    # │                                                                         │
    # │ Ce que l'instabilité a révélé au passage mérite d'être écrit : le       │
    # │ client de production d'ophelie pagine SANS tri explicite. Contre le     │
    # │ mock instable, il ne retrouvait que 18 des 24 ressources — il en saute  │
    # │ et en duplique. Contre une vraie API qui ne garantit pas son ordre, le  │
    # │ même défaut existe, en silence. Cf. docs/features/ordering.md.          │
    # └─────────────────────────────────────────────────────────────────────────┘
    # `state.profile` et non `settings.profile` : un `reset(profile=…)` par le
    # plan de contrôle doit porter, sinon un test qui bascule de profil garderait
    # la sémantique de l'autre.
    from .state import state

    if (
        settings.stable_order
        or state.profile == "ophelie"
        or engine.first("stable_order", "*") is not None
    ):
        return items

    return sorted(items, key=lambda i: hash((request_index, i.get("id"))))


def apply_page_drift(
    items: list[dict[str, Any]], page: int, page_size: int, path: str
) -> list[dict[str, Any]]:
    """Simule une donnée qui bouge EN COURS de pagination.

    Le scénario réel : un enregistrement est inséré (ou supprimé) entre la
    récupération de la page 1 et celle de la page 2. Tout glisse d'un cran, et
    un enregistrement se retrouve rendu deux fois — ou pas du tout.

    C'est la cause classique de duplication silencieuse, et la raison pour
    laquelle le pipeline doit dédupliquer sur sa clé de merge plutôt que faire
    confiance à la pagination.
    """
    rule = engine.first("page_drift", path)
    if rule is None or page <= rule.after_page:
        return items
    if not rule.consume():
        return items
    if rule.mode == "insert":
        # Décale d'un cran vers l'arrière : le dernier élément de la page
        # précédente réapparaît en tête de celle-ci.
        offset = max(0, (page - 1) * page_size - 1)
        return items[:offset] + items[offset:]
    return items


def paginate(
    items: list[dict[str, Any]], params: dict[str, str]
) -> tuple[list[dict[str, Any]], int, int] | None:
    """Rend (tranche, page, taille) ou None si les paramètres sont invalides."""
    try:
        page = max(1, int(params.get("page", 1)))
        requested = int(params.get("maxResults", settings.default_max_results))
    except ValueError:
        return None
    page_size = min(settings.max_results_cap, max(1, requested))
    start = (page - 1) * page_size
    return items[start : start + page_size], page, page_size


def envelope(data: list[dict[str, Any]], total: int) -> dict[str, Any]:
    """L'enveloppe JSON:API telle que le client la lit."""
    return {"data": data, "meta": {"totals": {"rows": total}}}
