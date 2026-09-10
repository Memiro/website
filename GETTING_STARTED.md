# Как начать

Страница для человека, который впервые открыл репозиторий. Правила для
агентов — в `AGENTS.md`, витрина проекта — в `README.md`; повторы между тремя
документами намеренные, каждый самодостаточен.

## Что понадобится

- **Python 3.13** — версия зафиксирована в `.python-version`, `uv` поставит её сам.
- **[uv](https://docs.astral.sh/uv/)** — единственный менеджер зависимостей;
  версии закреплены точным `==`, локфайл в репозитории.
- **[just](https://just.systems/)** — все команды проекта живут в `justfile`, и
  документация ссылается на рецепты, а не на сырые командные строки.
- **Docker с плагином compose** — контур базы для тестов и локального запуска.

## Первый запуск

```sh
just install
```

Рецепт делает три вещи: ставит зависимости из локфайла, создаёт `.env` из
`.env.example` (если его ещё нет) и ставит git-хуки. Хуки — страховка, а не
замена: перед коммитом `just lint` и `just static` запускают руками.

Дальше — тесты, они и проверяют, что окружение живое:

```sh
just test
```

Рецепт сам поднимает Postgres в docker, поэтому отдельного шага «поднять базу»
нет. Интеграционные тесты приносят собственную базу через testcontainers:
миграции один раз накатываются в шаблонную базу, а каждый тест получает её
свежий клон.

Запустить API локально:

```sh
just run          # uvicorn на 127.0.0.1:8000
```

Или контур целиком — так, как он работает в проде (nginx перед uvicorn и
gunicorn, миграции отдельным одноразовым сервисом):

```sh
just up
curl http://127.0.0.1:8080/internal/alive   # {"status":"ok"}
open http://127.0.0.1:8080/admin/           # админка владельца
just down
```

Одноразовый сервис `migrations` накатывает alembic, затем миграции Django
служебных таблиц, затем заводит учётку владельца из `MEMIRO_ADMIN_USERNAME`
и `MEMIRO_ADMIN_PASSWORD` (см. `.env.example`). Домен принадлежит alembic:
Django-миграции трогают только `auth_*` и `django_*`.

## Прод

Прод — VPS с docker. Образы собирает CI и кладёт в GitHub Container Registry
(`ghcr.io/memiro/website-backend`, `ghcr.io/memiro/website-frontend`): на
push в `dev` — под тегом `dev`, на релизный тег `v*` — под версией и `latest`.
Сервер ничего не собирает. Контур — тот же compose с override-файлом: nginx
выходит на 80 и 443 хоста, `www` и `http` отвечают одним 301 на
`https://memiro.ru`, HSTS и кеш статики — в `.config/nginx.prod.conf`.

В клоне репозитория на сервере (`/srv/memiro`) вне git лежат три файла:

- `.env` — `MEMIRO_IMAGE_TAG` (версия релиза), `MEMIRO_ADMIN_USERNAME` и
  `MEMIRO_ADMIN_PASSWORD`, `MEMIRO_DB_PASSWORD`; образец — `.env.example`.
- `.config/config.prod.toml` — конфигурация приложения с настоящим
  `secret_key`, `allowed_hosts = ["memiro.ru"]` и паролем базы из `.env`;
  образец — `.config/config.prod.example.toml`, override подставляет копию в
  `APP_CONFIG_PATH`.
- `.config/smtp_password` — см. «Письмо менеджеру».

Файлы с секретами — `chmod 600`. Compose сам ищет `.env` рядом с первым
compose-файлом, а не в корне, поэтому `--env-file .env` в командах обязателен
(локально это делает `just`). Выкатка релиза: поправить `MEMIRO_IMAGE_TAG`
в `.env` и выполнить

```sh
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.prod.yml pull
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --wait
```

`PUBLIC_SITE_URL` и `PUBLIC_METRIKA_ID` запекаются в образ витрины в CI из
variables репозитория; после смены счётчика нужен новый образ, а не рестарт.

Пакеты в GHCR приватные (настройки организации), поэтому один раз на
сервере: `docker login ghcr.io -u <логин GitHub>` с классическим PAT, у
которого единственный скоуп `read:packages`.

Сертификат живёт на хосте: certbot держит его в `/etc/letsencrypt`, nginx
монтирует каталог только на чтение. Без сертификата nginx не поднимется:
конфиг ссылается на файлы `live/memiro.ru/`. Выпуск и продление идут по
DNS-проверке через API Beget, значит домен может смотреть куда угодно, в
том числе на старый хостинг во время переезда:

1. В панели Beget включить «Доступ по API», на сервере положить
   `/root/.beget-api` (`chmod 600`) с двумя строками: `BEGET_LOGIN=…` и
   `BEGET_PASSWORD=…` (пароль API, не панели).
2. Скопировать `docker/certbot/beget-acme-auth.sh` и
   `beget-acme-cleanup.sh` в `/root/` (`chmod 700`); хук ставит TXT-запись
   `_acme-challenge`, ждёт её на всех четырёх NS Beget и убирает после.
   Нужен `dig` (`apt install dnsutils`).
3. Первый выпуск:
   `certbot certonly --manual --preferred-challenges dns --manual-auth-hook /root/beget-acme-auth.sh --manual-cleanup-hook /root/beget-acme-cleanup.sh -d memiro.ru -d www.memiro.ru -m memiro.ru@yandex.ru --agree-tos --no-eff-email`.
   Хуки сохраняются в renewal-конфиге, `certbot renew` (системный таймер)
   идёт тем же путём. Deploy-хук
   `/etc/letsencrypt/renewal-hooks/deploy/memiro-nginx-reload.sh` делает
   `docker compose … exec nginx nginx -s reload`; `certbot renew --dry-run`
   проверяет цепочку.
4. Контур проверяется до переключения DNS с самого сервера:
   `curl --resolve memiro.ru:443:127.0.0.1 https://memiro.ru/` — и с ноутбука
   через строку `<IP> memiro.ru www.memiro.ru` в hosts.

Синтаксис обоих edge-конфигов проверяется без прода: `just nginx-check`.

### Письмо менеджеру

Заявки уходят письмом на `memiro.ru@yandex.ru` с того же ящика. Яндекс пускает
почтовые программы только по паролю приложения, поэтому один раз:

1. В Яндекс ID → Безопасность → Пароли приложений создать пароль «Почта».
2. В настройках ящика включить доступ для почтовых программ (IMAP/SMTP).
3. На сервере положить пароль одной строкой в `.config/smtp_password`
   (`chmod 600`) — файл в `.gitignore`, конфиг ссылается на него полем
   `password_file`.
4. Перезапустить контур командой выше и проверить вход без отправки письма:

```sh
docker compose --env-file .env -f docker/docker-compose.yml -f docker/docker-compose.prod.yml exec api memiro email check
```

Ответ `OK` значит, что пароль подходит; иначе печатается ответ сервера
(`535 5.7.8 …` — пароль аккаунта вместо пароля приложения или доступ для
почтовых программ выключен). Без файла пароля канал молчит: пишет warning в
лог и не ходит в сеть, а заявка сохраняется как обычно.

## Конфигурация

Приложение читает **одну** переменную окружения — `APP_CONFIG_PATH`, путь к
TOML-файлу (учётные данные владельца админки — секрет деплоя, они приходят
своими переменными и в git не лежат). Локальный конфиг лежит в `.config/config.toml`, контурный —
в `.config/config.docker.toml`. Ни `os.environ` по коду, ни pydantic-settings:
секции конфига — это поля датакласса `Config`, и в тестах он собирается руками.
Пароль SMTP в TOML не лежит: секция `[email]`
называет файл `password_file` (относительный путь — от каталога конфига),
загрузчик читает из него одну строку, а без файла пароль пуст и канал почты
молчит. Так `.config/config.toml` и `.config/config.docker.toml` одинаково
живут и на проде, и в локальном контуре.

## Куда смотреть дальше

- `CONTEXT.md` — язык домена: что такое атрибут, значение, конфигурация и
  вердикт расчёта. Читается первым, если непонятны слова в коде.
- `docs/usecase/` — сценарии: актор, вход, выход и бизнес-правила по порядку
  выполнения, у каждого правила свой код ошибки.
- `docs/entities/` и `docs/value-objects/` — справочник сущностей и величин.
- `docs/adr/` — почему сделано так, а не иначе.
- `docs/agents/coding-instruction.md` — полный стандарт кодирования, на котором
  стоит репозиторий.

## Как здесь работают

1. Ветка от `dev`, PR в `dev`, rebase-merge; `main` — прод, туда только релиз.
2. Сначала страница сценария в `docs/usecase/`, потом красный тест, потом код.
3. Один PR — один вертикальный срез через все слои: домен, приложение,
   адаптеры, DI, презентация, миграция, тесты и документ.
4. Перед коммитом: `just lint`, `just static`, `just test`.
