# AGENTS.md

Operational rules for AI agents working in this repository — a distillation
of the coding standard the project was founded on (agent-coding-instruction).
This file is self-sufficient: where it is silent, follow the existing code,
the ADRs in `docs/adr/` and the patterns already in the repository. When this
file and existing code disagree, this file wins — propose a fix for the code
instead of copying the deviation.

Transitional note: this file describes the rewrite target. The legacy MVP
code lives in git history and on `main` until the first release replaces it;
it predates these rules and does not follow them — do not copy its patterns
into new work.

The repository is one bounded context `memiro`: a FastAPI backend
(`src/memiro/`), shared primitives (`src/memiro_common/`), a Django admin as a
second presentation of the same context, and an Astro SSR storefront in
`frontend/`. **These rules cover the Python backend only.** `frontend/` gets
its own `AGENTS.md` when it lands; nothing here extends to TypeScript.

Language: code, docstrings and comments — English only. Commit messages, PR
descriptions and product-facing docs (`docs/`, ADRs) — Russian.

## Boundaries

**Never:**

- commit or push to `dev` or `main` directly — the working trunk is `dev`:
  feature branch off `dev` → PR into `dev` → rebase-merge, and merging a PR
  requires the owner's explicit OK; `dev` flows into `main` only as a release
  by the owner (`main` is production);
- write production code before a red test; the use-case spec page
  (`docs/usecase/<feature>/`) comes before the red test;
- use `unittest.mock` or `monkeypatch` — they sit in ruff `banned-api`; the
  replacement is a fake behind a port (own infrastructure is real via
  testcontainers);
- run bare `pytest` — use `just test` / `just test-e2e`; bare pytest sweeps
  up e2e tests without a contour;
- import adapters, dishka, SQLAlchemy or Django from `entities/` or
  `application/` — import-linter enforces this;
- edit domain tables from Django migrations — alembic is the sole owner of
  domain tables; Django migrations own only the service tables (`auth_*`,
  `django_*`);
- log PII or secrets.

**Ask the owner first:**

- adding or bumping a dependency (a bump is its own PR);
- a destructive or data-rewriting migration;
- changing an error `code` or removing a route — both are external contracts.

**Always:**

- `just lint` and `just static` by hand before every commit;
- ship the whole vertical slice in one PR: code + tests + migration + DI +
  doc, ≤500–700 diff lines, never sliced by layer;
- register every new error in the HTTP mapping table and `docs/errors/`.

## Commands

The justfile is the single source of commands; refer to recipes, never to raw
command lines.

| Recipe | What it does |
|---|---|
| `just install` | venv, `.env`, pre-commit hooks |
| `just lint` | ruff format + check --fix, mypy, lint-imports, typos — **mutating, rewrites files** |
| `just static` | basedpyright, bandit |
| `just test` | unit + integration; brings the database up itself |
| `just test-e2e` | full contour up → e2e → down |
| `just up` / `just down` | local dev stack |
| `just db-up` / `just db-down` | Postgres only — **there is no Redis in this contour** |
| `just migrate` | apply migrations locally |
| `just run` | run the API locally |

## Architecture facts

- Layers: `entities/` (pure domain) → `application/` (interactors, ports) →
  `adapters/` (implementations) → `presentation/` (`fast_api/`,
  `django_admin/`) → `bootstrap/` (CLI, config, DI). `.importlinter` holds
  the contracts; a new package and the matching `.importlinter` edit land in
  the same commit.
- The domain is pure: plain dataclasses, zero framework imports; exactly two
  names from `memiro_common` are allowed in `entities/` (`Clock`,
  `AppError`/`app_error`). Decisions are made by the entity/factory/domain
  service; the interactor only orchestrates.
- Time flows only through `Clock`, passed as a parameter; every `now()` call
  lives in `entities/`.
- One use case = one package = one interactor per scenario; three isomorphic
  trees: `application/<feature>/` ↔ `tests/integration/<feature>/` ↔
  `docs/usecase/<feature>/`.
- Storage ports are `<Aggregate>Gateway` (the word `Repository` is not in
  this vocabulary); implementations are prefixed by technology
  (`SAProductGateway`, `LocalProductImageStorage`).
- All errors inherit `AppError` directly (flat hierarchy) with a
  SCREAMING_SNAKE `code`; `AppError` → 4xx, `RuntimeError` → 500. The
  machine `code` is the external contract; Russian wording is the job of the
  frontend and the admin, never the domain.
- One transaction — one aggregate; cross-aggregate work is a domain event
  published strictly after commit, carrying identifiers only. Django signals
  do not exist here (ADR-0014).
- `utils.py` does not exist. Helper placement: `memiro_common/` (primitive,
  zero domain knowledge) → `<layer>/common/<concrete_name>.py` →
  `<feature>/shared.py` → a private `_function` in the consuming module.
  Duplication is cheaper than the wrong abstraction.
- There is a single implementation of price calculation: the domain service
  in `entities/pricing/`. The xlsx workbook, the public endpoint, the variant
  builder and repricing all call it; a second formula anywhere is a bug.

## The Django admin

The admin is a second presentation of the same context
(`presentation/django_admin/`), not a separate app (ADR-0012).

- Reads go directly through mirror models: `managed = False`, explicit
  `db_table` matching the alembic tables, and `on_delete=models.DO_NOTHING`
  on **every** foreign key in **every** mirror — deletion rules belong to the
  database and the domain, never to Django.
- Writes to anything with invariants go through the same interactors the API
  uses: interactor first (domain commit), then the Django part (history,
  messages) best-effort — its failure is a warning, the domain does not roll
  back. Direct CRUD is allowed only for content without rules.
- The async bridge is a persistent background thread with one event loop per
  admin process; the dishka container and engine live in that loop
  (ADR-0012). Never create a per-call event loop.
- Mirror drift is caught by `test_admin_mirror_matches_schema.py` — the only
  test allowed to know both schemas.

## Test patterns to preserve

The test architecture is part of the contract. Coverage is a floor, not a
replacement for assertions.

1. AAA with blank-line separation; single Act per unit test; no `if` in test
   bodies; `sleep` in test bodies is banned — polling lives in waiter
   helpers with deadlines that return the awaited state.
2. Test names are complete English sentences promising behaviour
   (`test_a_profile_keeps_the_city_it_was_given`), never method calls; every
   test has a one-line docstring naming the error code where relevant.
3. No mocks, mechanically: fakes behind ports; own infrastructure real
   (testcontainers Postgres, session-scoped, template database); interactions
   verified only at true cross-process edges.
4. Arrange through factories (polyfactory) and gateway facades, never through
   `api_client`; direct DB writes only as named helpers (`_update_directly`,
   `prime_*`).
5. Integration tests go over HTTP through the typed `ApiClient` against the
   app assembled by the production `create_app(config)`; the test `Config` is
   built by hand — never `Config.load()`, no `dependency_overrides`; the
   app's DI container is the tests' container, and a test-only DI override
   (when needed at all) is a separate provider appended last. Negative tests
   are one line: `assert_error(status, "CODE")`; positive tests compare the
   whole object.
6. The mechanical negative checklist per use case: 401, role missing → 404
   (no existence oracle), interloper → 403, `uuid4()` → 404, every limit at
   `+1` from the production
   constant → 422, state conflicts → 409, domain validation → 400; races are
   two competitors in `asyncio.gather`.
7. Expected values are hardcoded, never re-derived by re-running production
   logic; production constants are imported so the test hits exactly
   `LIMIT + 1`.
8. Time: injected `Clock`; unit tests use `FakeClock` frozen on a module
   `NOW` with non-zero seconds and microseconds (otherwise missing
   normalization is invisible); integration uses the real `SystemClock`;
   data uses only `timedelta` from `now`.
9. Hypothesis — unit only, densest on `entities/pricing/`; strategies as
   `@st.composite` in one `composite.py`; invariants generated coherently,
   never patched after the draw.
10. Unit/integration duplication is deliberate: the unit test pins the type
    and text of the domain exception, the integration test pins the HTTP
    status and the machine code of the same rule.
11. Canonical actors: `owner`, `interloper`, `participant`, `admin`. File
    order: happy path → races → the `fails_if` quartet → conflicts →
    not_found.
12. `parametrize` only when the value changes and the scenario doesn't;
    different refusal causes are separate tests; `ids=` is never used;
    datasets are module constants `(patch, expected code)` where the code
    pins which layer catches.
13. A pure test refactor has no red to show, so its check is equivalence:
    the suite is green before and after, and the passing-test count moves by
    exactly the declared number; after splitting a test, break the step in
    production code and confirm the test naming it is the one that reddens.

## Checklist: adding a use case

1. Doc page `docs/usecase/<feature>/<scenario>.md`: actor, Input/Output,
   Business Rules in execution order with an error code per rule.
2. Red integration tests: happy path + every applicable negative-checklist
   item, red for the right reason.
3. Domain: entity/VO/factory/service + `entities/errors/` + red unit tests.
4. Application: package, ports in `common/gateway/`, the interactor, the
   passport `__init__.py`.
5. Adapters: the SA gateway (`@override`, protocol order), the alembic
   migration; a domain-table change also updates the admin mirror.
6. DI: registration in the providers; STRICT validation catches anything
   forgotten.
7. Presentation: the one-line handler; new errors → mapping table +
   `docs/errors/`.
8. `.importlinter` — if a new package appeared.
9. One commit/PR — the whole slice; `just lint`, `just static`, `just test`
   green; every Business Rule has a test naming it.

## Checklist: before every commit

1. `just lint` (mutating — run before staging).
2. `just static`.
3. `just test` (and `just test-e2e` when the contour changed).
4. Conventional Commit, imperative; the scope, when given, names a subsystem
   (`(db)`, `(admin)`), never a feature; message in Russian.
5. The diff is one vertical slice and fits the PR budget.
