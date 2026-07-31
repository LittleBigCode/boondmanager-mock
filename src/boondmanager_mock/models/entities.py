"""Les entités BoondManager — alignées sur la VRAIE API.

Double provenance : les schémas officiels RAML
(https://doc.boondmanager.com/api-externe/raml-build/, relevés le 2026-07-30)
CONFRONTÉS aux réponses réelles d'un tenant en 9.1.78.1 (sondes des
2026-07-30/31, avec un user token owner). Quand le RAML documente un champ que
la vraie API ne renvoie jamais (`creationSource` en recherche,
`numberbOfActiveOpportunity`…), c'est l'OBSERVÉ qui gagne — la matrice des
écarts vit dans docs/UNVERIFIED-FIELDS.md.

Les recherches et les profils sont des formes DIFFÉRENTES chez le fournisseur :
les modèles `Attributs*` décrivent les recherches ; `ProfilRessource` et
`ProfilProjet` décrivent les détails relevés en réel.

`extra="allow"` partout : ces modèles documentent ce que le mock émet, ils
n'interdisent rien — un mock strict casserait à chaque évolution du dialecte.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import Permissif, RefDonnee, Relation, unverified


class AttributsBase(Permissif):
    """The only cross-cutting field added by the mock."""

    isDeleted: bool = Field(
        default=False,
        json_schema_extra=unverified(
            "LOGICAL deletion — mock addition. An incremental pipeline running "
            "a merge strategy cannot observe a physical deletion; "
            "/__admin/delete sets this flag instead of removing the row. No "
            "equivalent vendor field is attested."
        ),
    )


class RelationListe(Permissif):
    """A to-many relationship: `{"data": [{id, type}, …]}`."""

    data: list[RefDonnee] = Field(default_factory=list)


# ── Sous-objets partagés (formes imbriquées du dialecte) ─────────────────────


class UniteOeuvre(Permissif):
    """`workUnitType` — the work-unit type of an activity row."""

    reference: int
    activityType: str = Field(
        description="production | absence | internal | exceptionalTime | exceptionalCalendar"
    )
    name: str


class ReseauSocial(Permissif):
    network: str = Field(description="facebook | viadeo | linkedin | x")
    url: str


class OutilNote(Permissif):
    tool: str
    level: int = Field(ge=1, le=5)


class LangueParlee(Permissif):
    language: str
    level: str


class SourceOuOrigine(Permissif):
    """`source` (candidates) and `origin` (opportunities): {typeOf, detail}."""

    typeOf: int
    detail: str = ""


class RaisonEtat(Permissif):
    """The opportunities' `stateReason`."""

    typeOf: int
    detail: str = ""


class ReferenceResumee(Permissif):
    """A résumé experience, summarized (resources search)."""

    id: str
    title: str
    description: str = ""


class AgenceImbriquee(Permissif):
    id: str
    name: str
    workUnitRate: float | None = None


class RessourceImbriquee(Permissif):
    id: str
    lastName: str
    firstName: str
    workUnitRate: float | None = None


class RapportAbsences(Permissif):
    """The absences report EMBEDDED in every /absences row."""

    id: str
    creationDate: str
    state: str = Field(
        description="savedAndNoValidation | waitingForValidation | validated | rejected"
    )
    agency: AgenceImbriquee
    resource: RessourceImbriquee


class TypeFrais(Permissif):
    reference: int
    taxRate: float | None = None
    name: str


class BaremeKilometrique(Permissif):
    reference: int
    name: str
    amount: float


class RapportFrais(Permissif):
    """The expenses report EMBEDDED in every /expenses row."""

    id: str
    term: str = Field(description="YYYY-MM")
    state: str
    ratePerKilometerType: BaremeKilometrique | None = None
    advance: float = 0.0
    agency: AgenceImbriquee | None = None
    resource: RessourceImbriquee | None = None


class MissionImbriquee(Permissif):
    id: str
    title: str = ""
    startDate: str = ""
    endDate: str = ""


class ProjetImbrique(Permissif):
    id: str
    reference: str = ""


class InviteFrais(Permissif):
    id: str
    lastName: str
    firstName: str
    thumbnail: str = ""


class ReferenceCvCandidat(Permissif):
    """A candidate's detailed experience — months/years as STRINGS, like the API."""

    id: str
    title: str = ""
    company: str = ""
    location: str = ""
    startMonth: str = ""
    startYear: str = ""
    endMonth: str = ""
    endYear: str = ""
    skills: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""
    row: int = 0


class NotationCritere(Permissif):
    criteria: int
    evaluation: str


class ManagerImbrique(Permissif):
    id: str
    firstName: str
    lastName: str


class EvaluationCandidat(Permissif):
    id: str
    notations: list[NotationCritere] = Field(default_factory=list)
    date: str = ""
    comments: str = ""
    manager: ManagerImbrique | None = None


class DetailFraisContrat(Permissif):
    id: str
    expenseType: dict[str, Any] = Field(default_factory=dict)
    periodicity: str = Field(default="monthly", description="daily | monthly")
    netAmount: float = 0.0


# ═════════════════════════════════════════════════════════════════════════════
#  Ressource (collaborateur)
# ═════════════════════════════════════════════════════════════════════════════


class RelationsRessource(Permissif):
    mainManager: Relation | None = None
    hrManager: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None


class AttributsRessource(AttributsBase):
    creationDate: str | None = None
    civility: int | None = None
    thumbnail: str | None = None
    firstName: str
    lastName: str
    reference: str | None = Field(default=None, description="Internal employee reference.")
    typeOf: int | None = Field(
        default=None, description="Instance dictionary (0 = employee, 1 = subcontractor…)."
    )
    state: int | None = Field(default=None, description="Instance dictionary.")
    isVisible: bool | None = None
    skills: str | None = None
    mobilityAreas: list[str] = Field(default_factory=list)
    title: str | None = None
    availability: str | None = Field(default=None, description="YYYY-MM-DD date or `immediate`.")
    forceAvailability: bool | None = None
    realAvailability: str | None = None
    averageDailyPriceExcludingTax: float | None = Field(
        default=None,
        description="Daily SELLING rate. Not a compensation figure.",
    )
    email1: str | None = None
    email2: str | None = None
    email3: str | None = None
    phone1: str | None = None
    phone2: str | None = None
    currency: int | None = None
    exchangeRate: float | None = None
    currencyAgency: int | None = None
    exchangeRateAgency: float | None = None
    numberOfResumes: int | None = None
    numberOfActivePositionings: int | None = None
    updateDate: str | None = None
    tools: list[OutilNote] = Field(default_factory=list)
    expertiseAreas: list[str] = Field(default_factory=list)
    activityAreas: list[str] = Field(default_factory=list)
    diplomas: list[str] = Field(default_factory=list)
    experience: int | None = None
    references: list[ReferenceResumee] = Field(default_factory=list)
    languages: list[LangueParlee] = Field(default_factory=list)
    canShowTechnicalData: bool | None = None
    canShowActions: bool | None = None
    socialNetworks: list[ReseauSocial] = Field(default_factory=list)


class Ressource(Permissif):
    id: str
    type: str = "resource"
    attributes: AttributsRessource
    relationships: RelationsRessource | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  Candidat
# ═════════════════════════════════════════════════════════════════════════════


class RelationsCandidat(Permissif):
    mainManager: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None


class AttributsCandidat(AttributsBase):
    creationDate: str | None = None
    updateDate: str | None = None
    civility: int | None = None
    thumbnail: str | None = None
    firstName: str
    lastName: str
    typeOf: int | None = None
    state: int | None = Field(default=None, description="Instance dictionary.")
    isVisible: bool | None = None
    skills: str | None = None
    mobilityAreas: list[str] = Field(default_factory=list)
    title: str | None = None
    availability: str | None = None
    email1: str | None = None
    email2: str | None = None
    email3: str | None = None
    phone1: str | None = None
    phone2: str | None = None
    town: str | None = None
    country: str | None = None
    source: SourceOuOrigine | None = None
    numberOfResumes: int | None = None
    numberOfActivePositionings: int | None = None
    socialNetworks: list[ReseauSocial] = Field(default_factory=list)
    diplomas: list[str] = Field(default_factory=list)
    activityAreas: list[str] = Field(default_factory=list)
    globalEvaluation: str | None = None
    languages: list[LangueParlee] = Field(default_factory=list)
    expertiseAreas: list[str] = Field(default_factory=list)
    experience: int | None = None
    references: list[ReferenceCvCandidat] = Field(default_factory=list)
    evaluations: list[EvaluationCandidat] = Field(default_factory=list)
    tools: list[OutilNote] = Field(default_factory=list)
    canShowTechnicalData: bool | None = None
    canShowActions: bool | None = None


class Candidat(Permissif):
    id: str
    type: str = "candidate"
    attributes: AttributsCandidat
    relationships: RelationsCandidat | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  Agence, business unit, pôle, rôle
# ═════════════════════════════════════════════════════════════════════════════


class AttributsAgence(AttributsBase):
    name: str
    calendar: str | None = None
    currency: int | None = None
    numberOfWorkingDays: float | None = None
    chargeFactor: float | None = None
    vatNumber: str | None = None
    registrationNumber: str | None = None
    address: str | None = None
    postcode: str | None = None
    town: str | None = None
    country: str | None = None
    staff: int | None = None
    state: bool | None = None
    workUnitRate: float | None = None
    workUnitRateOnProjectsAndOpportunities: float | None = None
    subDivision: str | None = None


class Agence(Permissif):
    id: str
    type: str = "agency"
    attributes: AttributsAgence


class RelationsUniteOperationnelle(Permissif):
    includedManagers: RelationListe | None = None


class AttributsUniteOperationnelle(AttributsBase):
    name: str


class UniteOperationnelle(Permissif):
    id: str
    type: str = "businessunit"
    attributes: AttributsUniteOperationnelle
    relationships: RelationsUniteOperationnelle | None = None


class AttributsPole(AttributsBase):
    name: str
    state: bool | None = None


class Pole(Permissif):
    id: str
    type: str = "pole"
    attributes: AttributsPole


class AttributsRole(AttributsBase):
    name: str
    numberOfAccounts: float | None = None
    numberOfActiveAccounts: float | None = None
    isSecondaryAgenciesAllowed: bool | None = None
    isSecondaryPolesAllowed: bool | None = None
    typeOf: str | None = Field(default=None, description="manager | intranet")
    isSystem: bool | None = None


class Role(Permissif):
    id: str
    type: str = "role"
    attributes: AttributsRole


# ═════════════════════════════════════════════════════════════════════════════
#  CRM : société, contact, opportunité, action
# ═════════════════════════════════════════════════════════════════════════════


class RelationsSociete(Permissif):
    mainManager: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None


class AttributsSociete(AttributsBase):
    name: str
    expertiseArea: str | None = None
    state: int | None = None
    informationComments: str | None = None
    thumbnail: str | None = None
    website: str | None = None
    phone1: str | None = None
    town: str | None = None
    country: str | None = None
    creationDate: str | None = None
    updateDate: str | None = None
    socialNetworks: list[ReseauSocial] = Field(default_factory=list)


class Societe(Permissif):
    id: str
    type: str = "company"
    attributes: AttributsSociete
    relationships: RelationsSociete | None = None


class RelationsContact(Permissif):
    mainManager: Relation | None = None
    company: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None


class AttributsContact(AttributsBase):
    creationDate: str | None = None
    civility: int | None = None
    thumbnail: str | None = None
    firstName: str
    lastName: str
    state: int | None = None
    function: str | None = None
    department: str | None = None
    email1: str | None = None
    email2: str | None = None
    email3: str | None = None
    phone1: str | None = None
    phone2: str | None = None
    town: str | None = None
    country: str | None = None
    canReadContact: bool | None = None
    canWriteContact: bool | None = None
    canShowAction: bool | None = None
    typesOf: list[str] = Field(default_factory=list)
    socialNetworks: list[ReseauSocial] = Field(default_factory=list)
    updateDate: str | None = None


class Contact(Permissif):
    id: str
    type: str = "contact"
    attributes: AttributsContact
    relationships: RelationsContact | None = None


class RelationsOpportunite(Permissif):
    mainManager: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None
    contact: Relation | None = None
    company: Relation | None = None
    parsingJob: Relation | None = None


class AttributsOpportunite(AttributsBase):
    creationDate: str | None = None
    title: str
    reference: str | None = None
    typeOf: int | None = None
    mode: int | None = Field(default=None, description="1 | 2 | 3 | 4 (instance dictionary).")
    state: int | None = None
    place: str | None = None
    isVisible: bool | None = None
    startDate: str | None = None
    endDate: str | None = None
    closingDate: str | None = None
    answerDate: str | None = None
    duration: int | None = None
    currency: int | None = None
    exchangeRate: float | None = None
    currencyAgency: int | None = None
    exchangeRateAgency: float | None = None
    turnoverWeightedExcludingTax: float | None = None
    estimatesExcludingTax: float | None = None
    turnoverEstimatedExcludingTax: float | None = None
    expertiseArea: str | None = None
    activityAreas: list[str] = Field(default_factory=list)
    origin: SourceOuOrigine | None = None
    tools: list[str] = Field(default_factory=list)
    numberOfActivePositionings: int | None = None
    canShowContact: bool | None = None
    canShowCompany: bool | None = None
    stateReason: RaisonEtat | None = None
    updateDate: str | None = None


class Opportunite(Permissif):
    id: str
    type: str = "opportunity"
    attributes: AttributsOpportunite
    relationships: RelationsOpportunite | None = None


class RelationsAction(Permissif):
    mainManager: Relation | None = None
    dependsOn: Relation | None = Field(
        default=None,
        description="The carrying entity: candidate, company, contact, opportunity, "
        "project, resource, invoice…",
    )
    company: Relation | None = None
    relatedActions: RelationListe | None = None


class AttributsAction(AttributsBase):
    startDate: str | None = None
    creationDate: str | None = None
    typeOf: int | None = Field(default=None, description="Per-entity instance dictionary.")
    text: str | None = None
    numberOfFiles: int | None = None
    canReadAction: bool | None = None
    canWriteAction: bool | None = None
    updateDate: str | None = None


class ActionCrm(Permissif):
    id: str
    type: str = "action"
    attributes: AttributsAction
    relationships: RelationsAction | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  Production : projet, mission (delivery)
# ═════════════════════════════════════════════════════════════════════════════


class RelationsProjet(Permissif):
    mainManager: Relation | None = None
    opportunity: Relation | None = None
    contact: Relation | None = None
    company: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None
    intermediaryCompany: Relation | None = None
    intermediaryContact: Relation | None = None


class AttributsProjet(AttributsBase):
    startDate: str | None = None
    endDate: str | None = None
    typeOf: int | None = None
    mode: int | None = None
    reference: str | None = None
    currency: int | None = None
    exchangeRate: float | None = None
    currencyAgency: int | None = None
    exchangeRateAgency: float | None = None
    turnoverSimulatedExcludingTax: float | None = None
    marginSimulatedExcludingTax: float | None = None
    profitabilitySimulated: float | None = None
    canReadProject: bool | None = None
    canShowContact: bool | None = None
    canShowCompany: bool | None = None
    canShowIntermediaryContact: bool | None = None
    canShowIntermediaryCompany: bool | None = None
    canShowCurrency: bool | None = None
    canShowCurrencyAgency: bool | None = None
    canShowExchangeRate: bool | None = None
    canShowExchangeRateAgency: bool | None = None
    canShowProfitabilitySimulated: bool | None = None
    canShowTurnoverSimulatedExcludingTax: bool | None = None
    canShowMarginSimulatedExcludingTax: bool | None = None
    creationDate: str | None = None
    updateDate: str | None = None


class Projet(Permissif):
    id: str
    type: str = "project"
    attributes: AttributsProjet
    relationships: RelationsProjet | None = None


class RelationsMission(Permissif):
    project: Relation | None = None
    dependsOn: Relation | None = Field(
        default=None, description="The resource (or product) staffed on the delivery."
    )
    purchase: Relation | None = None


class AttributsMission(AttributsBase):
    """GET /deliveries search does not exist (405 observed): these attributes
    follow the official delivery PROFILE schema, served on /deliveries/{id}."""

    startDate: str | None = None
    endDate: str | None = None
    title: str | None = None
    typeOf: int | None = None
    state: int | None = None
    canShowAverageDailyContractCost: bool | None = None
    averageDailyPriceExcludingTax: float | None = None
    forceAverageDailyPriceExcludingTax: bool | None = None
    subscriptionQuantityCharged: float | None = None
    subscriptionQuantityFree: float | None = None
    subscriptionPriceExcludingTax: float | None = None
    averageDailyCost: float | None = None
    averageDailyContractCost: float | None = None
    numberOfDaysInvoicedOrQuantity: float | None = None
    numberOfDaysFree: float | None = None
    informationComments: str | None = None
    conditions: str | None = None
    turnoverSimulatedExcludingTax: float | None = None
    costsSimulatedExcludingTax: float | None = None
    marginSimulatedExcludingTax: float | None = None
    profitabilitySimulated: float | None = None
    occupationRate: float | None = None
    dailyExpenses: float | None = None
    monthlyExpenses: float | None = None
    numberOfWorkingDays: float | None = None
    weeklyWorkingHours: float | None = None
    averageHourlyPriceExcludingTax: float | None = None
    forceAverageHourlyPriceExcludingTax: bool | None = None
    additionalTurnoverAndCosts: list[dict[str, Any]] = Field(default_factory=list)
    expensesDetails: list[dict[str, Any]] = Field(default_factory=list)
    advantageTypes: list[dict[str, Any]] = Field(default_factory=list)
    exceptionalScales: list[dict[str, Any]] = Field(default_factory=list)
    creationDate: str | None = None
    updateDate: str | None = None
    calendar: str | None = None
    isTurnoverProductionIncluded: bool | None = None


class Mission(Permissif):
    id: str
    type: str = "delivery"
    attributes: AttributsMission
    relationships: RelationsMission | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  Facturation : commande, facture, achat, paiement, banque
# ═════════════════════════════════════════════════════════════════════════════


class RelationsCommande(Permissif):
    mainManager: Relation | None = None
    project: Relation | None = None


class AttributsCommande(AttributsBase):
    date: str | None = None
    number: str | None = None
    reference: str | None = None
    customerAgreement: bool | None = None
    turnoverInvoicedExcludingTax: float | None = None
    turnoverOrderedExcludingTax: float | None = None
    deltaInvoicedExcludingTax: float | None = None
    state: int | None = None
    creationDate: str | None = None
    updateDate: str | None = None


class Commande(Permissif):
    id: str
    type: str = "order"
    attributes: AttributsCommande
    relationships: RelationsCommande | None = None


class RelationsFacture(Permissif):
    order: Relation | None = None
    schedule: Relation | None = None


class AttributsFacture(AttributsBase):
    date: str | None = None
    expectedPaymentDate: str | None = None
    turnoverInvoicedExcludingTax: float | None = None
    turnoverInvoicedIncludingTax: float | None = None
    isCreditNote: bool | None = None
    reference: str | None = None
    state: int | None = None
    selfBilling: bool | None = None
    sendingState: int | None = None
    refuseReason: str | None = None
    providerId: str | None = None
    providerUrl: str | None = None
    taxReportState: int | None = None
    currency: int | None = None
    exchangeRate: float | None = None
    currencyAgency: int | None = None
    exchangeRateAgency: float | None = None
    paymentMethod: int | None = None
    closed: bool | None = None
    totalPayableIncludingTax: float | None = None
    creationDate: str | None = None
    updateDate: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    performedPaymentDate: str | None = None
    canSendWithPeppol: bool | None = None
    canSendWithDgfip: bool | None = None
    canSendWithPennylane: bool | None = None


class Facture(Permissif):
    id: str
    type: str = "invoice"
    attributes: AttributsFacture
    relationships: RelationsFacture | None = None


class RelationsAchat(Permissif):
    mainManager: Relation | None = None
    project: Relation | None = None
    delivery: Relation | None = None
    contact: Relation | None = None
    company: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None


class AttributsAchat(AttributsBase):
    date: str | None = None
    title: str | None = None
    subscription: int | None = None
    typeOf: int | None = None
    reference: str | None = None
    state: int | None = None
    taxRate: float | None = None
    currency: int | None = None
    exchangeRate: float | None = None
    currencyAgency: int | None = None
    exchangeRateAgency: float | None = None
    amountExcludingTax: float | None = None
    quantity: float | None = None
    totalAmountExcludingTax: float | None = None
    deltaExcludingTax: float | None = None
    engagedPaymentsAmountExcludingTax: float | None = None
    creationDate: str | None = None
    updateDate: str | None = None


class Achat(Permissif):
    id: str
    type: str = "purchase"
    attributes: AttributsAchat
    relationships: RelationsAchat | None = None


class RelationsPaiement(Permissif):
    purchase: Relation | None = None


class AttributsPaiement(AttributsBase):
    date: str | None = None
    performedDate: str | None = None
    expectedDate: str | None = None
    state: int | None = None
    number: str | None = None
    amountExcludingTax: float | None = None
    amountIncludingTax: float | None = None
    numberOfFiles: float | None = None
    canWritePayment: bool | None = None
    creationDate: str | None = None
    updateDate: str | None = None


class Paiement(Permissif):
    id: str
    type: str = "payment"
    attributes: AttributsPaiement
    relationships: RelationsPaiement | None = None


class RelationsTransactionBancaire(Permissif):
    account: Relation | None = None


class AttributsTransactionBancaire(AttributsBase):
    amount: float | None = None
    currency: int | None = None
    date: str | None = None
    numberOfInvoices: int | None = None
    title: str | None = None
    state: int | None = Field(default=None, description="0 | 1 | 2 | 3 (rapprochement).")
    totalAmountToReconcile: float | None = None
    canReadTransaction: bool | None = None
    canWriteTransaction: bool | None = None
    canReconcile: bool | None = None


class TransactionBancaire(Permissif):
    id: str
    type: str = "bankingtransaction"
    attributes: AttributsTransactionBancaire
    relationships: RelationsTransactionBancaire | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  RH : contrat
# ═════════════════════════════════════════════════════════════════════════════


class RelationsContrat(Permissif):
    dependsOn: Relation | None = Field(
        default=None, description="The resource (or candidate) holding the contract."
    )
    createdBy: Relation | None = None
    agency: Relation | None = None
    parentContract: Relation | None = None
    childContract: Relation | None = None
    files: RelationListe | None = None


class AttributsContrat(AttributsBase):
    """GET /contracts search does not exist (405/WAF observed): these
    attributes follow the contract PROFILE shape as observed on
    /contracts/{id} (30 attributes)."""

    typeOf: int | None = None
    creationDate: str | None = None
    updateDate: str | None = None
    employeeType: int | None = None
    workingTimeType: int | None = None
    numberOfHoursPerWeek: float | None = None
    classification: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    endReason: int | None = None
    probationState: int | None = None
    monthlySalary: float | None = None
    hourlySalary: float | None = None
    forceHourlySalary: bool | None = None
    contractAverageDailyCost: float | None = None
    dailyExpenses: float | None = None
    monthlyExpenses: float | None = None
    numberOfWorkingDays: float | None = None
    chargeFactor: float | None = None
    expensesDetails: list[DetailFraisContrat] = Field(default_factory=list)
    advantageTypes: list[dict[str, Any]] = Field(default_factory=list)
    informationComments: str | None = None
    currency: int | None = None
    currencyAgency: int | None = None
    exchangeRate: float | None = None
    exchangeRateAgency: float | None = None
    calendar: str | None = None
    activityRate: float | None = None
    partialWorkTimes: list[str] = Field(default_factory=list)
    isPartialWorkTimeEvenOdd: bool | None = None


class Contrat(Permissif):
    id: str
    type: str = "contract"
    attributes: AttributsContrat
    relationships: RelationsContrat | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  Activité : absence, temps, CRA, frais
# ═════════════════════════════════════════════════════════════════════════════


class AttributsAbsence(AttributsBase):
    """An absence's whole context is EMBEDDED here — no relationships;
    that is the real /absences dialect."""

    startDate: str | None = None
    endDate: str | None = None
    duration: float | None = None
    title: str | None = None
    workUnitType: UniteOeuvre | None = None
    absencesReport: RapportAbsences | None = None


class Absence(Permissif):
    id: str
    type: str = "absence"
    attributes: AttributsAbsence


class RelationsTemps(Permissif):
    timesReport: Relation | None = None
    delivery: Relation | None = None
    batch: Relation | None = None
    project: Relation | None = None


class AttributsTemps(AttributsBase):
    category: str | None = Field(default=None, description="regular | exceptional")
    workUnitType: UniteOeuvre | None = None
    row: int | None = None
    startDate: str | None = None
    duration: float | None = None


class Temps(Permissif):
    id: str
    type: str = "time"
    attributes: AttributsTemps
    relationships: RelationsTemps | None = None


class RelationsCra(Permissif):
    agency: Relation | None = None
    resource: Relation | None = None


class AttributsCra(AttributsBase):
    term: str | None = Field(default=None, description="YYYY-MM")
    state: str | None = Field(
        default=None,
        description="savedAndNoValidation | waitingForValidation | validated | rejected",
    )
    closed: bool | None = None


class Cra(Permissif):
    id: str
    type: str = "timesreport"
    attributes: AttributsCra
    relationships: RelationsCra | None = None


class AttributsFrais(AttributsBase):
    """Like /absences: report, delivery and project EMBEDDED in attributes."""

    category: str | None = Field(default=None, description="actual | fixed")
    activityType: str | None = None
    expenseType: TypeFrais | None = None
    row: int | None = None
    startDate: str | None = None
    reinvoiced: bool | None = None
    amountIncludingTax: float | None = None
    tax: float | None = None
    numberOfKilometers: float | None = None
    number: int | None = None
    title: str | None = None
    currency: int | None = None
    exchangeRate: float | None = None
    isKilometricExpense: bool | None = None
    expensesReport: RapportFrais | None = None
    delivery: MissionImbriquee | None = None
    batch: dict[str, Any] | None = None
    project: ProjetImbrique | None = None
    guestResources: list[InviteFrais] = Field(default_factory=list)


class Frais(Permissif):
    id: str
    type: str = "expense"
    attributes: AttributsFrais


# ═════════════════════════════════════════════════════════════════════════════
#  Onglet administratif d'une ressource — là où vivent les contrats
# ═════════════════════════════════════════════════════════════════════════════


class RelationsAdministratif(Permissif):
    agency: Relation | None = None
    candidate: Relation | None = None
    contracts: RelationListe | None = Field(
        default=None,
        description="The resource's CONTRACTS — the official path to fetch them.",
    )
    providerContact: Relation | None = None
    providerCompany: Relation | None = Field(
        default=None, description="The supplying company, for a subcontractor."
    )
    files: RelationListe | None = None


class AttributsAdministratif(Permissif):
    """`GET /resources/{id}/administrative` — official schema
    `resources/administrative.json` (JSON:API type `resource`)."""

    reference: str | None = None
    dateOfBirth: str | None = None
    placeOfBirth: str | None = None
    nationality: str | None = None
    healthCareNumber: str | None = None
    address: str | None = None
    postcode: str | None = None
    town: str | None = None
    country: str | None = None
    subDivision: str | None = None
    situation: int | None = Field(default=None, description="Instance dictionary.")
    administrativeComments: str | None = None
    function: str | None = None
    seniorityDate: str | None = None
    originalSeniorityDate: str | None = None
    forceSeniorityDate: bool | None = None
    validitySeniorityDate: str | None = None


class AdministratifRessource(Permissif):
    id: str
    type: str = "resource"
    attributes: AttributsAdministratif
    relationships: RelationsAdministratif | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  Affordances conservées : dossier technique, identité
# ═════════════════════════════════════════════════════════════════════════════


class AttributsDonneesTechniques(Permissif):
    """`GET /resources/{id}/technical-data` — REAL shape observed: type
    `resource`, fifteen attributes, no relationships nor included."""

    activityAreas: list[str] = Field(default_factory=list)
    description: str | None = None
    diplomas: list[str] = Field(default_factory=list)
    experience: int | None = None
    expertiseAreas: list[str] = Field(default_factory=list)
    languages: list[LangueParlee] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(
        default_factory=list,
        description="The résumé experiences. The only place they live in detail.",
    )
    resourceCanModifyTechnicalData: bool | None = None
    skills: str | None = None
    summary: str | None = None
    tdId: str | None = None
    tdLink: str | None = None
    title: str | None = None
    tools: list[OutilNote] = Field(default_factory=list)
    training: list[dict[str, Any]] = Field(default_factory=list)


class DonneesTechniques(Permissif):
    id: str
    type: str = "resource"
    attributes: AttributsDonneesTechniques


class AttributsUtilisateurCourant(Permissif):
    """`GET /application/current-user` — real type `currentuser` (observed),
    the attribute subset consumers rely on."""

    firstName: str
    lastName: str
    login: str
    email1: str | None = None
    level: str | None = Field(default=None, description="manager | resource | administrator")
    isOwner: bool | None = None
    narrowPerimeter: bool | None = None
    language: str | None = None


class RelationsUtilisateurCourant(Permissif):
    agency: Relation | None = None
    role: Relation | None = None


class UtilisateurCourant(Permissif):
    id: str
    type: str = "currentuser"
    attributes: AttributsUtilisateurCourant
    relationships: RelationsUtilisateurCourant | None = None


# ═════════════════════════════════════════════════════════════════════════════
#  Profils — les formes de DÉTAIL relevées en réel (≠ recherches)
# ═════════════════════════════════════════════════════════════════════════════


class AttributsProfilRessource(Permissif):
    """Real `GET /resources/{id}`: eighteen attributes, distinct from search."""

    creationDate: str | None = None
    updateDate: str | None = None
    civility: int | None = None
    thumbnail: str | None = None
    firstName: str
    lastName: str
    typeOf: int | None = None
    level: str | None = Field(default=None, description="manager | resource | administrator")
    title: str | None = None
    dateOfBirth: str | None = None
    numberOfResumes: int | None = None
    seniorityDate: str | None = None
    forceSeniorityDate: bool | None = None
    originalSeniorityDate: str | None = None
    validitySeniorityDate: str | None = None
    tdLink: str | None = None
    tdId: str | None = None
    creationSource: str | None = None


class RelationsProfilRessource(Permissif):
    mainManager: Relation | None = None
    hrManager: Relation | None = None
    agency: Relation | None = None
    pole: Relation | None = None
    contracts: RelationListe | None = Field(
        default=None,
        description="LES CONTRATS de la ressource — le chemin officiel, validé en prod.",
    )


class ProfilRessource(Permissif):
    id: str
    type: str = "resource"
    attributes: AttributsProfilRessource
    relationships: RelationsProfilRessource | None = None


class AttributsProfilProjet(Permissif):
    """Real `GET /projects/{id}`: thirteen attributes — without `endDate`."""

    creationDate: str | None = None
    currency: int | None = None
    currencyAgency: int | None = None
    deliverySuggestFilters: list[dict[str, Any]] = Field(default_factory=list)
    exchangeRate: float | None = None
    exchangeRateAgency: float | None = None
    isProjectManager: bool | None = None
    mode: int | None = None
    reference: str | None = None
    startDate: str | None = None
    typeOf: int | None = None
    updateDate: str | None = None
    workUnitRate: float | None = None


class RelationsProfilProjet(Permissif):
    agency: Relation | None = None
    company: Relation | None = None
    mainManager: Relation | None = None
    opportunity: Relation | None = None
    pole: Relation | None = None


class ProfilProjet(Permissif):
    id: str
    type: str = "project"
    attributes: AttributsProfilProjet
    relationships: RelationsProfilProjet | None = None
