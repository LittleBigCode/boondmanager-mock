---
type: features
description: Pagination ordering — stable by default like the real API, with opt-in instability, and the client bug it once revealed.
sources_of_truth:
  - src/boondmanager_mock/envelope.py
review_triggers:
  - src/boondmanager_mock/envelope.py
  - src/boondmanager_mock/dataset/**
update_policy: auto
last_verified: 2026-07-31
---

# Pagination ordering

## What the mock does

| Situation | Order |
|---|---|
| `sort=<field>` provided | **stable**, sorted on that field (`order=asc\|desc`, dotted paths accepted: `workUnitType.reference`) |
| no `sort` (default) | **STABLE** — aligned with the observed real API (2026-07-31: two identical calls, same sequence) |
| `BOOND_MOCK_STABLE_ORDER=false` | unstable — pagination chaos, as an opt-in |
| injection `{"kind": "unstable_order"}` | unstable, for the duration of a test |

Instability is deterministic within a given test — `hash((request rank, id))`
— hence reproducible, while genuinely varying from one request to the next.

## Why instability remains available (opt-in)

An API that does not guarantee result ordering **skips records and duplicates
others** as soon as you paginate without an explicit sort. The mechanism is
simple: if the order changes between the page-1 and page-2 requests, an
element that was at the end of page 1 can reappear at the start of page 2
(served twice), while its neighbour disappears.

Nothing signals it. No error, no warning — just incomplete data that looks
complete.

The mock's default is now STABLE — because that is what the real API showed,
and fidelity comes first now that the mock doubles as a comparison bench. But
a robust pipeline must survive instability: enabling chaos mode before
signing off an extractor remains best practice.

## What it revealed, immediately

When the mock was first extracted from its original repository, the production
client's pagination test failed:

```
assert len({item["id"] for item in items}) == 24
E   AssertionError: assert 18 == 24
```

**Eighteen resources out of twenty-four.** That client paginated with `page`
and `maxResults` **without ever sending a sort**. Against an unstable mock it
lost six records out of twenty-four. That is not a mock artefact: it is how
that client would behave against any API that does not guarantee its ordering.

## What a correct consumer does

Always send a sort:

```python
params = {"page": page, "maxResults": page_size, "sort": "id", "order": "asc"}
```

Sorting on the identifier: stable, present everywhere, independent of business
content. And verify it **server-side**, via `GET /__admin/state` →
`last_query_params_by_path` — because a client that forgot its sort would
otherwise pass every other test.

## Official sort keys

The BoondManager documentation publishes a `sortList` per module. The ones
that matter for incremental extraction: **`updateDate` is an official sort key
on resources, candidates, companies, contacts and opportunities**
(`creationDate` on several others). Combined with the official
`period=updated&startDate&endDate` filter, that is the vendor's incremental
toolkit — both are implemented here. The mock sorts on any attribute: an
acknowledged superset, documented in `docs/UNVERIFIED-FIELDS.md`.
