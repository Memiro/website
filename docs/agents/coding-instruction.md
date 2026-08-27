# Agent Coding Instructions

The complete, self-contained coding standard for a Python backend project (FastAPI + SQLAlchemy 2.0 async + dishka). Follow it end to end when generating anything in the repository: from the first skeleton and shared primitives to domain entities, tests, commits and PRs. Every rule is binding; where a rule offers a recipe, use the recipe verbatim. When this document and existing code disagree, the document wins — propose a fix for the code instead of copying the deviation.

Language: code, docstrings and comments — English only. Commit messages, PR descriptions and product-facing docs — the team's language.

## Find your task

| You are about to… | Read |
|---|---|
| Bootstrap a new repository | §17, then §2–§3 |
| Add or change a use case | §18, then §6–§10 |
| Write a domain entity / VO / factory | §6 (naming: §4) |
| Write a port or an interactor | §7 |
| Write a gateway / migration / cache | §8 |
| Register something in DI | §9 |
| Add an HTTP route | §10 |
| Add or raise an error | §5.3 + §12 |
| Write or modify tests | §14 |
| Commit or open a PR | §15 |
| Write README / docs | §16 |

Whatever the task, §0 and §1 always apply.

## 0. Boundaries

**🚫 Never:**

- commit or push to the main branch — feature branch → PR → rebase-merge (§15);
- merge a PR without the owner's explicit OK;
- write production code before a red test (§14.3);
- use `unittest.mock` or `monkeypatch` — a fake behind a port instead (§14.1, rule 006);
- run bare `pytest` — use `just test` / `just test-e2e`: bare pytest sweeps up e2e without a contour;
- log PII or secrets;
- import adapters, dishka or SQLAlchemy from the application layer — import-linter enforces this (§2.2).

**⚠️ Ask the owner first:**

- adding or bumping a dependency (a bump is its own PR, §3.1);
- a destructive or data-rewriting migration;
- changing an error `code` or removing a route — both are external contracts (§12, §16.2).

**✅ Always:**

- `just lint` and `just static` by hand before every commit;
- ship the whole vertical slice in one PR: code + tests + migration + DI + doc (§1.10);
- register every new error in the HTTP mapping table and `docs/errors/` (§10.3, §16.2).

## 1. Ten load-bearing rules

1. **Layer boundaries are a machine-checked contract, not discipline**: import-linter runs in CI from day one. Anything that can be enforced by a tool (linter, type, contract, grep check) must be enforced by a tool — rules that live only in a reviewer's head get violated.
2. **The domain is pure**: entities and value objects are plain dataclasses with zero framework imports; decisions are made by the entity/factory/domain service, the interactor only orchestrates.
3. **A port is named by its role, an implementation by its technology**: `AvatarStorage` → `S3AvatarStorage`. The storage port is a `Gateway` (the word `Repository` is not part of this vocabulary).
4. **One use case = one package = one interactor per scenario**; three isomorphic trees: `application/<feature>/` ↔ `tests/integration/<feature>/` ↔ `docs/usecase/<feature>/`.
5. **Strict TDD**: a red test before the code, then green → refactor. The use case spec (doc-first, §16) comes before the red test.
6. **Mocks are banned mechanically**: `unittest.mock` and `monkeypatch` sit in ruff `banned-api`. Own infrastructure is real (testcontainers); foreign systems (external APIs, LLM providers) get a fake behind a port.
7. **Time flows only through `Clock`**, passed as a parameter to entity methods/factories; every `now()` call lives in the domain layer (verifiable with a single grep).
8. **`utils.py` does not exist.** Four placement levels for helpers (§2.3); a file holding one function is normal; duplication is cheaper than the wrong abstraction.
9. **All errors share one base `AppError`** with a machine-readable `code`; "client's fault" (`AppError` → 4xx) and "system bug" (`RuntimeError` → 500) are separated by exception type.
10. **One commit/PR is a vertical slice** through all layers (domain + application + adapters + DI + migration + presentation + tests + doc) — never sliced by layer.

## 2. Repository layout

### 2.1 Skeleton

```
src/
  <project>/               # bounded context (a second context gets a second package next to it)
    entities/              # domain: entities, VOs, factories, domain errors
      common/              # identifiers.py, cross-aggregate enums, datetime_utils.py
      errors/              # one file per aggregate
      <aggregate>/         # package with entity.py + one file per VO; a small aggregate is a flat file
    application/
      common/              # gateway/ (ports), dto/, events, input_limits.py
      errors/
      <feature>/           # use-case package: one file per interactor, shared.py, passport __init__.py
    adapters/              # port implementations: db/, cache/, auth/ …; a small adapter is a flat file
    presentation/          # fast_api/: routers/, error_handlers.py, HTTP configs
    bootstrap/             # cli.py, fast_api.py, config_loader.py, di/
  <project>_common/        # cross-context primitives: Clock, UoW, AppError, @interactor (§5; ~250 lines max)
tests/
  unit/                    # domain; mirrors entities/; synchronous, no I/O
  integration/<feature>/   # names 1:1 with application/<feature>/; via HTTP to the in-process app
  common/factory/          # factories, providers.py, pure helpers
docs/                      # domain reference: entities/, value-objects/, usecase/, errors/
docker/                    # Dockerfile + docker-compose.yml
.config/                   # TOML configs, nginx, init-db.sql
```

The repo root stays clean: metafiles only (`pyproject.toml`, `justfile`, `README.md`, `AGENTS.md`, `.importlinter`, `uv.lock`).

### 2.2 The layer contract

`.importlinter` holds forbidden contracts whose names read as sentences: entities imports nothing outward; application knows nothing of adapters/presentation/bootstrap; `*_common` knows nothing of the contexts; contexts never import each other (they talk only over HTTP/broker — duplicating a small transport DTO is better than coupling contexts by import). A new package and the matching `.importlinter` edit land in the same commit.

### 2.3 Where a helper goes (instead of utils)

- **(a) `<project>_common/`** — needed by every context + zero domain knowledge + it is a primitive (`Clock`, `UoW`, `AppError`, `@interactor`). Its `__init__.py` is empty; all imports are full-path.
- **(b) `<layer>/common/<concrete_name>.py`** — needed by several features of one layer (`input_limits.py`, `datetime_utils.py`). The file is named after its content: you cannot put `slugify` into `input_limits.py`.
- **(c) `<feature>/shared.py`** — needed by two interactors of one feature (`ensure_admin`).
- **(d) a private `_function` in the consuming module** — duplication at this level is allowed.

## 3. Tooling: set up before the first line of code

1. **uv**; every version pinned exactly with `==`, the lock file committed, CI installs `--frozen`; a version bump is its own deliberate PR. Dev dependencies are layered extras: `lint`/`test`/`docs` → `dev` → `ci`.
2. **Ruff**: `select = ["ALL"]`, line-length 120, a short ignore list with a justification comment on every entry; test-only relaxations go through per-file-ignores only. `banned-api` bans `unittest.mock` and `monkeypatch` with the message "fakes behind ports instead of mocks".
3. **Mypy strict** + `enable_error_code = ["explicit-override", "ignore-without-code", "possibly-undefined", "redundant-expr", "unused-awaitable"]`, `files = [src, tests]`; **basedpyright** as a second opinion.
4. **import-linter** (architecture), **typos/codespell** (spelling), **gitleaks** with a committed baseline (secrets), **bandit** (security).
5. **Pre-commit hooks as a safety net** (`just install` sets them up), but run `just lint` and `just static` by hand before committing — a hook firing on push mid-work costs more.
6. **CI**: lint job (same steps as `just lint`, non-mutating) → tests (xdist; when the suite grows — pytest-split over a committed `.test_durations`) → image builds only on `v*` tags (with a "tag is on the main branch" check). `persist-credentials: false` everywhere; `${{ }}` substitution only through `env:`.

### 3.1 The justfile

The justfile is the **single source of commands** — README, CI and this document refer to recipes, never to raw command lines. Naming: a verb plus a dashed qualifier; symmetric pairs (`up`/`down`, `db-up`/`db-down`); recipes compose by calling `just` inside just. The starter set:

```just
set positional-arguments := true

# List available commands
default:
    @just --list --unsorted

# Prepare venv, .env and git hooks for developing
install:
    uv sync --frozen
    test -f .env || cp .env.example .env
    uv run pre-commit install --hook-type pre-commit --hook-type pre-push

# Mutating lint chain; CI runs the same steps without mutations
lint:
    uv run ruff format
    uv run ruff check --fix
    uv run mypy
    uv run lint-imports
    uv run typos

# Static analysis beyond the lint chain
static:
    uv run basedpyright
    uv run bandit -c pyproject.toml -r src

# Unit + integration tests; brings the database contour up itself
test *args:
    just db-up
    uv run pytest tests/unit tests/integration "$@"

# End-to-end tests: full contour up, run, contour down
test-e2e:
    just up
    uv run pytest tests/e2e
    just down

# Local dev stack
up:
    docker compose -f docker/docker-compose.yml up -d --wait

down:
    docker compose -f docker/docker-compose.yml down

db-up:
    docker compose -f docker/docker-compose.yml up -d --wait db redis

db-down:
    docker compose -f docker/docker-compose.yml stop db redis

# Apply migrations to the local database
migrate:
    uv run <project> migrations apply

# Run the API locally
run:
    uv run <project> run api
```

Rules: `lint` is the only mutating recipe and its order matters (formatters first, checkers after); `test` never requires the developer to start docker by hand; the documented entry points are the just recipes — e2e without a contour must not be reachable by accident.

## 4. Naming dictionary

| What | Rule | Example |
|---|---|---|
| Use-case package | verb phrase in domain language | `submit_application/`, `manage_tags/` |
| Interactor | verb phrase, no suffix | `SubmitApplication`, `BlockUser` |
| Storage port | `<Aggregate>Gateway`, one file = one aggregate | `CompetitionGateway` |
| Other ports | suffix = role: `*Provider` (context/identity), `*Bus` (fire-and-forget), `*Storage` (binary objects), `*Cache` (accelerator, never the source of truth), `*Hasher`/`*Limiter` (single-verb services), `*Session` (stateful) | `IdProvider`, `EventBus` |
| Port implementation | prefix = technology; `Cached*` — a decorator; `InMemory*` — trivial | `SAUserGateway`, `RedisCompetitionCache`, `S3AvatarStorage` |
| Gateway methods | `get(id, *, for_update=False)` → entity/None (write flow); `read(id)` → DTO/None (outbound); `get_by_<field>`, `get_with_<relation>`, `list_*` → `tuple[list[T], int]`; `is_unique*`, `count_<x>_by_<y>` | `get_with_organizer` |
| Interactor models | `<Verb><Noun>Input` (query), `<Noun>Form` (body), `Created<Noun>` (id only), `<Noun>Model` (read), `<Noun>sList` (items/total/page), `<Noun>Data` (domain input) | `CreatedApplication` |
| IDs | PEP 695 `type` alias (not `NewType`) in `common/identifiers.py`, one per context | `type UserId = UUID` |
| Event | `<Entity><VerbInPastTense>`, fields are identifiers only | `UserBlocked` |
| Error | `Error` suffix; `code: ClassVar[str]` SCREAMING_SNAKE mirrors the name | `CompetitionNotFoundError` / `COMPETITION_NOT_FOUND` |
| Entity methods | mutation = bare verb; predicate = `is_*`; guard = `ensure_can_*` (raise/None), private `_ensure_*`; role attachment = `make_*` | `block`, `ensure_can_accept` |
| Factory | free function `<entity>_factory` in the entity's module | `application_factory` |
| DB table | `<plural>_table` variable, plural table name | `competition_table = Table("competitions", …)` |

Use-case verbs: `create/read/list/delete/update` for CRUD; domain verbs — `issue/revoke/publish/withdraw/block/…`. Enums are `StrEnum` + `auto()`; explicit string values only when the value is part of an external contract.

## 5. Shared primitives (`<project>_common/`): ready implementations

Copy these into every new project instead of re-deriving them. The whole package stays under ~250 lines; its `__init__.py` is empty. Entry criteria for anything new here: needed by every context + zero domain knowledge + it is a primitive, not a feature.

### 5.1 `clock.py`

```python
from datetime import UTC, datetime
from typing import Protocol, override


class Clock(Protocol):
    """Source of the current time for domain rules."""

    def now(self) -> datetime:
        """Return the current moment as an aware UTC datetime."""
        raise NotImplementedError


class SystemClock(Clock):
    """Clock backed by the system time."""

    @override
    def now(self) -> datetime:
        """Return the current system time in UTC."""
        return datetime.now(tz=UTC)
```

`SystemClock` inherits `Clock` explicitly: the protocol serves consumers structurally and implementations nominally, so mypy checks the signature. The test twin (lives in `tests/`, not in `src/`):

```python
from dataclasses import dataclass
from datetime import datetime
from typing import override

from <project>_common.clock import Clock


@dataclass(frozen=True, slots=True)
class FakeClock(Clock):
    """Clock frozen at a known instant for unit tests."""

    instant: datetime

    @override
    def now(self) -> datetime:
        """Return the frozen instant."""
        return self.instant
```

### 5.2 `uow.py`

```python
from collections.abc import Sequence
from typing import Protocol


class UoW(Protocol):
    """The four session members an interactor is allowed to touch.

    Honest framing: this is not the Unit of Work pattern but interface
    segregation over ``AsyncSession`` — the session itself is the only
    implementation, registered in DI under both types (§9.5). The protocol
    keeps SQLAlchemy out of the application layer and makes raw SQL from an
    interactor inexpressible.
    """

    def add(self, instance: object) -> None:
        """Schedule a new entity for INSERT on commit."""

    async def delete(self, instance: object) -> None:
        """Schedule a loaded entity for DELETE on commit."""

    async def flush(self, objects: Sequence[object] | None = None) -> None:
        """Push pending changes so generated ids exist before commit."""

    async def commit(self) -> None:
        """Commit the single transaction of the current request."""
```

### 5.3 `errors.py`

```python
from dataclasses import dataclass
from typing import Any, ClassVar, dataclass_transform


@dataclass_transform(kw_only_default=True)
def app_error[T](cls: type[T]) -> type[T]:
    """Turn an exception class into a kw-only slots dataclass."""
    return dataclass(slots=True, kw_only=True)(cls)


@app_error
class AppError(Exception):
    """Base for expected business failures, mapped to 4xx responses."""

    code: ClassVar[str] = "APP_ERROR"
    message: str = "Application error"

    def __post_init__(self) -> None:
        # Explicit base, not a zero-argument ``super()``: ``slots=True`` makes
        # the decorator build a *new* class, and the ``__class__`` cell of a
        # method compiled against the old one refuses every subclass instance.
        Exception.__init__(self, self.message)

    @property
    def meta(self) -> dict[str, Any] | None:
        """Machine-readable context for the error response, if any."""
        return None
```

Declaring concrete errors — two templates:

```python
@app_error
class AccessDeniedError(AppError):
    """Raised when the actor lacks the right to perform the action."""

    code: ClassVar[str] = "ACCESS_DENIED"
    # no default message: raised as
    # raise AccessDeniedError(message="Only admins can manage users")
    message: str


@app_error
class CompetitionNotFoundError(AppError):
    """Raised when the requested competition does not exist."""

    code: ClassVar[str] = "COMPETITION_NOT_FOUND"
    message: str = "Competition not found"
    # default message: raised bare — raise CompetitionNotFoundError
```

### 5.4 `interactor.py`

```python
import re
from dataclasses import dataclass
from functools import wraps
from typing import Any, dataclass_transform

from opentelemetry import trace

_tracer = trace.get_tracer(__name__)
_camel_to_snake = re.compile(r"(?<!^)(?=[A-Z])")


@dataclass_transform(kw_only_default=True, frozen_default=True)
def interactor[T](cls: type[T]) -> type[T]:
    """Make the class a frozen slots kw-only dataclass and trace ``execute``.

    One decorator carries three cross-cutting policies for every interactor:
    a DI-ready ``__init__`` synthesized from annotated fields, immutability
    (the only way to obtain a dependency is DI), and an OTel span named after
    the class.
    """
    cls = dataclass(frozen=True, slots=True, kw_only=True)(cls)
    original = cls.execute  # type: ignore[attr-defined]
    span_name = f"interactor.{_camel_to_snake.sub('_', cls.__name__).lower()}"

    @wraps(original)
    async def execute(self: Any, *args: Any, **kwargs: Any) -> Any:
        with _tracer.start_as_current_span(span_name):
            return await original(self, *args, **kwargs)

    cls.execute = execute  # type: ignore[attr-defined]
    return cls
```

### 5.5 `logger.py`

```python
import structlog

type Logger = structlog.stdlib.BoundLogger
```

The logger is imported, never injected — it carries no domain semantics. Every module opens with `logger: Logger = structlog.get_logger(__name__)`.

### 5.6 What must NOT land here

`identifiers.py` (domain-owned, one per context), `normalize_datetime` (a domain rule about granularity — lives in `entities/common/datetime_utils.py`), input limits (domain numbers). When two contexts need the same 9-line file, duplicate it — that is the price of context independence.

## 6. Domain layer (`entities/`)

The per-context domain base (`entities/common/`):

```python
from abc import ABC
from datetime import datetime


class Entity(ABC):
    """Marker base class for domain entities."""


def normalize_datetime(value: datetime) -> datetime:
    """Truncate to minute precision: domain time granularity is one minute."""
    return value.replace(second=0, microsecond=0)
```

1. **An entity is a mutable `@dataclass`** (no frozen/slots — imperative ORM mapping needs both), inheriting the empty `Entity` marker. Field order: `id` first, `created_at`/`updated_at` last. Mutation happens only through command methods that check access themselves and set `updated_at` as the last line:

```python
def change_archive_status(self, *, is_archived: bool, organizer: Organizer, clock: Clock) -> None:
    """Update competition archive status."""
    self._ensure_owned_by(organizer)
    self.is_archived = is_archived
    self.updated_at = clock.now()
```

2. **A VO is `@dataclass(frozen=True, slots=True)`** with validation in `__post_init__` raising a domain error. A validated collection is a `list[T]`/tuple subclass checking itself in `__init__`; after mutating a collection re-wrap it, after mutating a dataclass call `self.__post_init__()` explicitly. Mutable collections are never handed out: private field + property, the entity method is the only way in (an in-place edit would be lost on save without a word).
3. **Invariants have three levels**: (a) eternal shape invariants — in `__post_init__` (they must also hold when old rows are hydrated from the DB); (b) creation rules ("not in the past") — **only in factories**, or old entities would fail to load; (c) cross-aggregate rules — a domain service function in `*_service.py` that takes all entities and data as parameters (`accepted_count: int` is counted by the caller — the domain never touches the DB). This three-way split is the single most important domain rule in this document.
4. **Creation is `*_factory(data, <entities>, clock)`**: the input is a slots dataclass `*Data` without id/status/dates (they must be unforgeable), `uuid4()` inside, `now = clock.now()` taken once → into both `created_at` and `updated_at`. `Create*Data` ≠ `Update*Data` even with identical fields.
5. **Time only through `Clock`** as a parameter, never as an entity field (the entity stays serializable). All `now()` calls live in `entities/`; the interactor only passes the clock through. Permitted leak: `field(default_factory=lambda: datetime.now(UTC))` for purely audit fields that no rule reads.
6. **Domain imports**: stdlib + its own `entities.*` + exactly two names from `*_common` (`Clock`, `AppError`/`app_error`). No pydantic, no SQLAlchemy.
7. The actor is passed as an entity (`admin: User`), not an id: the method checks rights on the live object. Compound state is replaced whole (`BanStatus`) — a dangling reason on a lifted ban becomes unrepresentable.
8. `ValueError`/`RuntimeError` mean "this cannot happen, it is a bug" (→ 500); a broken business rule is always an `AppError` subclass (→ 4xx).

## 7. Application layer

1. **Package = use case**; the feature's `__init__.py` is a passport: docstring `Use case: <Title>. / Actor: <who>` + re-exports with a sorted `__all__`.
2. **An interactor is an `@interactor` class** (§5.4). Dependencies are annotated fields in a fixed order: `uow` → `idp` → `*_gateway` (in call order) → `event_bus` → `clock`. The method is always `async def execute(...)`: the path parameter as a separate argument, the body as one DTO.

```python
@interactor
class SubmitApplication:
    """Interactor for submitting an application to a competition."""

    uow: UoW
    idp: IdProvider
    user_gateway: UserGateway
    competition_gateway: CompetitionGateway
    event_bus: EventBus
    clock: Clock

    async def execute(self, competition_id: CompetitionId, data: ApplicationForm) -> CreatedApplication: ...
```

3. **The `execute` skeleton of a mutating interactor**: identity from `idp` → `logger.debug` → loads through gateways (every `None` → `logger.warning` + domain error) → the decision is delegated to the entity/factory/service → `uow.add|delete` → `await self.uow.commit()` → `event_bus.publish()` **strictly after commit** → `logger.info` → return DTO. Read interactors: no uow/event_bus, no `info` on success — read paths are silent.
4. **Input**: a pydantic `BaseModel` in the interactor's file (`*Form` for bodies, `*Input` for query); every `Field(...)` limit is a named constant from `input_limits.py`. **Output**: mutation → `None` or `Created<Noun>`; lists → the `{items, total, page}` envelope.
5. **Ports are `Protocol` + `@abstractmethod` + `raise NotImplementedError`**. The port's docstring carries the implementation contract ("Implementations must exclude blocked users"), including which errors each method raises. Filters/sorts are frozen dataclasses/enums **next to the gateway protocol**, not in the interactor. Flags are keyword-only (`eager_*`, `for_update`).
6. **UoW** — the four-method protocol from §5.2. **Gateways never commit**; an update = load the entity through the gateway → mutate it with a domain method → `uow.commit()` (no `add` — the identity map issues the UPDATE); `flush([obj])` — when the id is needed before the end of the transaction.
7. **Authorization is the first lines of `execute`**: `get_user_id()` → load the user → check the role; a repeated check becomes an `ensure_*` in `shared.py`. An anonymous use case does not inject `IdProvider`. Role checks live here — routers stay guard-free (§10).
8. **Input validation has two levels**: bounds/DoS — pydantic in application (→ 422); semantics — the domain (→ 400). Tests can tell the layers apart by the error code.
9. **Concurrency**: capacity-style invariants take `get(id, for_update=True)` (a shared mutex on the aggregate-root row); duplicates are double-covered by a unique constraint; a lock timeout maps to a dedicated error → 429.

## 8. Adapters

1. **Folder = technology, class = role + technology prefix**; a small adapter is a flat file; a folder appears once there is a config + at least one implementation. Every tech subpackage owns its `config.py` (frozen slots kw-only dataclass).
2. **An implementation inherits the port directly**, dependencies come through `__init__` into `self._x`, every method carries `@override`, methods appear **in protocol order**; the docstring is a short "how" (the contract lives on the port):

```python
class SAUserGateway(UserGateway):
    """SQLAlchemy-based implementation of UserGateway."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def get(self, user_id: UserId) -> User | None:
        """Load a bare user without organizer/participant relationships."""
        result = await self._session.execute(
            select(User).where(user_table.c.id == user_id),
        )
        return result.scalar_one_or_none()
```

3. **DB — imperative mapping**: one `mapper_registry`; `Table("<plural>", …)` with the `_table` suffix, `DateTime(timezone=True)`, `Enum(..., native_enum=False)`; VOs via `composite()`; relationships declared `relationship(..., lazy="raise_on_sql")` — accidental lazy IO is forbidden, loading happens only through explicit `selectinload` behind the gateway's `eager_*` flags. This same setting turns a missing eager flag into a failing integration test.
4. **Queries**: `select(DomainEntity)` + conditions on `table.c.*`; pagination — `func.count().over().label("total")` in the same query + a stable tie-breaker on `id`. Cross-aggregate JOINs live in the gateway of the selection root; the method name honestly encodes the join (`list_by_competition_with_participant`).
5. **Alembic lives inside `adapters/db/alembic/`**, the URL honors injection via `config.attributes["db_url"]` (the key to test databases), and runs through the project's own CLI. Custom column types deserialize **through domain constructors** — corrupted data never loads silently.
6. **Cache** (when it appears): `*Cache` ports live in `adapters/cache/common/` (the application layer never learns about caching); the caching gateway is a decorator class `Cached*Gateway` assembled in a DI provider (§9.4). Only read models (DTOs) are cached, never ORM entities. Any cache error → `logger.warning` + a miss — **the cache never fails a request**, and that graceful degradation is covered by a test. Invalidation — handlers of domain events.
7. **Infrastructure errors**: an addressable case gets its own `@app_error` class next to the raising code, chained with `from e`; `IntegrityError` is not caught in gateways — it travels to the global handler → 429.
8. **Authentication lives entirely in adapters**: the application knows only `IdProvider.get_user_id() -> UserId`; the bridge entity "external subject → UserId" belongs to adapters, not the domain.

## 9. DI (dishka)

1. **Providers by layer** in `bootstrap/di/providers/`: `ConfigProvider`, `AdapterProvider`, `InteractorProvider`. Exactly two scopes, and the scope is an **ownership decision**: `APP` = lives with the process (engine, Redis, clock), `REQUEST` = depends on the request (session, gateways, idp, interactors). Resources with a lifecycle are generator `@provide`s with teardown in `finally`.
2. **Config is not provided — it is passed in**: `ConfigProvider` is nothing but `from_context(X)` per section; assembly puts the sections into `context=`. No provider reads TOML/ENV itself — tests just pass a different `Config(...)`.
3. **Interactors — one explicit `provide_all(...)`** list, no autoscan; name collisions are solved with `as` aliases at import.
4. **Bindings**: default is `provide(WithParents[Impl])` — registered under itself and all its protocols. Decoration is the deliberate opt-out of `WithParents`: the raw implementation gets a bare `provide`, and the protocol is claimed by a method provider with `provides=Protocol` that composes the decorator. A method provider is also the legitimate home of composition and infrastructure arithmetic (pool splitting, `ensure_bucket_exists()`).

```python
@provide(scope=Scope.REQUEST, provides=ApplicationFormGateway)
def get_application_form_gateway(
    self,
    gateway: SAApplicationFormGateway,
    cache: ApplicationFormCache,
) -> CachedApplicationFormGateway:
    """Provide the cached application form gateway."""
    return CachedApplicationFormGateway(gateway, cache)
```

5. **One object under two types — `AnyOf`**: the session is the UoW implementation; one session = one transaction per request; `expire_on_commit=False` (interactors read entity attributes after commit).

```python
@provide(scope=Scope.REQUEST)
async def get_session(
    self,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AnyOf[AsyncSession, UoW]]:
    """Provide the request-scoped session doubling as the UoW port."""
    async with sessionmaker() as session:
        yield session
```

6. **Assembly is one function** `get_async_container(config)` with `validation_settings=STRICT_VALIDATION` — the graph is validated at process start; a forgotten registration never survives to the first request. Several entrypoints → one container factory per entrypoint sharing `_context(config)`; transport-specific auth is its own provider (the single point where transports differ).
7. The application layer never imports dishka — enforced by import-linter.

## 10. Presentation

1. **One file per resource** in `routers/`; `APIRouter(tags=[...], route_class=DishkaRoute, prefix="/...")`.
2. **A handler is one line**: `FromDishka[Interactor]` in the signature, the body is `return await interactor.execute(...)`; the only logic allowed before the call is transport-level (file magic bytes). Query params — `Annotated[<Input>, Query()]`. There are no separate presentation schemas: routers import application models directly.

```python
@router.post("/")
async def create_competition(
    interactor: FromDishka[PublishCompetition],
    data: CompetitionForm,
) -> CreatedCompetition:
    """HTTP endpoint for creating a competition."""
    return await interactor.execute(data)
```

3. **Errors → HTTP — two global handlers**: a flat table `dict[type[AppError], int]` keyed by exact type; a miss → `logger.critical` + 500 (an unmapped error is a bug); `IntegrityError`/lock timeout → **429 "retry"**; one response shape `{code, message, meta}` for everything including FastAPI validation. Log by threshold: <500 → info, ≥500 → error.
4. Health routes `/internal/alive`, `/internal/ready` are excluded from tracing.

## 11. Bootstrap, config, observability

1. **Three launch functions**: `create_app(config)` — testable and parameterized (order: observability → FastAPI(lifespan) → instrumentation → middleware → container + `setup_dishka` → routers → exception handlers); `app_factory()` — zero-arity for `uvicorn --factory` and the only place `Config.load()` is called; `run_api()` — the production launcher. The container closes in lifespan.
2. **Config**: a single env variable `APP_CONFIG_PATH` → TOML; the root frozen dataclass `Config`, sections = fields; config classes live next to their adapters, bootstrap composes them. No pydantic-settings, no scattered `os.environ`. Tuning comments sit above the fields they explain.
3. **Every process is a console script** through the bootstrap CLI (`[project.scripts]`); one docker image runs several services via different `command:`; migrations are a one-shot service the API waits on (`service_completed_successfully`).
4. **Observability** lives in `*_common/observability/` and is called from bootstrap: structlog with one processor chain reused as `foreign_pre_chain` (foreign library logs also become JSON with a trace_id); `SERVICE_INSTANCE_ID` = name+PID+uuid; `enabled=False` swaps in no-op providers so span-bearing code runs unchanged in tests.

## 12. Errors: the cross-cutting taxonomy

The base class and the two declaration templates are in §5.3; the HTTP mapping is in §10.3.

1. The hierarchy is flat — every error inherits `AppError` directly. One code + a contextual message beats twenty codes; the message template for access rules is "Only <who> can <what>".
2. **Location = meaning**: `entities/errors/` — invariant and access violations; `application/errors/` — not-found/uniqueness; adapter-local errors — next to the adapter that raises them.
3. **Non-domain exceptions** follow the pattern `msg = f"..."` → `raise RuntimeError(msg)`.
4. The two vocabularies never mix: the string code is the language of the HTTP contract, the class name is the language of the domain.

## 13. Docstrings, comments, logging, typing

1. **Every public object has a docstring** — including one-line routes and error classes. One line, imperative for functions, a business formulation for classes; entity names in ``double backticks``. **The contract lives on the port, the "how" on the implementation**; a delegating method documents *why* it delegates.
2. **`#` comments explain only "why"**: an external constraint, a non-obvious decision, an invariant the code cannot show. Never "what the next line does". A multi-line comment telling the story of a decision is welcome when the decision earns it.
3. **Logging**: `logger: Logger = structlog.get_logger(__name__)`; the message is a capitalized phrase, context goes only in kwargs, never f-interpolation: `logger.info("User blocked", target_user_id=..., admin_user_id=...)`. Level semantics: `debug` = intent, `info` = an accomplished mutation, `warning` = an expected refusal/degradation, `exception` = the unexpected, `critical` = a code defect. PII and secrets are never logged.
4. **Module order**: imports → private singletons (`_tracer`, `_retort`) → public constants → `logger` → private helpers → models → the class → a module-level factory at the bottom. Serializers/tracers — one per module, never global.
5. **Typing**: mypy strict; `@override` mandatory; absolute imports only; `TYPE_CHECKING` is not used (DI needs runtime types anyway; forward references are strings); `# type: ignore` always carries a code; `Any` only pointwise; PEP 695 aliases and generics. All bool arguments keyword-only; the primary id positional, everything else after `*`.
6. **"Three homes" for numbers**: input limits — `application/common/input_limits.py`; domain bounds — UPPERCASE next to the VO (the form imports them — one source); local tuning — in the consuming module. In pydantic `Field` — named constants only.

## 14. Tests

### 14.1 The ten rules

Every test is written and reviewed against these:

| ID | Rule | Scope |
|---|---|---|
| 001 | AAA (Arrange, Act, Assert) | all tests |
| 002 | Single Act per test | unit tests |
| 003 | No `if` statements in tests | all tests |
| 004 | Name tests in plain English (behaviour description) | all tests |
| 005 | Don't include the method name in the test name | business logic |
| 006 | Mocks ONLY for unmanaged dependencies — here: fakes behind ports, mock libs banned | integration |
| 007 | Verify interactions at system edges ONLY | integration |
| 008 | Object Mother / factories for fixtures | Arrange |
| 009 | Inject time as an explicit dependency | logic with dates |
| 010 | Hardcode expected values — never duplicate the algorithm | all tests |

How the rules are read in practice:

- **001** — phases are separated by a blank line, not by `# Arrange/# Act/# Assert` comments; a phase clarification is a dash comment. A test whose whole promise is "nothing was raised" says so in a comment where the Assert would be.
- **002** — the operation under test does not build its own Arrange. When a builder would cost more than a split, cut the test in two: "the first step landed" and "the second step landed on state built by a factory". Permitted Act extensions: "do and immediately read back", races.
- **003** — no branching in a test body. A polling loop lives in a waiter helper that returns the state it waited for; branching inside such a helper is fine, branching in a helper that feeds Assert a value is not. Filtering comprehensions in Assert are branching too — write the expected value out instead.
- **004/005** — the name is a promise, not a call: `test_a_profile_keeps_the_city_it_was_given`, not `test_profile_set_city_stores_city`. Binding for domain and application tests; adapter, HTTP-route and e2e tests may be named after the port — there the port's name *is* the behaviour. A type's name is not a method's name: `test_city_rejects_empty` is fine.
- **006** — fakes behind ports, never mocks; the ban is mechanical (ruff `banned-api`). Own infrastructure is real (testcontainers); an external HTTP system gets its own fake router/server.
- **007** — only true cross-process edges may have interactions asserted (a published message, a call to the external provider's fake). Counting a handler's trips to an in-process collaborator is banned: the count is not observable from outside, and the counter reddens on any internal reshuffle.
- **008** — build domain objects through factories, never by hand in Arrange.
- **009** — the clock is injected; `tests/clock.py` holds the shared `NOW` constant (details: §14.6.8).
- **010** — the expected value is written by hand, with a comment naming the second place to fix; production *constants* (limits, `PAGE_SIZE`) are imported — the test hits exactly `LIMIT + 1`; production *logic* is never re-executed. The one sanctioned middle case: a listing's sort key inside a dedicated expected-list helper, carrying a comment that names its production mirror.

### 14.2 The four pillars

| Pillar | Key question |
|---|---|
| Protection against regressions | Does it test complex domain logic? |
| Resistance to refactoring | Does it test behaviour, not implementation? |
| Fast feedback | Is it in-memory only (unit) or necessary I/O (integration)? |
| Maintainability | Is it short, clear, AAA-structured? |

`Quality = P × R × F × M` (each normalized 0–1). Two verdicts follow: `R < 1.0` — the test is coupled to the implementation, harmful, rewrite it; `P < 0.2` — the test is trivial, delete it, it does not pay for its own upkeep.

### 14.3 Process: doc-first + TDD

Working order for a use case: **spec** (Business Rules in the order of the future `execute()`, with an error code per rule — §16) → **red test** → code to green → refactor.

A pure test refactor has no red to show, so its check is equivalence: the suite is green before and after, and the number of passing tests moves by exactly the number the work declared — a discrepancy means the change touched something it did not mean to. After splitting a test that asserted several steps, break the step in production code and confirm that the test naming it is the one that reddens — one such mutation per touched file.

### 14.4 Structure and levels

1. `tests/unit/` mirrors `entities/` (one file = one entity method/operation); `tests/integration/<feature>/` is 1:1 with `application/` (one file = one operation); `tests/common/` holds factories and pure helpers. A module's test is found at the module's address: `tests/<level>/<module path>/test_<module>.py`; a scenario test with no mirror in `src` lives at the root of its level. Levels are separated by paths, not markers.
2. **Unit** — the domain only: VOs, invariants, factories, entity methods and state machines, domain services. Synchronous, no I/O. **Integration** — over HTTP against the in-process app assembled by the production `create_app(config)`.
3. **Unit/integration duplication is deliberate**: the unit test pins the type and the **text** of the domain exception, the integration test pins the HTTP status and the **machine code** of the same rule.

### 14.5 Integration machinery

1. **Testcontainers session-scoped** (one set per xdist worker) + **template database**: migrations run once into a template DB, then per test `CREATE DATABASE … TEMPLATE` → `DROP … WITH (FORCE)` over an AUTOCOMMIT engine. One Redis, autouse `flushdb()`.
2. **The test `Config` is built by hand** (its fixture docstring says "Never calls `Config.load()`") — no monkeypatch, no dependency_overrides; noise silenced explicitly: OTel off, jitter 0, small pools.
3. The app's container is the tests' container (`app.state.dishka_container`); `LifespanManager` really runs bootstrap; a REQUEST scope opens with `async with container()`. Test DI overrides (when needed at all) are a separate provider **appended last** (the last registration wins); objects the test owns come in via `from_context`.
4. **A typed `ApiClient`**: httpx over `ASGITransport(raise_app_exceptions=False)`; one typed method per endpoint; responses load into the **real production DTOs**; fluent asserts `assert_status(200).ensure_content()` / `assert_error(403, "ACCESS_DENIED")`; authorization is a context manager `authenticate(...)` over a `ContextVar` — parallel coroutines each carry their own credentials. Public URLs are checked with a second, plain `httpx.AsyncClient` — the way a browser would see them.
5. **Arrange goes only through gateway facades** (`await gateway.organizer.create_with_admin(gateway.admin)`), never through `api_client`; the philosophy is "arrange through public behaviour". Direct DB/Redis writes are allowed only where no API path exists or to "move time" — as a named helper (`_update_directly`, `prime_*`) that also invalidates the cache through the app's DI container.
6. **No mocks**; isolation — testcontainers; "dishonest" input — `Model.model_construct(...)` past client-side validation; "dishonest" state — the named direct-write helpers. A foreign system (external API, LLM provider) gets a fake behind its port/transport — not a stub with canned data but a bridge honoring the wire contract.
7. Polling only inside a waiter helper with a deadline that returns the awaited state and keeps the last seen model for its failure message; `sleep` in test bodies is banned.

### 14.6 Writing conventions

1. **The name is a complete English sentence promising behaviour**: `test_<actor>_can/cannot_<action>`, `test_<action>_fails_if_<cause>`, `test_<x>_rejects_<what>`, `test_concurrent_<action>_<invariant>`, declarative facts for listings (`test_archived_competitions_are_hidden`). Numbers in words; the refusal cause always in the name.
2. **Every test has a docstring**: one line, present tense, a finished sentence; the error code in caps in the text ("…is rejected with APPLICATION_ALREADY_EXISTS"); no "Test" prefix.
3. **A positive test compares the whole object** (`assert result == ExpectedModel(...)`; nondeterministic fields taken from the result; for mutations of `updated_at` — first monotonicity, then substitute and compare whole). **A negative test is exactly one line** `assert_error(status, "CODE")`; a side effect after a refusal is checked where the refusal protects an invariant.
4. **The mechanical negative checklist per use case**: 401 unauthenticated; role missing → 404 `<ROLE>_NOT_FOUND` (not 403 — no existence oracle); a stranger with the same role (`interloper`) → 403; `uuid4()` → 404; every limit hit at `+1` from the production constant → 422; state conflicts → 409 with a domain code; domain validation → 400; for listings — empty list, pagination, invalid pages, every filter and both sort directions, owner isolation, hiding of blocked/archived; a race on every mutation invariant.
5. **Races are a first-class genre**: exactly two competitors in `asyncio.gather`; symmetric — `sorted(statuses) == [200, 409]` + the invariant checked by a separate read; asymmetric — the expectation computed from the winner. This is the sufficient verification of `FOR UPDATE`: remove the lock and these tests go red.
6. **Canonical actors**: `owner`, `interloper`, `participant`, `admin`. File order: happy path → races → the `fails_if` quartet → conflicts → not_found.
7. **Parametrization**: `parametrize` when the value changes and the scenario doesn't; different refusal causes are separate tests; `ids=` is never used; datasets are module constants `(patch, expected code)` where the code pins which layer catches (`VALIDATION_ERROR` = pydantic vs a domain code).
8. **Time**: the injected `Clock`; unit tests use `FakeClock` frozen on a module `NOW` with non-zero seconds/microseconds (otherwise missing normalization is invisible); integration uses the real `SystemClock`; data uses only `timedelta` from `now`, never absolute dates — tests must not rot.
9. If the project drives an LLM: the wording of a prompt is not under test — whether the model obeys a rule is a question for a separate eval suite, not for a substring assertion.

### 14.7 Factories and Hypothesis

1. Factories (polyfactory): `DataclassFactory[Entity]` for unit, `ModelFactory[Form]` for integration; providers are private module-level functions; randomness only through `__random__`/`__faker__`; `@post_generated` keeps FK fields consistent; FKs into external aggregates stay empty — the test fills them explicitly. **A factory when the values are indifferent; by hand when the test is about the values.**
2. Hypothesis — unit only; strategies are `@st.composite` functions in one `composite.py`; `max_examples` 10–30; an invariant is **generated** coherently, never patched up after the draw; `valid_text()` excludes Unicode categories instead of blacklisting; `pytest.raises` with `match=` for errors carrying a rule sentence, without `match=` where the type says it all. After a raise from a mutating method — assert the state did not change.

## 15. Workflow: branches, commits, PRs

1. **Branches**: `feat|fix/<kebab>` off a fresh main branch → PR → rebase-merge (the branch discipline itself: §0).
2. **A PR is a vertical tracer-bullet slice**: one ticket = one PR, ≤500–700 diff lines; never sliced by layer. The `.importlinter` edit, the migration, the DI registration and the doc ride in the same PR as the code.
3. **Commits — Conventional Commits**, imperative; the scope names a subsystem/context (`(exporter)`, `(db)`), never a feature; a large slice gets a bulleted body (one bullet = one layer). A bugfix = the fix + its regression test in one commit.
4. Before every commit: `just lint` and `just static` by hand (§0); pre-commit hooks are the safety net, CI is the barrier.
5. **Releases**: SemVer tags `v*` trigger deploys; CI verifies the tag sits on the main branch.
6. Whatever outlives a feature moves into an ADR/docs in the same PR; the feature's working artifacts die with it.

## 16. Documentation

1. **Doc-first**: the use-case page is written **before** the implementation — documentation as specification; when a concept is renamed, the doc is renamed (git rename) together with the code.
2. **`docs/` is a domain reference, not a code reference** (hand-written, no autodoc), mirroring the code 1:1. Page templates are rigid: an entity — Purpose → Attributes table (types link to VOs) → numbered Business Rules → Lifecycle/Relationships in ASCII; an interactor — Purpose → Input/Output tables → **Business Rules in `execute()` order with an error code per rule** → Errors; `docs/errors/` — the code registry as the API contract. The doc describes the observable contract, not the code structure.
3. **Three documents — three audiences**: `README.md` (showcase + architecture: Features → Quickstart through `just` → a command cheat-sheet table → Architecture as an ASCII tree with an invariant sentence → Request flow numbered; no badges, emoji or marketing); `GETTING_STARTED.md` (human onboarding); `AGENTS.md` (operational rules for AI). Duplication between them is deliberate — each is self-sufficient.
4. **AGENTS.md as a genre**: every paragraph is a fact, a prohibition ("must not") or a recipe; a prohibition ships with the recipe that replaces it; explicit warnings about tool traps ("`just lint` rewrites files"); the finale is numbered checklists. The test architecture is declared part of the contract ("Test patterns to preserve"). On coverage: "a floor, not a replacement for assertions".

## 17. Checklist: starting a new project

1. Lay down the skeleton from §2.1 with empty packages; write `.importlinter` (§2.2). *Done when `lint-imports` passes.*
2. Write `pyproject.toml` with the full toolchain from §3 (ruff `ALL` + `banned-api`, mypy strict, basedpyright, typos, gitleaks baseline, pytest config); pin every version `==`; commit `uv.lock`.
3. Copy the shared primitives from §5 into `<project>_common/` verbatim, renaming only the package.
4. Write the justfile from §3.1. *Done when `just install`, `just lint`, `just static` all pass on the empty skeleton.*
5. Stand up the contour: `docker/` compose with DB + Redis, `Config` + `config_loader` (§11.2), `create_app(config)` with health routes (§11.1), alembic wired for URL injection (§8.5). Add the smoke test `test_probe.py` (liveness/readiness through the ApiClient) — it proves the pipeline containers → migrations → app → DI → client is alive. *Done when `just test` is green with the probe test in it.*
6. Wire CI (§3.6): lint job + test job on every PR. *Done when the first PR shows both jobs green.*
7. Write the project's `AGENTS.md` by distilling this document: the boundaries from §0, the commands from §3.1, the test patterns to preserve from §14. From then on the repository itself is the source of truth; this document stays as the reference behind it.
8. Build the first real use case through §18 — a walking skeleton proving every layer end to end.

## 18. Checklist: adding a use case

1. Page `docs/usecase/<feature>/<scenario>.md`: actor, Input/Output, Business Rules in execution order with error codes (§16.2).
2. Red integration tests in `tests/integration/<feature>/`: happy path + every applicable item of the negative checklist (§14.6.4). *Done when each Business Rule from step 1 has a test naming it, and all are red for the right reason.*
3. Domain: entity/VO/factory/service + `entities/errors/` (§6) + red unit tests alongside.
4. Application: package `application/<feature>/`, ports in `common/gateway/`, the interactor per the §7.3 skeleton, the passport `__init__.py`.
5. Adapters: the SA gateway (`@override`, protocol order), the alembic migration.
6. DI: registration in the providers (`provide_all` / `WithParents`); STRICT validation catches anything forgotten.
7. Presentation: the one-line handler; new errors added to the mapping table and `docs/errors/`.
8. `.importlinter` — if a new package appeared.
9. One commit/PR — the whole slice. *Done when `just lint`, `just static`, `just test` are green, every Business Rule from the doc has at least one green test naming it, and the diff is a single vertical slice within the PR budget (§15.2).*
