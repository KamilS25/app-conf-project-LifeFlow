# Правила работы в команде

## Git-стратегия

В проекте используется **GitHub Flow**.

Основная ветка `main` содержит стабильную версию проекта. Все изменения выполняются в отдельных ветках и попадают в `main` только через Pull Request (PR).

Схема работы:

```text
main --> work branch --> pull request --> review --> approval --> main
```

Документация и конфигурационные изменения также принимаются через PR.

Стратегия ветвления и принципы организации работы фиксируются в ADR 001 — «Стратегия ветвления проекта».

В практике №2 ADR и кодовый PR проверяют участники LifeFlow.

### Ветвление

Формат имени ветки: `<тип>/<краткое-название-задачи>`. Краткое название пишется в `kebab-case`.

Используем следующие типы:

- `feature/` — новая функциональность;
- `bugfix/` — исправление ошибки;
- `docs/` — документация;
- `refactor/` — рефакторинг;
- `test/` — тестирование;
- `chore/` — технические и вспомогательные задачи.

Примеры именования веток:

- `feature/version-endpoint` — разработка эндпоинта версии;
- `docs/contributing-rules` — изменение правил работы команды;
- `bugfix/health-response` — исправление ответа эндпоинта проверки состояния;
- `chore/update-dependencies` — обновление зависимостей проекта.

Рабочая ветка создаётся от актуальной `main`. После завершения работы автор открывает PR и назначает участника команды для ревью.

### Коммиты

Для сообщений коммитов используется соглашение Conventional Commits.

Формат: `<тип>: <краткое описание>`.

Основные типы:

- `feat` — добавление функциональности;
- `fix` — исправление ошибки;
- `docs` — изменение документации;
- `refactor` — рефакторинг;
- `test` — добавление или изменение тестов;
- `chore` — технические изменения.


Примеры из истории проекта LifeFlow:

- `docs: add reviewer checklist to CONTRIBUTING`;
- `docs: describe API endpoints in README`;
- `feat: add initial FastAPI application with health check`.

## Code Review

### Регламент code review

1. Автор PR назначает другого участника команды в качестве проверяющего. Автор не может одобрить собственный PR.
2. Первый ответ проверяющего предоставляется в течение 24 часов.
3. Проверяющий изучает изменения во вкладке Files changed, оценивает соответствие задаче, корректность реализации, читаемость кода, тесты и документацию.
4. Автор отвечает на каждое замечание и вносит необходимые исправления.
5. После новых коммитов автор повторно запрашивает проверку через Re-request review.
6. Обсуждение закрывает автор замечания после проверки исправления.
7. После двух безрезультатных кругов обсуждения вопрос выносится на встречу команды. Если разногласие не удаётся разрешить командой, позиции сторон фиксируются, а вопрос о соответствии требованиям практики передаётся преподавателю.
8. После получения необходимого количества Approve и разрешения всех обсуждений PR сливается в `main` способом Merge pull request с созданием merge-коммита. Способы Squash and merge и Rebase and merge не используются.

### Разрешение конфликтов в коде

Если GitHub сообщает о конфликтах между рабочей веткой и `main`, автор:

1. Получает актуальное состояние удалённого репозитория: `git fetch origin`.
2. Переходит в свою рабочую ветку.
3. Выполняет `git merge origin/main`.
4. Разрешает конфликты вручную, сохраняя необходимые изменения обеих сторон.
5. Проверяет результат и запускает доступные проверки.
6. Создаёт коммит с разрешением конфликтов и отправляет изменения в свою ветку.
7. Повторно запрашивает Code Review.

Прямое внесение изменений в `main` и принудительная отправка изменений (`git push --force`) запрещены.

### Что ревьюер делает перед approval

1. Проверяет, что имя рабочей ветки соответствует принятому шаблону `<тип>/<краткое-название-задачи>`.
2. Проверяет, что описание PR заполнено по шаблону и соответствует внесённым изменениям.
3. Проверяет, что автор PR заполнил свой чек-лист и отметил выполненные пункты.
4. Проверяет корректность изменений во вкладке Files changed, включая стиль кода, логику и отсутствие лишних файлов.
5. При изменении кода или зависимостей запускает приложение и проверяет `GET /health` и изменённые маршруты.
6. Проверяет, что сообщения коммитов следуют Conventional Commits.
7. Проверяет результаты доступных тестов и актуальность документации.
8. Проверяет отсутствие секретов, временных файлов и локального окружения (`venv/`, `__pycache__/`, `.env`).
9. Оставляет замечания к конкретным строкам, если обнаружены проблемы. Ставит Approve только после устранения блокирующих замечаний.

### Критерии approval

Перед Approval проверяющий также выполняет чек-лист из подраздела «Что ревьюер делает перед approval».

PR может получить Approval, если выполнены все условия:

- изменение соответствует описанию задачи;
- код не содержит очевидных ошибок и не затрагивает постороннюю функциональность;
- необходимые проверки и тесты выполнены успешно;
- документация обновлена, если изменение влияет на использование проекта;
- все замечания проверяющего обработаны;
- все обсуждения в PR разрешены;
- в изменениях отсутствуют пароли, токены, ключи и другие конфиденциальные данные;
- результат проверки можно воспроизвести по описанным в PR шагам.

Для слияния PR в `main` требуется минимум один Approval от другого участника команды. Автор PR не может одобрить собственные изменения.

## Защита ветки

Ветка `main` защищена активным ruleset `protect-main`:

- изменения только через Pull Request с минимум одним approval другого участника;
- новые коммиты сбрасывают прежние approvals;
- обсуждения должны быть закрыты до merge;
- обязательные проверки GitHub Actions `lint`, `secrets`, `test` и `build` должны пройти на актуальной версии PR. Правило не требует предварительно обновлять ветку до последней версии `main`;
- force-push и удаление ветки запрещены;
- bypass-список пуст, в том числе владелец не обходит защиту;
- автоматически удаляются слитые рабочие ветки.

`Restrict deletions` включено; на default-ветке экспериментом не проверяется. Для GitHub Flow удаление `main` в рамках этой проверки не выполняется.

### Проверка обычного push

01.11.2026 Салахетдинов Камиль проверил отправку пустого тестового коммита в `main`. Поскольку коммит находился в отдельной локальной ветке, команда эксперимента — `git push origin HEAD:main`.

Фактический фрагмент ответа сервера:

```text
 ! [remote rejected] HEAD -> main (push declined due to repository rule violations)
error: failed to push some refs to 'https://github.com/KamilS25/app-conf-project-LifeFlow.git'
```

Отправка нового коммита в `main` отклонена правилами репозитория.

### Проверка force-push

В тот же день Камиль проверил принудительную замену истории из отдельной локальной тестовой ветки командой `git push --force origin HEAD:main`.

Фактический фрагмент ответа сервера:

```text
remote: - Cannot force-push to this branch
remote:
remote: - Changes must be made through a pull request.
remote:
To https://github.com/KamilS25/app-conf-project-LifeFlow.git
 ! [remote rejected] HEAD -> main (push declined due to repository rule violations)
error: failed to push some refs to 'https://github.com/KamilS25/app-conf-project-LifeFlow.git'
```

Сервер подтвердил запрет force-push и требование Pull Request. После обоих экспериментов удалённый и локальный `main` остались на `664af89a658b8ad1cef75e2223213966ecddc550`; тестовые коммиты в `main` не попали.

### Проверка обязательного CI

24.11.2026 в `protect-main` включили обязательные проверки `lint` и `secrets` от GitHub Actions. На коммите `259f970` GitHub вернул `BLOCKED` при красном `lint`. Обе проверки получили признак `isRequired: true`. [Подтверждение в PR №13](https://github.com/KamilS25/app-conf-project-LifeFlow/pull/13#issuecomment-7137978890)

## Как запустить линтеры локально

Используйте Python 3.13 из `.python-version` и uv. Выполните в корне проекта те же проверки, что и в CI:

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy .
```

Чтобы применить форматирование, запустите `uv run --locked ruff format .`. Если mypy сообщает ошибку, исправьте код и повторите проверку. [ADR 004](docs/adr/004-ci-pipeline.md)

## Как запустить тесты локально

Запустите отдельный контейнер PostgreSQL 17. Docker выберет свободный порт на `127.0.0.1`. Понадобятся Docker, uv и Python из `.python-version`.

### Bash

```sh
uv sync --locked
test_password=$(uv run --locked python -c 'import secrets; print(secrets.token_hex(16))')
POSTGRES_PASSWORD="$test_password" docker run -d --name lifeflow-tests \
  -e POSTGRES_PASSWORD -e POSTGRES_USER=lifeflow_test -e POSTGRES_DB=lifeflow_test \
  -p 127.0.0.1::5432 postgres:17
```

Дождитесь ответа `accepting connections` от `docker exec lifeflow-tests pg_isready -h 127.0.0.1 -U lifeflow_test -d lifeflow_test`. Затем выполните:

```sh
endpoint=$(docker port lifeflow-tests 5432/tcp)
export LIFEFLOW_TEST_DATABASE_URL="postgresql://lifeflow_test:${test_password}@${endpoint}/lifeflow_test"
DATABASE_URL="$LIFEFLOW_TEST_DATABASE_URL" uv run --locked alembic upgrade head
uv run --locked python -m pytest -ra --cov --cov-report=term-missing
docker rm -f lifeflow-tests
unset LIFEFLOW_TEST_DATABASE_URL test_password endpoint
```

### PowerShell

```powershell
uv sync --locked
$testPassword = uv run --locked python -c 'import secrets; print(secrets.token_hex(16))'
docker run -d --name lifeflow-tests --env "POSTGRES_PASSWORD=$testPassword" `
  --env POSTGRES_USER=lifeflow_test --env POSTGRES_DB=lifeflow_test `
  --publish 127.0.0.1::5432 postgres:17
```

Дождитесь ответа `accepting connections` от `docker exec lifeflow-tests pg_isready -h 127.0.0.1 -U lifeflow_test -d lifeflow_test`. Затем выполните:

```powershell
$endpoint = docker port lifeflow-tests 5432/tcp
$env:LIFEFLOW_TEST_DATABASE_URL = "postgresql://lifeflow_test:${testPassword}@${endpoint}/lifeflow_test"
$previousDatabaseUrl = $env:DATABASE_URL
try {
    $env:DATABASE_URL = $env:LIFEFLOW_TEST_DATABASE_URL
    uv run --locked alembic upgrade head
    if ($LASTEXITCODE) { throw 'Alembic migration failed' }
    uv run --locked python -m pytest -ra --cov --cov-report=term-missing
    if ($LASTEXITCODE) { throw 'Tests failed' }
} finally {
    $env:DATABASE_URL = $previousDatabaseUrl
    Remove-Item Env:LIFEFLOW_TEST_DATABASE_URL
    docker rm -f lifeflow-tests
    Remove-Variable testPassword, endpoint, previousDatabaseUrl
}
```

Проверьте количество пройденных тестов и строку `TOTAL`. При полном прогоне тесты, которым нужна БД, выполняются, а покрытие кода приложения составляет минимум 60%. [ADR 005](docs/adr/005-testing-and-build.md)

### Pre-commit и ручная проверка

Перед первым коммитом установите проверки. Для Gitleaks должен быть запущен Docker.

```sh
uv sync --locked
uv run --locked python -X utf8 -m pre_commit install
uv run --locked pre-commit run --all-files
```

Режим UTF-8 сохраняет путь к интерпретатору в Git-хуке, в том числе в каталогах Windows с кириллицей.

Gitleaks проверяет изменения в индексе Git. Добавьте изменённые файлы через `git add` до запуска, если хотите проверить их до коммита. Для проверки полной Git-истории см. [ADR 003](docs/adr/003-configuration.md).

Интеграционные тесты запускаются на отдельной PostgreSQL. Настройте `LIFEFLOW_TEST_DATABASE_URL` по [инструкции в README](README.md#интеграционные-тесты) и выполните `uv run --locked python -m pytest -q`.

Для ручной проверки поднимите стек по [инструкции запуска](README.md#запуск-через-docker-compose). Проверьте `GET /`, `GET /health` и маршруты, затронутые изменением. При работающей базе `/health` отвечает HTTP 200. Для проверки отказа остановите `db` в тестовом стеке и убедитесь, что `/health` отвечает HTTP 503, затем восстановите стек.

Для [запуска FastAPI без Compose](README.md#локальный-запуск-без-docker) задайте `DATABASE_URL`, примените `uv run --locked alembic upgrade head` и запустите `uv run --locked uvicorn main:app --reload`.

## Встречи команды

- Частота: раз в две недели, на практических занятиях.
- Канал связи: командный чат в Telegram. Ссылка на чат в репозитории не размещена; по вопросам доступа обращайтесь к тимлиду.
- Время ответа на сообщения: в течение 24 часов.

## Разрешение конфликтов

1. Участники обсуждают проблему и предлагают варианты решения.
2. Если договориться не удалось, проводится голосование.
3. Если решение не найдено, вопрос передаётся преподавателю.

## Контакты

- Тимлид / Tech Lead: Салахетдинов Камиль — Telegram: [@Kamil2577](https://t.me/Kamil2577).
- DevOps Engineer: Сулейманова Виктория[@vst-17](https://t.me/viktoriyaaa7).
- Frontend Developer: Богаенко Елизавета[@ka-chow](https://t.me/ny_normalno_ili_net).

Основной канал командной коммуникации — общий чат в Telegram.
Срок ответа на сообщения — в течение 24 часов.
По вопросам, требующим согласования с преподавателем, обращение направляет тимлид.
