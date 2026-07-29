"""Configuration — tout par variables d'environnement, aucun fichier.

Le mock d'origine lisait ses cinq variables au moment de l'import, ce qui
rendait impossible d'en changer dans un test sans recharger le module. On les
centralise ici, dans un objet relu par `reload()`, tout en gardant EXACTEMENT
les mêmes noms de variables — la migration d'ophelie ne doit toucher aucun
docker-compose ni aucun values Helm.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Valeurs par défaut identiques à celles du mock d'origine : le compose
# d'ophelie et son chart Helm ne fixent que les trois premières.
DEFAULTS: dict[str, str] = {
    "BOOND_MOCK_USER_TOKEN": "mock-user-token",
    "BOOND_MOCK_CLIENT_TOKEN": "mock-client-token",
    "BOOND_MOCK_CLIENT_KEY": "mock-client-key",
    "BOOND_MOCK_BASIC_USER": "demo@ophelie.dev",
    "BOOND_MOCK_BASIC_PASSWORD": "mock-password",
}


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """État de configuration, relu à chaud par `reload()`."""

    user_token: str = ""
    client_token: str = ""
    client_key: str = ""
    basic_user: str = ""
    basic_password: str = ""

    # Le mock d'origine figeait la graine à 42 sans moyen d'en changer autrement
    # qu'en Python. En conteneur, ce n'était plus possible du tout.
    seed: int = 42

    # `ophelie` (gelé, 24 resources) ou `insights360` (50 employés, UPN, cas
    # limites, deliveries et times-reports).
    profile: str = "insights360"

    # Plan de contrôle /__admin. Fermé par défaut : il n'a de sens qu'en test.
    # Le déploiement d'ophelie le laisse à false.
    admin_enabled: bool = False
    admin_token: str = "mock-admin-token"

    # Ordre instable par défaut, sauf tri explicite — c'est le comportement que
    # la spec d'insights360 demande de reproduire. Ce drapeau permet de le
    # désactiver pour du `curl` exploratoire à la main.
    stable_order: bool = False

    # absent | csv | stub — cf. docs/adr/0004.
    compensation_mode: str = "csv"

    upn_domain: str = "ent.fr"

    max_results_cap: int = 500
    default_max_results: int = 30

    extra: dict[str, str] = field(default_factory=dict)

    def reload(self) -> None:
        self.user_token = os.environ.get("BOOND_MOCK_USER_TOKEN", DEFAULTS["BOOND_MOCK_USER_TOKEN"])
        self.client_token = os.environ.get(
            "BOOND_MOCK_CLIENT_TOKEN", DEFAULTS["BOOND_MOCK_CLIENT_TOKEN"]
        )
        self.client_key = os.environ.get("BOOND_MOCK_CLIENT_KEY", DEFAULTS["BOOND_MOCK_CLIENT_KEY"])
        self.basic_user = os.environ.get("BOOND_MOCK_BASIC_USER", DEFAULTS["BOOND_MOCK_BASIC_USER"])
        self.basic_password = os.environ.get(
            "BOOND_MOCK_BASIC_PASSWORD", DEFAULTS["BOOND_MOCK_BASIC_PASSWORD"]
        )
        self.seed = int(os.environ.get("BOOND_MOCK_SEED", "42"))
        self.profile = os.environ.get("BOOND_MOCK_DATASET_PROFILE", "insights360")
        self.admin_enabled = _flag("BOOND_MOCK_ADMIN_ENABLED", False)
        self.admin_token = os.environ.get("BOOND_MOCK_ADMIN_TOKEN", "mock-admin-token")
        self.stable_order = _flag("BOOND_MOCK_STABLE_ORDER", False)
        self.compensation_mode = os.environ.get("BOOND_MOCK_COMPENSATION_MODE", "csv")
        self.upn_domain = os.environ.get("BOOND_MOCK_UPN_DOMAIN", "ent.fr")


settings = Settings()
settings.reload()
