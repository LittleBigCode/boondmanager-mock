# boondmanager-mock

Mock of the **BoondManager** API, shipped both as a **container image** and as
an **installable Python package**. Aligned with the official documentation
(the RAML spec at [doc.boondmanager.com/api-externe](https://doc.boondmanager.com/api-externe/))
and **verified against a real instance** (9.1.78.1, probed on 2026-07-30/31):
the latest comparison report — replayable with `scripts/compare_real.py` —
shows **zero structural difference** on every comparable module, error dialect
and profiles included ([`docs/comparisons/`](docs/comparisons/)).

## Start in one command

```bash
# Container, ready to use (admin plane open, evolution active):
docker compose up --build           # or: make up
curl http://localhost:8000/health

# Or locally without Docker:
make bootstrap && make run

# The JWT to query /api:
python -c "from boondmanager_mock import build_client_jwt; \
           print(build_client_jwt('mock-user-token','mock-client-token','mock-client-key'))"
curl -H "X-Jwt-Client-Boondmanager: <jwt>" http://localhost:8000/api/resources
```

The image (152 MB, non-root, built-in healthcheck — `depends_on:
condition: service_healthy` works on the consumer side) is built with
`make image` and can be published as-is:

```bash
docker run -p 8000:8000 -e BOOND_MOCK_ADMIN_ENABLED=true boondmanager-mock:0.3.0
```

## Two modes, both maintained

```python
# In-process — for test suites.
from fastapi.testclient import TestClient
import boondmanager_mock as mock

client = TestClient(mock.app, base_url="http://boondmanager-mock/api")
mock.state.reset()
```

Container mode (above) is the one used by compose files and CI sidecars. The
property to preserve: **the application the stack queries IS the one the tests
exercise.** Container mode is what makes the `/__admin` control plane
essential: outside the process, state can no longer be mutated in Python.

## Served collections

22 collections under `/api`, with the vendor's paths and JSON:API types:

| Search + profile `/{id}` | Search only | Profile only (search → 405, as in production) |
|---|---|---|
| `actions`, `agencies`, `banking-transactions`, `business-units`, `candidates`, `companies`, `contacts`, `invoices`, `opportunities`, `orders`, `payments`, `poles`, `projects`, `purchases`, `resources`, `roles`, `times-reports`² | `absences`, `expenses`, `times` | `contracts`¹, `deliveries`¹ |

Plus `resources/{id}/administrative` (the administrative tab — **THE official
path to contracts**: `contracts` relationship + `included`, then
`GET /contracts/{id}` for the full salary detail; see
[`docs/EXTRACTION.md`](docs/EXTRACTION.md)), `resources/{id}/technical-data`
(the résumé tab) and `application/current-user` (credentials smoke test).

¹ `GET` search does not exist in production (405 observed): the mock replies
405 the same way, and the data is reached through `/{id}` and relationships.
² the `startMonth`/`endMonth` window is REQUIRED — 422 with business code 1017
otherwise, as in production.

## The reproduced dialect

| Aspect | Behaviour |
|---|---|
| Authentication | HS256 JWT in `X-Jwt-Client-Boondmanager`, base64url **without padding**, payload exactly `{"userToken","clientToken"}`. Basic auth accepted too. |
| Rejection | JWT **absent** → `401`. JWT **present but invalid** → `422`, not 401. |
| List envelope | `{"data", "included", "meta"}` — the full observed meta: `version`, `androidMinVersion`, `iosMinVersion`, `isLogged`, `language`, `timestamp`, `login`, `customer`, `totals.rows` + per-module keys (`solr`, `conditionalFields`, `resetCache`, `hasOpportunityAlerts`) |
| Profile envelope | same meta without `totals`; the `resources/{id}`, `projects/{id}`, `contracts/{id}`, `administrative` and `technical-data` profiles serve the REAL PROFILE shapes (≠ search) |
| Errors | the REAL envelope: meta present even on errors (`isLogged:false`/`"en"` outside a session), entries `{status, code, detail, title\|source}`, messages `HTTP 404 (GET /api/…)`, `422 - Signature verification failed` + `source.parameter: xJwtClient`, 1017 per missing parameter |
| `included` | related entities in reduced per-module shapes (agency → `name`, resource → `firstName`/`lastName`…), transitive closure; absent from modules that do not declare it (absences, expenses, agencies, poles, roles) |
| Identifiers | integers **as strings** (`^[1-9][0-9]*$`) — and **composite on `/times`** (`regular_1`, `exceptional_…`), lowercase types (`timesreport`, `bankingtransaction`…) |
| Timestamps | `2026-03-12T09:24:00+0100` — Europe/Paris offset WITHOUT a colon |
| Pagination | `page` (1-based) / `maxResults` (default 30, cap 500) |
| Sorting | `sort` + `order`, dotted paths accepted; **`sort=updateDate` is official** on resources, candidates, companies, contacts, opportunities |
| Incremental | **`period=updated|created` + `startDate`/`endDate`** (official, day granularity); `updatedSince=<ISO-8601>` as a finer-grained mock affordance |

## The dataset: “Boréal Conseil”

ONE dataset, realistic and coherent end to end — a French consulting firm of
34 people, 3 agencies, 4 business units, 6 poles: candidates → hires (chained
fixed-term → permanent contracts, official `monthlySalary`); clients →
contacts → opportunities → won projects → deliveries (daily rate by
seniority) → orders → **monthly invoices computed from the SAME worked days as
the time rows** → banking transactions for the settlements; supplier
purchases → payments; timesheets, absences and expenses attached to their
reports. Every cross-reference resolves — a test enforces it.

Default seed 42 (`BOOND_MOCK_SEED`), rebuild via
`POST /__admin/reset {"seed": 7}`.

The dataset content is deliberately French (names, job titles, action notes):
it mirrors what a real French tenant returns, which keeps comparisons honest.

## Time evolution — for incremental extraction

The dataset **lives**: one scripted event per minute (configurable) — new CRM
actions, enriched profiles, consultants **staffed/unstaffed** (delivery
created or closed, `availability` flipped), invoices settled with their
banking transaction, opportunities advancing, timesheets validated, new
contacts. Every event pushes `updateDate` past the base dataset ceiling: a
`period=updated&startDate=2026-07-14` cursor only sees the delta.

- the SEQUENCE depends only on the seed (replayable); only the NUMBER of
  applied events depends on elapsed time;
- `POST /__admin/clock {"advance_seconds": 3600}` fast-forwards company life
  without waiting;
- `GET /__admin/state` exposes the event journal — proof of what an
  incremental extraction should have seen;
- `BOOND_MOCK_EVOLUTION=false` (or interval 0) freezes everything.

**Ordering is STABLE by default** — that is what the real API does (observed).
Instability remains available as an opt-in (`BOOND_MOCK_STABLE_ORDER=false` or
the `unstable_order` injection) to catch pipelines that paginate without an
explicit sort. See [`docs/features/ordering.md`](docs/features/ordering.md).

## Failure modes

“The point of the mock is to reproduce failure modes, not just happy paths.”
All driveable over HTTP via `/__admin/inject`:

| `kind` | Reproduces |
|---|---|
| `rate_limit` | `429` with `Retry-After` after N requests |
| `status` | transient `500`/`503` (a `times` counter) or persistent ones |
| `latency` | slow responses, to exercise timeouts |
| `page_drift` | one record served on two consecutive pages — the classic cause of silent duplication |
| `auth_reject` | authentication rejection with the right status code |
| `unstable_order` | enables ordering instability (pagination chaos) |

And to simulate source-side changes: `POST /__admin/mutate` (bumps
`updateDate`), `POST /__admin/delete` (logical deletion via `isDeleted`).

## Compensation

Served as a **file**, at `/__fixtures/remuneration.csv`, deliberately
**outside `/api`**. Amounts are derived from the official `monthlySalary`
field of `/api/contracts/{id}` — the CSV remains for consumers that expected
it.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `BOOND_MOCK_USER_TOKEN` | `mock-user-token` | JWT `userToken` claim |
| `BOOND_MOCK_CLIENT_TOKEN` | `mock-client-token` | `clientToken` claim |
| `BOOND_MOCK_CLIENT_KEY` | `mock-client-key` | HS256 signing key |
| `BOOND_MOCK_BASIC_USER` / `_PASSWORD` | `demo@boreal-conseil.example` / `mock-password` | Basic auth |
| `BOOND_MOCK_SEED` | `42` | dataset seed |
| `BOOND_MOCK_EVOLUTION` | `true` | enables time evolution |
| `BOOND_MOCK_EVOLUTION_INTERVAL` | `60` | seconds between two events |
| `BOOND_MOCK_ADMIN_ENABLED` | `false` | mounts `/__admin` (absent otherwise, not merely forbidden) |
| `BOOND_MOCK_ADMIN_TOKEN` | `mock-admin-token` | `X-Mock-Admin-Token` header |
| `BOOND_MOCK_STABLE_ORDER` | `true` | stable ordering (like production); `false` = pagination chaos |
| `BOOND_MOCK_CUSTOMER` | `boreal-conseil` | tenant announced in `meta.customer` |
| `BOOND_MOCK_FORBIDDEN_COLLECTIONS` | — | collections answered with 403 — simulates a narrow-perimeter user token |
| `BOOND_MOCK_COMPENSATION_MODE` | `csv` | `absent` / `csv` |
| `BOOND_MOCK_RATE_LIMIT_AFTER` | — | permanent rate limit (reset baseline) |

Since 0.2.0, the `ophelie`/`insights360` profiles and their variables
(`BOOND_MOCK_DATASET_PROFILE`, `BOOND_MOCK_UPN_DOMAIN`) are gone: one single
dataset, more complete than both combined.

## Development

```bash
make bootstrap   # uv sync
make test        # pytest — dialect, 22 collections, evolution, failure modes
make lint        # ruff + strict mypy
make contract    # regenerates contracts/boondmanager.openapi.yaml
make run         # local uvicorn, admin plane open
```

### Replaying the comparison against a real instance

```bash
export BOOND_REAL_CLIENT_TOKEN=… BOOND_REAL_CLIENT_KEY=… BOOND_REAL_USER_TOKEN=…
make run &  # or docker compose up
python scripts/compare_real.py --output docs/comparisons/$(date +%F).md
```

GET only, structures only (keys, types, status codes — never a business
value): the report is safe to commit. The only differences shown should be the
documented ones from the matrix in
[`docs/UNVERIFIED-FIELDS.md`](docs/UNVERIFIED-FIELDS.md).

The committed OpenAPI contract describes the served dialect; any field not
backed by the official documentation or by live observation is flagged
`x-boond-confidence: unverified` and recorded in the registry — a test fails
otherwise.
