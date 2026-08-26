set positional-arguments := true

# List available commands
default:
    @just --list --unsorted

# Prepare venv, .env and git hooks for developing
install:
    uv sync --frozen --extra dev
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
    docker compose -f docker/docker-compose.yml up -d --wait db

db-down:
    docker compose -f docker/docker-compose.yml stop db

# Apply migrations to the local database
migrate:
    uv run memiro migrations apply

# Run the API locally
run:
    uv run memiro run api
