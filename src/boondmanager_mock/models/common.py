"""Modèles pydantic — la SOURCE du contrat OpenAPI.

┌─ POURQUOI TYPER, ET CE QUE ÇA COÛTE ────────────────────────────────────────┐
│ Avant, tous les handlers étaient `(request: Request) -> JSONResponse`. FastAPI │
│ générait donc un `/docs` qui documentait des CHEMINS et rien d'autre : aucune  │
│ forme de réponse, aucun champ. Un contrat vide n'est pas un contrat.          │
│                                                                                │
│ En typant, on obtient d'un coup : le contrat, la validation des réponses (le   │
│ générateur ne peut plus dériver en silence de la forme déclarée), et des types │
│ exploitables par les consommateurs.                                            │
│                                                                                │
│ Le coût est réel et il faut le nommer : **typer pousse à inventer des          │
│ champs**, ce que la spec d'insights360 interdit en toutes lettres. La parade   │
│ est structurelle, pas disciplinaire :                                          │
│                                                                                │
│   • `extra="allow"` partout — un champ inconnu de l'API réelle passe, il n'est │
│     simplement pas documenté. Le modèle décrit ce qu'on SAIT, pas ce qui EST.  │
│   • `x-boond-confidence` sur tout champ non adossé à une preuve de production. │
│   • un test échoue si un champ `unverified` n'est pas inscrit dans             │
│     docs/UNVERIFIED-FIELDS.md. L'honnêteté devient une contrainte de build.    │
└────────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


def unverified(description: str) -> dict[str, Any]:
    """Marque un champ dont le nom ou la forme n'est PAS attesté.

    À utiliser via `json_schema_extra`. Tout champ ainsi marqué DOIT figurer
    dans `docs/UNVERIFIED-FIELDS.md` — `tests/test_contract_is_current.py` le
    vérifie, pour que l'inventaire ne se dégrade pas en bonne intention.
    """
    return {"x-boond-confidence": "unverified", "x-boond-note": description}


def invented(description: str) -> dict[str, Any]:
    """Marque un champ ou un endpoint qui n'existe PAS chez le fournisseur.

    Distinct de `unverified` : ici on sait qu'on a fabriqué la forme, faute
    d'endpoint attesté. Le mode `stub` de la rémunération en est le seul usage.
    """
    return {"x-boond-confidence": "invented", "x-boond-note": description}


class Permissif(BaseModel):
    """Base commune : accepte les champs inconnus plutôt que de les rejeter.

    Un modèle strict transformerait toute évolution de l'API réelle en panne du
    mock. Ce n'est pas ce qu'on veut : le mock décrit ce que nous consommons,
    pas l'exhaustivité de ce que BoondManager expose.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ── Enveloppe JSON:API ───────────────────────────────────────────────────────


class RefDonnee(Permissif):
    """La référence `{id, type}` d'une relation JSON:API."""

    id: str
    type: str


class Relation(Permissif):
    """Une relation. `data` peut être nul — un collaborateur sans manager, par exemple."""

    data: RefDonnee | None = None


class Totaux(Permissif):
    rows: int = Field(description="Nombre total d'éléments AVANT pagination.")


class Meta(Permissif):
    totals: Totaux


class ListEnvelope[T](BaseModel):
    """`{"data": [...], "meta": {"totals": {"rows": N}}}` — l'enveloppe de liste.

    `meta.totals.rows` compte AVANT pagination : c'est ce qui permet au client de
    savoir quand s'arrêter. Un client qui s'arrêterait sur « page vide » ferait
    une requête de trop à chaque exécution.
    """

    model_config = ConfigDict(extra="allow")

    data: list[T]
    meta: Meta


class ItemEnvelope[T](BaseModel):
    """`{"data": {...}}` — l'enveloppe de détail."""

    model_config = ConfigDict(extra="allow")

    data: T


# ── Erreurs ──────────────────────────────────────────────────────────────────


class Erreur(Permissif):
    code: str = Field(description="Le code HTTP, en chaîne — comme le fait l'API réelle.")
    detail: str


class ErrorEnvelope(BaseModel):
    """`{"errors": [{"code", "detail"}]}`.

    Le client d'ophelie lit `errors[0].detail || errors[0].title` : s'écarter de
    cette forme rendrait les erreurs illisibles côté consommateur sans que rien
    n'échoue franchement.
    """

    model_config = ConfigDict(extra="allow")

    errors: list[Erreur]


# Réponses d'erreur déclarées sur chaque route : elles apparaissent au contrat
# sans passer par `response_model`, qui ne décrit que le cas nominal.
REPONSES_ERREUR: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "Aucun identifiant fourni."},
    404: {"model": ErrorEnvelope, "description": "Ressource inconnue."},
    422: {
        "model": ErrorEnvelope,
        "description": (
            "Jeton présent mais invalide, ou paramètre de pagination illisible. "
            "**422 et non 401** — c'est ce que fait l'API réelle, et le code de "
            "retour est ce sur quoi une logique de retry se décide."
        ),
    },
    429: {
        "model": ErrorEnvelope,
        "description": "Limite de débit atteinte. En-tête `Retry-After` en secondes.",
    },
    500: {"model": ErrorEnvelope, "description": "Panne injectée."},
    503: {"model": ErrorEnvelope, "description": "Panne injectée, transitoire."},
}

# Paramètres de requête partagés par toutes les collections.
ParamPage = Annotated[int, Field(ge=1, description="Numéro de page, base 1.")]
ParamMaxResults = Annotated[
    int, Field(ge=1, le=500, description="Taille de page. Défaut 30, plafond 500.")
]
