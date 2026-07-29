"""Mock de l'API BoondManager — image container et paquet Python installable.

Extrait de `ophelie/backend/app/boond/mock_api.py`, où il était déjà autonome
par conception (aucun import de `app.*`, ni base ni configuration applicative).

Pourquoi un dépôt à part : deux consommateurs ont besoin du MÊME dialecte —
ophelie (qui l'alimente depuis une intégration production vérifiée) et
insights360 (qui en dépend pour toute sa suite de tests d'extraction). Dupliquer
le mock aurait créé deux dialectes BoondManager divergents dans la même
organisation, c'est-à-dire exactement ce qu'un contrat est censé empêcher.

Deux modes d'utilisation, délibérément maintenus tous les deux :

  • **En process** — `TestClient(boondmanager_mock.app)`. C'est ainsi
    qu'ophelie teste depuis toujours, et la propriété qu'il ne faut pas perdre :
    l'application que la stack interroge EST celle que les tests exercent.

  • **En conteneur** — `python -m boondmanager_mock`. Le mode d'insights360, en
    docker compose comme en sidecar Tekton. C'est ce mode qui rend indispensable
    le plan de contrôle `/__admin` : hors du processus, on ne peut plus muter
    l'état en Python.

Ré-exports pour que rien n'ait besoin de connaître la structure interne :

    app                  l'application FastAPI
    state                l'état mutable (dataset, fail_collections, reset)
    build_dataset        construction du jeu de données
    build_client_jwt     le JWT HS256 de X-Jwt-Client-Boondmanager
    JWT_HEADER_NAME      le nom de cet en-tête

`build_client_jwt` et `JWT_HEADER_NAME` vivaient dans le client de PRODUCTION
d'ophelie, ce qui obligeait la suite de tests du mock à importer du code
applicatif. Les publier ici rompt ce couplage.
"""

from __future__ import annotations

from .app import app, contrat_openapi
from .auth import JWT_HEADER_NAME, build_client_jwt
from .injection import engine
from .settings import settings
from .state import build_dataset, state

__all__ = [
    "JWT_HEADER_NAME",
    "app",
    "build_client_jwt",
    "build_dataset",
    "contrat_openapi",
    "engine",
    "settings",
    "state",
]

__version__ = "0.1.0"
