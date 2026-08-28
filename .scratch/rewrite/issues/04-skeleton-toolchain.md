# 04: Скелет репозитория и тулчейн

**What to build:** Старый код MVP уходит в ветку-справочник, main переписывается с нуля в этом же репозитории (решение пользователя при нарезке). Перенос в ветку и очистка main — операция владельца: §0 инструкции запрещает агенту коммит и пуш в main, поэтому агентская часть тикета начинается с чистого main и идёт как всё остальное — feature branch → PR → rebase-merge с OK владельца. Содержимое: пустой скелет §2.1 (`src/memiro/` + `src/memiro_common/`), проходящий линт: `.importlinter` с контрактами слоёв §2.2 и решения 41, pyproject с полным тулчейном §3 (ruff ALL + banned-api с запретом mock/monkeypatch, mypy strict с доп. кодами, basedpyright, import-linter, typos, gitleaks с baseline, bandit, pytest; dev-зависимости слоёными extras), версии запинены `==`, примитивы §5 скопированы в `memiro_common/` дословно с переименованием пакета (~250 строк, пустой `__init__.py`), justfile §3.1 с поправкой решения 51 (`db-up` поднимает только db, Redis нет).

**Blocked by:** 02 (учредительные документы)

**Status:** ready-for-human

- [x] Владелец перенёс старый код в ветку-справочник и очистил main; доменные документы (CONTEXT.md, docs/adr/) сохранены на main — до этого агентская часть не стартует
  - 2026-08-26: модель изменена решением 65 — рабочий ствол теперь `dev` (MVP-код остался в истории и в `main` до первого релиза); `dev` очищен коммитом c80d7a1, документы сохранены
- [x] Скелет §2.1 лежит пустыми пакетами; `lint-imports` проходит
- [x] `just install` ставит pre-commit хуки; `just lint`, `just static` зелёные на пустом скелете
- [x] `memiro_common/` содержит Clock, UoW, AppError/app_error, @interactor, logger + observability — дословно по §5
- [x] uv.lock закоммичен, версии запинены; корень репозитория — только метафайлы

## Comments

**2026-08-26, агент.** Сделано в ветке `feat/skeleton-toolchain`, PR #12
(https://github.com/Memiro/website/pull/12), база — `dev` (решение 65; MVP
остался в истории и в `main`). Двухосевое ревью пройдено, правки внесены:
добавлен временный контракт «django нигде» (половина решения 41, доступная до
тикета 16), extras дополнены пустым `docs` до слоёв §3.1. Зафиксированные
отступления от канона: два `# pyright: ignore` в `interactor.py` (плата за
basedpyright strict поверх дословного §5.4) + per-file-ignore ANN401;
`just install` ставит `--extra dev` (дословный `uv sync --frozen` не ставил
бы pre-commit); CI — тикет 05. Merge — за владельцем.

**2026-08-26, агент (второй раунд).** По слову владельца: повторное двухосевое
ревью (Spec: pass, контракт no-django-yet проверен инъекцией пробного импорта;
Standards: ноль нарушений), правки третьим коммитом — типы pre-commit-хуков
задаёт только `just install`, bandit добавлен в pre-push, мёртвый
`targets` у bandit убран, оговорка про fixture-форму monkeypatch в AGENTS.md.
PR #12 смержен rebase-merge в dev (1e74603), ветка удалена.
