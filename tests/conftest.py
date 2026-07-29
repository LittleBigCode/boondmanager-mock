"""Harnais de tests.

┌─ ISOLATION DES PROFILS ─────────────────────────────────────────────────────┐
│ Deux familles de tests coexistent et exigent des jeux de données DIFFÉRENTS :│
│   • la régression ophelie      → profil `ophelie` (gelé, 24 resources)      │
│   • les capacités nouvelles    → profil `insights360` (50, UPN, cas limites)│
│                                                                             │
│ Se reposer sur une variable d'environnement globale ne marche pas : le      │
│ profil serait décidé par l'ORDRE D'IMPORT des modules de test, ce qui rend  │
│ les échecs irreproductibles en isolation. Chaque fixture force donc son     │
│ profil EXPLICITEMENT à chaque reset.                                        │
└─────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os

# Le plan de contrôle doit être monté au moment de l'import du paquet : le
# montage est conditionnel (`if settings.admin_enabled` dans app.py), donc
# régler la variable après coup n'aurait aucun effet.
os.environ.setdefault("BOOND_MOCK_ADMIN_ENABLED", "true")

import pytest


@pytest.fixture()
def boond_state():
    """L'état mutable du mock, sur le profil GELÉ d'ophelie.

    Le profil est forcé ici et pas via l'environnement : c'est ce qui rend la
    régression ophelie insensible à ce que font les autres modules de test.
    """
    import boondmanager_mock as mock

    mock.state.reset(profile="ophelie")
    yield mock.state
    mock.state.reset(profile="ophelie")
