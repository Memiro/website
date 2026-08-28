# 05: Контур, probe-тест и CI

**What to build:** Живой конвейер «контейнеры → миграции → приложение → DI → клиент»: docker-контур за nginx (api на uvicorn, migrations one-shot, одна Postgres — без Redis, решение 51), Config + config_loader §11.2, `create_app(config)` с health-роутами §11.1, alembic с инъекцией URL, смоук-тест `test_probe` (liveness/readiness через типизированный ApiClient на testcontainers + template database §14.5), CI с джобами lint и test на каждый PR. Сервисы admin и frontend добавятся своими срезами.

**Blocked by:** 04 (скелет и тулчейн)

**Status:** ready-for-human

- [x] `just up` поднимает локальный контур (nginx + api + db), health-роуты отвечают
  - 2026-08-26: проверено — nginx (:8080) → api → DI → Postgres, `/api/internal/alive` и `/ready` отвечают 200; migrations one-shot завершился с кодом 0
- [x] `just test` зелёный с probe-тестом: интеграционная машинерия §14.5 работает целиком
  - 2026-08-26: testcontainers (postgres:17) + template database + LifespanManager + типизированный ApiClient; 2 passed
- [x] Порядок накатки миграций зашит в one-shot сервис, не в память
  - 2026-08-26: сервис `migrations` в compose гоняет `memiro migrations apply`; api стартует по `service_completed_successfully`; django migrate допишется в срезе админки (комментарий в compose)
- [x] Первый PR показывает оба CI-джоба зелёными
  - 2026-08-26: PR #13 — lint (28s) и test (33s) зелёные; testcontainers работает на GitHub-раннере

## Comments

2026-08-26, двухосевое ревью (Standards + Spec) перед мержем PR #13:

- Исправлено: xdist в CI-джобе test (§3.6); `ObservabilityConfig` переехал в `memiro_common/observability/config.py` (§11.2 — конфиг живёт рядом со своим кодом); явный `elif` в CLI; комментарий-обоснование отступления от §10.2 в `/internal/ready` (проба — инфраструктура, интерактор был бы церемонией).
- Осознанные отложенности: `assert_error` и `authenticate(...)` в ApiClient появятся с первым контрактом ошибок / авторизацией (тикеты 06+); джоб lint включает и шаги `just static` (строже канона §3.6 — оставлено); триггер `push: dev` даёт сигнал на стволе после rebase-merge (оставлено).

2026-08-26, второе двухосевое ревью (полный дифф ветки):

- Исправлено: `set dotenv-load` в justfile — хостовые `just run`/`just migrate` читали бы `APP_CONFIG_PATH` из ниоткуда (`just migrate` проверен вживую); честный докстринг `app_factory` (CLI-миграции тоже зовут `Config.load()`); CI-джоб test ходит через рецепт `just test-ci`, не сырой pytest; YAML-якорь `x-app` убрал дубль build/env/volumes в compose; развёрнут комментарий, почему `HealthStatus` живёт в презентации.
- Осознанно оставлено: `SystemClock` в DI (канонная §9-обвязка, нужна тикету 06 — удалять и возвращать было бы churn).
