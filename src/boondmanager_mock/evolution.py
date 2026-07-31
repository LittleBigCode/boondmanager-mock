"""Évolution temporelle du jeu de données — pour éprouver l'extraction incrémentale.

Un extracteur incrémental ne se teste pas contre un jeu de données figé : il
faut que des enregistrements CHANGENT entre deux exécutions, sinon le curseur
(`period=updated`, `sort=updateDate`, `updatedSince`) passe tous les tests sans
avoir rien filtré. Ce module fait vivre l'ESN entre deux requêtes :

  cadence     un événement toutes les `BOOND_MOCK_EVOLUTION_INTERVAL` secondes
              (60 par défaut ; 0 ou BOOND_MOCK_EVOLUTION=false pour figer) ;
  événements  nouvelles actions CRM, mise à jour de profils, STAFFING et
              DÉSTAFFING de consultants (mission créée ou terminée, `icStatus`
              basculé), factures réglées (+ la transaction bancaire qui
              arrive), opportunités qui avancent, CRA validés, nouveaux
              contacts ;
  horloge     `engine.now()` — donc `POST /__admin/clock {advance_seconds}`
              fait défiler la vie de l'entreprise sans attendre, exactement
              comme pour les fenêtres de limite de débit.

DÉTERMINISME : la SÉQUENCE d'événements ne dépend que de la graine — l'événement
k tire son aléa de `Random(f"{seed}:{k}")` et son horodatage vaut toujours
ÉPOQUE + (k+1) x intervalle. Deux serveurs démarrés avec la même graine servent
donc les mêmes données au même âge. Ce qui dépend du temps réel, c'est combien
d'événements sont déjà appliqués — c'est le but : deux extractions successives
voient un delta, et `meta.totals.rows` bouge comme chez le fournisseur.

Chaque événement pousse `updateDate` des enregistrements touchés à son
horodatage (postérieur au plafond du jeu de base) : un curseur incrémental posé
après la construction ne revoit QUE ce qui a bougé.
"""

from __future__ import annotations

import copy
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from .settings import settings

#: L'époque des événements : l'ancre du jeu de données, 9 h heure de Paris.
#: Tous les horodatages d'évolution sont STRICTEMENT postérieurs au plafond
#: des `updateDate` du jeu de base (2026-07-12) — c'est ce qui rend le delta
#: incrémental propre.
EPOQUE = datetime(2026, 7, 15, 9, 0, 0, tzinfo=timezone(timedelta(hours=2)))

#: Le cycle des événements. `staffing` alterne de lui-même entre « staffé » et
#: « déstaffé » selon l'état du banc au moment où il se déclenche.
CYCLE = (
    "action",
    "profil",
    "staffing",
    "facture",
    "action",
    "opportunite",
    "cra",
    "contact",
)

_TEXTES_ACTION = (
    "Appel de suivi — prochaines échéances passées en revue.",
    "Point hebdomadaire avec le client, plan de charge confirmé.",
    "Envoi du compte rendu d'atelier et des prochaines étapes.",
    "Qualification d'un nouveau besoin exprimé par le client.",
    "Relance sur la proposition en attente de décision.",
)

_COMPETENCES_EVOLUTION = ("DuckDB", "Rust", "LangChain", "OpenTelemetry", "Iceberg", "Dagster")

_PRENOMS_CONTACT = ("Margaux", "Étienne", "Salomé", "Corentin", "Awa", "Baptiste")
_NOMS_CONTACT = ("Vasseur", "Lefevre", "Nguyen", "Da Silva", "Kaddour", "Petit")


def _ts(secondes: float) -> str:
    return (EPOQUE + timedelta(seconds=secondes)).strftime("%Y-%m-%dT%H:%M:%S%z")


def _jour(secondes: float) -> str:
    return (EPOQUE + timedelta(seconds=secondes)).strftime("%Y-%m-%d")


def _prochain_id(items: list[dict[str, Any]]) -> str:
    return str(max((int(i["id"]) for i in items), default=0) + 1)


def _actifs(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Les consultants actifs (ni direction, ni managers, ni sortis)."""
    return [
        r for r in dataset["resources"] if int(r["id"]) >= 7 and r["attributes"].get("state") == 1
    ]


def _au_banc(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Le banc d'intercontrat — `availability: "immediate"`, champ OBSERVÉ en
    réel (les icStatus/icSince du RAML ne sont jamais renvoyés)."""
    return [r for r in _actifs(dataset) if r["attributes"].get("availability") == "immediate"]


class Evolution:
    """La chronologie d'événements d'une instance, réarmée à chaque reset."""

    def __init__(self, seed: int, demarrage: float) -> None:
        self.seed = seed
        self.demarrage = demarrage
        self.appliques = 0
        self.journal: list[dict[str, Any]] = []
        self._verrou = threading.Lock()

    # ── Pilotage ─────────────────────────────────────────────────────────────

    def avancer(self, dataset: dict[str, Any], maintenant: float) -> int:
        """Applique tous les événements devenus dus ; rend leur NOMBRE (pour
        l'invalidation des caches). Idempotent et verrouillé — les handlers
        FastAPI tournent dans un pool de threads."""
        if not settings.evolution_enabled or settings.evolution_interval <= 0:
            return 0
        dus = int((maintenant - self.demarrage) // settings.evolution_interval)
        if dus <= self.appliques:
            return 0
        appliques_ici = 0
        with self._verrou:
            while self.appliques < dus:
                k = self.appliques
                age = (k + 1) * settings.evolution_interval
                detail = self._appliquer(dataset, k, age)
                self.journal.append(
                    {"index": k, "at": _ts(age), "kind": CYCLE[k % len(CYCLE)], "detail": detail}
                )
                del self.journal[:-50]
                self.appliques += 1
                appliques_ici += 1
        return appliques_ici

    def apercu(self) -> dict[str, Any]:
        """Ce que /__admin/state expose — l'observabilité du delta."""
        return {
            "enabled": settings.evolution_enabled and settings.evolution_interval > 0,
            "interval_seconds": settings.evolution_interval,
            "applied": self.appliques,
            "journal": self.journal[-20:],
        }

    # ── Les événements ───────────────────────────────────────────────────────

    def _appliquer(self, dataset: dict[str, Any], k: int, age: float) -> str:
        rng = random.Random(f"{self.seed}:{k}")
        genre = CYCLE[k % len(CYCLE)]
        gestionnaires = {
            "action": self._action,
            "profil": self._profil,
            "staffing": self._staffing,
            "facture": self._facture,
            "opportunite": self._opportunite,
            "cra": self._cra,
            "contact": self._contact,
        }
        detail = gestionnaires[genre](dataset, rng, k, age)
        # Un gestionnaire sans matière (plus de facture à régler, plus de CRA à
        # valider…) retombe sur l'événement le plus neutre : une action CRM.
        return detail or self._action(dataset, rng, k, age)

    def _nouvelle_action(
        self,
        dataset: dict[str, Any],
        rng: random.Random,
        age: float,
        *,
        cible_type: str,
        cible_id: str,
        texte: str,
        societe_id: str | None,
    ) -> str:
        ident = _prochain_id(dataset["actions"])
        dataset["actions"].append(
            {
                "id": ident,
                "type": "action",
                "attributes": {
                    "startDate": _ts(age),
                    "creationDate": _ts(age),
                    "typeOf": rng.choice([1, 2, 3, 5]),
                    "text": texte,
                    "numberOfFiles": 0,
                    "canReadAction": True,
                    "canWriteAction": True,
                    "updateDate": _ts(age),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": {"data": {"id": str(rng.choice((2, 3, 5))), "type": "resource"}},
                    "dependsOn": {"data": {"id": cible_id, "type": cible_type}},
                    "company": {
                        "data": {"id": societe_id, "type": "company"} if societe_id else None
                    },
                    "relatedActions": {"data": []},
                },
            }
        )
        return f"action {ident} ({cible_type} {cible_id})"

    def _action(self, dataset: dict[str, Any], rng: random.Random, k: int, age: float) -> str:
        contacts = dataset["contacts"]
        if not contacts:
            return "aucune cible"
        contact = contacts[k % len(contacts)]
        return self._nouvelle_action(
            dataset,
            rng,
            age,
            cible_type="contact",
            cible_id=contact["id"],
            texte=rng.choice(_TEXTES_ACTION),
            societe_id=contact["relationships"]["company"]["data"]["id"],
        )

    def _profil(self, dataset: dict[str, Any], rng: random.Random, k: int, age: float) -> str:
        actifs = _actifs(dataset)
        if not actifs:
            return ""
        res = actifs[k % len(actifs)]
        attrs = res["attributes"]
        nouvelle = rng.choice(_COMPETENCES_EVOLUTION)
        if nouvelle not in attrs.get("skills", ""):
            attrs["skills"] = f"{attrs['skills']}, {nouvelle}" if attrs.get("skills") else nouvelle
            attrs["tools"] = [
                *attrs.get("tools", []),
                {"tool": nouvelle, "level": rng.randint(2, 4)},
            ]
        attrs["numberOfResumes"] = (attrs.get("numberOfResumes") or 0) + 1
        attrs["updateDate"] = _ts(age)
        return f"profil ressource {res['id']} ({nouvelle})"

    def _staffing(self, dataset: dict[str, Any], rng: random.Random, _k: int, age: float) -> str:
        """Le cœur du réalisme incrémental : le banc bouge dans les deux sens."""
        jour = _jour(age)
        banc = _au_banc(dataset)
        if banc:
            return self._staffer(dataset, rng, banc[0], jour, age)
        return self._destaffer(dataset, rng, jour, age)

    def _staffer(
        self,
        dataset: dict[str, Any],
        rng: random.Random,
        res: dict[str, Any],
        jour: str,
        age: float,
    ) -> str:
        en_cours = [
            p
            for p in dataset["projects"]
            if p["attributes"]["startDate"] <= jour <= p["attributes"]["endDate"]
        ]
        if not en_cours:
            return ""
        projet = rng.choice(en_cours)
        modele = next(
            (
                m
                for m in dataset["deliveries"]
                if m["relationships"]["project"]["data"]["id"] == projet["id"]
            ),
            dataset["deliveries"][0],
        )
        mission = copy.deepcopy(modele)
        mission["id"] = _prochain_id(dataset["deliveries"])
        tjm = res["attributes"].get("averageDailyPriceExcludingTax") or 650.0
        fin = projet["attributes"]["endDate"]
        jours_prevus = 40.0
        attrs = mission["attributes"]
        attrs.update(
            {
                "startDate": jour,
                "endDate": fin,
                "title": res["attributes"]["title"],
                "state": 1,
                "averageDailyPriceExcludingTax": tjm,
                "averageDailyCost": round(tjm * 0.58, 2),
                "averageDailyContractCost": round(tjm * 0.58, 2),
                "numberOfDaysInvoicedOrQuantity": jours_prevus,
                "turnoverSimulatedExcludingTax": round(tjm * jours_prevus, 2),
                "costsSimulatedExcludingTax": round(tjm * 0.58 * jours_prevus, 2),
                "marginSimulatedExcludingTax": round(tjm * 0.42 * jours_prevus, 2),
                "creationDate": _ts(age),
                "updateDate": _ts(age),
            }
        )
        mission["relationships"] = {
            "project": {"data": {"id": projet["id"], "type": "project"}},
            "dependsOn": {"data": {"id": res["id"], "type": "resource"}},
            "purchase": {"data": None},
        }
        dataset["deliveries"].append(mission)

        res["attributes"].update(
            {
                "availability": fin,
                "realAvailability": "",
                "numberOfActivePositionings": 0,
                "updateDate": _ts(age),
            }
        )
        self._nouvelle_action(
            dataset,
            rng,
            age,
            cible_type="resource",
            cible_id=res["id"],
            texte=f"Positionnement confirmé — démarrage sur {projet['attributes']['reference']}.",
            societe_id=projet["relationships"]["company"]["data"]["id"],
        )
        return f"ressource {res['id']} staffée sur projet {projet['id']} (mission {mission['id']})"

    def _destaffer(self, dataset: dict[str, Any], rng: random.Random, jour: str, age: float) -> str:
        candidates = [
            m
            for m in dataset["deliveries"]
            if m["attributes"]["state"] == 1
            and m["attributes"]["endDate"] > jour
            and m["relationships"]["dependsOn"]["data"] is not None
            and m["relationships"]["dependsOn"]["data"]["type"] == "resource"
        ]
        if not candidates:
            return ""
        mission = rng.choice(candidates)
        res_id = mission["relationships"]["dependsOn"]["data"]["id"]
        res = next(r for r in dataset["resources"] if r["id"] == res_id)
        mission["attributes"].update({"endDate": jour, "state": 2, "updateDate": _ts(age)})
        res["attributes"].update(
            {
                "availability": "immediate",
                "realAvailability": jour,
                "numberOfActivePositionings": rng.randint(1, 2),
                "updateDate": _ts(age),
            }
        )
        self._nouvelle_action(
            dataset,
            rng,
            age,
            cible_type="resource",
            cible_id=res["id"],
            texte="Fin de mission anticipée — retour en intercontrat, recherche de positionnement.",
            societe_id=None,
        )
        return f"ressource {res_id} déstaffée (mission {mission['id']} close)"

    def _facture(self, dataset: dict[str, Any], _rng: random.Random, _k: int, age: float) -> str:
        en_attente = [
            f
            for f in dataset["invoices"]
            if f["attributes"]["state"] == 1 and not f["attributes"]["isCreditNote"]
        ]
        if not en_attente:
            return ""
        facture = en_attente[0]
        attrs = facture["attributes"]
        attrs.update(
            {
                "state": 2,
                "sendingState": 2,
                "closed": True,
                "performedPaymentDate": _jour(age),
                "updateDate": _ts(age),
            }
        )
        ident = _prochain_id(dataset["banking_transactions"])
        dataset["banking_transactions"].append(
            {
                "id": ident,
                "type": "bankingtransaction",
                "attributes": {
                    "amount": attrs["totalPayableIncludingTax"],
                    "currency": 0,
                    "date": _ts(age),
                    "numberOfInvoices": 0,
                    "title": f"VIR SEPA {attrs['reference']}",
                    "state": 0,
                    "totalAmountToReconcile": attrs["totalPayableIncludingTax"],
                    "canReadTransaction": True,
                    "canWriteTransaction": True,
                    "canReconcile": True,
                    "isDeleted": False,
                },
                "relationships": {"account": {"data": {"id": "1", "type": "bankingaccount"}}},
            }
        )
        return f"facture {facture['id']} réglée (transaction {ident})"

    def _opportunite(self, dataset: dict[str, Any], _rng: random.Random, k: int, age: float) -> str:
        ouvertes = [o for o in dataset["opportunities"] if o["attributes"]["state"] in (1, 2, 3)]
        if not ouvertes:
            return ""
        opp = ouvertes[k % len(ouvertes)]
        attrs = opp["attributes"]
        attrs["state"] += 1
        attrs["updateDate"] = _ts(age)
        if attrs["state"] == 4:  # gagnée
            attrs["closingDate"] = _jour(age)
            attrs["turnoverWeightedExcludingTax"] = attrs["turnoverEstimatedExcludingTax"]
            societe_id = opp["relationships"]["company"]["data"]["id"]
            societe = next(s for s in dataset["companies"] if s["id"] == societe_id)
            societe["attributes"]["updateDate"] = _ts(age)
            return f"opportunité {opp['id']} gagnée"
        return f"opportunité {opp['id']} avance (état {attrs['state']})"

    def _cra(self, dataset: dict[str, Any], _rng: random.Random, _k: int, _age: float) -> str:
        en_attente = [
            t
            for t in dataset["times_reports"]
            if t["attributes"]["state"] in ("waitingForValidation", "savedAndNoValidation")
        ]
        if not en_attente:
            return ""
        cra = en_attente[0]
        cra["attributes"]["state"] = "validated"
        return f"CRA {cra['id']} validé ({cra['attributes']['term']})"

    def _contact(self, dataset: dict[str, Any], rng: random.Random, k: int, age: float) -> str:
        clients = [s for s in dataset["companies"] if int(s["id"]) <= 10]
        if not clients:
            return ""
        societe = clients[k % len(clients)]
        prenom = rng.choice(_PRENOMS_CONTACT)
        nom = rng.choice(_NOMS_CONTACT)
        domaine = societe["attributes"]["website"].removeprefix("https://")
        ident = _prochain_id(dataset["contacts"])
        dataset["contacts"].append(
            {
                "id": ident,
                "type": "contact",
                "attributes": {
                    "creationDate": _ts(age),
                    "civility": rng.randint(0, 1),
                    "thumbnail": "",
                    "firstName": prenom,
                    "lastName": nom,
                    "state": 1,
                    "function": rng.choice(["Product Manager", "Responsable BI", "Architecte SI"]),
                    "department": "Direction des systèmes d'information",
                    "email1": f"{prenom.lower()}.{nom.lower().replace(' ', '')}@{domaine}",
                    "email2": "",
                    "email3": "",
                    "phone1": "",
                    "phone2": "",
                    "town": societe["attributes"]["town"],
                    "country": societe["attributes"]["country"],
                    "canReadContact": True,
                    "canWriteContact": True,
                    "canShowAction": True,
                    "typesOf": [],
                    "socialNetworks": [],
                    "updateDate": _ts(age),
                    "isDeleted": False,
                },
                "relationships": {
                    "mainManager": societe["relationships"]["mainManager"],
                    "company": {"data": {"id": societe["id"], "type": "company"}},
                    "agency": societe["relationships"]["agency"],
                    "pole": societe["relationships"]["pole"],
                },
            }
        )
        return f"contact {ident} créé chez {societe['attributes']['name']}"
