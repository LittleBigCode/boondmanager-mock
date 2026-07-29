"""Profil `insights360` — 50 collaborateurs, UPN, et les huit cas limites.

Génération en DEUX TEMPS, et c'est le point important :

  1. `_generer_figurants` produit N employés déterministes depuis
     `random.Random(seed)` ;
  2. `_appliquer_cas_limites` ÉCRASE des indices précis.

Faire émerger les cas limites d'un tirage aléatoire serait fragile (un
changement de graine les ferait disparaître) et introuvable au grep. Ici chaque
cas est une constante nommée, documentée, et vérifiée par un test dédié —
exactement le motif que le mock d'origine utilisait déjà pour épingler ses
trois comptes Keycloak.

Les huit cas limites exigés par la spec, et leur porteur :

    id  upn                             cas
    ─── ─────────────────────────────── ──────────────────────────────────────
    1   claire.durand@ent.fr            sommet de hiérarchie (sans manager) + Comex
    2   sophie.m@ent.fr                 niveau 2 (l'UPN de l'exemple de la spec)
    3   marc.leroy@ent.fr               niveau 3 → chaîne à trois niveaux
    4   joël.françois-mercier@ent.fr    accents ET trait d'union, nom et UPN
    5   marie.dupont@ent.fr             homonyme #1
    6   marie.dupont2@ent.fr            homonyme #2, et rattachés sur 2 entités
    7   luc.moreau@ent.fr               changement d'entité en cours d'année
    8   anne.petit@ent.fr               sorti, avec rémunération historique
    9   pierre.roux@ent.lu              seul ENT-LU → le cas de rognage
    10  ext.consultant@ent.fr           dans un groupe Entra, absent du SIRH
    11  tom.absent@ent.fr               dans le SIRH, dans aucun groupe Entra
"""

from __future__ import annotations

import random
import unicodedata
from typing import Any

from ..settings import settings

ENTITES: list[tuple[str, str, str]] = [
    ("1", "ENT-FR", "Entité France"),
    ("2", "ENT-BE", "Entité Belgique"),
    ("3", "ENT-LU", "Entité Luxembourg"),
]

_PRENOMS = [
    "Camille",
    "Jules",
    "Léa",
    "Hugo",
    "Manon",
    "Louis",
    "Chloé",
    "Nathan",
    "Emma",
    "Lucas",
    "Inès",
    "Théo",
    "Sarah",
    "Adam",
    "Zoé",
    "Paul",
    "Alice",
    "Antoine",
    "Clara",
    "Maxime",
]
_NOMS = [
    "Bernard",
    "Girard",
    "Fontaine",
    "Rousseau",
    "Blanc",
    "Garnier",
    "Chevalier",
    "Robin",
    "Masson",
    "Perrin",
    "Lemoine",
    "Renaud",
    "Barbier",
    "Colin",
    "Marchand",
    "Dupuis",
    "Gauthier",
    "Meunier",
    "Brun",
    "Faure",
]
_TITRES = [
    "Consultant",
    "Consultant senior",
    "Tech lead",
    "Architecte",
    "Data engineer",
    "Chef de projet",
]
_CLIENTS = [
    "Alpha Industries",
    "Beta Santé",
    "Gamma Finance",
    "Delta Retail",
    "Epsilon Energie",
    "Zeta Transport",
    "Eta Assurance",
    "Theta Media",
]

# ── Le SEUL horodatage du jeu de données ────────────────────────────────────
# Fixe, jamais `datetime.now()`. Sans cela, deux exécutions produiraient des
# données différentes et le test « deux runs consécutifs produisent un `raw`
# identique » — critère d'acceptation de la spec — serait impossible à écrire.
_BASE_UPDATE = "2026-01-15T09:00:00Z"


def _slug(valeur: str) -> str:
    """Translittère pour un UPN : NFD puis retrait des diacritiques."""
    decompose = unicodedata.normalize("NFD", valeur)
    sans_accent = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return sans_accent.lower().replace(" ", "-").replace("'", "")


def _upn(prenom: str, nom: str, pris: set[str], domaine: str) -> str:
    """Construit un UPN unique.

    ┌─ LA RÉSOLUTION DE COLLISION N'EST PAS COSMÉTIQUE ──────────────────────┐
    │ Deux « Marie Dupont » DOIVENT obtenir des UPN distincts. Une dérivation │
    │ naïve les effondrerait en une seule identité — et comme tout le modèle  │
    │ d'autorisation est keyé sur l'UPN, cela FUSIONNERAIT LEURS VISIBILITÉS. │
    │ C'est une escalade de privilège réelle, silencieuse, et c'est la raison │
    │ d'être du cas limite « deux employés de même nom complet ».             │
    └─────────────────────────────────────────────────────────────────────────┘
    """
    base = f"{_slug(prenom)}.{_slug(nom)}"
    candidat = f"{base}@{domaine}"
    n = 2
    while candidat in pris:
        candidat = f"{base}{n}@{domaine}"
        n += 1
    pris.add(candidat)
    return candidat


def _resource(
    *,
    ident: int,
    prenom: str,
    nom: str,
    upn: str,
    entite: str,
    manager_upn: str | None,
    statut: str,
    titre: str,
    agency_id: str,
    rng: random.Random,
) -> dict[str, Any]:
    return {
        "id": str(ident),
        "type": "resource",
        "attributes": {
            "firstName": prenom,
            "lastName": nom,
            "email1": upn,
            # L'UPN est la clé de TOUT le modèle d'autorisation. Il est exposé
            # comme un attribut à part entière, et pas seulement déduit de
            # l'e-mail : dans une organisation réelle les deux divergent.
            "upn": upn,
            "title": titre,
            "state": 1 if statut == "actif" else 0,
            "statut": statut,
            "businessUnit": entite,
            "averageDailyPriceExcludingTax": rng.choice([450, 520, 600, 680, 750]),
            "dateOfHiring": f"20{rng.randint(15, 25)}-{rng.randint(1, 12):02d}-01",
            "managerUpn": manager_upn,
            "updateDate": _BASE_UPDATE,
            "isDeleted": False,
        },
        "relationships": {
            "agency": {"data": {"id": agency_id, "type": "agency"}},
            "mainManager": {"data": None},
        },
    }


# ── Les onze porteurs de cas limites ────────────────────────────────────────
# (id, prénom, nom, upn explicite ou None, entité, manager, statut)
_CAS_LIMITES: list[tuple[int, str, str, str | None, str, str | None, str]] = [
    (1, "Claire", "Durand", None, "ENT-FR", None, "actif"),
    (2, "Sophie", "Martin", "sophie.m@{d}", "ENT-FR", "claire.durand@{d}", "actif"),
    (3, "Marc", "Leroy", None, "ENT-FR", "sophie.m@{d}", "actif"),
    (4, "Joël", "François-Mercier", "joël.françois-mercier@{d}", "ENT-BE", "sophie.m@{d}", "actif"),
    (5, "Marie", "Dupont", None, "ENT-FR", "sophie.m@{d}", "actif"),
    (6, "Marie", "Dupont", None, "ENT-BE", "sophie.m@{d}", "actif"),
    (7, "Luc", "Moreau", None, "ENT-BE", "marc.leroy@{d}", "actif"),
    (8, "Anne", "Petit", None, "ENT-FR", "marc.leroy@{d}", "sorti"),
    (9, "Pierre", "Roux", "pierre.roux@ent.lu", "ENT-LU", "claire.durand@{d}", "actif"),
    # id 10 = ext.consultant : membre d'un groupe Entra, ABSENT du SIRH.
    #         Il n'apparaît donc PAS ici — c'est tout le sujet du cas limite.
    (11, "Tom", "Absent", None, "ENT-FR", "sophie.m@{d}", "actif"),
]

# Membre d'un groupe Entra, inconnu du SIRH. Publié pour que le mock Entra
# d'insights360 puisse s'y référer, et qu'un test prouve que la jointure sur
# dim_collaborateur le laisse tomber au lieu de produire une ligne à clé
# inconnue — ce qui ferait dégénérer le prédicat interne en « pas de filtre ».
UPN_ABSENT_DU_SIRH = "ext.consultant@{d}"


def build_insights360_dataset(seed: int = 42, taille: int = 50) -> dict[str, Any]:
    rng = random.Random(seed)
    domaine = settings.upn_domain
    pris: set[str] = set()

    agencies = [
        {
            "id": aid,
            "type": "agency",
            "attributes": {"name": libelle, "code": code, "updateDate": _BASE_UPDATE},
        }
        for aid, code, libelle in ENTITES
    ]
    agency_par_entite = {code: aid for aid, code, _ in ENTITES}

    resources: list[dict[str, Any]] = []

    # ── Temps 1 : les cas limites, à des identifiants FIXES ──────────────────
    for ident, prenom, nom, upn_tpl, entite, manager_tpl, statut in _CAS_LIMITES:
        upn = upn_tpl.format(d=domaine) if upn_tpl else _upn(prenom, nom, pris, domaine)
        pris.add(upn)
        resources.append(
            _resource(
                ident=ident,
                prenom=prenom,
                nom=nom,
                upn=upn,
                entite=entite,
                manager_upn=manager_tpl.format(d=domaine) if manager_tpl else None,
                statut=statut,
                titre=rng.choice(_TITRES),
                agency_id=agency_par_entite[entite],
                rng=rng,
            )
        )

    # ── Temps 2 : les figurants, pour le volume ──────────────────────────────
    # Rattachés aux managers connus, pour que la hiérarchie aplatie ait de la
    # matière au-delà des onze cas nommés.
    managers = [f"sophie.m@{domaine}", f"marc.leroy@{domaine}", f"claire.durand@{domaine}"]
    ident = 12
    while len(resources) < taille:
        prenom = rng.choice(_PRENOMS)
        nom = rng.choice(_NOMS)
        entite = rng.choice(["ENT-FR", "ENT-FR", "ENT-BE", "ENT-LU"])
        resources.append(
            _resource(
                ident=ident,
                prenom=prenom,
                nom=nom,
                upn=_upn(prenom, nom, pris, domaine),
                entite=entite,
                manager_upn=rng.choice(managers),
                statut="actif",
                titre=rng.choice(_TITRES),
                agency_id=agency_par_entite[entite],
                rng=rng,
            )
        )
        ident += 1

    par_upn = {r["attributes"]["upn"]: r for r in resources}

    # Le lien managérial est aussi exprimé en relationship, comme le fait la
    # vraie API — le pipeline peut consommer l'un ou l'autre.
    for r in resources:
        mgr = r["attributes"]["managerUpn"]
        if mgr and mgr in par_upn:
            r["relationships"]["mainManager"] = {
                "data": {"id": par_upn[mgr]["id"], "type": "resource"}
            }

    companies = [
        {
            "id": str(100 + i),
            "type": "company",
            "attributes": {
                "name": nom,
                "businessUnit": rng.choice(["ENT-FR", "ENT-BE", "ENT-LU"]),
                "updateDate": _BASE_UPDATE,
                "isDeleted": False,
            },
        }
        for i, nom in enumerate(_CLIENTS)
    ]

    contacts = [
        {
            "id": str(200 + i),
            "type": "contact",
            "attributes": {
                "firstName": rng.choice(_PRENOMS),
                "lastName": rng.choice(_NOMS),
                "updateDate": _BASE_UPDATE,
                "isDeleted": False,
            },
            "relationships": {"company": {"data": {"id": c["id"], "type": "company"}}},
        }
        for i, c in enumerate(companies)
    ]

    projects = [
        {
            "id": str(300 + i),
            "type": "project",
            "attributes": {
                "name": f"Projet {c['attributes']['name']}",
                "status": "in_progress",
                "updateDate": _BASE_UPDATE,
                "isDeleted": False,
            },
            "relationships": {"company": {"data": {"id": c["id"], "type": "company"}}},
        }
        for i, c in enumerate(companies)
    ]

    deliveries, times_reports, remuneration = _faits(resources, projects, domaine, rng)

    return {
        "agencies": agencies,
        "resources": resources,
        "companies": companies,
        "contacts": contacts,
        "projects": projects,
        "deliveries": deliveries,
        "times_reports": times_reports,
        # Servie hors de /api — cf. app.remuneration_csv et docs/adr/0004.
        "remuneration": remuneration,
        "technical_data": {
            r["id"]: {
                "id": r["id"],
                "type": "technicalData",
                "attributes": {"references": [], "updateDate": _BASE_UPDATE},
            }
            for r in resources
        },
    }


def _faits(
    resources: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    domaine: str,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Missions, CRA et rémunération.

    Deux subtilités portées par le jeu de données :

      • Luc Moreau (id 7) a DEUX lignes de rémunération, d'entités différentes.
        C'est ce qui prouve que le prédicat RLS porte sur l'`entite` de la LIGNE
        DE FAIT, et non sur celle du collaborateur. Un modèle qui joindrait la
        dimension pour retrouver l'entité passerait à côté.

      • Anne Petit (id 8) est SORTIE et conserve son historique. La donnée
        reste, la visibilité disparaît : c'est exactement la distinction que le
        test négatif « un employé sorti ne conserve aucune visibilité » vérifie.
    """
    deliveries: list[dict[str, Any]] = []
    times_reports: list[dict[str, Any]] = []
    remuneration: list[dict[str, Any]] = []

    for r in resources:
        rid = r["id"]
        attrs = r["attributes"]
        entite = attrs["businessUnit"]
        projet = rng.choice(projects)

        deliveries.append(
            {
                # Plage 1000+ : distincte des resources, mais numérique comme chez le
                # fournisseur (JSON:API sérialise les identifiants en chaînes,
                # mais ce sont des nombres).
                "id": str(1000 + int(rid)),
                "type": "delivery",
                "attributes": {
                    "startDate": "2026-01-15",
                    # Une mission sur trois est terminée. Ce n'est pas du
                    # réalisme décoratif : avec un endDate TOUJOURS nul, dlt ne
                    # matérialise pas la colonne, et le modèle aval échoue sur
                    # « column end_date does not exist ». Le schéma produit
                    # dépendrait alors du contenu du jeu de données.
                    "endDate": "2026-06-30" if int(rid) % 3 == 0 else None,
                    "businessUnit": entite,
                    "updateDate": _BASE_UPDATE,
                    "isDeleted": False,
                },
                "relationships": {
                    "resource": {"data": {"id": rid, "type": "resource"}},
                    "project": {"data": {"id": projet["id"], "type": "project"}},
                },
            }
        )

        times_reports.append(
            {
                # Plage 2000+, même logique.
                "id": str(2000 + int(rid)),
                "type": "timesReport",
                "attributes": {
                    "term": "2026-06",
                    "businessUnit": entite,
                    "workedDays": round(rng.uniform(15, 21), 1),
                    "updateDate": _BASE_UPDATE,
                    "isDeleted": False,
                },
                "relationships": {"resource": {"data": {"id": rid, "type": "resource"}}},
            }
        )

        remuneration.append(
            {
                "collaborateur_id": rid,
                "upn": attrs["upn"],
                "entite": entite,
                "periode": "2026-01-01",
                "montant_brut_annuel": rng.choice([45000, 52000, 58000, 71000, 120000]),
            }
        )

    # Luc Moreau : la ligne d'AVANT son changement d'entité, en ENT-FR.
    luc = next((r for r in resources if r["attributes"]["upn"] == f"luc.moreau@{domaine}"), None)
    if luc is not None:
        remuneration.append(
            {
                "collaborateur_id": luc["id"],
                "upn": luc["attributes"]["upn"],
                "entite": "ENT-FR",
                "periode": "2026-07-01",
                "montant_brut_annuel": 49000,
            }
        )

    return deliveries, times_reports, remuneration
