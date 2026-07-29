"""Modèles pydantic — la source du contrat OpenAPI.

Sans eux, FastAPI génère un `/docs` qui documente des chemins et rien d'autre.
Cf. le préambule de `common.py` pour le raisonnement complet, y compris le coût
assumé (typer pousse à inventer des champs, et comment on s'en garde).
"""

from .common import (
    REPONSES_ERREUR,
    ErrorEnvelope,
    ItemEnvelope,
    ListEnvelope,
    Permissif,
    invented,
    unverified,
)
from .entities import (
    Agence,
    Compte,
    Contact,
    Cra,
    DonneesTechniques,
    Mission,
    Projet,
    Ressource,
    Societe,
)

__all__ = [
    "REPONSES_ERREUR",
    "Agence",
    "Compte",
    "Contact",
    "Cra",
    "DonneesTechniques",
    "ErrorEnvelope",
    "ItemEnvelope",
    "ListEnvelope",
    "Mission",
    "Permissif",
    "Projet",
    "Ressource",
    "Societe",
    "invented",
    "unverified",
]
