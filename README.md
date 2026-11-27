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

В режиме `dev` работает CRUD задач на PostgreSQL. Регистрация и вход запланированы на следующий этап.

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

Укажите `APP_ENV` в `.env`: `dev` включает Swagger UI (`/docs`), ReDoc (`/redoc`) и схему `/openapi.json`, а `prod` отключает эти три маршрута. После смены значения выполните `docker compose up --wait`. `GET /health` и `GET /version` работают в обоих режимах.

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

Задача принадлежит одному владельцу и содержит название, статус `todo`, `in_progress` или `done`, необязательное описание и необязательный срок в формате даты `ГГГГ-ММ-ДД`.

На первом этапе API задач доступен в `dev`. Сервер создаёт демонстрационного владельца `demo@lifeflow.invalid` при первом создании задачи и ограничивает все операции его записями. Вход в личный аккаунт появится на следующем этапе.

## API

| Метод и путь | Ответ | Назначение |
|---|---|---|
| `GET /` | `{"message": "Hello World"}` | Проверка доступности приложения |
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
| `DELETE /tasks/{id}` | `204` | Удалить задачу |

Запрос с некорректными данными получает `400`, запрос к отсутствующей или чужой задаче — `404`. Для проверки из PowerShell можно создать задачу так:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/tasks' -Method Post `
  -ContentType 'application/json' -Body '{"title":"Prepare the demo","due_date":"2026-12-01"}'
```

Тот же запрос и модели ответов доступны в [Swagger UI](http://localhost:8000/docs).

### Интеграционные тесты задач

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
