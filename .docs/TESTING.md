# Тестирование Reflebot Backend

## Общая информация

В проекте используются два основных уровня проверки:

- обычные автоматические тесты через `pytest`
- integration и smoke-прогоны через живую инфраструктуру

На момент последней полной проверки:

- `220` тестов `pytest` прошли успешно
- smoke-прогон task 25 прошёл успешно на локальном окружении
- E2E smoke reflection prompt workflow прошёл успешно на локальном окружении

---

## Что покрывают обычные тесты

`pytest` в проекте покрывает:

- сервисы
- use cases
- handlers
- роутеры
- навигацию и контекст пользователя
- парсеры Excel и CSV
- обработку ошибок
- property-based сценарии через `hypothesis`

Основные файлы лежат в папке `tests/`.

---

## Что покрывает smoke и integration

Task 25 smoke-прогон проверяет реальное поведение системы через HTTP API и настоящую инфраструктуру:

- Swagger UI и OpenAPI
- вход администратора по `telegram_username`
- многошаговое создание администратора
- создание курса из Excel
- просмотр и редактирование лекций
- управление вопросами
- загрузку и повторную выдачу Telegram `file_id`
- привязку преподавателя к курсу
- привязку студентов из CSV
- teacher analytics workflow
- проверку ошибок:
  - некорректный Excel
  - некорректный CSV
  - дубликат username
  - недостаточно прав
- bulk-сценарии:
  - курс на `55` лекций
  - привязка `110` студентов
  - пагинация больших списков

Smoke-скрипт расположен в [scripts/task25_smoke.py](/home/pavel/Programming/SENATAI/HSE/reflebot/backend/scripts/task25_smoke.py).

Дополнительно есть отдельный integration/E2E слой для reflection prompt delivery workflow:

- реальные integration-тесты `PostgreSQL + RabbitMQ` в [test_notification_delivery_integration.py](/home/pavel/Programming/SENATAI/HSE/reflebot/backend/tests/test_notification_delivery_integration.py)
- живой E2E smoke через Celery и RabbitMQ в [reflection_prompt_delivery_smoke.py](/home/pavel/Programming/SENATAI/HSE/reflebot/backend/scripts/reflection_prompt_delivery_smoke.py)

---

## Предварительные условия для smoke и integration

Перед запуском smoke должны быть готовы:

- локальная PostgreSQL
- локальный RabbitMQ
- применённые миграции
- корректный `.env`
- существующий администратор с `telegram_username = Syrnick`

Smoke использует текущие `settings` проекта. Отдельные DSN для него не требуются.

---

## Как запускать обычные тесты

Полный прогон:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

Теперь этот прогон включает и integration-тесты reflection prompt workflow, поэтому требует живые PostgreSQL и RabbitMQ.

Прогон одного файла:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_handlers.py
```

Прогон конкретного теста:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_handlers.py::test_file_handler_returns_friendly_message_for_missing_csv_column
```

---

## Как запускать smoke

### 1. Поднять backend

```bash
./run.sh
```

Backend должен отвечать на:

```text
http://127.0.0.1:8080
```

### 2. Запустить smoke

В отдельном терминале:

```bash
.venv/bin/python scripts/task25_smoke.py
```

Smoke сам вызывает реальные endpoint’ы backend и сам проверяет результаты в PostgreSQL.

### 3. Остановить backend

Если backend запущен через `./run.sh`, его можно остановить обычным `Ctrl+C`.

## Как запускать reflection prompt E2E smoke

В отдельных терминалах должны быть запущены:

```bash
./run_celery_worker.sh
./run_celery_beat.sh
./run_delivery_result_consumer.sh
```

После этого можно запускать:

```bash
uv run python scripts/reflection_prompt_delivery_smoke.py
```

Этот smoke:

- создаёт тестовые лекции и студентов
- ждёт реальные команды в RabbitMQ
- имитирует bot-consumer
- публикует result events обратно в RabbitMQ
- проверяет итоговые статусы в PostgreSQL

---

## Последние результаты

### Обычные тесты

Команда:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

Результат:

```text
220 passed in 20.18s
```

### Smoke

Команда:

```bash
.venv/bin/python scripts/task25_smoke.py
```

Результат:

- Swagger / OpenAPI проверены
- все основные workflows пройдены успешно
- реальная PostgreSQL использована успешно

### Reflection Prompt E2E Smoke

Команда:

```bash
uv run python scripts/reflection_prompt_delivery_smoke.py
```

Результат:

- подтверждён поток `Celery Beat -> Celery Worker -> RabbitMQ -> test bot-consumer -> RabbitMQ -> backend result consumer`
- подтверждены оба статуса:
  - `queued -> sent`
  - `queued -> failed`
- реальная PostgreSQL и реальный RabbitMQ использованы успешно

---

## Нагрузочные замеры

Ниже приведены замеры из последнего успешного smoke-прогона. Они зависят от локального железа и текущего состояния окружения, поэтому их стоит воспринимать как ориентир, а не как жёсткий SLA.

- создание курса с `55` лекциями: `0.076s`
- привязка `110` студентов: `1.276s`
- полный smoke-прогон: `6.112s`

Также были подтверждены итоговые объёмы данных в bulk-сценарии:

- `55` лекций в курсе
- `110` привязок `student_courses`
- `6050` привязок `student_lections`
- `55` привязок `teacher_lections`

---

## Практическая рекомендация

Для повседневной разработки достаточно запускать:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

Smoke имеет смысл запускать:

- перед финальной сдачей задачи
- после изменений в workflow handlers
- после изменений в интеграции с PostgreSQL
- после изменений в файлах `.env`, `settings`, миграциях или DI
