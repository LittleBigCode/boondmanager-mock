"""Profil `ophelie` — reproduction GELÉE du jeu de données historique.

┌─ NE PAS MODIFIER CE FICHIER ────────────────────────────────────────────────┐
│ C'est la copie verbatim du générateur qui vivait dans                       │
│ ophelie/backend/app/boond/mock_api.py. Il produit exactement 24 resources,  │
│ 6 agencies, 10 companies, 18 contacts et 14 projects, avec le même          │
│ algorithme de trigramme et les trois e-mails Keycloak épinglés.             │
│                                                                             │
│ C'est ce qui permet à ophelie de migrer vers ce paquet sans toucher UNE     │
│ SEULE de ses assertions (`meta.totals.rows == 24`, unicité des trigrammes,  │
│ pagination 10/10/4, projet id 1 en `in_progress`…), et ce qui découple      │
│ ensuite les cadences de release des deux dépôts.                            │
│                                                                             │
│ Toute évolution du jeu de données va dans le profil `insights360`.          │
│ tests/test_ophelie_regression.py est le garde-fou : il porte le fichier de  │
│ test d'ophelie verbatim.                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import random
import string
from typing import Any


_FIRST = [
    "Camille",
    "Jules",
    "Sofia",
    "Hugo",
    "Amara",
    "Louis",
    "Priya",
    "Arthur",
    "Emma",
    "Mateo",
    "Chen",
    "Gabriel",
    "Aisha",
    "Rafael",
    "Yuki",
    "Nathan",
    "Olivia",
    "Diego",
    "Nina",
    "Youssef",
    "Ana",
    "Lars",
    "Wei",
    "Adam",
]
_LAST = [
    "Martin",
    "Silva",
    "Nakamura",
    "Okafor",
    "Rossi",
    "Müller",
    "Santos",
    "Dubois",
    "Moreau",
    "Laurent",
    "Kim",
    "Ivanov",
    "Fernández",
    "Andersson",
    "Nguyen",
    "Costa",
    "Bertrand",
    "Haddad",
    "Johnson",
    "García",
    "Patel",
    "Schmidt",
    "Lambert",
    "Oliveira",
]
_TITLES = [
    "Data Consultant",
    "Cloud Architect",
    "Solutions Architect",
    "Full-Stack Developer",
    "Data Engineer",
    "ML Engineer",
    "DevOps Consultant",
    "UX Designer",
    "Strategy Consultant",
    "Change Manager",
    "Product Owner",
    "Data Scientist",
]
_SKILLS = [
    "Python",
    "React",
    "Kubernetes",
    "Terraform",
    "Spark",
    "FastAPI",
    "AWS",
    "dbt",
    "Azure",
    "Snowflake",
    "TensorFlow",
    "Power BI",
    "Kafka",
    "Agile",
    "Change Management",
]
# Consultant grade rungs — labels on the ONE firm-wide `grade` ladder the sync
# maps onto (matched case-insensitively; these are the real seeded rungs).
_CONSULTANT_GRADES = ["Associate", "Confirmed", "Senior"]
# Spoken languages (name, ISO 639-1) → target `language` catalog + person_language
# with a 1–5 level. Everyone gets English; the rest are sampled.
_LANGUAGES = [
    ("English", "en"),
    ("French", "fr"),
    ("Spanish", "es"),
    ("German", "de"),
    ("Portuguese", "pt"),
    ("Italian", "it"),
]
# Diametral's offices — the Boond "agency" relationship resolves to one of these,
# and the sync lands the person on the matching `agency` referential row. (name,
# town, country) — the town/country are echoed on the Boond agency payload.
_AGENCIES = [
    ("Paris", "Paris", "France"),
    ("Lyon", "Lyon", "France"),
    ("Brussels", "Brussels", "Belgium"),
    ("New York", "New York", "United States"),
    ("Bogota", "Bogota", "Colombia"),
    ("São Paulo", "São Paulo", "Brazil"),
]
# The 8 CONSULTANT business-unit engines (must match migration 0012's seed so the
# sync lands people on the seeded rows). Carried on the resource as `businessUnit`
# — decoupled from the office `agency` (a person has both a BU and an office).
_ENGINES = [
    "Strategy",
    "Gouvernance & Quality",
    "Architecture & Engineering",
    "Decision Analytics",
    "Applied AI & Data Science",
    "Product Delivery",
    "Acculturation & Change Management",
    "Innovation & Developpement",
]
# Clients span the office footprint (name, city, country, website).
_COMPANIES = [
    ("Nordwind Energy", "Brussels", "Belgium", "https://nordwind.example"),
    ("Meridian Bank", "New York", "United States", "https://meridianbank.example"),
    ("AndesCom", "Bogota", "Colombia", "https://andescom.example"),
    ("Cafezal Foods", "São Paulo", "Brazil", "https://cafezal.example"),
    ("Lumière Retail", "Paris", "France", "https://lumiere-retail.example"),
    ("Rhône Industries", "Lyon", "France", "https://rhone-industries.example"),
    ("Atlantic Logistics", "Boston", "United States", "https://atlanticlog.example"),
    ("Flandria Telecom", "Antwerp", "Belgium", "https://flandria.example"),
    ("Rio Seguros", "Rio de Janeiro", "Brazil", "https://rioseguros.example"),
    ("Caribe Health", "Medellín", "Colombia", "https://caribehealth.example"),
]
_PROJECT_KINDS = [
    "Data platform rebuild",
    "Cloud migration",
    "CI/CD enablement",
    "Finance dashboard",
    "E-commerce platform",
    "MLOps industrialization",
    "Security audit",
    "Data mesh pilot",
]
# Varied case-study narrative fragments — chosen per reference so the demo track
# record reads like distinct engagements rather than one template. Each is a
# format string over {company}, {kind} (lower-cased), {city}, {s0}, {s1}.
_REF_CONTEXTS = [
    "{company} was losing ground to faster competitors: its {kind} ran on an "
    "ageing stack nobody trusted, and every release was a gamble.",
    "Ahead of a board-level deadline, {company} had to deliver a {kind} without "
    "disrupting the systems already in production.",
    "{company}'s data had outgrown its tooling — reporting took days and the "
    "{kind} had become the team's biggest bottleneck.",
    "Rising regulatory scrutiny forced {company} to rethink its {kind} from the "
    "ground up, with auditability as a first-class requirement.",
    "After two failed internal attempts, {company} brought us in to get its "
    "{kind} over the line for good.",
    "{company} wanted to consolidate a sprawl of legacy tools into a single "
    "{kind} its teams would actually adopt.",
]
_REF_CONSTRAINTS = [
    "A hard go-live date, a legacy {s0} platform to keep running in parallel, and "
    "zero tolerance for downtime.",
    "A small in-house team to upskill, strict data-residency rules, and a fixed "
    "budget envelope.",
    "Sensitive production data, a demanding audit trail, and a change window of a "
    "few hours a week.",
    "Fragmented ownership across three departments and a {s1} estate no one fully " "understood.",
    "A tight timeline, an unforgiving compliance regime, and stakeholders in four " "time zones.",
]
_REF_APPROACHES = [
    "Framed the problem with the business, stood up a {s0}-on-{s1} platform, and "
    "industrialised it through CI/CD while coaching the client's team.",
    "Ran a short discovery, then delivered in fortnightly increments — {s0} for "
    "the core, {s1} for the edges — with the client pairing throughout.",
    "Started with a thin end-to-end slice on {s0}, proved it in production, then "
    "scaled out and handed over runbooks and {s1} training.",
    "Rebuilt the pipeline around {s0}, automated the {s1} toolchain, and embedded "
    "with the client's engineers to transfer ownership.",
    "Mapped the value stream, cut the {s1} dead weight, and re-platformed onto "
    "{s0} with observability baked in from day one.",
]
_REF_RESULTS = [
    "Processing time cut by {x}x and {p}% lower run costs; the platform is now the "
    "team's system of record.",
    "Release cadence went from quarterly to weekly, with {p}% fewer incidents " "after cutover.",
    "{p}% faster reporting and a {x}x throughput gain — adopted firm-wide within a " "quarter.",
    "Cleared the audit with no findings, and the client's team now ships changes " "unaided.",
    "Manual effort down {p}% and time-to-insight from days to minutes; the sponsor "
    "renewed for a second phase.",
]
# Short role held on the mission (target `reference.role`) — a real role label,
# not the person's job title echoed back.
_REF_ROLES = [
    "Tech Lead",
    "Lead Developer",
    "Solution Architect",
    "Delivery Lead",
    "Technical Referent",
    "Squad Lead",
    "Principal Engineer",
]
# The longer prose (target `reference.role_description`) — reads like a real CV
# entry describing the contribution, weaving in the stack without repeating the
# role label.
_REF_ROLE_DESCRIPTIONS = [
    "Led the {s0} workstream from architecture to production, coordinating a team "
    "of {n} across engineering and the client side.",
    "Owned the {s0} services and the data model, and drove the migration off the "
    "legacy platform.",
    "Technical referent on {s0}: paired daily with the client's engineers and "
    "reviewed every change into the codebase.",
    "Designed and shipped the {s1} integration layer, then ran the cut-over and "
    "the post-go-live stabilisation.",
    "Ran delivery as lead — sprint planning, architecture calls and hands-on {s0} "
    "development with a team of {n}.",
    "Built the {s0} pipeline and the {s1} test harness, and wrote the runbooks the "
    "client's team now operates from.",
]
# Company activity area → the target `organization.sector`.
_SECTORS = [
    "Banking & Insurance",
    "Retail & Distribution",
    "Energy & Utilities",
    "Manufacturing",
    "Telecom & Media",
    "Transport & Logistics",
    "Public Sector",
    "Healthcare & Pharma",
]
# Buying/using departments seeded under each client entity (target `department`).
_DEPARTMENTS = [
    "Information Systems",
    "Data & AI Office",
    "Finance",
    "Marketing & Digital",
    "Operations",
    "Human Resources",
]
# Country → international dialling prefix, for plausible phone numbers.
_DIAL = {
    "France": "+33",
    "Belgium": "+32",
    "United States": "+1",
    "Colombia": "+57",
    "Brazil": "+55",
}
# Credential catalog — a resource earns a subset (target `certification`).
_CERTIFICATIONS = [
    ("AWS Certified Solutions Architect – Associate", "Amazon Web Services"),
    ("Certified Kubernetes Administrator (CKA)", "CNCF"),
    ("Professional Scrum Master I", "Scrum.org"),
    ("Google Cloud Professional Data Engineer", "Google Cloud"),
    ("TOGAF 9 Certified", "The Open Group"),
    ("HashiCorp Certified: Terraform Associate", "HashiCorp"),
    ("Databricks Certified Data Engineer Associate", "Databricks"),
    ("Microsoft Certified: Azure Fundamentals", "Microsoft"),
]
# Diploma catalog — the education history (target `diploma`).
_DIPLOMAS = [
    ("MSc Computer Science", "ETH Zürich"),
    ("MBA", "INSEAD"),
    ("BSc Data Science", "MIT"),
    ("MSc Artificial Intelligence", "Imperial College London"),
    ("Engenharia de Software", "Universidade de São Paulo"),
    ("Ingeniería de Sistemas", "Universidad de los Andes"),
    ("MSc Business Analytics", "Solvay Brussels School"),
    ("Diplôme d'Ingénieur", "École Polytechnique"),
]
# Client-side involvement roles on a mission (target `mission_contact.role`).
_MISSION_CONTACT_ROLES = ["sponsor", "buyer", "key_user", "other"]
# Free-text relationship intel appended to a contact's notes (→ contact.notes).
_CONTACT_RELATIONSHIP_NOTES = [
    "Key decision-maker.",
    "Budget-conscious.",
    "Long-standing relationship.",
    "Technical champion.",
]
# Streets used to synthesise a plausible client postal address (target
# `entity.address`).
_STREETS = [
    "Main Street",
    "Fifth Avenue",
    "Boulevard du Régent",
    "Avenida Paulista",
    "Carrera 7",
    "King Street",
    "Rue Royale",
]


def _resource(i: int, rng: random.Random) -> dict[str, Any]:
    first, last = _FIRST[i % len(_FIRST)], _LAST[i % len(_LAST)]
    # ids 1-2 are the BU directors, 3-6 the managers, the rest consultants.
    manager_id = None if i <= 2 else (rng.choice([1, 2]) if i <= 6 else rng.choice([3, 4, 5, 6]))
    # A career coach — a manager other than the direct manager where possible.
    coach_id = None if i <= 6 else rng.choice([m for m in (3, 4, 5, 6) if m != manager_id])
    # Spread people across the offices; give each a consultant engine as its BU.
    # The person's town/country/phone follow their office.
    agency_id = (i - 1) % len(_AGENCIES) + 1
    _office_name, office_city, office_country = _AGENCIES[agency_id - 1]
    business_unit = _ENGINES[(i - 1) % len(_ENGINES)]
    grade = "Director" if i <= 2 else ("Manager" if i <= 6 else rng.choice(_CONSULTANT_GRADES))
    title = rng.choice(_TITLES)
    email = f"{first.lower()}.{last.lower()}@ophelie.dev"
    hire_year = rng.randint(2015, 2024)
    # Started their career a few years before joining the firm.
    career_start_year = hire_year - rng.randint(0, 9)
    experience_years = 2026 - career_start_year
    # Spoken languages — English (fluent) plus 1–2 more, each with a 1–5 level.
    languages = [{"name": "English", "iso": "en", "level": 5}]
    for name, iso in rng.sample(_LANGUAGES[1:], k=rng.randint(1, 2)):
        languages.append({"name": name, "iso": iso, "level": rng.randint(3, 5)})
    # Self-declared skills with a 1–5 level → person_skill_level.
    declared_skills = [
        {"name": s, "level": rng.randint(3, 5)} for s in rng.sample(_SKILLS, k=rng.randint(4, 6))
    ]
    # A few free-text profile tags → person.keywords.
    keywords = rng.sample(_SKILLS, k=3) + [rng.choice(_SECTORS)]
    return {
        "id": str(i),
        "type": "resource",
        "attributes": {
            "firstName": first,
            "lastName": last,
            "email1": email,
            "phone1": f"{_DIAL[office_country]} {rng.randint(100, 999)} "
            f"{rng.randint(100, 999)} {rng.randint(1000, 9999)}",
            "title": title,
            "country": office_country,
            "town": office_city,
            "state": 1,
            # Seniority label + its function name — mapped onto the target
            # consultant `grade` ladder by the sync. `trigramme` is assigned in
            # build_dataset (needs cross-resource uniqueness).
            "grade": grade,
            "function": grade.title(),
            # Consultant engine → target `business_unit` (decoupled from office).
            "businessUnit": business_unit,
            "averageDailyPriceExcludingTax": rng.choice([450, 520, 600, 680, 750]),
            # --- profile substance (target `person`) ---
            # dateOfHiring → person.hire_date; startYear → career_start_year.
            "dateOfHiring": f"{hire_year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "startYear": career_start_year,
            # A short professional bio → person.summary.
            "description": (
                f"{title} with {experience_years} years of experience. "
                f"Delivers {rng.choice(_SKILLS)} / {rng.choice(_SKILLS)} engagements "
                f"in demanding environments out of the {office_city} office. "
                "Known for rigour and a strong delivery mindset."
            ),
            # Deterministic avatar (seeded by email) → person.profile_image_url.
            "photoUrl": f"https://i.pravatar.cc/300?u={email}",
            # CV credentials/education → certification / diploma (+ joins).
            "certifications": [
                {
                    "name": _CERTIFICATIONS[idx][0],
                    "organisation": _CERTIFICATIONS[idx][1],
                    "year": rng.randint(career_start_year, 2025),
                }
                for idx in sorted(rng.sample(range(len(_CERTIFICATIONS)), k=rng.randint(0, 3)))
            ],
            "diplomas": [
                {
                    "title": _DIPLOMAS[idx][0],
                    "school": _DIPLOMAS[idx][1],
                    "year": career_start_year - rng.randint(0, 1),
                }
                for idx in sorted(rng.sample(range(len(_DIPLOMAS)), k=rng.randint(1, 2)))
            ],
            # Spoken languages → language catalog + person_language (1–5 level).
            "languages": languages,
            # Self-declared skills with a level → person_skill_level.
            "skills": declared_skills,
            # Free-text profile tags → person.keywords.
            "keywords": keywords,
        },
        "relationships": {
            "agency": {"data": {"id": str(agency_id), "type": "agency"}},
            "mainManager": {
                "data": {"id": str(manager_id), "type": "resource"} if manager_id else None
            },
            "coach": {"data": {"id": str(coach_id), "type": "resource"} if coach_id else None},
        },
    }


def _technical_data(resource: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    references = []
    for n in range(rng.randint(1, 3)):
        company, city, _country, _site = rng.choice(_COMPANIES)
        start = rng.randint(2018, 2024)
        skills = rng.sample(_SKILLS, k=2)
        kind = rng.choice(_PROJECT_KINDS)
        references.append(
            {
                "id": f"{resource['id']}00{n + 1}",
                "title": kind,
                "company": company,
                # The situation narrative → staged as `description` → reference.context.
                "description": rng.choice(_REF_CONTEXTS).format(
                    company=company, kind=kind.lower(), city=city, s0=skills[0], s1=skills[1]
                ),
                # --- full case-study narrative (target `reference`) ---
                # role → reference.role (short); roleDescription → role_description;
                # constraints/approach/results map 1:1 onto the columns. Each is
                # drawn from a varied pool so no two read alike.
                "role": rng.choice(_REF_ROLES),
                "roleDescription": rng.choice(_REF_ROLE_DESCRIPTIONS).format(
                    s0=skills[0], s1=skills[1], n=rng.randint(3, 9)
                ),
                "constraints": rng.choice(_REF_CONSTRAINTS).format(
                    company=company, kind=kind.lower(), city=city, s0=skills[0], s1=skills[1]
                ),
                "approach": rng.choice(_REF_APPROACHES).format(
                    company=company, kind=kind.lower(), city=city, s0=skills[0], s1=skills[1]
                ),
                "results": rng.choice(_REF_RESULTS).format(
                    x=rng.randint(2, 6), p=rng.randint(15, 60)
                ),
                "location": rng.choice([city, "Remote"]),
                "startMonth": rng.randint(1, 12),
                "startYear": start,
                "endMonth": rng.randint(1, 12),
                "endYear": min(start + rng.randint(0, 2), 2026),
                # A JSON array of skill names (was a comma string) — feeds
                # reference_skill directly.
                "skills": skills,
            }
        )
    return {
        "id": resource["id"],
        "type": "technicaldata",
        "attributes": {
            "title": resource["attributes"]["title"],
            "skills": ", ".join(rng.sample(_SKILLS, k=3)),
            "experience": rng.randint(2, 15),
            "references": references,
        },
    }


# The 3 Keycloak login users, pinned onto the last 3 generated resources so
# GET /persons/me resolves (matched by email) without changing the resource count
# the sync tests assert on. They stay full consultants with rich profiles.
_LOGIN_USERS = [
    ("Demo", "Consultant", "demo@ophelie.test"),
    ("Manager", "Lead", "manager@ophelie.test"),
    ("Admin", "Owner", "admin@ophelie.test"),
]


def build_ophelie_dataset(seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    resources = [_resource(i, rng) for i in range(1, 25)]
    # Pin the last 3 resources to the Keycloak login identities (name + email),
    # keeping every other attribute the generator produced.
    for res, (first, last, email) in zip(resources[-len(_LOGIN_USERS) :], _LOGIN_USERS):
        res["attributes"]["firstName"] = first
        res["attributes"]["lastName"] = last
        res["attributes"]["email1"] = email
        res["attributes"]["photoUrl"] = f"https://i.pravatar.cc/300?u={email}"
    # Assign a unique 3-char trigramme per resource (upper(first[0]+last[:2]),
    # rotating the last char on collision) — the `person` table requires one.
    _used_trigrammes: set[str] = set()
    _alphabet = string.ascii_uppercase + string.digits
    for _res in resources:
        _a = _res["attributes"]
        _base = (_a["firstName"][:1] + _a["lastName"][:2] + "XXX").upper()[:3]
        _trig = _base
        _pool = iter(_alphabet)
        while _trig in _used_trigrammes:
            _trig = _base[:2] + next(_pool)
        _used_trigrammes.add(_trig)
        _a["trigramme"] = _trig
    agencies = [
        {
            "id": str(i + 1),
            "type": "agency",
            "attributes": {"name": name, "town": town, "country": country},
        }
        for i, (name, town, country) in enumerate(_AGENCIES)
    ]
    companies = []
    for i, (name, town, country, site) in enumerate(_COMPANIES):
        slug = name.lower().replace(" ", "")
        domain = site.replace("https://", "")
        companies.append(
            {
                "id": str(i + 1),
                "type": "company",
                "attributes": {
                    "name": name,
                    "town": town,
                    "country": country,
                    "website": site,
                    "phone1": f"{_DIAL[country]} {rng.randint(100, 999)} "
                    f"{rng.randint(100, 999)} {rng.randint(1000, 9999)}",
                    "email1": f"contact@{slug}.example",
                    "state": 1,
                    # --- master-record substance (target `organization`) ---
                    "activityArea": rng.choice(_SECTORS),  # → organization.sector
                    "staff": rng.choice([35, 120, 340, 780, 1500, 4200]),  # → headcount bucket
                    "logoUrl": f"https://logo.clearbit.com/{domain}",  # → logo_url
                    "description": (
                        f"{name} is a major player in its sector, invested in "
                        "transforming its information system and making the most of "
                        "its data."
                    ),
                    # Postal address → entity.address.
                    "address": (f"{rng.randint(1, 200)} {rng.choice(_STREETS)}, {town}, {country}"),
                    # Buying/using departments → department rows under the entity.
                    "departments": sorted(
                        rng.sample(_DEPARTMENTS, k=rng.randint(2, 4)),
                    ),
                },
                "relationships": {
                    # The BM who owns the account → entity.account_owner_id.
                    "mainManager": {"data": {"id": str(rng.randint(3, 6)), "type": "resource"}},
                },
            }
        )
    contacts = []
    for i in range(1, 19):
        first, last = rng.choice(_FIRST), rng.choice(_LAST)
        company = rng.choice(companies)
        title = rng.choice(["CIO", "CTO", "Head of Data", "IT Procurement", "CFO"])
        contacts.append(
            {
                "id": str(i),
                "type": "contact",
                "attributes": {
                    "firstName": first,
                    "lastName": last,
                    "email1": f"{first.lower()}.{last.lower()}@"
                    f"{company['attributes']['name'].lower().replace(' ', '')}.example",
                    "phone1": f"{_DIAL[company['attributes']['country']]} "
                    f"{rng.randint(100, 999)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
                    "title": title,
                    # Which client department they sit in → contact.department_id
                    # (resolved under this contact's entity).
                    "department": rng.choice(company["attributes"]["departments"]),
                    # Free-text relationship intel → contact.notes.
                    "notes": (
                        f"{title} contact at {company['attributes']['name']}. "
                        f"{rng.choice(_CONTACT_RELATIONSHIP_NOTES)}"
                    ),
                },
                "relationships": {"company": {"data": {"id": company["id"], "type": "company"}}},
            }
        )
    projects = []
    for i in range(1, 15):
        company = rng.choice(companies)
        start_year = rng.randint(2023, 2026)
        kind = rng.choice(_PROJECT_KINDS)
        # Vary the workflow state so on_hold / cancelled missions exist too —
        # but keep project 1 'in_progress' (the anchor the sync tests assert on).
        status = (
            "in_progress"
            if i == 1
            else rng.choice(["in_progress", "in_progress", "in_progress", "on_hold", "cancelled"])
        )
        # Client contacts involved on the engagement → mission_contact rows.
        client_contacts = [
            c for c in contacts if c["relationships"]["company"]["data"]["id"] == company["id"]
        ]
        involved = rng.sample(client_contacts, k=min(len(client_contacts), rng.randint(1, 2)))
        projects.append(
            {
                "id": str(i),
                "type": "project",
                "attributes": {
                    "title": f"{kind} — {company['attributes']['name']}",
                    "startDate": f"{start_year}-{rng.randint(1, 12):02d}-01",
                    "endDate": f"{start_year + 1}-{rng.randint(1, 12):02d}-28",
                    "state": 1,
                    "typeOf": 1,
                    # Engagement status → mission.status (new missions only).
                    "status": status,
                    # Scope narrative → mission.description.
                    "description": (
                        f"{kind} for {company['attributes']['name']}: framing, design "
                        "and industrialisation of the target solution, in collaboration "
                        "with the client's internal teams."
                    ),
                    # Delivery location → mission.city.
                    "town": rng.choice([company["attributes"]["town"], "Remote"]),
                    # Buying department → mission.department_id (under the entity).
                    "department": rng.choice(company["attributes"]["departments"]),
                },
                "relationships": {
                    "company": {"data": {"id": company["id"], "type": "company"}},
                    "mainManager": {"data": {"id": str(rng.randint(3, 6)), "type": "resource"}},
                    # Client involvement, each carrying its role.
                    "contacts": {
                        "data": [
                            {
                                "id": c["id"],
                                "type": "contact",
                                "role": rng.choice(_MISSION_CONTACT_ROLES),
                            }
                            for c in involved
                        ]
                    },
                },
            }
        )
    return {
        "resources": resources,
        "agencies": agencies,
        "companies": companies,
        "contacts": contacts,
        "projects": projects,
        "technical_data": {r["id"]: _technical_data(r, rng) for r in resources},
    }


