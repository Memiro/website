# 01 — Скаффолдинг Django-проекта

**What to build:** Фундамент проекта: Django-проект запускается локально, пустая главная страница отдаётся браузеру, тестовая инфраструктура работает, django-modern-rest подключён и отвечает на пробный JSON-эндпоинт.

**Blocked by:** None — can start immediately.

**Status:** ready-for-human

- [x] `runserver` поднимает сайт локально, главная отдаёт HTML-заглушку
- [x] Тестовый раннер работает, первый HTTP-тест (главная отвечает 200) зелёный
- [x] django-modern-rest подключён, пробный типизированный эндпоинт отвечает и отражён в OpenAPI-схеме
- [x] Админка открывается, суперпользователь создаётся
- [x] База: SQLite для разработки, конфигурация готова к PostgreSQL в проде

## Comments

2026-08-19 (agent): Реализовано. Django 6.1 + django-modern-rest 0.14 (pydantic-сериализатор),
src-layout (`src/memiro`), обвязка по образцу dAIry: pyproject с пином версий и группами
lint/test/dev, justfile, docker-compose base + local/test оверлеи (PostgreSQL + gunicorn),
двухстадийный uv-Dockerfile, pre-commit (conventional commits, detect-secrets).
Dev — SQLite (`just run`), контуры compose — PostgreSQL (переключение по `POSTGRES_HOST`).
5 HTTP-тестов зелёные: главная, /api/ping, OpenAPI-схема, админка (вход суперпользователя,
редирект анонима). Live-smoke через runserver пройден. Статус ready-for-human — на приёмку владельцем.
