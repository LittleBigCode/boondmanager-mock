"""Le jeu de données : « Boréal Conseil », ESN française de 34 personnes.

UN SEUL jeu de données, complet et cohérent — les anciens profils `ophelie` et
`insights360` sont supprimés. Chaque collection suit la forme de réponse de la
documentation OFFICIELLE BoondManager (RAML + schémas JSON de
https://doc.boondmanager.com/api-externe/, relevés le 2026-07-30) :

  • les `type` JSON:API sont ceux du fournisseur, en minuscules
    (`timesreport`, `bankingtransaction`, `businessunit`…) ;
  • les noms d'attributs viennent des schémas `search.json` de chaque module —
    y compris la coquille officielle `numberbOfActiveOpportunity` des sociétés ;
  • les horodatages suivent le format du fournisseur
    (`2026-03-12T09:24:00+0100`, décalage SANS deux-points) ;
  • `/absences`, `/expenses` et `/times` portent leur contexte IMBRIQUÉ dans
    `attributes` (rapport, agence, ressource) — c'est le dialecte réel, pas une
    relation JSON:API.

La COHÉRENCE est la propriété centrale, parce que c'est elle qui rend le mock
comparable à une vraie instance :

  ressources ← contrats ; clients ← contacts ; opportunités gagnées → projets
  → missions (deliveries) → commandes → factures mensuelles (jours travaillés x
  TJM de la mission) → transactions bancaires des règlements ; achats →
  paiements fournisseurs ; CRA ← lignes de temps des mêmes jours travaillés que
  les factures ; absences et frais rattachés à leurs rapports.

Ce qui reste VOLONTAIREMENT approximatif, et documenté dans
docs/UNVERIFIED-FIELDS.md : la sémantique des entiers de dictionnaire
(`typeOf`, `state`…), propre à chaque instance BoondManager — les valeurs
choisies ici sont plausibles, pas attestées.

Déterminisme : `random.Random(seed)` et une ancre temporelle FIXE (15 juillet
2026). Jamais `datetime.now()` — deux exécutions produisent le même jeu de
données à l'octet près, c'est ce qui rend les tests aval reproductibles.
"""

from __future__ import annotations

import calendar
import random
from datetime import date, timedelta
from typing import Any

# ── Ancre temporelle ─────────────────────────────────────────────────────────

AUJOURDHUI = date(2026, 7, 15)
#: Mois couverts par les CRA, lignes de temps, frais et absences détaillés.
MOIS_ACTIVITE: tuple[tuple[int, int], ...] = ((2026, 5), (2026, 6), (2026, 7))
#: Premier mois facturé de l'exercice courant.
DEBUT_FACTURATION = date(2026, 1, 1)
#: Plafond de tous les `updateDate` — un curseur incrémental postérieur doit
#: rendre zéro ligne (cf. tests d'incrémentalité).
DERNIERE_MAJ = date(2026, 7, 12)

TVA = 0.20


def _tz(mois: int) -> str:
    """Décalage Europe/Paris, SANS deux-points — le format du fournisseur."""
    return "+0200" if 4 <= mois <= 10 else "+0100"


def _dt(d: date, h: int = 9, mn: int = 0, s: int = 0) -> str:
    return f"{d:%Y-%m-%d}T{h:02d}:{mn:02d}:{s:02d}{_tz(d.month)}"


def _d(d: date) -> str:
    return f"{d:%Y-%m-%d}"


def _fin_mois(annee: int, mois: int) -> date:
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def _jours_ouvres(annee: int, mois: int) -> int:
    """Jours ouvrés du mois (hors week-ends ; les fériés sont ignorés — mock)."""
    dernier = calendar.monthrange(annee, mois)[1]
    return sum(1 for j in range(1, dernier + 1) if date(annee, mois, j).weekday() < 5)


def _maj(rng: random.Random, apres: date) -> str:
    """Un `updateDate` plausible : postérieur à la création, jamais après l'ancre."""
    if apres >= DERNIERE_MAJ:
        return _dt(DERNIERE_MAJ, 8, 30)
    delta = (DERNIERE_MAJ - apres).days
    jour = apres + timedelta(days=rng.randint(0, delta))
    return _dt(jour, rng.randint(8, 18), rng.randint(0, 59), rng.randint(0, 59))


def _rel(type_: str, ident: Any) -> dict[str, Any]:
    """Une relation JSON:API. `ident` à None rend `{"data": null}` — le dialecte réel."""
    if ident is None:
        return {"data": None}
    return {"data": {"id": str(ident), "type": type_}}


# ── Catalogues ───────────────────────────────────────────────────────────────

_PRENOMS = [
    "Camille",
    "Jules",
    "Sofia",
    "Hugo",
    "Amara",
    "Louis",
    "Priya",
    "Arthur",
    "Emma",
    "Mateo",
    "Lina",
    "Gabriel",
    "Aïcha",
    "Rafael",
    "Yuki",
    "Nathan",
    "Olivia",
    "Diego",
    "Nina",
    "Youssef",
    "Ana",
    "Lars",
    "Wei",
    "Adam",
    "Chloé",
    "Théo",
    "Inès",
    "Maxime",
    "Sarah",
    "Paul",
    "Alice",
    "Antoine",
    "Clara",
    "Romain",
    "Léa",
    "Bastien",
    "Manon",
    "Kevin",
    "Julie",
    "Thomas",
]
_NOMS = [
    "Martin",
    "Silva",
    "Nakamura",
    "Okafor",
    "Rossi",
    "Muller",
    "Santos",
    "Dubois",
    "Moreau",
    "Laurent",
    "Kim",
    "Ivanov",
    "Fernandez",
    "Andersson",
    "Nguyen",
    "Costa",
    "Bertrand",
    "Haddad",
    "Meyer",
    "Garcia",
    "Patel",
    "Schmidt",
    "Lambert",
    "Oliveira",
    "Roux",
    "Fontaine",
    "Girard",
    "Blanc",
    "Perrin",
    "Chevalier",
    "Lemoine",
    "Renard",
    "Colin",
    "Marchand",
    "Dupuis",
    "Gauthier",
    "Meunier",
    "Brunet",
    "Faure",
    "Bourgeois",
]
_TITRES_CONSULTANT = [
    "Data Engineer",
    "Data Engineer senior",
    "Data Scientist",
    "ML Engineer",
    "Architecte cloud",
    "Consultant DevOps",
    "Développeur full-stack",
    "Tech Lead",
    "Consultant cybersécurité",
    "Product Owner",
    "Consultant data gouvernance",
    "Ingénieur plateforme",
]
_COMPETENCES = [
    "Python",
    "Spark",
    "dbt",
    "Snowflake",
    "Kafka",
    "Airflow",
    "Terraform",
    "Kubernetes",
    "AWS",
    "Azure",
    "GCP",
    "React",
    "FastAPI",
    "Power BI",
    "SQL",
    "Databricks",
]
_EXPERTISES = [
    "Data Engineering",
    "Data Science",
    "Cloud & Infrastructure",
    "Cybersécurité",
    "Product & Agilité",
    "Gouvernance des données",
]
_SECTEURS = [
    "Banque & Assurance",
    "Retail & Distribution",
    "Énergie & Utilities",
    "Industrie",
    "Télécoms & Médias",
    "Transport & Logistique",
    "Secteur public",
    "Santé & Pharma",
]
_DIPLOMES = [
    "Diplôme d'ingénieur — CentraleSupélec (2017)",
    "Master Informatique — Université de Nantes (2019)",
    "Master Data Science — Université Paris-Saclay (2020)",
    "Diplôme d'ingénieur — INSA Lyon (2016)",
    "Master MIAGE — Université Lyon 1 (2018)",
    "MSc Computer Science — EPFL (2015)",
]
_LANGUES = [
    ("FR", "Langue maternelle"),
    ("EN", "Courant"),
    ("ES", "Intermédiaire"),
    ("DE", "Notions"),
]

#: (nom, ville, code postal, adresse, SIREN+NIC, TVA, effectif)
_AGENCES = [
    (
        "Boréal Conseil Paris",
        "Paris",
        "75009",
        "24 rue de Châteaudun",
        "482 154 796 00031",
        "FR 62 482154796",
        21,
    ),
    (
        "Boréal Conseil Lyon",
        "Lyon",
        "69002",
        "18 quai Saint-Antoine",
        "482 154 796 00049",
        "FR 62 482154796",
        8,
    ),
    (
        "Boréal Conseil Nantes",
        "Nantes",
        "44000",
        "5 allée Duguay-Trouin",
        "482 154 796 00056",
        "FR 62 482154796",
        5,
    ),
]
_BUSINESS_UNITS = ["Data & IA", "Cloud & Plateformes", "Cybersécurité", "Transformation digitale"]
_POLES = [
    "Pôle Data Engineering",
    "Pôle Data Science & IA",
    "Pôle Cloud & SRE",
    "Pôle Sécurité opérationnelle",
    "Pôle Produit & Design",
    "Pôle Pilotage & PMO",
]

#: (nom, ville, secteur, site, prospect) — 10 clients puis 3 fournisseurs.
_CLIENTS = [
    ("Lumina Retail", "Paris", "Retail & Distribution", "https://lumina-retail.example", False),
    ("Banque Hexagone", "Paris", "Banque & Assurance", "https://banque-hexagone.example", False),
    ("Voltalis Énergie", "Lyon", "Énergie & Utilities", "https://voltalis-energie.example", False),
    ("Mutuelle Armor", "Nantes", "Banque & Assurance", "https://mutuelle-armor.example", False),
    (
        "TransEuropa Fret",
        "Lille",
        "Transport & Logistique",
        "https://transeuropa-fret.example",
        False,
    ),
    ("Pharmadis", "Lyon", "Santé & Pharma", "https://pharmadis.example", False),
    ("Citymob", "Bordeaux", "Transport & Logistique", "https://citymob.example", False),
    ("Assurial", "Bruxelles", "Banque & Assurance", "https://assurial.example", False),
    ("Groupe Ardentes", "Nantes", "Industrie", "https://groupe-ardentes.example", False),
    ("MediaQuartz", "Paris", "Télécoms & Médias", "https://mediaquartz.example", True),
    (
        "Fivetech Partners",
        "Paris",
        "Conseil & Services numériques",
        "https://fivetech-partners.example",
        False,
    ),
    ("Softalliance", "Paris", "Éditeur de logiciels", "https://softalliance.example", False),
    ("Foncière Beaumont", "Paris", "Immobilier", "https://fonciere-beaumont.example", False),
]
_ID_FOURNISSEUR_SOUSTRAITANCE = 11  # Fivetech Partners
_ID_FOURNISSEUR_LICENCES = 12  # Softalliance
_ID_FOURNISSEUR_LOYER = 13  # Foncière Beaumont

_FONCTIONS_CONTACT = [
    "DSI",
    "CTO",
    "Directeur Data",
    "Head of Data",
    "Responsable BI",
    "Directrice de la transformation",
    "Responsable achats IT",
    "CISO",
    "CFO",
    "Chef de projet MOA",
]
_SERVICES_CONTACT = [
    "Direction des systèmes d'information",
    "Direction Data",
    "Direction financière",
    "Direction digitale",
    "Achats",
    "Direction générale",
]

#: (titre-type de mission, outils dominants)
_SUJETS = [
    ("Refonte de la plateforme data", ["Snowflake", "dbt", "Airflow"]),
    ("Migration cloud des applications métier", ["AWS", "Terraform", "Kubernetes"]),
    ("Mise en place du socle MLOps", ["Databricks", "Python", "Kubernetes"]),
    ("Tableau de bord de pilotage finance", ["Power BI", "SQL", "dbt"]),
    ("Industrialisation des pipelines de données", ["Spark", "Kafka", "Airflow"]),
    ("Audit sécurité et remédiation", ["Kubernetes", "Terraform", "AWS"]),
    ("Data mesh — pilote domaine client", ["Snowflake", "dbt", "Kafka"]),
    ("Modernisation du SI e-commerce", ["React", "FastAPI", "GCP"]),
]

_TYPES_ABSENCE = [
    (20, "Congés payés"),
    (21, "RTT"),
    (22, "Maladie"),
    (23, "Congé exceptionnel"),
]
_TYPES_FRAIS = [
    (1, "Restauration", 10.0),
    (2, "Transport", 10.0),
    (3, "Hébergement", 10.0),
    (4, "Péage & carburant", 20.0),
]

# Sémantique de dictionnaire PLAUSIBLE (propre à l'instance — non attestée) :
ETAT_RESSOURCE_SORTIE = 0
ETAT_RESSOURCE_ACTIVE = 1
ETAT_RESSOURCE_INTEGRATION = 2


# ═════════════════════════════════════════════════════════════════════════════
#  Référentiels : agences, BU, pôles, rôles
# ═════════════════════════════════════════════════════════════════════════════


def _agences() -> list[dict[str, Any]]:
    agences: list[dict[str, Any]] = []
    for i, (nom, ville, cp, adresse, immat, tva, effectif) in enumerate(_AGENCES, start=1):
        agences.append(
            {
                "id": str(i),
                "type": "agency",
                "attributes": {
                    "name": nom,
                    "calendar": "Standard",
                    "currency": 0,
                    "numberOfWorkingDays": 218,
                    "chargeFactor": 1.47,
                    "vatNumber": tva,
                    "registrationNumber": immat,
                    "address": adresse,
                    "postcode": cp,
                    "town": ville,
                    "country": "France",
                    "staff": effectif,
                    "state": True,
                    "workUnitRate": 1,
                    "workUnitRateOnProjectsAndOpportunities": 1,
                    "subDivision": "",
                    "isDeleted": False,
                },
            }
        )
    return agences


def _business_units(ressources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Les BU. `includedManagers` : les managers rattachés (relation officielle)."""
    unites: list[dict[str, Any]] = []
    for i, nom in enumerate(_BUSINESS_UNITS, start=1):
        managers = [r for r in ressources if r["attributes"]["_bu"] == i and int(r["id"]) <= 6]
        unites.append(
            {
                "id": str(i),
                "type": "businessunit",
                "attributes": {
                    "name": nom,
                    "isDeleted": False,
                },
                "relationships": {
                    "includedManagers": {
                        "data": [{"id": m["id"], "type": "resource"} for m in managers]
                    }
                },
            }
        )
    return unites


def _poles() -> list[dict[str, Any]]:
    return [
        {
            "id": str(i),
            "type": "pole",
            "attributes": {
                "name": nom,
                "state": True,
                "isDeleted": False,
            },
        }
        for i, nom in enumerate(_POLES, start=1)
    ]


def _roles() -> list[dict[str, Any]]:
    lignes = [
        # (nom, comptes, actifs, agences secondaires, pôles secondaires, typeOf, système)
        ("Administrateur", 2, 2, True, True, "manager", True),
        ("Direction", 3, 3, True, True, "manager", False),
        ("Manager d'agence", 5, 5, False, True, "manager", False),
        ("Responsable RH", 2, 2, False, False, "manager", False),
        ("Consultant intranet", 28, 26, False, False, "intranet", True),
    ]
    return [
        {
            "id": str(i),
            "type": "role",
            "attributes": {
                "name": nom,
                "numberOfAccounts": comptes,
                "numberOfActiveAccounts": actifs,
                "isSecondaryAgenciesAllowed": ag,
                "isSecondaryPolesAllowed": po,
                "typeOf": type_of,
                "isSystem": systeme,
                "isDeleted": False,
            },
        }
        for i, (nom, comptes, actifs, ag, po, type_of, systeme) in enumerate(lignes, start=1)
    ]


# ═════════════════════════════════════════════════════════════════════════════
#  Ressources et contrats
# ═════════════════════════════════════════════════════════════════════════════

#: ids 1-6 : direction et managers ; 7-30 consultants ; 31-32 en intégration ;
#: 33-34 sortis. Les sous-traitants portent typeOf 1.
_NB_RESSOURCES = 34
_IDS_MANAGERS = (2, 3, 4, 5, 6)
_IDS_SOUS_TRAITANTS = (23, 24)
_IDS_INTEGRATION = (31, 32)
_IDS_SORTIS = (33, 34)

#: ┌─ CAS LIMITES D'AUTORISATION ───────────────────────────────────────────────┐
#: │ Ces cohortes ne servent pas la vraisemblance : elles servent à ce qu'un    │
#: │ modèle d'autorisation construit sur ce jeu de données PUISSE ÉCHOUER.      │
#: │ Un jeu uniforme rend un test de visibilité vrai par vacuité — il passe     │
#: │ aussi bien avec un modèle correct qu'avec un modèle cassé.                 │
#: └────────────────────────────────────────────────────────────────────────────┘

#: Deux personnes de MÊME prénom et MÊME nom, dans deux agences différentes.
#: C'est le cas limite le plus dangereux du lot : un consommateur qui dérive un
#: identifiant d'annuaire (UPN, e-mail) du seul « prénom.nom » leur attribue la
#: même identité, et FUSIONNE leurs périmètres de visibilité. Ce n'est pas un
#: défaut cosmétique, c'est une escalade de privilège silencieuse. Leurs
#: adresses sont donc délibérément distinctes — la résolution de collision par
#: ordinal est ce que le consommateur doit reproduire.
_IDS_HOMONYMES = (27, 28)

#: Une personne dont l'agence de rattachement a changé en cours d'année. Ses
#: faits (temps, missions) restent portés par l'agence où ils ont été produits,
#: pas par son agence actuelle. Un modèle qui rattache les faits au
#: collaborateur plutôt qu'à la ligne de fait réécrit rétroactivement
#: l'historique — invisible tant qu'aucun collaborateur ne bouge.
_ID_MUTATION = 22
_AGENCE_AVANT_MUTATION = 2
#: Mois de la mutation : les CRA ANTÉRIEURS portent l'ancienne agence.
#: Choisi DANS la fenêtre MOIS_ACTIVITE (mai-juillet 2026), sans quoi le cas
#: n'existe pas : aucun CRA ne tomberait du bon côté de la bascule.
_MOIS_MUTATION = 6

#: Mois de sortie des ressources sorties. Elles conservent leur historique
#: JUSQU'À ce mois, et rien après. Également choisi dans MOIS_ACTIVITE, pour
#: que « a produit puis est parti » soit observable et non seulement déclaré.
_MOIS_SORTIE = 5


def _ressources(rng: random.Random) -> list[dict[str, Any]]:
    ressources: list[dict[str, Any]] = []
    for i in range(1, _NB_RESSOURCES + 1):
        if i in _IDS_HOMONYMES:
            # Même prénom ET même nom pour les deux : cf. _IDS_HOMONYMES.
            prenom, nom = "Camille", "Fontaine"
        else:
            prenom = _PRENOMS[(i * 7) % len(_PRENOMS)]
            nom = _NOMS[(i * 11) % len(_NOMS)]
        est_direction = i == 1
        est_manager = i in _IDS_MANAGERS
        sorti = i in _IDS_SORTIS
        integration = i in _IDS_INTEGRATION
        sous_traitant = i in _IDS_SOUS_TRAITANTS

        agence = 1 if i in (1, 2, 3) else (2 if i % 3 == 0 else (3 if i % 7 == 0 else 1))
        if i in _IDS_HOMONYMES:
            # Deux agences distinctes : c'est ce qui rend le cas discriminant.
            # Homonymes dans la même agence, une fusion d'identité ne changerait
            # aucun périmètre et le test resterait vert à tort.
            agence = 1 if i == _IDS_HOMONYMES[0] else 3
        pole = ((i - 1) % len(_POLES)) + 1
        bu = ((i - 1) % len(_BUSINESS_UNITS)) + 1
        if est_direction:
            titre = "Directeur général"
        elif est_manager:
            titre = rng.choice(["Directeur d'agence", "Manager de BU", "Directrice des opérations"])
        else:
            titre = rng.choice(_TITRES_CONSULTANT)

        if integration:
            embauche = date(2026, 7, 1)
        elif sorti:
            embauche = date(2019 + i % 4, rng.randint(1, 12), 1)
        else:
            embauche = date(rng.randint(2016, 2025), rng.randint(1, 12), 1)
        experience = max(1, 2026 - embauche.year + rng.randint(0, 6))

        tjm = 0.0
        if not est_direction and not est_manager:
            senior = "senior" in titre or "Lead" in titre or experience >= 8
            tjm = float(rng.choice([780, 850, 920] if senior else [520, 580, 640, 700]))

        etat = (
            ETAT_RESSOURCE_SORTIE
            if sorti
            else (ETAT_RESSOURCE_INTEGRATION if integration else ETAT_RESSOURCE_ACTIVE)
        )
        courriel = f"{prenom.lower()}.{nom.lower()}@boreal-conseil.example"
        if i == _IDS_HOMONYMES[1]:
            # Résolution de collision par ordinal. Le SECOND porte le suffixe :
            # c'est la convention des annuaires, et elle rend le cas asymétrique
            # — un consommateur qui suffixerait les deux passerait quand même.
            courriel = f"{prenom.lower()}.{nom.lower()}2@boreal-conseil.example"
        competences = rng.sample(_COMPETENCES, k=rng.randint(4, 6))
        en_intercontrat = i in (25, 26, 29, 30)

        ressources.append(
            {
                "id": str(i),
                "type": "resource",
                "attributes": {
                    "creationDate": _dt(embauche - timedelta(days=rng.randint(20, 90)), 11, 5),
                    "civility": i % 2,
                    "thumbnail": "",
                    "firstName": prenom,
                    "lastName": nom,
                    "reference": f"BC-{i:04d}",
                    "typeOf": 1 if sous_traitant else 0,
                    "state": etat,
                    "isVisible": not sorti,
                    "skills": ", ".join(competences),
                    "mobilityAreas": rng.choice(
                        [
                            ["Île-de-France"],
                            ["Île-de-France", "Télétravail total"],
                            ["Auvergne-Rhône-Alpes"],
                            ["Pays de la Loire", "Bretagne"],
                        ]
                    ),
                    "title": titre,
                    "availability": "immediate" if en_intercontrat else _d(date(2026, 9, 1)),
                    "forceAvailability": False,
                    "realAvailability": _d(AUJOURDHUI) if en_intercontrat else "",
                    "averageDailyPriceExcludingTax": tjm,
                    "email1": courriel,
                    "email2": f"{prenom.lower()}.{nom.lower()}@courriel.example",
                    "email3": "",
                    "phone1": f"+33 6 {rng.randint(10, 99)} {rng.randint(10, 99)} "
                    f"{rng.randint(10, 99)} {rng.randint(10, 99)}",
                    "phone2": "",
                    "currency": 0,
                    "exchangeRate": 1.0,
                    "currencyAgency": 0,
                    "exchangeRateAgency": 1.0,
                    "numberOfResumes": rng.randint(1, 3),
                    "numberOfActivePositionings": rng.randint(1, 3) if en_intercontrat else 0,
                    "updateDate": _maj(rng, date(2026, rng.randint(1, 6), rng.randint(1, 28))),
                    "tools": [{"tool": c, "level": rng.randint(3, 5)} for c in competences[:4]],
                    "expertiseAreas": rng.sample(_EXPERTISES, k=2),
                    "activityAreas": rng.sample(_SECTEURS, k=2),
                    "diplomas": [rng.choice(_DIPLOMES)],
                    "experience": experience,
                    "references": [],  # rempli après création des projets
                    "languages": [
                        {"language": code, "level": niveau}
                        for code, niveau in rng.sample(_LANGUES, k=2)
                    ],
                    "canShowTechnicalData": True,
                    "canShowActions": True,
                    "socialNetworks": [
                        {
                            "network": "linkedin",
                            "url": f"https://www.linkedin.com/in/{prenom.lower()}-{nom.lower()}",
                        }
                    ],
                    "isDeleted": False,
                    # Clé INTERNE au générateur (retirée avant publication).
                    "_bu": bu,
                },
                "relationships": {
                    "mainManager": _rel(
                        "resource",
                        None
                        if est_direction
                        else (1 if est_manager else rng.choice(_IDS_MANAGERS)),
                    ),
                    # Le réel émet toujours la clé hrManager ; le RH (id 4) suit
                    # les consultants, la direction n'en a pas.
                    "hrManager": _rel("resource", 4 if i >= 7 else None),
                    "agency": _rel("agency", agence),
                    "pole": _rel("pole", pole),
                },
            }
        )
    return ressources


def _contrats(ressources: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    """Un contrat par salarié, plus six historiques CDD → CDI chaînés."""
    contrats: list[dict[str, Any]] = []
    ident = 1

    def _salaire(res: dict[str, Any]) -> float:
        tjm = res["attributes"]["averageDailyPriceExcludingTax"]
        if res["attributes"]["title"] == "Directeur général":
            return 9800.0
        if int(res["id"]) in _IDS_MANAGERS:
            return float(rng.choice([6200, 6800, 7400]))
        return round((tjm or 600) * 4.6 + rng.randint(-150, 150), 0)

    avec_cdd = {7, 9, 12, 15, 18, 21}
    for res in ressources:
        if res["attributes"]["typeOf"] == 1:
            continue  # les sous-traitants n'ont pas de contrat de travail ici
        rid = int(res["id"])
        embauche = date.fromisoformat(res["attributes"]["creationDate"][:10]) + timedelta(days=30)
        sortie = rid in _IDS_SORTIS
        mensuel = _salaire(res)

        precedent: int | None = None
        if rid in avec_cdd:
            fin_cdd = embauche + timedelta(days=180)
            contrats.append(
                _contrat(
                    ident,
                    res,
                    "CDD",
                    embauche,
                    fin_cdd,
                    mensuel=mensuel * 0.92,
                    rng=rng,
                    enfant=ident + 1,
                )
            )
            precedent = ident
            ident += 1
            embauche = fin_cdd + timedelta(days=1)

        fin = _fin_mois(2026, 5) if sortie else None
        contrats.append(
            _contrat(ident, res, "CDI", embauche, fin, mensuel=mensuel, rng=rng, parent=precedent)
        )
        ident += 1
    return contrats


def _contrat(
    ident: int,
    res: dict[str, Any],
    nature: str,
    debut: date,
    fin: date | None,
    *,
    mensuel: float,
    rng: random.Random,
    parent: int | None = None,
    enfant: int | None = None,
) -> dict[str, Any]:
    cout_jour = round(mensuel * 12 * 1.47 / 218, 2)
    # Le réel émet TOUJOURS les clés parentContract/childContract (data null).
    rels: dict[str, Any] = {
        "dependsOn": _rel("resource", res["id"]),
        "createdBy": _rel("resource", 4),
        "agency": res["relationships"]["agency"],
        "parentContract": _rel("contract", parent),
        "childContract": _rel("contract", enfant),
        "files": {"data": []},
    }
    return {
        "id": str(ident),
        "type": "contract",
        "attributes": {
            "typeOf": 0 if nature == "CDI" else 1,
            "creationDate": _dt(debut - timedelta(days=15), 14, 30),
            "updateDate": _maj(rng, debut),
            "employeeType": 0,
            "workingTimeType": 0,
            "numberOfHoursPerWeek": 38.5,
            "classification": rng.choice(
                ["Syntec 2.1 coef 115", "Syntec 2.2 coef 130", "Syntec 3.1 coef 170"]
            ),
            "startDate": _d(debut),
            "endDate": _d(fin) if fin else "",
            "endReason": 3 if fin and nature == "CDI" else 0,
            "probationState": 2,
            "monthlySalary": mensuel,
            "hourlySalary": round(mensuel / 151.67, 2),
            "forceHourlySalary": False,
            "contractAverageDailyCost": cout_jour,
            "dailyExpenses": 9.05,
            "monthlyExpenses": 75.0,
            "numberOfWorkingDays": 218,
            "chargeFactor": 1.47,
            "expensesDetails": [
                {
                    "id": str(ident * 10 + 1),
                    "expenseType": {"reference": 1, "name": "Titres restaurant"},
                    "periodicity": "daily",
                    "netAmount": 9.05,
                }
            ],
            "advantageTypes": [],
            "informationComments": "",
            "currency": 0,
            "currencyAgency": 0,
            "exchangeRate": 1.0,
            "exchangeRateAgency": 1.0,
            "calendar": "Standard",
            "activityRate": 100,
            "partialWorkTimes": [],
            "isPartialWorkTimeEvenOdd": False,
            "isDeleted": False,
        },
        "relationships": rels,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Candidats
# ═════════════════════════════════════════════════════════════════════════════


def _candidats(rng: random.Random) -> list[dict[str, Any]]:
    sources = [
        (1, "LinkedIn"),
        (2, "Cooptation"),
        (3, "Site carrière"),
        (4, "Chasse"),
        (5, "Salon Big Data Paris"),
    ]
    candidats: list[dict[str, Any]] = []
    for i in range(1, 13):
        prenom = _PRENOMS[(i * 13 + 3) % len(_PRENOMS)]
        nom = _NOMS[(i * 17 + 5) % len(_NOMS)]
        creation = date(2026, rng.randint(1, 6), rng.randint(1, 28))
        etat = [0, 1, 1, 2, 2, 3, 4, 5][i % 8]
        titre = rng.choice(_TITRES_CONSULTANT)
        competences = rng.sample(_COMPETENCES, k=4)
        type_source, detail_source = rng.choice(sources)
        candidats.append(
            {
                "id": str(i),
                "type": "candidate",
                "attributes": {
                    "creationDate": _dt(creation, 10, 12),
                    "updateDate": _maj(rng, creation),
                    "civility": i % 2,
                    "thumbnail": "",
                    "firstName": prenom,
                    "lastName": nom,
                    "typeOf": 0,
                    "state": etat,
                    "isVisible": True,
                    "skills": ", ".join(competences),
                    "mobilityAreas": rng.choice(
                        [["Île-de-France"], ["Télétravail total"], ["Auvergne-Rhône-Alpes"]]
                    ),
                    "title": titre,
                    "availability": _d(date(2026, rng.randint(8, 12), 1)),
                    "email1": f"{prenom.lower()}.{nom.lower()}@courriel.example",
                    "email2": "",
                    "email3": "",
                    "phone1": f"+33 7 {rng.randint(10, 99)} {rng.randint(10, 99)} "
                    f"{rng.randint(10, 99)} {rng.randint(10, 99)}",
                    "phone2": "",
                    "town": rng.choice(["Paris", "Lyon", "Nantes", "Bordeaux"]),
                    "country": "France",
                    "source": {"typeOf": type_source, "detail": detail_source},
                    "numberOfResumes": rng.randint(1, 2),
                    "numberOfActivePositionings": 1 if etat in (2, 3) else 0,
                    "socialNetworks": [
                        {
                            "network": "linkedin",
                            "url": f"https://www.linkedin.com/in/{prenom.lower()}-{nom.lower()}",
                        }
                    ],
                    "diplomas": [rng.choice(_DIPLOMES)],
                    "activityAreas": rng.sample(_SECTEURS, k=2),
                    "globalEvaluation": rng.choice(["3.5", "4.0", "4.5", ""]),
                    "languages": [
                        {"language": code, "level": niveau}
                        for code, niveau in rng.sample(_LANGUES, k=2)
                    ],
                    "expertiseAreas": rng.sample(_EXPERTISES, k=1),
                    "experience": rng.randint(2, 12),
                    "references": [
                        {
                            "id": str(i * 10 + n),
                            "title": rng.choice(_TITRES_CONSULTANT),
                            "company": rng.choice(_CLIENTS)[0],
                            "location": rng.choice(["Paris", "Lyon", "Télétravail"]),
                            "startMonth": f"{rng.randint(1, 12):02d}",
                            "startYear": str(2020 + n),
                            "endMonth": f"{rng.randint(1, 12):02d}",
                            "endYear": str(2021 + n),
                            "skills": ", ".join(rng.sample(_COMPETENCES, k=3)),
                            "description": "Mission de conseil et de mise en œuvre.",
                            "startDate": "",
                            "endDate": "",
                            "row": n,
                        }
                        for n in range(1, rng.randint(2, 3))
                    ],
                    "evaluations": (
                        [
                            {
                                "id": str(i),
                                "notations": [
                                    {"criteria": 1, "evaluation": str(rng.randint(3, 5))},
                                    {"criteria": 2, "evaluation": str(rng.randint(3, 5))},
                                ],
                                "date": _d(creation + timedelta(days=10)),
                                "comments": "Bon entretien technique, à suivre.",
                                "manager": {"id": "4", "firstName": "Hugo", "lastName": "Dubois"},
                            }
                        ]
                        if etat >= 2
                        else []
                    ),
                    "tools": [{"tool": c, "level": rng.randint(2, 5)} for c in competences[:3]],
                    "canShowTechnicalData": True,
                    "canShowActions": True,
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": _rel("resource", rng.choice((2, 4, 6))),
                    "agency": _rel("agency", rng.randint(1, 3)),
                    "pole": _rel("pole", rng.randint(1, len(_POLES))),
                },
            }
        )
    return candidats


# ═════════════════════════════════════════════════════════════════════════════
#  CRM : sociétés, contacts, opportunités
# ═════════════════════════════════════════════════════════════════════════════


def _societes(rng: random.Random) -> list[dict[str, Any]]:
    societes: list[dict[str, Any]] = []
    for i, (nom, ville, secteur, site, prospect) in enumerate(_CLIENTS, start=1):
        creation = date(2022 + i % 3, ((i * 5) % 12) + 1, 15)
        societes.append(
            {
                "id": str(i),
                "type": "company",
                "attributes": {
                    "name": nom,
                    "expertiseArea": secteur,
                    "state": 0 if prospect else 1,
                    "informationComments": (
                        "Prospect qualifié — première proposition en cours."
                        if prospect
                        else "Client actif."
                    ),
                    "thumbnail": "",
                    "website": site,
                    "phone1": f"+33 {rng.randint(1, 5)} {rng.randint(10, 99)} "
                    f"{rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}",
                    "town": ville,
                    "country": "Belgique" if ville == "Bruxelles" else "France",
                    "creationDate": _dt(creation, 9, 45),
                    "updateDate": _maj(rng, date(2026, 1, 10)),
                    "socialNetworks": [
                        {
                            "network": "linkedin",
                            "url": "https://www.linkedin.com/company/"
                            f"{nom.lower().replace(' ', '-')}",
                        }
                    ],
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": _rel("resource", rng.choice((2, 3, 5))),
                    "agency": _rel(
                        "agency", 2 if ville == "Lyon" else (3 if ville == "Nantes" else 1)
                    ),
                    "pole": _rel("pole", rng.randint(1, len(_POLES))),
                },
            }
        )
    return societes


def _contacts(societes: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    contacts: list[dict[str, Any]] = []
    ident = 1
    for societe in societes[:10]:  # les contacts vivent chez les clients
        for _ in range(2 if int(societe["id"]) % 2 == 0 else 3):
            if ident > 22:
                break
            prenom = _PRENOMS[(ident * 19 + 7) % len(_PRENOMS)]
            nom = _NOMS[(ident * 23 + 2) % len(_NOMS)]
            domaine = societe["attributes"]["website"].removeprefix("https://")
            creation = date(2024 + ident % 2, ((ident * 3) % 12) + 1, 10)
            contacts.append(
                {
                    "id": str(ident),
                    "type": "contact",
                    "attributes": {
                        "creationDate": _dt(creation, 11, 20),
                        "civility": ident % 2,
                        "thumbnail": "",
                        "firstName": prenom,
                        "lastName": nom,
                        "state": 1,
                        "function": rng.choice(_FONCTIONS_CONTACT),
                        "department": rng.choice(_SERVICES_CONTACT),
                        "email1": f"{prenom.lower()}.{nom.lower()}@{domaine}",
                        "email2": "",
                        "email3": "",
                        "phone1": f"+33 6 {rng.randint(10, 99)} {rng.randint(10, 99)} "
                        f"{rng.randint(10, 99)} {rng.randint(10, 99)}",
                        "phone2": "",
                        "town": societe["attributes"]["town"],
                        "country": societe["attributes"]["country"],
                        "canReadContact": True,
                        "canWriteContact": True,
                        "canShowAction": True,
                        "typesOf": [],
                        "socialNetworks": [],
                        "updateDate": _maj(rng, creation),
                        "isDeleted": False,
                    },
                    "relationships": {
                        "mainManager": societe["relationships"]["mainManager"],
                        "company": _rel("company", societe["id"]),
                        "agency": societe["relationships"]["agency"],
                        "pole": societe["relationships"]["pole"],
                    },
                }
            )
            ident += 1
    return contacts


def _opportunites(
    societes: list[dict[str, Any]],
    contacts: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """15 opportunités : 6 gagnées (→ projets), 5 en cours, 3 perdues, 1 en veille.

    États retenus (dictionnaire d'instance, sémantique plausible) :
    1 = en cours de qualification, 2 = proposition envoyée, 3 = négociation,
    4 = gagnée, 5 = perdue, 6 = en veille.
    """
    plan = [4, 4, 4, 4, 4, 4, 1, 2, 2, 3, 1, 5, 5, 5, 6]
    opportunites: list[dict[str, Any]] = []
    for i, etat in enumerate(plan, start=1):
        societe = societes[(i * 3) % 10]
        contacts_societe = [
            c for c in contacts if c["relationships"]["company"]["data"]["id"] == societe["id"]
        ]
        contact = rng.choice(contacts_societe) if contacts_societe else None
        sujet, outils = _SUJETS[(i * 5) % len(_SUJETS)]
        creation = date(2025, ((i * 7) % 12) + 1, rng.randint(2, 26))
        perdue = etat == 5
        mode = 1 if i % 3 else 2  # 1 = assistance technique, 2 = forfait
        jours = rng.choice([120, 180, 240, 300])
        tjm_moyen = rng.choice([620, 680, 750, 820])
        estime = float(jours * tjm_moyen)
        proba = {1: 0.3, 2: 0.5, 3: 0.7, 4: 1.0, 5: 0.0, 6: 0.1}[etat]
        cloture = creation + timedelta(days=rng.randint(30, 120))
        opportunites.append(
            {
                "id": str(i),
                "type": "opportunity",
                "attributes": {
                    "creationDate": _dt(creation, 9, 30),
                    "title": f"{sujet} — {societe['attributes']['name']}",
                    "reference": f"AO-{creation.year}-{i:03d}",
                    "typeOf": 1,
                    "mode": mode,
                    "state": etat,
                    "place": societe["attributes"]["town"],
                    "isVisible": True,
                    "startDate": _d(cloture + timedelta(days=30)) if not perdue else "",
                    "endDate": _d(cloture + timedelta(days=30 + jours)) if not perdue else "",
                    "closingDate": _d(cloture) if etat in (4, 5) else "",
                    "answerDate": _d(creation + timedelta(days=21)),
                    "duration": jours,
                    "currency": 0,
                    "exchangeRate": 1.0,
                    "currencyAgency": 0,
                    "exchangeRateAgency": 1.0,
                    "turnoverWeightedExcludingTax": round(estime * proba, 2),
                    "estimatesExcludingTax": estime,
                    "turnoverEstimatedExcludingTax": estime,
                    "expertiseArea": rng.choice(_EXPERTISES),
                    "activityAreas": [societe["attributes"]["expertiseArea"]],
                    "origin": {
                        "typeOf": rng.randint(1, 4),
                        "detail": rng.choice(
                            [
                                "Appel entrant",
                                "Recommandation",
                                "Consultation cadre",
                                "Réponse à appel d'offres",
                            ]
                        ),
                    },
                    "tools": outils,
                    "numberOfActivePositionings": 0 if etat in (4, 5, 6) else rng.randint(1, 3),
                    "canShowContact": True,
                    "canShowCompany": True,
                    "stateReason": (
                        {
                            "typeOf": 2,
                            "detail": rng.choice(["Prix", "Concurrent retenu", "Projet reporté"]),
                        }
                        if perdue
                        else {"typeOf": 0, "detail": ""}
                    ),
                    "updateDate": _maj(rng, cloture if etat in (4, 5) else creation),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": societe["relationships"]["mainManager"],
                    "agency": societe["relationships"]["agency"],
                    "pole": societe["relationships"]["pole"],
                    "contact": _rel("contact", contact["id"] if contact else None),
                    "company": _rel("company", societe["id"]),
                    "parsingJob": _rel("opportunityparsingjob", None),
                },
            }
        )
    return opportunites


# ═════════════════════════════════════════════════════════════════════════════
#  Production : projets, missions, jours travaillés
# ═════════════════════════════════════════════════════════════════════════════


def _projets(
    opportunites: list[dict[str, Any]],
    societes: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """12 projets : 6 issus des opportunités gagnées, 6 historiques (2025).

    8 sont en cours à l'ancre (juillet 2026), 4 sont terminés — leurs bornes
    pilotent missions, CRA et factures.
    """
    projets = []
    gagnees = [o for o in opportunites if o["attributes"]["state"] == 4]
    for i in range(1, 13):
        if i <= len(gagnees):
            opp = gagnees[i - 1]
            societe_id = opp["relationships"]["company"]["data"]["id"]
            societe = societes[int(societe_id) - 1]
            debut = date.fromisoformat(opp["attributes"]["startDate"])
            mode = opp["attributes"]["mode"]
            reference_annee = debut.year
        else:
            opp = None
            societe = societes[(i * 7) % 10]
            debut = date(2025, ((i * 5) % 10) + 1, 1)
            mode = 1 if i % 2 else 2
            reference_annee = debut.year
        en_cours = i <= 8
        fin = date(2026, 12, 31) if en_cours else _fin_mois(2026, (i % 4) + 1)
        if not en_cours and fin <= debut:
            fin = _fin_mois(debut.year, min(12, debut.month + 6))
        projets.append(
            {
                "id": str(i),
                "type": "project",
                "attributes": {
                    "startDate": _d(debut),
                    "endDate": _d(fin),
                    "typeOf": mode,
                    "mode": mode,
                    "reference": f"PRJ-{reference_annee}-{i:03d}",
                    "currency": 0,
                    "exchangeRate": 1.0,
                    "currencyAgency": 0,
                    "exchangeRateAgency": 1.0,
                    # Recalculés depuis les missions juste après.
                    "turnoverSimulatedExcludingTax": 0.0,
                    "marginSimulatedExcludingTax": 0.0,
                    "profitabilitySimulated": 0.0,
                    "canReadProject": True,
                    "canShowContact": True,
                    "canShowCompany": True,
                    "canShowIntermediaryContact": True,
                    "canShowIntermediaryCompany": True,
                    "canShowCurrency": True,
                    "canShowCurrencyAgency": True,
                    "canShowExchangeRate": True,
                    "canShowExchangeRateAgency": True,
                    "canShowProfitabilitySimulated": True,
                    "canShowTurnoverSimulatedExcludingTax": True,
                    "canShowMarginSimulatedExcludingTax": True,
                    "creationDate": _dt(debut - timedelta(days=20), 15, 10),
                    "updateDate": _maj(rng, debut),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": societe["relationships"]["mainManager"],
                    "opportunity": _rel("opportunity", opp["id"] if opp else None),
                    "contact": opp["relationships"]["contact"] if opp else _rel("contact", None),
                    "company": _rel("company", societe["id"]),
                    "agency": societe["relationships"]["agency"],
                    "pole": societe["relationships"]["pole"],
                    "intermediaryCompany": _rel("company", None),
                    "intermediaryContact": _rel("contact", None),
                },
            }
        )
    return projets


def _missions(
    projets: list[dict[str, Any]],
    ressources: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """20 missions (deliveries) — le lien consultant ↔ projet.

    La liste GET /deliveries n'est pas documentée au RAML externe (POST
    uniquement) : les items suivent la forme du schéma PROFILE officiel,
    allégée des barèmes (tableaux vides, comme une instance jeune).
    """
    consultants = [
        r
        for r in ressources
        if int(r["id"]) >= 7
        and r["attributes"]["state"] == ETAT_RESSOURCE_ACTIVE
        and int(r["id"]) not in (25, 26, 29, 30)  # l'intercontrat reste au banc
    ]
    missions: list[dict[str, Any]] = []
    ident = 1
    file_consultants = consultants.copy()
    for projet in projets:
        nb = 2 if int(projet["id"]) % 2 == 0 else 1
        if projet["id"] in ("1", "2"):
            nb = 3
        for _ in range(nb):
            if not file_consultants:
                file_consultants = consultants.copy()
            consultant = file_consultants.pop(0)
            if ident > 20:
                break
            debut_projet = date.fromisoformat(projet["attributes"]["startDate"])
            fin_projet = date.fromisoformat(projet["attributes"]["endDate"])
            tjm = consultant["attributes"]["averageDailyPriceExcludingTax"] or 650.0
            cout = round(tjm * 0.58, 2)
            jours_prevus = max(20, min(((fin_projet - debut_projet).days * 5) // 7 - 10, 220))
            ca = round(tjm * jours_prevus, 2)
            couts = round(cout * jours_prevus, 2)
            sous_traite = int(consultant["id"]) in _IDS_SOUS_TRAITANTS
            missions.append(
                {
                    "id": str(ident),
                    "type": "delivery",
                    "attributes": {
                        "startDate": _d(debut_projet),
                        "endDate": _d(fin_projet),
                        "title": consultant["attributes"]["title"],
                        "typeOf": 1 if sous_traite else 0,
                        "state": 1 if fin_projet >= AUJOURDHUI else 2,
                        "canShowAverageDailyContractCost": True,
                        "averageDailyPriceExcludingTax": tjm,
                        "forceAverageDailyPriceExcludingTax": False,
                        "subscriptionQuantityCharged": 0,
                        "subscriptionQuantityFree": 0,
                        "subscriptionPriceExcludingTax": 0.0,
                        "averageDailyCost": cout,
                        "averageDailyContractCost": cout,
                        "numberOfDaysInvoicedOrQuantity": float(jours_prevus),
                        "numberOfDaysFree": 0,
                        "informationComments": "",
                        "conditions": "",
                        "turnoverSimulatedExcludingTax": ca,
                        "costsSimulatedExcludingTax": couts,
                        "marginSimulatedExcludingTax": round(ca - couts, 2),
                        "profitabilitySimulated": round((ca - couts) / ca * 100, 2) if ca else 0.0,
                        "occupationRate": 100.0,
                        "dailyExpenses": 9.05,
                        "monthlyExpenses": 75.0,
                        "numberOfWorkingDays": 218,
                        "weeklyWorkingHours": 38.5,
                        "averageHourlyPriceExcludingTax": 0.0,
                        "forceAverageHourlyPriceExcludingTax": False,
                        "additionalTurnoverAndCosts": [],
                        "expensesDetails": [],
                        "advantageTypes": [],
                        "exceptionalScales": [],
                        "creationDate": _dt(debut_projet - timedelta(days=12), 16, 40),
                        "updateDate": _maj(rng, debut_projet),
                        "calendar": "Standard",
                        "isTurnoverProductionIncluded": True,
                        "isDeleted": False,
                    },
                    "relationships": {
                        "project": _rel("project", projet["id"]),
                        "dependsOn": _rel("resource", consultant["id"]),
                        "purchase": _rel("purchase", None),  # renseigné pour la sous-traitance
                    },
                }
            )
            ident += 1
    return missions


def _jours_travailles(
    missions: list[dict[str, Any]], rng: random.Random
) -> dict[tuple[str, int, int], float]:
    """Jours travaillés par (mission, année, mois) — la matrice qui fait tenir
    factures et lignes de temps ENSEMBLE : les deux la consomment telle quelle."""
    matrice: dict[tuple[str, int, int], float] = {}
    for mission in missions:
        debut = date.fromisoformat(mission["attributes"]["startDate"])
        fin = date.fromisoformat(mission["attributes"]["endDate"])
        mois_courant = date(2026, 1, 1)
        while mois_courant <= min(fin, date(2026, 7, 31)):
            annee, mois = mois_courant.year, mois_courant.month
            if _fin_mois(annee, mois) >= debut:
                ouvres = _jours_ouvres(annee, mois)
                if (annee, mois) == (2026, 7):
                    travailles = 9.0  # mois en cours à l'ancre du 15 juillet
                else:
                    travailles = float(ouvres - rng.choice([0, 0, 1, 1, 2]))
                matrice[(mission["id"], annee, mois)] = travailles
            mois_courant = _fin_mois(annee, mois) + timedelta(days=1)
    return matrice


# ═════════════════════════════════════════════════════════════════════════════
#  Facturation : commandes, factures, transactions bancaires
# ═════════════════════════════════════════════════════════════════════════════


def _commandes(
    projets: list[dict[str, Any]],
    missions: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    commandes: list[dict[str, Any]] = []
    ident = 1
    for projet in projets:
        missions_projet = [
            m for m in missions if m["relationships"]["project"]["data"]["id"] == projet["id"]
        ]
        if not missions_projet:
            continue
        commande_ca = round(
            sum(m["attributes"]["turnoverSimulatedExcludingTax"] for m in missions_projet), 2
        )
        debut = date.fromisoformat(projet["attributes"]["startDate"])
        commandes.append(
            {
                "id": str(ident),
                "type": "order",
                "attributes": {
                    "date": _d(debut - timedelta(days=5)),
                    "number": f"CMD-{debut.year}-{ident:03d}",
                    "reference": f"PO-{rng.randint(40000, 99999)}",
                    "customerAgreement": True,
                    # turnoverInvoiced/delta recalculés après les factures.
                    "turnoverInvoicedExcludingTax": 0.0,
                    "turnoverOrderedExcludingTax": commande_ca,
                    "deltaInvoicedExcludingTax": commande_ca,
                    "state": 1,
                    "creationDate": _dt(debut - timedelta(days=5), 17, 5),
                    "updateDate": _maj(rng, debut),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": projet["relationships"]["mainManager"],
                    "project": _rel("project", projet["id"]),
                },
            }
        )
        ident += 1
    return commandes


def _factures(
    commandes: list[dict[str, Any]],
    missions: list[dict[str, Any]],
    matrice: dict[tuple[str, int, int], float],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Une facture par commande et par mois échu — montant = somme des jours x TJM.

    Mai et avant : réglées. Juin : envoyées, échéance à 30 jours. Juillet : un
    brouillon. Une facture d'avoir (`isCreditNote`) corrige un trop-facturé.
    """
    factures: list[dict[str, Any]] = []
    ident = 1
    for commande in commandes:
        projet_id = commande["relationships"]["project"]["data"]["id"]
        missions_projet = [
            m for m in missions if m["relationships"]["project"]["data"]["id"] == projet_id
        ]
        for annee, mois in [(2026, m) for m in range(1, 8)]:
            montant = sum(
                matrice.get((m["id"], annee, mois), 0.0)
                * m["attributes"]["averageDailyPriceExcludingTax"]
                for m in missions_projet
            )
            if montant <= 0:
                continue
            emission = _fin_mois(annee, mois) + timedelta(days=2)
            if emission > AUJOURDHUI:
                if mois != 7 or int(commande["id"]) % 4 != 1:
                    continue
                emission = AUJOURDHUI  # brouillon du mois en cours
                etat, envoi, payee_le = 0, 0, None
            elif mois <= 5:
                etat, envoi = 2, 2
                payee_le = emission + timedelta(days=rng.randint(18, 32))
            else:
                etat, envoi, payee_le = 1, 1, None
            montant = round(montant, 2)
            ttc = round(montant * (1 + TVA), 2)
            factures.append(
                {
                    "id": str(ident),
                    "type": "invoice",
                    "attributes": {
                        "date": _d(emission),
                        "expectedPaymentDate": _d(emission + timedelta(days=30)),
                        "turnoverInvoicedExcludingTax": montant,
                        "turnoverInvoicedIncludingTax": ttc,
                        "isCreditNote": False,
                        "reference": f"FAC-{annee}-{ident:04d}",
                        "state": etat,
                        "selfBilling": False,
                        "sendingState": envoi,
                        "refuseReason": "",
                        "providerId": "",
                        "providerUrl": "",
                        "taxReportState": 0,
                        "currency": 0,
                        "exchangeRate": 1.0,
                        "currencyAgency": 0,
                        "exchangeRateAgency": 1.0,
                        "paymentMethod": 1,
                        "closed": etat == 2,
                        "totalPayableIncludingTax": ttc,
                        "creationDate": _dt(emission, 8, 5),
                        "updateDate": _dt(min(payee_le or emission, DERNIERE_MAJ), 14, 10),
                        "startDate": _d(date(annee, mois, 1)),
                        "endDate": _d(_fin_mois(annee, mois)),
                        "performedPaymentDate": _d(payee_le) if payee_le else "",
                        "canSendWithPeppol": True,
                        "canSendWithDgfip": False,
                        "canSendWithPennylane": False,
                        "isDeleted": False,
                    },
                    "relationships": {
                        "order": _rel("order", commande["id"]),
                        "schedule": _rel("schedule", None),
                    },
                }
            )
            ident += 1

    # L'avoir : correction d'un trop-facturé sur la première facture réglée.
    reglees = [f for f in factures if f["attributes"]["state"] == 2]
    if reglees:
        origine = reglees[0]
        montant = round(-0.1 * origine["attributes"]["turnoverInvoicedExcludingTax"], 2)
        avoir_date = date.fromisoformat(origine["attributes"]["date"]) + timedelta(days=14)
        factures.append(
            {
                "id": str(ident),
                "type": "invoice",
                "attributes": {
                    **origine["attributes"],
                    "date": _d(avoir_date),
                    "expectedPaymentDate": _d(avoir_date),
                    "turnoverInvoicedExcludingTax": montant,
                    "turnoverInvoicedIncludingTax": round(montant * (1 + TVA), 2),
                    "totalPayableIncludingTax": round(montant * (1 + TVA), 2),
                    "isCreditNote": True,
                    "reference": f"AV-2026-{ident:04d}",
                    "performedPaymentDate": "",
                    "closed": False,
                    "state": 1,
                    "sendingState": 1,
                    "creationDate": _dt(avoir_date, 9, 55),
                    "updateDate": _dt(avoir_date, 9, 55),
                },
                "relationships": dict(origine["relationships"]),
            }
        )

    # Recalage des cumuls de commande — la cohérence qui se voit au premier diff.
    for commande in commandes:
        facture_total = round(
            sum(
                f["attributes"]["turnoverInvoicedExcludingTax"]
                for f in factures
                if f["relationships"]["order"]["data"]["id"] == commande["id"]
                and f["attributes"]["state"] > 0
            ),
            2,
        )
        commande["attributes"]["turnoverInvoicedExcludingTax"] = facture_total
        commande["attributes"]["deltaInvoicedExcludingTax"] = round(
            commande["attributes"]["turnoverOrderedExcludingTax"] - facture_total, 2
        )
    return factures


def _banque(
    factures: list[dict[str, Any]],
    societes: list[dict[str, Any]],
    commandes: list[dict[str, Any]],
    projets: list[dict[str, Any]],
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Comptes, connexions et transactions : les encaissements des factures réglées."""
    connexions = [
        {"id": "1", "type": "bankingconnection", "attributes": {"bankName": "BNP Paribas"}},
        {"id": "2", "type": "bankingconnection", "attributes": {"bankName": "Qonto"}},
    ]
    comptes = [
        {
            "id": "1",
            "type": "bankingaccount",
            "attributes": {
                "name": "Compte courant principal",
                "title": "FR76 3000 4028 3700 0104 5678 921",
            },
            "relationships": {"connection": _rel("bankingconnection", 1)},
        },
        {
            "id": "2",
            "type": "bankingaccount",
            "attributes": {"name": "Compte dépenses", "title": "FR76 1695 8000 0187 6543 2109 876"},
            "relationships": {"connection": _rel("bankingconnection", 2)},
        },
    ]

    def _client_de(facture: dict[str, Any]) -> str:
        commande = next(
            c for c in commandes if c["id"] == facture["relationships"]["order"]["data"]["id"]
        )
        projet = next(
            p for p in projets if p["id"] == commande["relationships"]["project"]["data"]["id"]
        )
        societe = next(
            s for s in societes if s["id"] == projet["relationships"]["company"]["data"]["id"]
        )
        return str(societe["attributes"]["name"])

    transactions: list[dict[str, Any]] = []
    reglees = [f for f in factures if f["attributes"]["performedPaymentDate"]]
    for i, facture in enumerate(reglees[:14], start=1):
        attrs = facture["attributes"]
        jour = date.fromisoformat(attrs["performedPaymentDate"])
        rapprochee = i <= 11
        transactions.append(
            {
                "id": str(i),
                "type": "bankingtransaction",
                "attributes": {
                    "amount": attrs["totalPayableIncludingTax"],
                    "currency": 0,
                    "date": _dt(jour, rng.randint(3, 7), rng.randint(0, 59)),
                    "numberOfInvoices": 1 if rapprochee else 0,
                    "title": f"VIR SEPA {_client_de(facture).upper()} {attrs['reference']}",
                    "state": 2 if rapprochee else 0,
                    "totalAmountToReconcile": 0.0
                    if rapprochee
                    else attrs["totalPayableIncludingTax"],
                    "canReadTransaction": True,
                    "canWriteTransaction": True,
                    "canReconcile": True,
                    "isDeleted": False,
                },
                "relationships": {"account": _rel("bankingaccount", 1)},
            }
        )
    # Deux débits fournisseurs sur le second compte, non rapprochés.
    for n, (libelle, montant) in enumerate(
        [
            ("PRLV SEPA SOFTALLIANCE ABONNEMENT DATA-2026-07", 1068.0),
            ("PRLV SEPA FONCIERE BEAUMONT LOYER 2026-07", 9960.0),
        ],
        start=len(transactions) + 1,
    ):
        transactions.append(
            {
                "id": str(n),
                "type": "bankingtransaction",
                "attributes": {
                    "amount": montant,
                    "currency": 0,
                    "date": _dt(date(2026, 7, 5), 4, 45),
                    "numberOfInvoices": 0,
                    "title": libelle,
                    "state": 0,
                    "totalAmountToReconcile": montant,
                    "canReadTransaction": True,
                    "canWriteTransaction": True,
                    "canReconcile": True,
                    "isDeleted": False,
                },
                "relationships": {"account": _rel("bankingaccount", 2)},
            }
        )
    return comptes, connexions, transactions


# ═════════════════════════════════════════════════════════════════════════════
#  Achats et paiements fournisseurs
# ═════════════════════════════════════════════════════════════════════════════


def _achats(
    missions: list[dict[str, Any]],
    ressources: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """8 achats : sous-traitance adossée aux missions, licences, loyer, matériel."""
    achats: list[dict[str, Any]] = []
    ident = 1

    missions_st = [
        m
        for m in missions
        if int(m["relationships"]["dependsOn"]["data"]["id"]) in _IDS_SOUS_TRAITANTS
    ][:2]
    for mission in missions_st:
        consultant = next(
            r for r in ressources if r["id"] == mission["relationships"]["dependsOn"]["data"]["id"]
        )
        tjm_achat = round(mission["attributes"]["averageDailyPriceExcludingTax"] * 0.72, 2)
        jours = mission["attributes"]["numberOfDaysInvoicedOrQuantity"]
        debut = date.fromisoformat(mission["attributes"]["startDate"])
        achats.append(
            {
                "id": str(ident),
                "type": "purchase",
                "attributes": {
                    "date": _d(debut - timedelta(days=8)),
                    "title": f"Sous-traitance {consultant['attributes']['firstName']} "
                    f"{consultant['attributes']['lastName']} — Fivetech Partners",
                    "subscription": 0,
                    "typeOf": 0,
                    "reference": f"ACH-2026-{ident:03d}",
                    "state": 1,
                    "taxRate": 20.0,
                    "currency": 0,
                    "exchangeRate": 1.0,
                    "currencyAgency": 0,
                    "exchangeRateAgency": 1.0,
                    "amountExcludingTax": tjm_achat,
                    "quantity": jours,
                    "totalAmountExcludingTax": round(tjm_achat * jours, 2),
                    "deltaExcludingTax": 0.0,  # recalculé après les paiements
                    "engagedPaymentsAmountExcludingTax": 0.0,
                    "creationDate": _dt(debut - timedelta(days=8), 11, 45),
                    "updateDate": _maj(rng, debut),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": _rel("resource", 2),
                    "project": mission["relationships"]["project"],
                    "delivery": _rel("delivery", mission["id"]),
                    "contact": _rel("contact", None),
                    "company": _rel("company", _ID_FOURNISSEUR_SOUSTRAITANCE),
                    "agency": _rel("agency", 1),
                    "pole": _rel("pole", None),
                },
            }
        )
        mission["relationships"]["purchase"] = _rel("purchase", ident)
        ident += 1

    generaux = [
        ("Licences plateforme data — Softalliance", 1, 2, 890.0, 12, _ID_FOURNISSEUR_LICENCES),
        ("Abonnement observabilité — Softalliance", 1, 2, 340.0, 12, _ID_FOURNISSEUR_LICENCES),
        ("Postes de travail consultants", 0, 4, 1650.0, 6, _ID_FOURNISSEUR_LICENCES),
        ("Loyer agence Paris", 1, 3, 8300.0, 12, _ID_FOURNISSEUR_LOYER),
        ("Loyer agence Lyon", 1, 3, 2900.0, 12, _ID_FOURNISSEUR_LOYER),
        ("Mobilier salle projet Nantes", 0, 4, 4200.0, 1, _ID_FOURNISSEUR_LOYER),
    ]
    for titre, abonnement, type_of, montant, quantite, fournisseur in generaux:
        jour = date(2026, 1, rng.randint(3, 20))
        achats.append(
            {
                "id": str(ident),
                "type": "purchase",
                "attributes": {
                    "date": _d(jour),
                    "title": titre,
                    "subscription": abonnement,
                    "typeOf": type_of,
                    "reference": f"ACH-2026-{ident:03d}",
                    "state": 1,
                    "taxRate": 20.0,
                    "currency": 0,
                    "exchangeRate": 1.0,
                    "currencyAgency": 0,
                    "exchangeRateAgency": 1.0,
                    "amountExcludingTax": montant,
                    "quantity": float(quantite),
                    "totalAmountExcludingTax": round(montant * quantite, 2),
                    "deltaExcludingTax": 0.0,
                    "engagedPaymentsAmountExcludingTax": 0.0,
                    "creationDate": _dt(jour, 10, 25),
                    "updateDate": _maj(rng, jour),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": _rel("resource", 1),
                    "project": _rel("project", None),
                    "delivery": _rel("delivery", None),
                    "contact": _rel("contact", None),
                    "company": _rel("company", fournisseur),
                    "agency": _rel("agency", 1),
                    "pole": _rel("pole", None),
                },
            }
        )
        ident += 1
    return achats


def _paiements(achats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Échéanciers de règlement des achats — passés réglés, à venir prévus."""
    paiements: list[dict[str, Any]] = []
    ident = 1
    for achat in achats:
        attrs = achat["attributes"]
        if attrs["subscription"] == 1:
            echeances = [(date(2026, mois, 5), attrs["amountExcludingTax"]) for mois in (5, 6, 7)]
        else:
            total = attrs["totalAmountExcludingTax"]
            echeances = [
                (date(2026, 4, 15), round(total * 0.4, 2)),
                (date(2026, 7, 25), round(total * 0.6, 2)),
            ]
        for jour, montant in echeances:
            effectue = jour <= AUJOURDHUI
            paiements.append(
                {
                    "id": str(ident),
                    "type": "payment",
                    "attributes": {
                        "date": _d(jour),
                        "performedDate": _d(jour + timedelta(days=1)) if effectue else "",
                        "expectedDate": _d(jour),
                        "state": 1 if effectue else 0,
                        "number": f"VIR-2026-{ident:03d}",
                        "amountExcludingTax": montant,
                        "amountIncludingTax": round(montant * (1 + TVA), 2),
                        "numberOfFiles": 0,
                        "canWritePayment": True,
                        "creationDate": _dt(jour - timedelta(days=10), 9, 20),
                        "updateDate": _dt(min(jour, DERNIERE_MAJ), 15, 40),
                        "isDeleted": False,
                    },
                    "relationships": {"purchase": _rel("purchase", achat["id"])},
                }
            )
            ident += 1
        engages = round(
            sum(
                p["attributes"]["amountExcludingTax"]
                for p in paiements
                if p["relationships"]["purchase"]["data"]["id"] == achat["id"]
            ),
            2,
        )
        attrs["engagedPaymentsAmountExcludingTax"] = engages
        attrs["deltaExcludingTax"] = round(attrs["totalAmountExcludingTax"] - engages, 2)
    return paiements


# ═════════════════════════════════════════════════════════════════════════════
#  Activité : CRA, temps, absences, frais
# ═════════════════════════════════════════════════════════════════════════════


def _cras(
    ressources: list[dict[str, Any]], rng: random.Random
) -> tuple[list[dict[str, Any]], dict[tuple[str, int, int], str]]:
    """Un CRA par consultant actif et par mois d'activité. Rend aussi l'index
    (resource_id, année, mois) → cra_id que les lignes de temps consomment."""
    cras: list[dict[str, Any]] = []
    index: dict[tuple[str, int, int], str] = {}
    ident = 1
    for res in ressources:
        rid = int(res["id"])
        if rid <= 6:
            continue
        sorti = res["attributes"]["state"] == ETAT_RESSOURCE_SORTIE
        for annee, mois in MOIS_ACTIVITE:
            if rid in _IDS_INTEGRATION and mois < 7:
                continue
            # Un SORTI conserve son historique jusqu'à son départ, et rien
            # après. Ne lui donner AUCUN CRA effacerait le passé : un ancien
            # collaborateur doit rester visible dans les faits historiques
            # (rémunération, temps produits) tout en n'ayant plus aucune
            # visibilité applicative. Ce sont deux propriétés distinctes, et
            # les confondre est ce qui fait qu'un partant garde des droits —
            # ou qu'on perd la trace de ce qu'il a produit.
            if sorti and mois > _MOIS_SORTIE:
                continue
            if mois == 7:
                etat = rng.choice(["waitingForValidation", "savedAndNoValidation"])
                clos = False
            else:
                etat = "validated"
                clos = True
            cras.append(
                {
                    "id": str(ident),
                    "type": "timesreport",
                    "attributes": {
                        "term": f"{annee:04d}-{mois:02d}",
                        "state": etat,
                        "closed": clos,
                        "isDeleted": False,
                    },
                    "relationships": {
                        # L'agence vient de la LIGNE DE FAIT, pas du
                        # collaborateur : cf. _ID_MUTATION. Un mutant garde ses
                        # CRA antérieurs sous son ancienne agence.
                        "agency": (
                            _rel("agency", _AGENCE_AVANT_MUTATION)
                            if rid == _ID_MUTATION and mois < _MOIS_MUTATION
                            else res["relationships"]["agency"]
                        ),
                        "resource": _rel("resource", res["id"]),
                    },
                }
            )
            index[(res["id"], annee, mois)] = str(ident)
            ident += 1
    return cras, index


def _temps(
    missions: list[dict[str, Any]],
    ressources: list[dict[str, Any]],
    matrice: dict[tuple[str, int, int], float],
    index_cra: dict[tuple[str, int, int], str],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Lignes de temps : production par mission (les MÊMES jours que les
    factures), intercontrat pour le banc, et quelques astreintes."""
    temps: list[dict[str, Any]] = []
    # Les ids réels sont composites et séquentiels PAR CATÉGORIE :
    # `regular_1`, `exceptional_1`… (relevé tenant : premier id `regular_1`).
    compteurs = {"regular": 0, "exceptional": 0}

    def _id_temps(categorie: str) -> str:
        compteurs[categorie] += 1
        return f"{categorie}_{compteurs[categorie]}"

    for mission in missions:
        res_id = mission["relationships"]["dependsOn"]["data"]["id"]
        for annee, mois in MOIS_ACTIVITE:
            jours = matrice.get((mission["id"], annee, mois))
            cra_id = index_cra.get((res_id, annee, mois))
            if not jours or cra_id is None:
                continue
            temps.append(
                {
                    "id": _id_temps("regular"),
                    "type": "time",
                    "attributes": {
                        "category": "regular",
                        "workUnitType": {
                            "reference": 1,
                            "activityType": "production",
                            "name": "Journée de production",
                        },
                        "row": 1,
                        "startDate": _d(date(annee, mois, 1)),
                        "duration": jours,
                        "isDeleted": False,
                    },
                    "relationships": {
                        "timesReport": _rel("timesreport", cra_id),
                        "delivery": _rel("delivery", mission["id"]),
                        "batch": _rel("batch", None),
                        "project": mission["relationships"]["project"],
                    },
                }
            )
            if rng.random() < 0.12:
                temps.append(
                    {
                        "id": _id_temps("exceptional"),
                        "type": "time",
                        "attributes": {
                            "category": "exceptional",
                            "workUnitType": {
                                "reference": 40,
                                "activityType": "exceptionalTime",
                                "name": "Astreinte week-end",
                            },
                            "row": 2,
                            "startDate": _d(date(annee, mois, rng.choice([7, 14, 21]))),
                            "duration": 1.0,
                            "isDeleted": False,
                        },
                        "relationships": {
                            "timesReport": _rel("timesreport", cra_id),
                            "delivery": _rel("delivery", mission["id"]),
                            "batch": _rel("batch", None),
                            "project": mission["relationships"]["project"],
                        },
                    }
                )

    # Le banc saisit de l'intercontrat — sans mission ni projet, le dialecte réel.
    for res in ressources:
        if res["attributes"]["availability"] != "immediate":
            continue
        for annee, mois in MOIS_ACTIVITE:
            cra_id = index_cra.get((res["id"], annee, mois))
            if cra_id is None or mois < 6:
                continue
            temps.append(
                {
                    "id": _id_temps("regular"),
                    "type": "time",
                    "attributes": {
                        "category": "regular",
                        "workUnitType": {
                            "reference": 10,
                            "activityType": "internal",
                            "name": "Intercontrat",
                        },
                        "row": 1,
                        "startDate": _d(date(annee, mois, 1)),
                        "duration": 9.0 if mois == 7 else float(_jours_ouvres(annee, mois)),
                        "isDeleted": False,
                    },
                    "relationships": {
                        "timesReport": _rel("timesreport", cra_id),
                        "delivery": _rel("delivery", None),
                        "batch": _rel("batch", None),
                        "project": _rel("project", None),
                    },
                }
            )
    return temps


def _absences_et_rapports(
    ressources: list[dict[str, Any]],
    agences: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Lignes d'absence, contexte IMBRIQUÉ (rapport, agence, ressource) — le
    dialecte réel de /absences : tout vit dans `attributes`, pas de relations."""
    absences: list[dict[str, Any]] = []
    ident = 1
    rapport_id = 1
    for res in ressources:
        rid = int(res["id"])
        if rid <= 2 or res["attributes"]["state"] != ETAT_RESSOURCE_ACTIVE:
            continue
        agence = next(a for a in agences if a["id"] == res["relationships"]["agency"]["data"]["id"])
        plages: list[tuple[date, date, tuple[int, str]]] = [
            # Les congés d'été, posés à l'avance — rapport en attente.
            (date(2026, 8, 3), date(2026, 8, 14), _TYPES_ABSENCE[0]),
        ]
        if rid % 2 == 0:
            rtt = date(2026, 5, rng.choice([15, 22]))  # deux vendredis de mai
            plages.append((rtt, rtt, _TYPES_ABSENCE[1]))
        if rid % 5 == 0:
            # Deux jours ouvrés consécutifs : on recule jusqu'à un lundi-jeudi.
            debut_maladie = date(2026, 6, rng.randint(8, 18))
            while debut_maladie.weekday() > 3:
                debut_maladie -= timedelta(days=1)
            plages.append((debut_maladie, debut_maladie + timedelta(days=1), _TYPES_ABSENCE[2]))
        if rid % 9 == 0:
            jour = date(2026, 6, 26)
            plages.append((jour, jour, _TYPES_ABSENCE[3]))

        for debut, fin, (reference, libelle) in plages:
            jours = sum(
                1
                for n in range((fin - debut).days + 1)
                if (debut + timedelta(days=n)).weekday() < 5
            )
            futur = debut > AUJOURDHUI
            creation = debut - timedelta(days=rng.randint(15, 45))
            absences.append(
                {
                    "id": str(ident),
                    "type": "absence",
                    "attributes": {
                        "startDate": _d(debut),
                        "endDate": _d(fin),
                        "duration": float(jours),
                        "title": libelle,
                        "workUnitType": {
                            "reference": reference,
                            "activityType": "absence",
                            "name": libelle,
                        },
                        "absencesReport": {
                            "id": str(rapport_id),
                            "creationDate": _dt(creation, 8, 40),
                            "state": "waitingForValidation" if futur else "validated",
                            "agency": {
                                "id": agence["id"],
                                "name": agence["attributes"]["name"],
                                "workUnitRate": 1,
                            },
                            "resource": {
                                "id": res["id"],
                                "lastName": res["attributes"]["lastName"],
                                "firstName": res["attributes"]["firstName"],
                                "workUnitRate": 1,
                            },
                        },
                        "isDeleted": False,
                    },
                }
            )
            ident += 1
            rapport_id += 1
    return absences


def _frais(
    missions: list[dict[str, Any]],
    ressources: list[dict[str, Any]],
    projets: list[dict[str, Any]],
    agences: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Notes de frais — contexte imbriqué (rapport, mission, projet), comme
    /absences. Un rapport par (consultant, mois), km et frais réels mêlés."""
    frais: list[dict[str, Any]] = []
    ident = 1
    rapport_id = 1
    missions_frais = [m for m in missions if int(m["id"]) % 2 == 1][:10]
    for mission in missions_frais:
        res = next(
            r for r in ressources if r["id"] == mission["relationships"]["dependsOn"]["data"]["id"]
        )
        projet = next(
            p for p in projets if p["id"] == mission["relationships"]["project"]["data"]["id"]
        )
        agence = next(a for a in agences if a["id"] == res["relationships"]["agency"]["data"]["id"])
        for annee, mois in MOIS_ACTIVITE:
            if mois == 7 and int(res["id"]) % 3 == 0:
                continue
            rapport = {
                "id": str(rapport_id),
                "term": f"{annee:04d}-{mois:02d}",
                "state": "validated" if mois < 7 else "waitingForValidation",
                "ratePerKilometerType": {"reference": 3, "name": "Barème 5 CV", "amount": 0.548},
                "advance": 0.0,
                "agency": {"id": agence["id"], "name": agence["attributes"]["name"]},
                "resource": {
                    "id": res["id"],
                    "lastName": res["attributes"]["lastName"],
                    "firstName": res["attributes"]["firstName"],
                },
            }
            rapport_id += 1
            lignes: list[tuple[tuple[int, str, float], float, bool, int]] = [
                (_TYPES_FRAIS[0][:3], round(rng.uniform(18, 52), 2), False, 0),
                (_TYPES_FRAIS[1][:3], round(rng.uniform(30, 120), 2), True, 0),
            ]
            if int(res["id"]) % 4 == 0:
                lignes.append((_TYPES_FRAIS[3][:3], 0.0, False, rng.choice([180, 240, 320])))
            for row, ((type_ref, type_nom, taux), montant_base, refacture, km) in enumerate(
                lignes, start=1
            ):
                kilometrique = km > 0
                montant_ttc = round(km * 0.548, 2) if kilometrique else montant_base
                jour = date(annee, mois, rng.randint(2, 26))
                frais.append(
                    {
                        "id": str(ident),
                        "type": "expense",
                        "attributes": {
                            "category": "actual",
                            "activityType": "production",
                            "expenseType": {
                                "reference": type_ref,
                                "taxRate": taux,
                                "name": type_nom,
                            },
                            "row": row,
                            "startDate": _d(jour),
                            "reinvoiced": refacture,
                            "amountIncludingTax": montant_ttc,
                            "tax": 0.0
                            if kilometrique
                            else round(montant_ttc - montant_ttc / (1 + taux / 100), 2),
                            "numberOfKilometers": float(km),
                            "number": 1,
                            "title": f"{type_nom} — {projet['attributes']['reference']}",
                            "currency": 0,
                            "exchangeRate": 1.0,
                            "isKilometricExpense": kilometrique,
                            "expensesReport": rapport,
                            "delivery": {
                                "id": mission["id"],
                                "title": mission["attributes"]["title"],
                                "startDate": mission["attributes"]["startDate"],
                                "endDate": mission["attributes"]["endDate"],
                            },
                            "project": {
                                "id": projet["id"],
                                "reference": projet["attributes"]["reference"],
                            },
                            "isDeleted": False,
                        },
                    }
                )
                ident += 1
    return frais


# ═════════════════════════════════════════════════════════════════════════════
#  Actions CRM
# ═════════════════════════════════════════════════════════════════════════════


def _actions(
    candidats: list[dict[str, Any]],
    contacts: list[dict[str, Any]],
    opportunites: list[dict[str, Any]],
    projets: list[dict[str, Any]],
    *,
    ressources: list[dict[str, Any]],
    factures: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """~45 actions rattachées à leurs entités via `dependsOn` — le dialecte réel."""
    actions: list[dict[str, Any]] = []
    ident = 1

    def _ajouter(
        cible_type: str,
        cible_id: str,
        type_of: int,
        texte: str,
        *,
        jour: date,
        manager: int,
        societe_id: str | None,
    ) -> None:
        nonlocal ident
        actions.append(
            {
                "id": str(ident),
                "type": "action",
                "attributes": {
                    "startDate": _dt(jour, rng.randint(9, 18), rng.choice([0, 15, 30, 45])),
                    "creationDate": _dt(jour, 8, 5),
                    "typeOf": type_of,
                    "text": texte,
                    "numberOfFiles": 0,
                    "canReadAction": True,
                    "canWriteAction": True,
                    "updateDate": _dt(min(jour, DERNIERE_MAJ), 18, 55),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": _rel("resource", manager),
                    "dependsOn": _rel(cible_type, cible_id),
                    "company": _rel("company", societe_id),
                    "relatedActions": {"data": []},
                },
            }
        )
        ident += 1

    for candidat in candidats:
        jour = date.fromisoformat(candidat["attributes"]["creationDate"][:10]) + timedelta(days=7)
        _ajouter(
            "candidate",
            candidat["id"],
            4,
            f"Entretien technique avec {candidat['attributes']['firstName']} "
            f"{candidat['attributes']['lastName']} — retour globalement positif.",
            jour=jour,
            manager=rng.choice((2, 4, 6)),
            societe_id=None,
        )
    for contact in contacts[:12]:
        jour = date(2026, rng.randint(2, 7), rng.randint(1, 26))
        _ajouter(
            "contact",
            contact["id"],
            rng.choice([1, 2, 3]),
            rng.choice(
                [
                    "Appel de suivi — points d'attention budgétaires évoqués.",
                    "Déjeuner de suivi de compte, prochaines échéances passées en revue.",
                    "Envoi de la plaquette d'offres data & IA.",
                ]
            ),
            jour=min(jour, AUJOURDHUI),
            manager=rng.choice((2, 3, 5)),
            societe_id=contact["relationships"]["company"]["data"]["id"],
        )
    for opportunite in opportunites[:10]:
        jour = date.fromisoformat(opportunite["attributes"]["creationDate"][:10]) + timedelta(
            days=rng.randint(5, 40)
        )
        _ajouter(
            "opportunity",
            opportunite["id"],
            rng.choice([3, 5]),
            rng.choice(
                [
                    "Soutenance de la proposition devant le comité de sélection.",
                    "Relance sur la proposition envoyée — décision attendue sous quinzaine.",
                    "Cadrage du besoin avec l'équipe métier.",
                ]
            ),
            jour=jour,
            manager=rng.choice((2, 3, 5)),
            societe_id=opportunite["relationships"]["company"]["data"]["id"],
        )
    for projet in projets[:8]:
        jour = date(2026, rng.randint(4, 7), rng.randint(1, 26))
        _ajouter(
            "project",
            projet["id"],
            6,
            "Comité de pilotage mensuel — avancement conforme au plan de charge.",
            jour=min(jour, AUJOURDHUI),
            manager=rng.choice((2, 3, 5)),
            societe_id=projet["relationships"]["company"]["data"]["id"],
        )
    for res in [r for r in ressources if 7 <= int(r["id"]) <= 14]:
        jour = date(2026, rng.randint(1, 6), rng.randint(2, 26))
        _ajouter(
            "resource",
            res["id"],
            7,
            "Entretien annuel — objectifs et plan de formation actualisés.",
            jour=jour,
            manager=4,
            societe_id=None,
        )
    en_retard = [
        f for f in factures if f["attributes"]["state"] == 1 and not f["attributes"]["isCreditNote"]
    ][:3]
    for facture in en_retard:
        jour = date.fromisoformat(facture["attributes"]["expectedPaymentDate"])
        _ajouter(
            "invoice",
            facture["id"],
            2,
            f"Relance règlement {facture['attributes']['reference']} auprès du service comptable.",
            jour=min(jour, AUJOURDHUI),
            manager=2,
            societe_id=None,
        )
    return actions


# ═════════════════════════════════════════════════════════════════════════════
#  Dossier technique et rémunération (affordances conservées)
# ═════════════════════════════════════════════════════════════════════════════


def _donnees_techniques(
    ressources: list[dict[str, Any]],
    projets: list[dict[str, Any]],
    societes: list[dict[str, Any]],
    rng: random.Random,
) -> dict[str, dict[str, Any]]:
    donnees = {}
    for res in ressources:
        attrs = res["attributes"]
        nb = rng.randint(1, 3)
        references: list[dict[str, Any]] = []
        for n in range(nb):
            projet = rng.choice(projets)
            societe = next(
                s for s in societes if s["id"] == projet["relationships"]["company"]["data"]["id"]
            )
            debut = date.fromisoformat(projet["attributes"]["startDate"])
            competences = rng.sample(_COMPETENCES, k=3)
            references.append(
                {
                    "id": f"{int(res['id']) * 100 + n + 1}",
                    "title": attrs["title"],
                    "company": societe["attributes"]["name"],
                    "description": (
                        f"Intervention {attrs['title']} pour {societe['attributes']['name']} : "
                        "cadrage, mise en œuvre et industrialisation de la solution cible."
                    ),
                    "location": societe["attributes"]["town"],
                    "startMonth": debut.month,
                    "startYear": debut.year,
                    "endMonth": min(12, debut.month + 6),
                    "endYear": debut.year,
                    "skills": competences,
                }
            )
        donnees[res["id"]] = {
            "id": res["id"],
            "type": "resource",
            "attributes": {
                "description": (
                    f"{attrs['title']} — {attrs['experience']} ans d'expérience, "
                    f"interventions {', '.join(attrs['expertiseAreas'])}."
                ),
                "summary": f"{attrs['title']}, {attrs['experience']} ans d'expérience.",
                "references": references,
            },
        }
    return donnees


def _remuneration(
    ressources: list[dict[str, Any]],
    contrats: list[dict[str, Any]],
    agences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """La fixture CSV hors /api — désormais DÉRIVÉE des contrats officiels."""
    lignes: list[dict[str, Any]] = []
    for contrat in contrats:
        if contrat["attributes"]["typeOf"] != 0:  # CDI uniquement
            continue
        res = next(
            r for r in ressources if r["id"] == contrat["relationships"]["dependsOn"]["data"]["id"]
        )
        agence = next(a for a in agences if a["id"] == res["relationships"]["agency"]["data"]["id"])
        lignes.append(
            {
                "collaborateur_id": res["id"],
                "upn": res["attributes"]["email1"],
                "entite": agence["attributes"]["name"],
                "periode": contrat["attributes"]["startDate"],
                "montant_brut_annuel": int(contrat["attributes"]["monthlySalary"] * 12),
            }
        )
    return lignes


# ═════════════════════════════════════════════════════════════════════════════
#  Assemblage
# ═════════════════════════════════════════════════════════════════════════════


def build_realiste_dataset(seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)

    agences = _agences()
    poles = _poles()
    roles = _roles()
    ressources = _ressources(rng)
    business_units = _business_units(ressources)
    contrats = _contrats(ressources, rng)
    candidats = _candidats(rng)
    societes = _societes(rng)
    contacts = _contacts(societes, rng)
    opportunites = _opportunites(societes, contacts, rng)
    projets = _projets(opportunites, societes, rng)
    missions = _missions(projets, ressources, rng)
    matrice = _jours_travailles(missions, rng)
    commandes = _commandes(projets, missions, rng)
    factures = _factures(commandes, missions, matrice, rng)
    achats = _achats(missions, ressources, rng)
    paiements = _paiements(achats)
    comptes, connexions, transactions = _banque(factures, societes, commandes, projets, rng)
    cras, index_cra = _cras(ressources, rng)
    temps = _temps(missions, ressources, matrice, index_cra, rng)
    absences = _absences_et_rapports(ressources, agences, rng)
    frais = _frais(missions, ressources, projets, agences, rng)
    actions = _actions(
        candidats,
        contacts,
        opportunites,
        projets,
        ressources=ressources,
        factures=factures,
        rng=rng,
    )

    # Consolidation projets ← missions (CA simulé, marge, rentabilité).
    for projet in projets:
        missions_projet = [
            m for m in missions if m["relationships"]["project"]["data"]["id"] == projet["id"]
        ]
        ca = round(
            sum(m["attributes"]["turnoverSimulatedExcludingTax"] for m in missions_projet), 2
        )
        couts = round(
            sum(m["attributes"]["costsSimulatedExcludingTax"] for m in missions_projet), 2
        )
        projet["attributes"]["turnoverSimulatedExcludingTax"] = ca
        projet["attributes"]["marginSimulatedExcludingTax"] = round(ca - couts, 2)
        projet["attributes"]["profitabilitySimulated"] = (
            round((ca - couts) / ca * 100, 2) if ca else 0.0
        )

    # Le CV résumé des ressources pointe des références réelles du dossier technique.
    donnees_techniques = _donnees_techniques(ressources, projets, societes, rng)
    for res in ressources:
        res["attributes"]["references"] = [
            {"id": ref["id"], "title": ref["title"], "description": ref["description"]}
            for ref in donnees_techniques[res["id"]]["attributes"]["references"]
        ]
        del res["attributes"]["_bu"]  # clé interne au générateur

    return {
        "absences": absences,
        "actions": actions,
        "agencies": agences,
        "banking_accounts": comptes,
        "banking_connections": connexions,
        "banking_transactions": transactions,
        "business_units": business_units,
        "candidates": candidats,
        "companies": societes,
        "contacts": contacts,
        "contracts": contrats,
        "deliveries": missions,
        "expenses": frais,
        "invoices": factures,
        "opportunities": opportunites,
        "orders": commandes,
        "payments": paiements,
        "poles": poles,
        "projects": projets,
        "purchases": achats,
        "resources": ressources,
        "roles": roles,
        "times": temps,
        "times_reports": cras,
        "technical_data": donnees_techniques,
        "remuneration": _remuneration(ressources, contrats, agences),
    }
