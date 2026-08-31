# 13: Скелет фронта (Astro SSR)

**What to build:** Сервис frontend живёт в контуре: Astro в SSR-режиме (не SSG) на Node, свой Dockerfile, nginx маршрутизирует витрину на него, а `/api/` — на api. У фронта свой AGENTS.md — правила python-инструкции на TypeScript не распространяются (решение 39). Заготовка структуры (pages, layouts, components, islands, lib, styles), базовый layout с русским языком (i18n нет). Авторизации и глобального стора (Pinia) нет. Демо: заглавная страница отвечает с сервера через nginx.

**Blocked by:** 05 (контур и CI)

**Status:** resolved

- [ ] `just up` поднимает контур с frontend; страница отдаётся SSR через nginx
- [ ] AGENTS.md фронта написан; описаны команды сборки и запуска
- [ ] CI собирает и проверяет фронт на PR
- [ ] Островная архитектура заготовлена (директория islands, пример client:visible)
