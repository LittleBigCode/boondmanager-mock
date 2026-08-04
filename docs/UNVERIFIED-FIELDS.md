---
type: reference
description: The registry of gaps between this mock, the official BoondManager documentation, and the real API as observed — what is attested, what is added, what is approximated.
sources_of_truth:
  - src/boondmanager_mock/models/entities.py
  - src/boondmanager_mock/dataset/realiste.py
  - src/boondmanager_mock/envelope.py
  - src/boondmanager_mock/errors.py
  - src/boondmanager_mock/included.py
review_triggers:
  - contracts/boondmanager.openapi.yaml
  - docs/comparisons/
update_policy: propose
last_verified: 2026-07-31
---

# Gap registry — official RAML × real API × mock

Repository rule: *do not invent BoondManager fields*. Every field flagged
`x-boond-confidence: unverified` or `invented` in the contract **must** appear
here — a test enforces it.

## The hierarchy of evidence

Since v0.3.0 the reference is TWOFOLD, and observation wins:

1. **Observed on the real API** — a tenant running 9.1.78.1, probed on
   2026-07-30/31 with an *owner* user token (replayable report:
   `scripts/compare_real.py`; latest committed run in
   [`docs/comparisons/`](comparisons/)). The 2026-07-31 report shows **zero
   structural difference** across the 19 comparable modules, the error dialect
   and the four profile endpoints.
2. **Documented in the official RAML** (https://doc.boondmanager.com/api-externe/,
   `raml-build/`) — used where the real API showed nothing (module empty on
   the tenant, permissions).

## Attested by OBSERVATION (the bulk of the mock)

- paths, methods and cardinalities: 20 searchable collections; `/absences`,
  `/expenses`, `/times` without a profile endpoint; **`GET /contracts` and
  `GET /deliveries` answering 405** (observed);
- the envelope: full `meta` (`version`, `androidMinVersion`, `iosMinVersion`,
  `isLogged`, `language`, `timestamp`, `login`, `customer`, `totals.rows`) +
  PER-MODULE keys (`solr`, `conditionalFields`, `resetCache`,
  `hasOpportunityAlerts`); per-module `included` reduced shapes as observed;
- **the entire error dialect**: `meta` present even on errors (outside a
  session: `isLogged:false`/`"en"`), entries `{status, code, detail,
  title|source}`, `HTTP {code} ({method} {path})` messages,
  `422 - Signature verification failed` + `source.parameter: xJwtClient`,
  1017 + `source.parameter` per missing parameter on `times-reports`;
- identifiers: numeric strings everywhere, **composite on `/times`**
  (`regular_1`, `exceptional_…`);
- `times-reports`: the `startMonth`/`endMonth` window is REQUIRED;
- the profile endpoints `resources/{id}` (18 attributes, `contracts`
  relationship), `contracts/{id}`, `resources/{id}/administrative`,
  `resources/{id}/technical-data` (type `resource`) — all at zero difference;
- default ordering is STABLE; `sort=updateDate` and `period=updated|created`.

## Behaviour DOCUMENTED but not implemented by the provider

Distinct from the field matrix below: here the API *accepts* something and does
not act on it. Silent, and therefore expensive — a rejected parameter at least
tells the caller something.

| Endpoint | Documented | Observed | Measured |
|---|---|---|---|
| `/times` | `period=updated\|created` + `startDate`/`endDate` filters the collection | **accepted and ignored** — all three filter shapes return the full set (106 976 rows on a production tenant) | 2026-08-04, [comparisons/2026-08-04.md](comparisons/2026-08-04.md) |

The mock reproduces this via `CollectionSpec(..., filtre_periode=False)` and
locks it with `tests/test_ecarts_api_documentation.py`. It is NOT turned into a
`422`: the real API does not reject these parameters, and a consumer seeing an
error would fix a problem that does not exist.

Compounding gap: `times` also has no `updateDate` (see the matrix below). No
timestamp to filter on, and no filter that works — a consumer has **no
incremental path at all** on this collection, and must size its cadence
accordingly.

## The RAML × observed matrix

Fields DOCUMENTED in the RAML that the real API never returned (even with the
owner token) — the mock no longer emits them:

| Module | RAML fields never observed |
|---|---|
| CRM searches (resources, candidates, companies, contacts, opportunities) | `creationSource` (present only on the resources PROFILE) |
| companies | `numberbOfActiveOpportunity` (documented typo field, never served) |
| resources (search) | `icSince`, `icStatus` — the bench is read through `availability: "immediate"` |
| orders | `billableItemTypes`, `requestTimesheetsSignature` |
| contracts (profile) | `probationEndDate`, `renewalProbationEndDate`, `exceptionalScales`, `contractAverageDailyProductionCost`, `forceContractAverageDailyProductionCost` |
| times | `endDate`, `updateDate` |
| absences, roles, times-reports, agencies, poles, business-units, banking-transactions, expenses | `updateDate` |

Gaps the mock KEEPS deliberately (tolerated by `compare_real.py`):

| Gap | Why |
|---|---|
| `orders.creationDate` / `orders.updateDate` | documented in the RAML, and the official `period=updated` incremental cursor on orders needs them — the observed tenant did not return them (version?) |
| `expenses`: `row`, `numberOfKilometers`, `delivery`, `project` always emitted | the real API OMITS empty keys item by item (sparse emission); the mock emits the full RAML shape whenever the value exists |
| `isDeleted` everywhere | mock marker (see below) |

## Still unattested

### 1. `isDeleted` — **mock addition** (`unverified`)

Carried by every item; set to `true` by `POST /__admin/delete`. An incremental
pipeline running a `merge` strategy cannot observe a physical deletion. No
equivalent field exists at the vendor. Profile projections do not carry it —
the flag is read on searches.

### 2. `updatedSince` / `filter[updateDate][gte]` — **mock affordance**

The official way is `period=updated` (DAY granularity). These two parameters
offer a finer cursor that no documentation attests — they only apply to
modules that expose `updateDate`.

### 3. Values of per-module meta keys and of included-only attributes

`solr`, `conditionalFields`, `resetCache`, `hasOpportunityAlerts` (meta) and
`canReadCompany`, `canReadContact`, `invoicesLockingStates`, `workUnitRate`
(included): the KEYS are observed, the VALUES served are plausible (`true`,
`[]`, `1`…) — the exact content is not documented.

### 4. Dictionary integer semantics

`typeOf`, `state`, `civility`, `currency`…: their meaning is per-instance
(`/application/dictionary`). Values are plausible; the exact mapping is not
attested. Never encode a business rule on these integers without the target
tenant's dictionary.

### 5. Profile endpoints of secondary modules

Only resources, projects, contracts, administrative and technical-data have a
profile projection VERIFIED against the real API. The other profile endpoints
(`/invoices/{id}`, `/candidates/{id}`…) serve the search shape — verify them
if a consumer starts relying on them.

### 6. Synthetic civil status

`dateOfBirth`, `nationality`, seniority… in the administrative tab and the
resource profile: official keys, FABRICATED deterministic values.

### 7. Compensation outside `/api`

`/__fixtures/remuneration.csv` — a convenience view derived from the official
`monthlySalary` field of `/contracts/{id}`.

### 8. Time evolution — a mock affordance, not vendor behaviour

The dataset evolves (see `evolution.py`). `BOOND_MOCK_EVOLUTION=false`
freezes everything. The real API moves because humans are working.
