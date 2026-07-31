"""Injection de pannes — le vrai intérêt d'un mock.

« The point of the mock is to reproduce failure modes, not just happy paths »
(spec insights360, §4.1). Le mock d'origine ne savait simuler qu'une panne :
une collection ajoutée à un `set` Python, donc uniquement depuis le même
processus. Dès que le mock tourne en conteneur — ce qui est le cas pour
insights360, en compose comme en sidecar Tekton — cette voie disparaît.

D'où : des règles d'injection déclaratives, pilotables par HTTP (`/__admin`).

Un SEUL point de dispatch, ordonné, évalué AVANT l'authentification, pour que
`auth_reject` puisse préempter. Chaque règle porte un compteur `times`
optionnel : une panne « transitoire » doit cesser d'elle-même, sinon on ne teste
pas un retry, on teste un échec.
"""

from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field
from typing import Any, Literal

Kind = Literal["rate_limit", "status", "latency", "page_drift", "auth_reject", "unstable_order"]


@dataclass
class Rule:
    """Une règle d'injection.

    `scope` est un motif glob sur le chemin (`/api/resources`, `/api/*`, `*`),
    ce qui permet de viser une collection précise sans énumérer ses routes.
    """

    id: str
    kind: Kind
    scope: str = "*"
    # Nombre d'applications restantes. None = illimité. Décrémenté à chaque
    # déclenchement : c'est ce qui fait la différence entre une panne
    # transitoire (que le retry doit absorber) et une panne persistante (qui
    # doit faire échouer le run avec un code de sortie non nul).
    times: int | None = None

    # rate_limit
    after_requests: int = 0
    retry_after_seconds: int = 1
    # status
    status: int = 500
    # latency
    seconds: float = 0.0
    # page_drift
    after_page: int = 1
    mode: Literal["insert", "remove"] = "insert"

    extra: dict[str, Any] = field(default_factory=dict)

    def matches(self, path: str) -> bool:
        return fnmatch.fnmatch(path, self.scope)

    def consume(self) -> bool:
        """Décrémente le compteur. Rend False quand la règle est épuisée."""
        if self.times is None:
            return True
        if self.times <= 0:
            return False
        self.times -= 1
        return True


class InjectionEngine:
    """Le moteur, et le compteur de requêtes par chemin dont il dépend."""

    def __init__(self) -> None:
        self.rules: list[Rule] = []
        self.request_counts: dict[str, int] = {}
        self.last_query_params: dict[str, dict[str, str]] = {}
        self._next_id = 1
        # Horloge virtuelle : permet de tester des fenêtres temporelles sans
        # `sleep`, donc sans rendre la suite lente ni dépendante du timing réel.
        self.clock_offset: float = 0.0

    # ── Gestion des règles ───────────────────────────────────────────────────

    def add(self, **kwargs: Any) -> Rule:
        rule = Rule(id=f"r{self._next_id}", **kwargs)
        self._next_id += 1
        self.rules.append(rule)
        return rule

    def remove(self, rule_id: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        return len(self.rules) != before

    def clear(self) -> None:
        self.rules.clear()

    def reset_counters(self) -> None:
        self.request_counts.clear()
        self.last_query_params.clear()
        self.clock_offset = 0.0

    # ── Observation ──────────────────────────────────────────────────────────

    def observe(self, path: str, params: dict[str, str]) -> int:
        """Enregistre le passage d'une requête et rend son rang (1-based).

        `last_query_params` est porteur : c'est ce qui permet à un consommateur
        de prouver qu'il a bien ENVOYÉ le paramètre incrémental et le tri, au
        lieu de simplement tolérer leur absence. Un pipeline qui aurait oublié
        son curseur passerait sinon tous ses tests.
        """
        self.request_counts[path] = self.request_counts.get(path, 0) + 1
        self.last_query_params[path] = dict(params)
        return self.request_counts[path]

    def now(self) -> float:
        return time.time() + self.clock_offset

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def first(self, kind: Kind, path: str) -> Rule | None:
        """Première règle active du type demandé pour ce chemin."""
        for rule in self.rules:
            if rule.kind == kind and rule.matches(path):
                if rule.times is not None and rule.times <= 0:
                    continue
                return rule
        return None

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r.id,
                "kind": r.kind,
                "scope": r.scope,
                "times_left": r.times,
                **{
                    k: v
                    for k, v in (
                        ("after_requests", r.after_requests),
                        ("retry_after_seconds", r.retry_after_seconds),
                        ("status", r.status),
                        ("seconds", r.seconds),
                        ("after_page", r.after_page),
                        ("mode", r.mode),
                    )
                    if _relevant(r.kind, k)
                },
            }
            for r in self.rules
        ]


_CHAMPS_PAR_KIND: dict[str, set[str]] = {
    "rate_limit": {"after_requests", "retry_after_seconds"},
    "status": {"status"},
    "latency": {"seconds"},
    "page_drift": {"after_page", "mode"},
    "auth_reject": {"status"},
    "unstable_order": set(),
}


def _relevant(kind: str, champ: str) -> bool:
    return champ in _CHAMPS_PAR_KIND.get(kind, set())


engine = InjectionEngine()
