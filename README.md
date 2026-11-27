# LifeFlow

Система управления личными задачами, целями и финансами.

Приложение предназначено для пользователей, которые хотят планировать личные дела, отслеживать цели и вести учёт доходов и расходов.

## Команда

- Салахетдинов Камиль (@KamilS25) — тимлид / Product Owner, Tech Lead / Backend Developer.
- Богаенко Елизавета (@ka-chow) — Frontend Developer.
- Сулейманова Виктория (@vst-17) — DevOps Engineer.

## Стек технологий

- Python 3.13
- FastAPI
- PostgreSQL 17
- SQLAlchemy — ORM, Alembic — миграции
- Docker и Docker Compose
- uv — менеджер зависимостей
- pydantic-settings — конфигурация приложения
- GitHub Actions

## Статус

В LifeFlow можно зарегистрироваться, вести личные задачи и цели, записывать доходы и расходы и смотреть сводку по своему аккаунту. Веб-интерфейс использует тот же API FastAPI и PostgreSQL.

## Установка и запуск

### Требования

Для запуска проекта необходимы:

- Git;
- Docker с плагином Compose или Docker Desktop.
- Свободный локальный порт 8000. Его можно изменить в `.env`.

### Запуск через Docker Compose

1. Клонируйте репозиторий и перейдите в его каталог:

   ```sh
   git clone https://github.com/KamilS25/app-conf-project-LifeFlow.git
   cd app-conf-project-LifeFlow
   ```

   При проверке открытого PR переключитесь на его ветку перед запуском.

2. Создайте локальный файл конфигурации на основе примера. В macOS, Linux или Git Bash:

   ```sh
   cp .env.example .env
   ```

   В PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Задайте собственный `POSTGRES_PASSWORD` в `.env`. Если пароль содержит `$` или `#`, заключите значение в одинарные кавычки. Храните файл только локально.

4. Соберите образы и запустите приложение вместе с базой данных:

   ```sh
   docker compose up --build
   ```

При запуске Docker Compose поднимает два сервиса:

- `app` — FastAPI-приложение;
- `db` — PostgreSQL 17.

После проверки готовности PostgreSQL контейнер приложения выполняет `alembic upgrade head` и запускает Uvicorn. Для фонового запуска с ожиданием готовности обоих сервисов используйте `docker compose up --build --wait`. Данные PostgreSQL сохраняются в именованном томе `postgres_data`.

Откройте [LifeFlow](http://localhost:8000/app) в браузере. В режиме `dev` кнопка **Посмотреть демо** открывает отдельный демонстрационный аккаунт с синтетическими задачами, целями и операциями. Для своего аккаунта выберите **Создать аккаунт** и задайте пароль длиной от 15 символов.

### Проверка работоспособности

Проверить состояние контейнеров:

```sh
docker compose ps
```

В выводе `app` и `db` должны иметь статус `healthy`. Проверьте приложение и подключение к PostgreSQL:

```powershell
Invoke-RestMethod http://localhost:8000/
Invoke-RestMethod http://localhost:8000/health
```

В macOS, Linux или Git Bash:

```sh
curl -fsS http://localhost:8000/
curl -fsS http://localhost:8000/health
```

Оба запроса возвращают HTTP 200. Тела ответов приведены в разделе [API](#api). При остановке PostgreSQL `/health` возвращает HTTP 503, а `/` продолжает отвечать HTTP 200.

### Окружения `dev` и `prod`

Укажите `APP_ENV` в `.env`. Режим `dev` включает демо, Swagger UI (`/docs`), ReDoc (`/redoc`) и схему `/openapi.json`. Режим `prod` использует cookie с флагом `Secure`. Для входа в этом режиме открывайте сайт по HTTPS. После смены значения выполните `docker compose up --wait`. `GET /health` и `GET /version` работают в обоих режимах.

Пример использует `APP_ENV=dev`. Для отдельного локального файла `.env.prod` создайте его из `.env.example`, задайте собственный `POSTGRES_PASSWORD` и `APP_ENV=prod`, затем запустите `docker compose --env-file .env.prod up --build --wait`. Для параллельной проверки используйте другое имя проекта (`-p lifeflow-prod`) и свободный `APP_PORT`, чтобы у него был отдельный том и порт.

### Настройка портов

По умолчанию приложение доступно с этого компьютера на `localhost:8000`. PostgreSQL доступна приложению внутри сети Compose на `db:5432`.

Если порт приложения занят, измените `APP_PORT` в `.env`, например:

```env
APP_PORT=8001
```

После изменения конфигурации перезапустите стек:

```sh
docker compose up --wait
```

В запросах и адресе Swagger UI используйте новый порт.

### Просмотр логов и остановка

Просмотр логов всех сервисов:

```sh
docker compose logs -f
```

Остановка контейнеров:

```sh
docker compose down
```

Команда `docker compose down` сохраняет данные PostgreSQL в именованном томе. Для повторной проверки чистого запуска используйте новый проект Compose с отдельным именем и свободным портом. Команда `docker compose down -v` удаляет том и все данные выбранного проекта.

### Локальный запуск без Docker

Для локальной разработки необходимы Python 3.13 и uv.

Установка зависимостей:

```powershell
uv sync --locked
```

Перед запуском задайте `DATABASE_URL` с адресом доступной PostgreSQL. Если база требует пароль, задайте `PGPASSWORD` в окружении процесса. Затем примените миграции и запустите приложение.

```powershell
$env:DATABASE_URL = 'postgresql://localhost:5432/lifeflow'
$env:PGUSER = 'lifeflow'
uv run --locked alembic upgrade head
uv run --locked uvicorn main:app --reload
```

При необходимости укажите `DB_CONNECT_TIMEOUT` (по умолчанию 3 секунды). Приложение читает переменные процесса. Файл `.env` из инструкции Compose при таком запуске автоматически не загружается.

В режиме `dev` документация API доступна на `http://localhost:8000/docs`. Пустой или отсутствующий `DATABASE_URL` останавливает запуск. При заданном адресе и недоступной PostgreSQL `/health` возвращает HTTP 503.

## Предметная область

- **Задачи.** У задачи есть название, статус `todo`, `in_progress` или `done` и необязательные описание, срок и цель. Доска группирует задачи по статусам. Статус меняется через меню на карточке.
- **Цели.** Для цели нужна хотя бы одна связанная задача. Прогресс — процент выполненных задач. При удалении цели связанные задачи остаются на доске.
- **Финансы.** Для дохода или расхода задайте сумму, валюту, свою категорию и дату. Сводка показывает итоги за выбранный период и остаток за всё время по каждой валюте: RUB, USD, EUR и CNY. Покупку валюты можно отразить расходом в одной валюте и поступлением в другой. Рядом с котировками указаны дата и источник. Приложение запрашивает [XML Банка России](https://www.cbr.ru/development/SXML/), а при недоступности пользуется [Курсами ЦБ РФ в XML и JSON, API](https://www.cbr-xml-daily.ru/). Учёт операций работает независимо от получения курсов.
- **Обзор.** Показывает распределение задач по статусам, ближайшие сроки, прогресс целей и валютные остатки аккаунта.

## API

| Метод и путь | Ответ | Назначение |
|---|---|---|
| `GET /` | `{"message": "Hello World"}` для API-клиента, переход на `/app` для браузера | Проверка доступности приложения и вход в интерфейс |
| `GET /health` | `200` и `{"status": "healthy", "database": "ok"}` или `503` и `{"detail": "Service unavailable"}` | Проверка подключения к PostgreSQL запросом `SELECT 1` |
| `GET /docs` | Swagger UI в `dev`, HTTP 404 в `prod` | [Документация API](http://localhost:8000/docs) и [схема OpenAPI](http://localhost:8000/openapi.json) после запуска в `dev` |
| `GET /version` | `{"version": "0.2.0", "team": "LifeFlow"}` | Информация о версии приложения и команде |

### Задачи

| Метод и путь | Успешный ответ | Назначение |
|---|---|---|
| `POST /tasks` | `201` и задача | Создать задачу. Статус по умолчанию `todo` |
| `GET /tasks?limit=20&offset=0` | `200` и список | Получить задачи по возрастанию ID. `limit` от 1 до 100, `offset` от 0 |
| `GET /tasks/{id}` | `200` и задача | Прочитать задачу |
| `PUT /tasks/{id}` | `200` и задача | Заменить изменяемые поля. `title` и `status` обязательны. Пропущенные `description` и `due_date` очищаются |
| `PATCH /tasks/{id}/status` | `200` и задача | Изменить статус задачи |
| `DELETE /tasks/{id}` | `204` | Удалить задачу |

### Аккаунты, цели и финансы

| Метод и путь | Назначение |
|---|---|
| `POST /auth/register`, `POST /auth/login`, `POST /auth/logout` | Регистрация, вход и отзыв сессии |
| `GET /auth/me` | Текущий аккаунт |
| `POST /auth/demo` | Создать отдельную сессию с демоданными в `dev` |
| `POST /goals`, `GET /goals` | Создать или получить цели |
| `GET`, `PUT`, `DELETE /goals/{id}` | Прочитать, изменить или удалить цель |
| `POST /finance/transactions`, `GET /finance/transactions` | Создать или получить финансовые операции |
| `GET`, `PUT`, `DELETE /finance/transactions/{id}` | Прочитать, изменить или удалить операцию |
| `GET /finance/summary?start=2026-11-01&end=2026-11-30` | Доходы, расходы и разница за период, а также остаток по каждой валюте |
| `GET /finance/rates` | Официальные курсы USD, EUR и CNY к рублю и дата действия |
| `GET /dashboard` | Сводка своего аккаунта |

Сервер выдаёт cookie при регистрации, входе или запуске демо. Для `POST`, `PUT`, `PATCH` и `DELETE` передавайте `X-LifeFlow-Request: 1`. Без входа защищённый API возвращает `401`. Ошибки валидации возвращают `400`, а чужой или отсутствующий объект — `404`.

Пример PowerShell для режима `dev`:

```powershell
$apiHeaders = @{ 'X-LifeFlow-Request' = '1' }
Invoke-RestMethod -Uri 'http://localhost:8000/auth/demo' -Method Post `
  -Headers $apiHeaders -SessionVariable lifeflowSession
Invoke-RestMethod -Uri 'http://localhost:8000/tasks' -Method Post `
  -Headers $apiHeaders -WebSession $lifeflowSession `
  -ContentType 'application/json' -Body '{"title":"Prepare the demo","due_date":"2026-12-01"}'
```

Тот же запрос и модели ответов доступны в [Swagger UI](http://localhost:8000/docs).

### Интеграционные тесты

Укажите `LIFEFLOW_TEST_DATABASE_URL` в окружении с адресом отдельной тестовой PostgreSQL и ролью с правом создать схему. Тесты применяют миграции к отдельной схеме для каждого сценария и удаляют её после проверки.

```sh
uv sync --locked
uv run --locked python -m pytest -q
```

## Структура окружения

Конфигурация окружения проекта включает:

- `Dockerfile` — сборка образа приложения;
- `compose.yaml` — описание сервисов приложения и базы данных;
- `.dockerignore` — исключение локальных и служебных файлов из контекста сборки;
- `.env.example` — пример переменных окружения;
- `pyproject.toml` — описание зависимостей проекта;
- `uv.lock` — фиксация версий зависимостей;
- `docs/environment-schema.md` — схема окружения проекта;
- `docs/adr/002-dependency-manager.md` — архитектурное решение о выборе менеджера зависимостей;
- `docs/adr/003-configuration.md` — архитектурное решение о конфигурации и защите секретов.
