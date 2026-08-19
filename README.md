# Memiro

Сайт студии **Memiro** — производство интерьерных зеркал.

## О проекте

Django-монолит с серверным рендерингом страниц, встроенной админкой и
типизированными JSON-эндпоинтами на
[django-modern-rest](https://github.com/wemake-services/django-modern-rest).

- Репозиторий: https://github.com/Memiro/website
- Python 3.14, зависимости через [uv](https://docs.astral.sh/uv/),
  команды через [just](https://just.systems/)

## Быстрый старт

```sh
just install   # venv, .env, git-хуки
just run       # миграции + runserver на 127.0.0.1:8000 (SQLite)
just test      # тесты (in-process, docker не нужен)
just lint      # ruff + codespell
just static    # mypy + bandit + django check
```

Контуры в docker (PostgreSQL, gunicorn — как в проде):

```sh
just up        # локальный контур на 127.0.0.1:8000
just test-up   # тестовый контур на 127.0.0.1:8001
```

Пробные точки: `/` — главная, `/api/ping` — живость API,
`/api/openapi/schema.json` — OpenAPI-схема, `/admin/` — админка
(`just manage createsuperuser`).

## Структура

- `src/memiro/` — код сайта (settings, urls, api)
- `tests/` — HTTP-тесты через тестовый клиент Django
- `CLAUDE.md` — инструкции для AI-агентов (Claude Code)
- `docs/agents/` — конфигурация инженерных скиллов (issue-трекер, triage-метки, домен-доки)
- `docs/adr/` — архитектурные решения (ADR)

## Задачи

Спека и тикеты — локальные markdown-файлы в `.scratch/new-site/`
(см. `docs/agents/issue-tracker.md`).
