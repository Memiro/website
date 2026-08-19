set shell := ["sh", "-c"]
# recipe arguments reach the command as "$@", not glued into one string
set positional-arguments := true


[doc("All command information")]
[private]
default:
  @just --list --unsorted --list-heading $'commands…\n'


[doc("Prepare venv, .env and git hooks for developing")]
[group("Common")]
@install:
    uv sync --all-groups
    test -f .env || cp .env.example .env
    uv run pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

[doc("Run manage.py (e.g. `just manage createsuperuser`)")]
[group("Common")]
@manage *args:
    uv run python manage.py "$@"

[doc("Run the dev server (SQLite, runserver)")]
[group("Common")]
@run:
    uv run python manage.py migrate
    uv run python manage.py runserver

[doc("Lint check")]
[group("Linter and Static")]
@lint:
    echo "Run ruff check..." && uv run ruff check --exit-non-zero-on-fix
    echo "Run ruff format..." && uv run ruff format --check
    echo "Run codespell..." && uv run codespell

[doc("Static analysis")]
[group("Linter and Static")]
@static:
    echo "Run mypy..." && uv run mypy --config-file pyproject.toml
    echo "Run bandit..." && uv run bandit -c pyproject.toml -r src
    echo "Run django checks..." && uv run python manage.py check

[doc("Run pre-commit on all files")]
[group("Linter and Static")]
@pre-commit:
    uv run pre-commit run --show-diff-on-failure --color=always --all-files

[doc("Run tests (SQLite in-process, no docker needed)")]
[group("Test")]
@test *args:
    uv run pytest -x --ff "$@"

[doc("Run tests with coverage")]
[group("Test")]
@test-cov *args:
    uv run coverage run -m pytest -x --ff "$@"
    uv run coverage combine
    uv run coverage report --show-missing --skip-covered --sort=cover --precision=2
    rm .coverage*

[doc("Run the local contour (PostgreSQL, gunicorn)")]
[group("Docker")]
@up:
    docker compose -f docker-compose.yaml -f docker-compose.local.yaml up -d --build --wait

[doc("Stop the local contour")]
[group("Docker")]
@down:
    docker compose -f docker-compose.yaml -f docker-compose.local.yaml down

[doc("Run the test contour")]
[group("Docker")]
@test-up:
    docker compose -f docker-compose.yaml -f docker-compose.test.yaml up -d --build --wait

[doc("Stop the test contour")]
[group("Docker")]
@test-down:
    docker compose -f docker-compose.yaml -f docker-compose.test.yaml down
