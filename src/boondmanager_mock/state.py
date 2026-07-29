"""État mutable du serveur.

L'API publique de cette classe — `state.dataset`, `state.fail_collections`,
`state.reset(seed=…)` — est CONSERVÉE À L'IDENTIQUE. C'est ce qui permet à la
suite de tests d'ophelie de migrer sans être réécrite : ses fixtures appellent
`mock_api.state.reset()` et mutent `state.dataset` directement.

Ce qui est ajouté : le choix du profil de jeu de données, et la remise à la
ligne de base des injections plutôt qu'à vide (voir `reset`).
"""

from __future__ import annotations

from typing import Any

from .injection import engine
from .settings import settings


def build_dataset(seed: int = 42, profile: str | None = None) -> dict[str, Any]:
    """Construit le jeu de données du profil demandé.

    Signature compatible avec l'ancien `build_dataset(seed)` : le profil est un
    paramètre optionnel qui retombe sur la configuration.
    """
    profile = profile or settings.profile
    if profile == "ophelie":
        from .dataset.ophelie import build_ophelie_dataset

        return build_ophelie_dataset(seed)
    if profile == "insights360":
        from .dataset.insights360 import build_insights360_dataset

        return build_insights360_dataset(seed)
    raise ValueError(f"profil de jeu de données inconnu : {profile!r}")


class MockState:
    """État serveur mutable, pour simuler des changements distants et des pannes."""

    def __init__(self) -> None:
        self.dataset: dict[str, Any] = {}
        # Conservé pour compatibilité : c'est le seul levier d'injection du mock
        # d'origine, et les tests d'ophelie s'en servent. Les nouvelles pannes
        # passent par `injection.engine`, qui lui est pilotable par HTTP.
        self.fail_collections: set[str] = set()
        self.profile: str = settings.profile
        self.seed: int = settings.seed
        self.reset()

    def reset(self, seed: int | None = None, profile: str | None = None) -> None:
        """Reconstruit le jeu de données et remet les compteurs à zéro.

        ⚠️ Les règles d'injection sont remises À LA LIGNE DE BASE DÉCLARÉE PAR
        L'ENVIRONNEMENT, et non à vide. La nuance compte : si un `reset` vidait
        les règles, la première requête d'une suite de tests effacerait
        silencieusement une limite de débit configurée au niveau du compose —
        et le test « le 429 est honoré » passerait sans rien avoir testé.
        """
        self.seed = settings.seed if seed is None else seed
        self.profile = profile or settings.profile
        self.dataset = build_dataset(self.seed, self.profile)
        self.fail_collections = set()
        engine.clear()
        engine.reset_counters()
        _apply_baseline_injections()

    def totals(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.dataset.items() if isinstance(v, list)}


def _apply_baseline_injections() -> None:
    """Règles d'injection déclarées par l'environnement, réappliquées à chaque reset.

    Permet à un docker-compose ou à un sidecar Tekton de faire tourner le mock
    en permanence dégradé (limite de débit basse, par exemple) sans qu'un test
    ne l'annule par inadvertance.
    """
    import os

    if (seuil := os.environ.get("BOOND_MOCK_RATE_LIMIT_AFTER")) is not None:
        engine.add(
            kind="rate_limit",
            scope="/api/*",
            after_requests=int(seuil),
            retry_after_seconds=int(os.environ.get("BOOND_MOCK_RETRY_AFTER", "1")),
        )


state = MockState()
