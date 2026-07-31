"""Authentification — le dialecte exact de BoondManager.

Ce module porte AUSSI `build_client_jwt` et `JWT_HEADER_NAME`, qui vivaient dans
le client de production d'ophelie (`app/boond/client.py`). C'est délibéré : le
fichier de test du mock chez ophelie importait ces deux symboles depuis le
client de production, ce qui couplait le mock au code applicatif. En les
publiant ici, le mock devient testable seul, et les consommateurs (le pipeline
dlt d'insights360, la suite de tests d'ophelie) ont une source unique pour la
construction du jeton.

Le client de PRODUCTION d'ophelie n'est pas déplacé : il reste chez ophelie.

Trois détails du dialecte réel qu'il ne faut pas « simplifier » :

  1. base64url SANS padding. Le padding fait échouer la vérification côté API.
  2. Le payload est EXACTEMENT {"userToken", "clientToken"} — pas d'iat, pas
     d'exp, pas d'iss. C'est un credential statique, pas un jeton de session.
  3. Un JWT présent mais invalide donne **422, pas 401**. C'est ce que fait la
     vraie API, et le code de retour est ce sur quoi une logique de retry se
     décide : un 401 invite à re-tenter avec d'autres identifiants, un 422 dit
     que la requête est malformée.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from .settings import settings

JWT_HEADER_NAME = "X-Jwt-Client-Boondmanager"


def _b64url(raw: bytes) -> str:
    """base64url SANS padding — le `=` final ferait échouer la vérification."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def build_client_jwt(user_token: str, client_token: str, client_key: str) -> str:
    """Le JWT HS256 attendu dans ``X-Jwt-Client-Boondmanager``."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"userToken": user_token, "clientToken": client_token}).encode())
    signature = _b64url(
        hmac.new(client_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def jwt_is_valid(token: str) -> bool:
    """Signature ET revendications.

    Vérifier la seule signature ne suffirait pas : un jeton correctement signé
    portant d'autres tokens serait accepté. La vraie API vérifie les deux.
    """
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        expected = hmac.new(
            settings.client_key.encode(),
            f"{header_b64}.{payload_b64}".encode(),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
            return False
        payload = json.loads(_b64url_decode(payload_b64))
        return bool(
            payload.get("userToken") == settings.user_token
            and payload.get("clientToken") == settings.client_token
        )
    except Exception:
        return False


def basic_is_valid(value: str) -> bool:
    try:
        user, _, password = base64.b64decode(value).decode().partition(":")
    except Exception:
        return False
    return user == settings.basic_user and password == settings.basic_password
