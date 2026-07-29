"""RÉGRESSION — le fichier de test du mock d'ophelie, PORTÉ VERBATIM.

┌─ CE FICHIER NE S'ADAPTE PAS ────────────────────────────────────────────────┐
│ C'est ophelie/backend/tests/test_boond_mock_api.py, mot pour mot. Les deux  │
│ seules modifications du corps sont les lignes d'import :                    │
│                                                                             │
│   from app.boond import mock_api                → import boondmanager_mock  │
│   from app.boond.client import JWT_HEADER_NAME  → from boondmanager_mock    │
│                                                                             │
│ Cette seconde ligne EST la raison d'être de l'extraction : la suite de      │
│ tests du mock importait jusqu'ici du code de PRODUCTION d'ophelie           │
│ (app/boond/client.py) pour construire son JWT. Le mock publie désormais     │
│ ces deux symboles lui-même.                                                 │
│                                                                             │
│ S'y ajoute une fixture `autouse` de HARNAIS (pas une modification de test)  │
│ qui force le profil GELÉ `ophelie` : sans elle, ces tests hériteraient du   │
│ profil laissé par le module de test précédent et échoueraient selon l'ordre │
│ d'exécution.                                                                │
│                                                                             │
│ S'il échoue, c'est l'extraction qui est infidèle — jamais le test qui est   │
│ périmé. Ne pas ajuster les assertions : corriger le code.                   │
└─────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import pytest as _pytest


@_pytest.fixture(autouse=True)
def _profil_ophelie():
    """Force le profil GELÉ pour chaque test de ce module (harnais, pas test)."""
    import boondmanager_mock as _mock

    _mock.state.reset(profile="ophelie")
    yield
    _mock.state.reset(profile="ophelie")


# ruff: noqa
# ── à partir d'ici : copie verbatim ───────────────────────────────────────────

import base64

import boondmanager_mock as mock_api
from boondmanager_mock import JWT_HEADER_NAME, build_client_jwt
from fastapi.testclient import TestClient

client = TestClient(mock_api.app)

GOOD_JWT = {
    JWT_HEADER_NAME: build_client_jwt("mock-user-token", "mock-client-token", "mock-client-key")
}


def _basic(user: str, password: str) -> dict[str, str]:
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


def test_health_is_public(boond_state):
    assert client.get("/health").status_code == 200


def test_missing_auth_is_401_with_errors_envelope(boond_state):
    resp = client.get("/api/resources")
    assert resp.status_code == 401
    assert resp.json()["errors"][0]["code"] == "401"


def test_bad_jwt_signature_is_422_like_the_real_api(boond_state):
    bad = build_client_jwt("mock-user-token", "mock-client-token", "WRONG-KEY")
    resp = client.get("/api/resources", headers={JWT_HEADER_NAME: bad})
    assert resp.status_code == 422
    assert "Signature verification failed" in resp.json()["errors"][0]["detail"]


def test_wrong_tokens_in_valid_signature_rejected(boond_state):
    forged = build_client_jwt("other-user", "mock-client-token", "mock-client-key")
    assert client.get("/api/resources", headers={JWT_HEADER_NAME: forged}).status_code == 422


def test_good_jwt_lists_resources(boond_state):
    resp = client.get("/api/resources", headers=GOOD_JWT)
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["totals"]["rows"] == 24
    assert body["data"][0]["type"] == "resource"
    attrs = body["data"][0]["attributes"]
    # Target-schema propagation fields: a 3-char trigramme and a grade label.
    assert {"firstName", "lastName", "email1", "trigramme", "grade"} <= set(attrs)
    assert len(attrs["trigramme"]) == 3


def test_resource_trigrammes_are_unique(boond_state):
    body = client.get("/api/resources?maxResults=100", headers=GOOD_JWT).json()
    trigrammes = [item["attributes"]["trigramme"] for item in body["data"]]
    assert len(trigrammes) == 24
    assert len(set(trigrammes)) == 24


def test_basic_auth_accepted(boond_state):
    resp = client.get("/api/companies", headers=_basic("demo@ophelie.dev", "mock-password"))
    assert resp.status_code == 200
    denied = client.get("/api/companies", headers=_basic("demo@ophelie.dev", "nope"))
    assert denied.status_code == 401


def test_pagination_slices_and_reports_totals(boond_state):
    page1 = client.get("/api/resources?page=1&maxResults=10", headers=GOOD_JWT).json()
    page3 = client.get("/api/resources?page=3&maxResults=10", headers=GOOD_JWT).json()
    assert len(page1["data"]) == 10
    assert len(page3["data"]) == 4
    assert page1["meta"]["totals"]["rows"] == 24
    assert page1["data"][0]["id"] != page3["data"][0]["id"]


def test_keywords_filters(boond_state):
    name = boond_state.dataset["companies"][0]["attributes"]["name"]
    body = client.get(f"/api/companies?keywords={name}", headers=GOOD_JWT).json()
    assert body["meta"]["totals"]["rows"] >= 1
    assert all(name in str(item) for item in body["data"])


def test_detail_and_404(boond_state):
    assert client.get("/api/projects/1", headers=GOOD_JWT).json()["data"]["id"] == "1"
    assert client.get("/api/projects/999", headers=GOOD_JWT).status_code == 404


def test_technical_data_has_references(boond_state):
    body = client.get("/api/resources/1/technical-data", headers=GOOD_JWT).json()
    refs = body["data"]["attributes"]["references"]
    assert refs and {"title", "company", "startYear", "description", "skills"} <= set(refs[0])
    # skills is a JSON array (feeds reference_skill directly), not a string.
    assert isinstance(refs[0]["skills"], list)
    assert client.get("/api/resources/999/technical-data", headers=GOOD_JWT).status_code == 404


def test_simulated_outage(boond_state):
    boond_state.fail_collections.add("projects")
    assert client.get("/api/projects", headers=GOOD_JWT).status_code == 500
    assert client.get("/api/companies", headers=GOOD_JWT).status_code == 200


def test_current_user(boond_state):
    body = client.get("/api/application/current-user", headers=GOOD_JWT).json()
    assert body["data"]["type"] == "account"
