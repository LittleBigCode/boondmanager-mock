"""Harnais de tests.

Deux réglages d'environnement, posés AVANT l'import du paquet (la
configuration est lue à l'import) :

  • le plan de contrôle `/__admin` est monté — le montage est conditionnel ;
  • l'intervalle d'évolution passe à 3600 s : aucun événement ne se déclenche
    au fil de l'horloge murale pendant la suite, même sur une CI lente. Les
    tests d'évolution font défiler le temps EXPLICITEMENT via /__admin/clock —
    c'est ce qui les rend déterministes.
"""

from __future__ import annotations

import os

os.environ.setdefault("BOOND_MOCK_ADMIN_ENABLED", "true")
os.environ.setdefault("BOOND_MOCK_EVOLUTION_INTERVAL", "3600")

import pytest
from fastapi.testclient import TestClient

import boondmanager_mock as mock

JWT = {
    mock.JWT_HEADER_NAME: mock.build_client_jwt(
        "mock-user-token", "mock-client-token", "mock-client-key"
    )
}
ADMIN = {"X-Mock-Admin-Token": "mock-admin-token"}


@pytest.fixture()
def client():
    """Un client sur un état REMIS À NEUF — avant ET après, pour qu'un test ne
    lègue ni règle d'injection ni événement d'évolution au suivant."""
    c = TestClient(mock.app)
    mock.state.reset()
    yield c
    mock.state.reset()


@pytest.fixture()
def boond_state(client):  # noqa: ARG001 — la fixture chaîne le reset
    """L'état mutable du mock, pour les tests qui inspectent le dataset."""
    return mock.state
