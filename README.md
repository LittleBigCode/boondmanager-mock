# boondmanager-mock

Mock de l'API **BoondManager**, livré à la fois comme **image container** et
comme **paquet Python installable**.

## Pourquoi ce dépôt existe

Un mock BoondManager existait déjà, dans `ophelie/backend/app/boond/mock_api.py`,
adossé à une intégration production **vérifiée** — c'est lui qui documente le
dialecte réel (l'en-tête JWT, le 422 sur signature invalide, l'enveloppe
`meta.totals.rows`). Un second consommateur est arrivé, `insights360`, dont
toute la suite de tests d'extraction en dépend.

Le dupliquer aurait produit deux dialectes BoondManager divergents dans la même
organisation — exactement ce qu'un contrat est censé empêcher. Il est donc
centralisé ici, et les deux dépôts le consomment.

## Deux modes, tous les deux maintenus

```python
# En process — le mode d'ophelie depuis toujours.
from fastapi.testclient import TestClient
import boondmanager_mock as mock

client = TestClient(mock.app, base_url="http://boondmanager-mock/api")
mock.state.reset()
```

La propriété à ne pas perdre : **l'application que la stack interroge est celle
que les tests exercent**. C'est la raison pour laquelle le mock vivait dans le
paquet backend d'ophelie, et le paquet pip la préserve.

```bash
# En conteneur — le mode d'insights360 (compose, sidecar Tekton).
docker run -p 8000:8000 harbor.build.graal.systems/boondmanager-mock/boondmanager-mock:0.1.0
```

C'est ce second mode qui rend indispensable le plan de contrôle `/__admin` :
hors du processus, on ne peut plus muter l'état en Python.

## Le dialecte reproduit

| Aspect | Comportement |
|---|---|
| Authentification | JWT HS256 dans `X-Jwt-Client-Boondmanager`, base64url **sans padding**, payload exactement `{"userToken","clientToken"}`. Basic auth acceptée aussi. |
| Rejet | JWT **absent** → `401`. JWT **présent mais invalide** → `422`, pas 401. |
| Enveloppe | `{"data": [...], "meta": {"totals": {"rows": N}}}` |
| Pagination | `page` (base 1) / `maxResults` (défaut 30, plafond 500) |
| Erreurs | `{"errors": [{"code": "...", "detail": "..."}]}` |
| Collections | `resources`, `companies`, `contacts`, `projects`, `agencies`, `deliveries`, `times-reports` + `resources/{id}/technical-data` + `application/current-user` |

## Modes de panne

« The point of the mock is to reproduce failure modes, not just happy paths. »
Toutes pilotables par HTTP via `/__admin/inject` :

| `kind` | Reproduit |
|---|---|
| `rate_limit` | `429` avec `Retry-After` après N requêtes |
| `status` | `500`/`503` transitoires (compteur `times`) ou persistants |
| `latency` | réponses lentes, pour éprouver les timeouts |
| `page_drift` | un enregistrement rendu sur deux pages consécutives — la cause classique d'une duplication silencieuse |
| `auth_reject` | rejet d'authentification avec le bon code |
| `stable_order` | désactive l'instabilité d'ordre (activée par défaut) |

**L'ordre est instable par défaut**, sauf `sort=` explicite. C'est délibéré : un
pipeline qui « marche » contre un mock trié est un pipeline dont le bug attend
la production.

## Profils de jeu de données

| Profil | Contenu |
|---|---|
| `ophelie` | **Gelé.** 24 resources / 6 agencies / 10 companies / 18 contacts / 14 projects, trigrammes et comptes Keycloak épinglés. C'est ce qui permet à ophelie de migrer sans réécrire une seule assertion. |
| `insights360` | 50 collaborateurs, UPN, trois entités, les huit cas limites de la spec, `deliveries` et `times-reports`. |

## Rémunération : ce qui n'est pas inventé

Aucun endpoint de rémunération par ressource n'est attesté chez BoondManager.
Elle est donc servie comme un **fichier**, sur `/__fixtures/remuneration.csv`,
délibérément **hors de `/api`** pour que personne ne la prenne pour un endpoint
fournisseur. Voir [`docs/adr/0004`](docs/adr/0004-compensation-is-not-a-boond-endpoint.md)
et [`docs/UNVERIFIED-FIELDS.md`](docs/UNVERIFIED-FIELDS.md).

## Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `BOOND_MOCK_USER_TOKEN` | `mock-user-token` | revendication `userToken` du JWT |
| `BOOND_MOCK_CLIENT_TOKEN` | `mock-client-token` | revendication `clientToken` |
| `BOOND_MOCK_CLIENT_KEY` | `mock-client-key` | clé de signature HS256 |
| `BOOND_MOCK_BASIC_USER` / `_PASSWORD` | `demo@ophelie.dev` / `mock-password` | Basic auth |
| `BOOND_MOCK_SEED` | `42` | graine — **nouveau**, le mock d'origine la figeait |
| `BOOND_MOCK_DATASET_PROFILE` | `insights360` | `ophelie` ou `insights360` |
| `BOOND_MOCK_ADMIN_ENABLED` | `false` | monte `/__admin` (absent sinon, pas seulement interdit) |
| `BOOND_MOCK_ADMIN_TOKEN` | `mock-admin-token` | en-tête `X-Mock-Admin-Token` |
| `BOOND_MOCK_STABLE_ORDER` | `false` | désactive l'instabilité d'ordre |
| `BOOND_MOCK_COMPENSATION_MODE` | `csv` | `absent` / `csv` / `stub` |
| `BOOND_MOCK_UPN_DOMAIN` | `ent.fr` | domaine des UPN générés |

## Développement

```bash
make bootstrap   # uv sync
make test        # pytest — dont la régression ophelie portée verbatim
make lint        # ruff + mypy
make contract    # régénère contracts/boondmanager.openapi.yaml
```

`tests/test_ophelie_regression.py` est le fichier de test d'ophelie **porté
verbatim**. Il ne doit jamais être adapté : s'il échoue, c'est l'extraction qui
est infidèle, pas le test qui est périmé.
