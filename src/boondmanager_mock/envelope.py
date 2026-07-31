"""Enveloppes, pagination, tri, filtre incrémental — et les pannes associées.

L'enveloppe suit le schéma OFFICIEL (doc.boondmanager.com, RAML) :

    liste  : {"data": [...], "included": [...], "meta": {"totals": {"rows": N},
              "version": "…", "isLogged": true, "language": "fr"}}
    détail : {"data": {...}, "included": [...], "meta": {version, isLogged, language}}

`included` n'apparaît que sur les modules dont le schéma le déclare, et
seulement s'il est non vide.

Au-delà du chemin heureux, ce module reproduit :
  • la pagination `page`/`maxResults` (défaut 30, plafond 500), dernière page
    plus courte ;
  • l'ordre INSTABLE sauf tri explicite — une API qui ne garantit pas son ordre
    fait sauter et dupliquer des enregistrements dès qu'on pagine sans tri ;
  • la dérive de pagination (un enregistrement rendu sur deux pages) ;
  • un filtre incrémental sur `updateDate` (affordance du mock, cf. plus bas).
"""

from __future__ import annotations

import json
from typing import Any

from .injection import engine
from .settings import settings

#: Les versions que `meta` annonce — relevées sur la vraie API le 2026-07-31.
VERSION_BOOND = "9.1.78.1"
VERSION_ANDROID_MIN = "2.31.5"
VERSION_IOS_MIN = "2.28.6"


def _horodatage_ms() -> int:
    """`meta.timestamp` — epoch millisecondes, DÉTERMINISTE.

    Dérivé de l'horloge VIRTUELLE : époque du jeu de données + temps écoulé
    depuis le reset (y compris les avances de /__admin/clock). Deux serveurs au
    même âge rendent le même timestamp — la propriété que le réel n'a pas, et
    que le mock garde pour rester rejouable.
    """
    from .evolution import EPOQUE
    from .state import state

    ecoule = engine.now() - state.evolution.demarrage
    return int(EPOQUE.timestamp() * 1000 + ecoule * 1000)


def _meta_commun(connecte: bool) -> dict[str, Any]:
    """Le socle `meta` observé sur la vraie API — présent MÊME en erreur.

    Hors session (401, JWT invalide, route inconnue) : `isLogged: false`,
    `language: "en"`, sans `login` ni `customer`.
    """
    meta: dict[str, Any] = {
        "version": VERSION_BOOND,
        "androidMinVersion": VERSION_ANDROID_MIN,
        "iosMinVersion": VERSION_IOS_MIN,
        "isLogged": connecte,
        "language": "fr" if connecte else "en",
        "timestamp": _horodatage_ms(),
    }
    if connecte:
        meta["login"] = settings.basic_user
        meta["customer"] = settings.customer
    return meta


def meta_erreur(connecte: bool) -> dict[str, Any]:
    """Le meta des réponses d'erreur (importé par errors.py)."""
    return _meta_commun(connecte)


# ┌─ INCRÉMENTAL : LA VOIE OFFICIELLE, PUIS L'AFFORDANCE ──────────────────────┐
# │ La voie OFFICIELLE (RAML) : `period=updated&startDate=AAAA-MM-JJ&endDate=…`│
# │ — documentée sur candidates, companies, contacts, invoices, opportunities,│
# │ orders, payments, purchases ; granularité JOUR. `period=created` idem sur │
# │ la date de création. `sort=updateDate` est une clé de tri officielle sur  │
# │ resources, candidates, companies, contacts, opportunities.                │
# │                                                                            │
# │ Le mock applique `period=updated|created` sur TOUTES ses collections      │
# │ (sur-ensemble documenté) ; les autres valeurs de `period` (working, hired,│
# │ inProgress…) et les filtres métier (`flags`, `states`, `keywordsType`…)    │
# │ sont ACCEPTÉS et ignorés — un stub ne doit pas casser un client réel.     │
# │                                                                            │
# │ S'y ajoute une affordance du mock, plus fine que le jour :                │
# │ `updatedSince=<ISO-8601>` (ou `filter[updateDate][gte]`). Ces deux noms ne │
# │ sont PAS attestés — marqués `unverified`, cf. docs/UNVERIFIED-FIELDS.md.  │
# └─────────────────────────────────────────────────────────────────────────────┘
UPDATED_SINCE_PARAMS = ("updatedSince", "filter[updateDate][gte]")

UPDATED_AT_FIELD = "updateDate"

#: `period` → champ filtré, bornes [startDate, endDate] inclusives au jour.
PERIODES_SUPPORTEES = {"updated": "updateDate", "created": "creationDate"}


def apply_period(items: list[dict[str, Any]], params: dict[str, str]) -> list[dict[str, Any]]:
    """Le filtre incrémental OFFICIEL : `period=updated|created` + bornes en jours.

    Un item sans le champ visé est exclu quand le filtre est actif — une ligne
    sans date de création ne peut pas être « créée entre deux dates ».
    """
    champ = PERIODES_SUPPORTEES.get(params.get("period", ""))
    if champ is None:
        return items
    debut = params.get("startDate", "0000-00-00")
    fin = params.get("endDate", "9999-12-31")
    return [
        i
        for i in items
        if (jour := str(i.get("attributes", {}).get(champ, ""))[:10]) and debut <= jour <= fin
    ]


def apply_keywords(
    items: list[dict[str, Any]],
    keywords: str,
    blobs: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Recherche plein-texte grossière — suffisante pour un mock.

    `blobs` : le texte de recherche précalculé par item (state.blobs), aligné
    sur la collection COMPLÈTE — évite de resérialiser le dataset à chaque
    requête."""
    if not keywords:
        return items
    needle = keywords.strip().lower()
    if blobs is not None and len(blobs) == len(items):
        return [i for i, blob in zip(items, blobs, strict=True) if needle in blob]
    return [i for i in items if needle in json.dumps(i, ensure_ascii=False).lower()]


def apply_incremental(items: list[dict[str, Any]], since: str | None) -> list[dict[str, Any]]:
    """Filtre sur l'horodatage de mise à jour.

    Comparaison lexicographique : les horodatages sont ISO-8601 (fuseau
    Europe/Paris, décalage sans deux-points, comme la vraie API), donc l'ordre
    lexicographique et l'ordre chronologique coïncident au jour près — assez
    pour un mock, sans parsing ni mode de défaillance sur une date malformée.
    """
    if not since:
        return items
    return [i for i in items if str(i.get("attributes", {}).get(UPDATED_AT_FIELD, "")) >= since]


def extract_since(params: dict[str, str]) -> str | None:
    for name in UPDATED_SINCE_PARAMS:
        if (value := params.get(name)) is not None:
            return value
    return None


def _valeur_triable(item: dict[str, Any], chemin: str) -> str:
    """Valeur de tri, chemin pointé accepté (`workUnitType.reference`)."""
    noeud: Any = item.get("attributes", {})
    for segment in chemin.split("."):
        if not isinstance(noeud, dict):
            return ""
        noeud = noeud.get(segment)
    return "" if noeud is None else str(noeud)


def apply_order(
    items: list[dict[str, Any]], params: dict[str, str], request_index: int
) -> list[dict[str, Any]]:
    """Ordre STABLE par défaut — c'est ce que la vraie API fait (relevé
    2026-07-31 : deux appels identiques rendent la même séquence).

    L'instabilité reste disponible, en OPT-IN, pour éprouver les pipelines qui
    paginent sans tri (`BOOND_MOCK_STABLE_ORDER=false` ou une injection
    `unstable_order`) : une API qui ne garantit pas son ordre fait sauter des
    enregistrements et en duplique d'autres. L'instabilité est DÉTERMINISTE
    dans un test donné — `hash((rang de requête, id))` — donc reproductible.
    """
    sort_field = params.get("sort")
    if sort_field:
        reverse = params.get("order", "asc").lower() == "desc"
        return sorted(items, key=lambda i: _valeur_triable(i, sort_field), reverse=reverse)

    instable = not settings.stable_order or engine.first("unstable_order", "*") is not None
    if not instable:
        return items

    return sorted(items, key=lambda i: hash((request_index, i.get("id"))))


def apply_page_drift(
    tous: list[dict[str, Any]], page: int, page_size: int, path: str
) -> list[dict[str, Any]] | None:
    """Simule une donnée qui bouge EN COURS de pagination.

    Le scénario réel : un enregistrement est inséré (ou supprimé) entre la
    récupération de la page 1 et celle de la page 2. Tout glisse d'un cran, et
    un enregistrement se retrouve rendu deux fois — ou pas du tout.

    C'est la cause classique de duplication silencieuse, et la raison pour
    laquelle un pipeline doit dédupliquer sur sa clé de merge plutôt que faire
    confiance à la pagination.

    Opère sur la liste COMPLÈTE et rend la tranche décalée — ou None si aucune
    règle ne s'applique. (Le mock d'origine décalait la tranche déjà découpée :
    `items[:n] + items[n:]`, une identité — la panne ne s'appliquait jamais.)
    """
    rule = engine.first("page_drift", path)
    if rule is None or page <= rule.after_page:
        return None
    if not rule.consume():
        return None
    if rule.mode == "insert":
        # Une insertion en amont décale tout vers l'arrière : le dernier
        # élément de la page précédente réapparaît en tête de celle-ci.
        debut = max(0, (page - 1) * page_size - 1)
    else:
        # Une suppression en amont fait tout remonter d'un cran : le premier
        # élément attendu de cette page a déjà été servi… ou est perdu.
        debut = (page - 1) * page_size + 1
    return tous[debut : debut + page_size]


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


def envelope(
    data: list[dict[str, Any]],
    total: int,
    included: list[dict[str, Any]] | None = None,
    meta_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """L'enveloppe de liste — meta complet observé + clés propres au module."""
    corps: dict[str, Any] = {"data": data}
    if included:
        corps["included"] = included
    corps["meta"] = {**_meta_commun(True), **(meta_extra or {}), "totals": {"rows": total}}
    return corps


def envelope_detail(
    item: dict[str, Any], included: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """L'enveloppe de détail — même `meta`, sans `totals`, comme les profils réels."""
    corps: dict[str, Any] = {"data": item}
    if included:
        corps["included"] = included
    corps["meta"] = _meta_commun(True)
    return corps
