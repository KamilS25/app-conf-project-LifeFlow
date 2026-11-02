# Правила работы в команде

## Git-стратегия
Мы используем **GitHub Flow**.
Схема: `main` (стабильная) -> `feature/<название>` (разработка) -> PR -> `main`.
Документы процесса (`docs/*`) вливаются в `main` через PR.

### Ветвление

- `main` — стабильная версия
- `feature/<кратко>` — новые функции и документация
- `bugfix/<кратко>` — исправление ошибок

### Коммиты

Используем [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` новая функция
- `fix:` исправление бага
- `docs:` изменения в документации
- `style:` форматирование кода
- `refactor:` рефакторинг
- `test:` добавление тестов
- `chore:` рутинные задачи

Пример: `feat: add user authentication endpoint`

## Code Review

- Каждый PR требует минимум 1 approval от другого участника команды
- Ревьюер проверяет: стиль кода, архитектуру, наличие тестов
- Автор отвечает на все комментарии в PR

### Что ревьюер делает перед approval

1. Читает изменения во вкладке Files changed
2. Если PR меняет код или зависимости — переключается на ветку PR, ставит зависимости, запускает приложение и проверяет `GET /health`
3. Проверяет, что сообщения коммитов следуют Conventional Commits
4. Проверяет, что в PR нет `venv/`, `__pycache__/`, `.env`
5. Ставит Approve только после пунктов 1–4; замечания оставляет комментарием к конкретной строке

## Встречи команды

- Частота: раз в две недели, на практических занятиях.
- Канал связи: командный чат в Telegram. Ссылка на чат в репозитории не размещена; по вопросам доступа обращайтесь к тимлиду.
- Время ответа на сообщения: в течение 24 часов.

## Разрешение конфликтов (в команде)
1. Обсуждение
2. Голосование
3. Обращение к преподавателю

## Разрешение конфликтов

Если GitHub пишет `This branch has conflicts`:
1. `git checkout <ваша-ветка>`
2. `git fetch origin`
3. `git merge origin/main`
4. В файлах убрать маркеры `<<<<<<<`, `=======`, `>>>>>>>`, оставить нужное.
5. `git add <файл>`
6. `git commit -m "chore: resolve merge conflict with main"`
7. `git push`
Затем нажать **Re-request review** на GitHub.

## Защита ветки
Включены правила: Restrict deletions, Block force pushes, Require a pull request (1 approval), Dismiss stale approvals, Require conversation resolution.
Текст отказа при прямом push:
> remote: error: GH013: Repository rule violations found for refs/heads/main.
> remote: - Changes must be made through a pull request.
> remote: - Cannot force-push to this branch.

> TODO (модуль 3): после появления CI-пайплайна включить "Require status checks to pass".

## Как запустить тесты
TODO (модуль 3): тестов пока нет, раздел появится вместе с ними.


## Контакты
- Тимлид: Салахетдинов Камиль — Telegram: [@Kamil2577](https://t.me/Kamil2577).
- DevOps Engineer: Сулейманова Виктория.
- Frontend Developer: Богаенко Елизавета.