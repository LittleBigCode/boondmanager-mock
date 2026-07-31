#!/usr/bin/env python3
"""Compare the mock against a REAL BoondManager instance, module by module.

Replayable whenever the mock or the vendor evolves:

    export BOOND_REAL_CLIENT_TOKEN=…  BOOND_REAL_CLIENT_KEY=…  BOOND_REAL_USER_TOKEN=…
    python scripts/compare_real.py --output docs/comparisons/$(date +%F).md

The script only issues GETs, and the report only contains structures (key
names, JSON:API types, status codes) — never a business value: it can be
committed without leaking any tenant data.

What is compared, for every accessible module:
  • the HTTP status and the `meta` keys;
  • the attribute and relationship keys of the first item;
  • the reduced `included` shapes (type → keys);
  • the error dialect (401, invalid JWT 422, 404, 405).

EXPECTED gaps (documented in docs/UNVERIFIED-FIELDS.md): `isDeleted` (mock
marker) and the fields listed in the RAML x observed matrix.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

MODULES: list[tuple[str, dict[str, str]]] = [
    ("absences", {}),
    ("actions", {}),
    ("agencies", {}),
    ("banking-transactions", {}),
    ("business-units", {}),
    ("candidates", {}),
    ("companies", {}),
    ("contacts", {}),
    ("expenses", {}),
    ("invoices", {}),
    ("opportunities", {}),
    ("orders", {}),
    ("payments", {}),
    ("poles", {}),
    ("projects", {}),
    ("purchases", {}),
    ("resources", {}),
    ("roles", {}),
    ("times", {}),
    ("times-reports", {"startMonth": "2026-05", "endMonth": "2026-07"}),
]

#: Timesheet window on the real side: wide, to find rows on the tenant.
REAL_WINDOW = {"startMonth": "2025-01", "endMonth": "2026-12"}

#: DOCUMENTED gaps (see the matrix in docs/UNVERIFIED-FIELDS.md) — reported
#: separately:
#:   orders   : creationDate/updateDate kept for the incremental cursor;
#:   expenses : the real API omits empty keys item by item (sparse emission).
TOLERATED: dict[str, set[str]] = {
    "orders": {"creationDate", "updateDate"},
    "expenses": {"delivery", "numberOfKilometers", "project", "row", "batch", "guestResources"},
}


def jwt_client(user_token: str, client_token: str, client_key: str) -> str:
    """The dialect's HS256 JWT: base64url WITHOUT padding, minimal payload."""

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"userToken": user_token, "clientToken": client_token}).encode())
    signature = b64(
        hmac.new(client_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


class Side:
    """One side of the comparison (real or mock)."""

    def __init__(self, name: str, base: str, jwt: str, pause: float = 0.0) -> None:
        self.name = name
        self.base = base.rstrip("/")
        self.jwt = jwt
        self.pause = pause
        self.rid: str | None = None

    def get(
        self, path: str, params: dict[str, str] | None = None, jwt: str | None = None
    ) -> tuple[int, Any]:
        target = f"{self.base}/{path}"
        if params:
            target += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        request = urllib.request.Request(target)
        token = self.jwt if jwt is None else jwt
        if token:
            request.add_header("X-Jwt-Client-Boondmanager", token)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                code, body = response.status, response.read().decode()
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read().decode()
        except Exception as e:
            return -1, {"__error__": str(e)}
        if self.pause:
            time.sleep(self.pause)
        try:
            return code, json.loads(body)
        except Exception:
            return code, {"__non_json__": body[:80]}


def summarize(code: int, body: Any) -> dict[str, Any]:
    """The STRUCTURE of a response — no business value whatsoever."""
    if not isinstance(body, dict):
        return {"status": code}
    if "errors" in body:
        first = body["errors"][0] if body["errors"] else {}
        return {"status": code, "error": {k: first.get(k) for k in ("status", "code")}}
    summary: dict[str, Any] = {"status": code, "meta": sorted(body.get("meta", {}))}
    data = body.get("data")
    if isinstance(data, list) and data:
        summary["type"] = data[0].get("type")
        summary["attrs"] = sorted(data[0].get("attributes", {}))
        summary["rels"] = sorted(data[0].get("relationships", {}) or {})
    elif isinstance(data, dict):
        summary["type"] = data.get("type")
        summary["attrs"] = sorted(data.get("attributes", {}))
        summary["rels"] = sorted(data.get("relationships", {}) or {})
    included: dict[str, list[str]] = {}
    for entity in body.get("included", []) or []:
        shape = sorted(entity.get("attributes", {}))
        included.setdefault(entity["type"], shape)
    if "included" in body:
        summary["included"] = included
    return summary


def diff_keys(
    label: str,
    real: list[str] | None,
    mock: list[str] | None,
    lines: list[str],
    tolerated: set[str] | None = None,
) -> None:
    if real is None or mock is None:
        return
    tolerated = tolerated or set()
    gap = (set(mock) ^ set(real)) - {"isDeleted"}
    documented = sorted(gap & tolerated)
    extra = sorted(set(mock) - set(real) - {"isDeleted"} - tolerated)
    missing = sorted(set(real) - set(mock) - tolerated)
    if extra:
        lines.append(f"  - {label} — mock EXTRA: `{', '.join(extra)}`")
    if missing:
        lines.append(f"  - {label} — mock MISSING: `{', '.join(missing)}`")
    if documented:
        lines.append(
            f"  - {label} — documented gap (UNVERIFIED-FIELDS matrix): `{', '.join(documented)}`"
        )


def compare_module(
    path: str, params: dict[str, str], real: Side, mock: Side, lines: list[str]
) -> None:
    real_params = REAL_WINDOW if path == "times-reports" else params
    code_r, body_r = real.get(path, {**real_params, "maxResults": "2"})
    code_m, body_m = mock.get(path, {**params, "maxResults": "2"})
    r, m = summarize(code_r, body_r), summarize(code_m, body_m)

    if "error" in r:
        lines.append(f"### /{path}\n- real side inaccessible ({r['status']}) — module skipped")
        return
    header = [f"### /{path}", f"- statuses: real {r['status']} / mock {m['status']}"]
    if r["status"] == 200 and "type" not in r:
        lines.extend(header)
        lines.append("- ⚪ no data on this tenant — shapes not comparable")
        lines.append("")
        return
    detail: list[str] = []
    if r.get("type") != m.get("type"):
        detail.append(f"  - type: real `{r.get('type')}` / mock `{m.get('type')}`")
    diff_keys("meta", r.get("meta"), m.get("meta"), detail)
    diff_keys("attributes", r.get("attrs"), m.get("attrs"), detail, TOLERATED.get(path))
    diff_keys("relationships", r.get("rels"), m.get("rels"), detail)
    for type_, shape in (r.get("included") or {}).items():
        diff_keys(f"included `{type_}`", shape, (m.get("included") or {}).get(type_), detail)
    lines.extend(header)
    raw = [line for line in detail if "documented gap" not in line]
    if raw:
        lines.append("- gaps:")
        lines.extend(detail)
    elif detail:
        lines.append("- ✅ conforming, documented gaps only:")
        lines.extend(detail)
    else:
        lines.append("- ✅ no structural difference")
    lines.append("")


def compare_errors(real: Side, mock: Side, lines: list[str]) -> None:
    lines.append("### Error dialect")
    cases = [
        ("no authentication", "resources", {"maxResults": "1"}, ""),
        ("invalid JWT", "resources", {"maxResults": "1"}, "a.b.c"),
        ("unknown profile id", "resources/999999999", {}, None),
        ("unserved search (deliveries)", "deliveries", {"maxResults": "1"}, None),
    ]
    for label, path, params, token in cases:
        code_r, body_r = real.get(path, params, jwt=token)
        code_m, body_m = mock.get(path, params, jwt=token)

        def _shape(body: Any) -> str:
            if not isinstance(body, dict) or "errors" not in body:
                return "—"
            entry = body["errors"][0]
            keys = "+".join(sorted(entry))
            meta = body.get("meta", {})
            return f"{keys} (isLogged={meta.get('isLogged')})"

        match = "✅" if (code_r, _shape(body_r)) == (code_m, _shape(body_m)) else "❌"
        shape_r, shape_m = _shape(body_r), _shape(body_m)
        lines.append(f"- {match} {label}: real {code_r} `{shape_r}` / mock {code_m} `{shape_m}`")
    lines.append("")


def compare_profiles(real: Side, mock: Side, lines: list[str]) -> None:
    """resources/{id} + administrative + technical-data + contracts/{id}."""
    lines.append("### Profiles")
    code, body = real.get("resources", {"maxResults": "1"})
    real.rid = body["data"][0]["id"] if code == 200 and body.get("data") else None
    mock.rid = "7"
    for sub_path in ("", "/administrative", "/technical-data"):
        code_r, body_r = real.get(f"resources/{real.rid}{sub_path}") if real.rid else (0, {})
        code_m, body_m = mock.get(f"resources/{mock.rid}{sub_path}")
        r, m = summarize(code_r, body_r), summarize(code_m, body_m)
        detail: list[str] = []
        if r.get("type") != m.get("type"):
            detail.append(f"  - type: real `{r.get('type')}` / mock `{m.get('type')}`")
        diff_keys("attributes", r.get("attrs"), m.get("attrs"), detail)
        diff_keys("relationships", r.get("rels"), m.get("rels"), detail)
        status = "✅ no difference" if not detail and code_r == code_m else ""
        lines.append(f"- `resources/{{id}}{sub_path}`: real {code_r} / mock {code_m} {status}")
        lines.extend(detail)

        # The contracts flow: from the profile, follow the first reference.
        if sub_path == "" and code_r == 200:
            relationships = body_r.get("data", {}).get("relationships", {})
            refs = (relationships.get("contracts") or {}).get("data") or []
            if refs:
                code_cr, body_cr = real.get(f"contracts/{refs[0]['id']}")
                code_cm, body_cm = mock.get("contracts/7")
                rc, mc = summarize(code_cr, body_cr), summarize(code_cm, body_cm)
                detail = []
                diff_keys("attributes", rc.get("attrs"), mc.get("attrs"), detail)
                diff_keys("relationships", rc.get("rels"), mc.get("rels"), detail)
                status = "✅ no difference" if not detail and code_cr == code_cm else ""
                lines.append(f"- `contracts/{{id}}`: real {code_cr} / mock {code_cm} {status}")
                lines.extend(detail)
    lines.append("")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="markdown report file (default: stdout)")
    parser.add_argument(
        "--mock-base", default=os.environ.get("BOOND_MOCK_BASE", "http://localhost:8000/api")
    )
    parser.add_argument(
        "--real-base", default=os.environ.get("BOOND_REAL_BASE", "https://ui.boondmanager.com/api")
    )
    args = parser.parse_args()

    try:
        real_jwt = jwt_client(
            os.environ["BOOND_REAL_USER_TOKEN"],
            os.environ["BOOND_REAL_CLIENT_TOKEN"],
            os.environ["BOOND_REAL_CLIENT_KEY"],
        )
    except KeyError as missing:
        print(f"missing environment variable: {missing}", file=sys.stderr)
        return 2
    mock_jwt = jwt_client(
        os.environ.get("BOOND_MOCK_USER_TOKEN", "mock-user-token"),
        os.environ.get("BOOND_MOCK_CLIENT_TOKEN", "mock-client-token"),
        os.environ.get("BOOND_MOCK_CLIENT_KEY", "mock-client-key"),
    )
    real = Side("real", args.real_base, real_jwt, pause=0.35)
    mock = Side("mock", args.mock_base, mock_jwt)

    lines = [
        "# Mock ↔ real BoondManager comparison",
        "",
        f"- real: `{args.real_base}` | mock: `{args.mock_base}`",
        "- structures only (keys, types, status codes) — no business value",
        "- gap tolerated by construction: `isDeleted` (mock marker)",
        "",
    ]
    compare_errors(real, mock, lines)
    compare_profiles(real, mock, lines)
    for path, params in MODULES:
        compare_module(path, params, real, mock, lines)

    report = "\n".join(lines) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(report)
        print(f"report written: {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
