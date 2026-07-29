"""Les entités BoondManager que nous consommons.

Chaque champ est dans l'un de trois états, et la distinction est le cœur de ce
fichier :

  **attesté**      — vu dans l'intégration production d'ophelie
                     (`docs/adr/0002` de ce dépôt d'origine). Aucun marqueur.
  **unverified**   — plausible, non prouvé. Marqué, et inscrit dans
                     `docs/UNVERIFIED-FIELDS.md` — un test l'exige.
  **ajout du mock** — n'existe pas chez le fournisseur, ajouté pour un besoin
                     aval précis. Marqué, et la raison est écrite.

`extra="allow"` est hérité de `Permissif` : ces modèles décrivent ce que NOUS
consommons, jamais l'exhaustivité de ce que BoondManager expose.
"""

from __future__ import annotations

from pydantic import Field

from .common import Permissif, Relation, unverified

# ── Champs communs à toutes les entités ──────────────────────────────────────


class AttributsBase(Permissif):
    """Ce que toute entité porte, dans ce mock."""

    updateDate: str | None = Field(
        default=None,
        json_schema_extra=unverified(
            "Curseur du filtre incrémental. L'intégration production d'ophelie ne "
            "consomme AUCUN filtre sur horodatage : ni le champ ni le paramètre ne "
            "sont attestés. Le pipeline d'insights360 en a pourtant besoin."
        ),
    )
    isDeleted: bool = Field(
        default=False,
        json_schema_extra=unverified(
            "Suppression LOGIQUE. Ajout du mock : un pipeline incrémental en "
            "stratégie merge ne peut pas observer une suppression physique sans "
            "rafraîchissement complet. Reste à déterminer si BoondManager expose "
            "un tel drapeau, et sous quel nom."
        ),
    )


# ── Ressource (collaborateur) ────────────────────────────────────────────────


class RelationsRessource(Permissif):
    agency: Relation | None = None
    mainManager: Relation | None = None


class AttributsRessource(AttributsBase):
    firstName: str
    lastName: str
    email1: str | None = None
    title: str | None = None
    state: int | None = Field(default=None, description="1 = actif chez le fournisseur.")
    businessUnit: str | None = None
    averageDailyPriceExcludingTax: float | None = Field(
        default=None,
        description=(
            "Tarif de VENTE journalier. À ne pas confondre avec une rémunération : "
            "c'est le seul champ monétaire par ressource, et il ne dit rien du salaire."
        ),
    )
    dateOfHiring: str | None = None

    upn: str | None = Field(
        default=None,
        json_schema_extra=unverified(
            "AJOUT DU MOCK. Tout le modèle d'autorisation d'insights360 est keyé sur "
            "l'UPN, et `email1` n'est pas la même chose : dans une organisation "
            "réelle, e-mail de contact et UPN Entra divergent. Le mock expose les "
            "deux ; le consommateur doit choisir explicitement."
        ),
    )
    statut: str | None = Field(
        default=None,
        json_schema_extra=unverified(
            "AJOUT DU MOCK — `actif` | `sorti`. Le fournisseur expose `state` (entier). "
            "Le libellé sert aux cas limites d'insights360 (un partant ne conserve "
            "aucune visibilité) ; correspondance à confirmer."
        ),
    )
    managerUpn: str | None = Field(
        default=None,
        json_schema_extra=unverified(
            "AJOUT DU MOCK. La relation `mainManager` est attestée ; ce doublon par "
            "UPN évite au consommateur une résolution d'identifiant pour aplatir la "
            "hiérarchie. Les deux sont servis et cohérents."
        ),
    )


class Ressource(Permissif):
    id: str
    type: str = "resource"
    attributes: AttributsRessource
    relationships: RelationsRessource | None = None


# ── Agence (entité juridique) ────────────────────────────────────────────────


class AttributsAgence(AttributsBase):
    name: str
    code: str | None = Field(
        default=None,
        json_schema_extra=unverified(
            "AJOUT DU MOCK. Code court de l'entité (ENT-FR…), utilisé comme clé de "
            "périmètre. Le fournisseur expose-t-il un code stable ? À confirmer."
        ),
    )


class Agence(Permissif):
    id: str
    type: str = "agency"
    attributes: AttributsAgence


# ── Société cliente ──────────────────────────────────────────────────────────


class AttributsSociete(AttributsBase):
    name: str
    businessUnit: str | None = None


class Societe(Permissif):
    id: str
    type: str = "company"
    attributes: AttributsSociete


# ── Contact ──────────────────────────────────────────────────────────────────


class RelationsContact(Permissif):
    company: Relation | None = None


class AttributsContact(AttributsBase):
    firstName: str
    lastName: str


class Contact(Permissif):
    id: str
    type: str = "contact"
    attributes: AttributsContact
    relationships: RelationsContact | None = None


# ── Projet ───────────────────────────────────────────────────────────────────


class RelationsProjet(Permissif):
    company: Relation | None = None


class AttributsProjet(AttributsBase):
    name: str
    status: str | None = None


class Projet(Permissif):
    id: str
    type: str = "project"
    attributes: AttributsProjet
    relationships: RelationsProjet | None = None


# ── Mission (delivery) — collection NON consommée par ophelie ────────────────


class RelationsMission(Permissif):
    resource: Relation | None = None
    project: Relation | None = None


class AttributsMission(AttributsBase):
    startDate: str | None = Field(
        default=None,
        json_schema_extra=unverified(
            "Nom d'attribut non vérifié — collection non consommée par ophelie."
        ),
    )
    endDate: str | None = Field(
        default=None,
        json_schema_extra=unverified("Idem. Nul tant que la mission est en cours."),
    )
    businessUnit: str | None = None


class Mission(Permissif):
    id: str
    type: str = "delivery"
    attributes: AttributsMission
    relationships: RelationsMission | None = None


# ── Compte rendu d'activité (times-report) ───────────────────────────────────


class RelationsCra(Permissif):
    resource: Relation | None = None


class AttributsCra(AttributsBase):
    term: str | None = Field(
        default=None,
        json_schema_extra=unverified(
            "Période « AAAA-MM ». Collection non consommée par ophelie : ni le nom "
            "d'attribut ni le format ne sont vérifiés."
        ),
    )
    workedDays: float | None = Field(
        default=None,
        json_schema_extra=unverified("Idem."),
    )
    businessUnit: str | None = None


class Cra(Permissif):
    id: str
    type: str = "timesReport"
    attributes: AttributsCra
    relationships: RelationsCra | None = None


# ── Données techniques (l'onglet CV) ─────────────────────────────────────────


class AttributsDonneesTechniques(AttributsBase):
    references: list[dict] = Field(
        default_factory=list,
        description="Les expériences du CV. Seul endroit où elles vivent.",
    )


class DonneesTechniques(Permissif):
    id: str
    type: str = "technicalData"
    attributes: AttributsDonneesTechniques


# ── Identité ─────────────────────────────────────────────────────────────────


class AttributsCompte(Permissif):
    firstName: str
    lastName: str
    email: str


class Compte(Permissif):
    id: str
    type: str = "account"
    attributes: AttributsCompte
