# Reflection Prompt Delivery Workflow

## Назначение

Этот документ описывает эксплуатацию и проверку workflow автоматической доставки
запросов на рефлексию после завершения лекции.

Архитектура потока:

```text
PostgreSQL -> Celery Beat -> Celery Worker -> RabbitMQ -> bot-consumer -> RabbitMQ -> backend result consumer -> PostgreSQL
```

Backend не отправляет сообщения в Telegram напрямую. Он:

- хранит доменное состояние доставок в `notification_deliveries`
- планирует scan через `Celery Beat`
- публикует команды для bot-consumer в `RabbitMQ`
- принимает result events через backend result consumer

---

## Необходимые компоненты

Для полного workflow должны быть подняты:

- PostgreSQL
- RabbitMQ
- backend
- Celery Worker
- Celery Beat
- backend result consumer
- Telegram bot или тестовый bot-consumer

---

## RabbitMQ

Пример сервиса для `docker-compose`:

```yaml
rabbitmq:
  image: rabbitmq:4-management
  container_name: reflebot-rabbitmq
  restart: unless-stopped
  environment:
    RABBITMQ_DEFAULT_USER: reflebot
    RABBITMQ_DEFAULT_PASS: password
    RABBITMQ_DEFAULT_VHOST: /
  ports:
    - "5672:5672"
    - "15672:15672"
  healthcheck:
    test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
    interval: 10s
    timeout: 5s
    retries: 10
```

Минимальные env для backend:

```env
REFLEBOT_RABBITMQ__HOST=localhost
REFLEBOT_RABBITMQ__PORT=5672
REFLEBOT_RABBITMQ__USER=reflebot
REFLEBOT_RABBITMQ__PASSWORD=password
REFLEBOT_RABBITMQ__VHOST=/
```

---

## Скрипты запуска

### Backend

```bash
./run.sh
```

### Celery Worker

```bash
./run_celery_worker.sh
```

### Celery Beat

```bash
./run_celery_beat.sh
```

### Backend Result Consumer

```bash
./run_delivery_result_consumer.sh
```

Result consumer запускает [run_delivery_result_consumer.py](/home/pavel/Programming/SENATAI/HSE/reflebot/backend/scripts/run_delivery_result_consumer.py), который:

- подключается к `RabbitMQ`
- читает `backend.notification-results`
- валидирует `ReflectionPromptResultEvent`
- обновляет `notification_deliveries`

---

## Контракт очередей для bot-consumer

### Команда от backend к bot-consumer

Exchange:

```text
reflebot.notifications
```

Queue:

```text
bot.reflection-prompts
```

Routing key:

```text
reflection_prompt.send
```

Payload:

```json
{
  "event_type": "send_reflection_prompt",
  "delivery_id": "uuid",
  "student_id": "uuid",
  "telegram_id": 123456789,
  "lection_session_id": "uuid",
  "message_text": "Текст запроса на рефлексию",
  "parse_mode": "HTML",
  "scheduled_for": "2026-03-28T20:00:00+00:00"
}
```

### Result event от bot-consumer к backend

Exchange:

```text
reflebot.notification-results
```

Queue:

```text
backend.notification-results
```

Routing key:

```text
reflection_prompt.result
```

Payload:

```json
{
  "event_type": "reflection_prompt_result",
  "delivery_id": "uuid",
  "success": true,
  "sent_at": "2026-03-28T20:01:00+00:00",
  "telegram_message_id": 123,
  "error": null
}
```

Если `success = false`, bot-consumer должен передать:

- `delivery_id`
- `error`

---

## Как запускать integration и E2E проверки

### Интеграционные тесты

Обычный `pytest` теперь включает integration-тесты автоматически, если живы PostgreSQL и RabbitMQ.

Полный прогон:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

Отдельно workflow интеграции:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_notification_delivery_integration.py
```

### E2E smoke

1. Поднять PostgreSQL и RabbitMQ.
2. Применить миграции.
3. Запустить:

```bash
./run_celery_worker.sh
./run_celery_beat.sh
./run_delivery_result_consumer.sh
```

4. В отдельном терминале запустить smoke:

```bash
uv run python scripts/reflection_prompt_delivery_smoke.py
```

Smoke:

- создаёт тестовые лекции и студентов
- ждёт команды в `bot.reflection-prompts`
- имитирует тестовый bot-consumer
- публикует `success` и `failure` result events
- проверяет итоговые статусы в PostgreSQL

---

## Эксплуатационные сценарии

### Как смотреть stuck pending deliveries

```sql
select id, lection_session_id, student_id, scheduled_for, attempts, created_at
from notification_deliveries
where status = 'pending'
order by scheduled_for asc, created_at asc;
```

Если таких записей много, проверь:

- запущен ли `Celery Worker`
- есть ли ошибки публикации в логах worker
- доступен ли `RabbitMQ`

### Как смотреть failed deliveries

```sql
select id, lection_session_id, student_id, attempts, last_error, updated_at
from notification_deliveries
where status = 'failed'
order by updated_at desc;
```

Это основной запрос для анализа проблем bot-consumer или Telegram transport.

### Как повторно запускать retry

Можно дождаться ближайшего тика `Celery Beat`, либо руками вызвать задачу:

```bash
uv run python - <<'PY'
from reflebot.apps.reflections.tasks.reflection_prompt import retry_failed_reflection_prompts
print(retry_failed_reflection_prompts())
PY
```

### Как понять, что backend result consumer работает

Признаки живой работы:

- в логах есть старт consumer на `backend.notification-results`
- после публикации result event статусы в `notification_deliveries` меняются на `sent` или `failed`
- `last_error` сохраняется при неуспешной доставке

---

## Последняя подтверждённая проверка

Последний полный прогон после включения integration и E2E smoke:

- `uv run pytest` -> `220 passed`
- `uv run python scripts/reflection_prompt_delivery_smoke.py` -> успешный live E2E smoke

Проверенный контур:

- PostgreSQL
- RabbitMQ
- Celery Worker
- Celery Beat
- backend result consumer
- тестовый bot-consumer через RabbitMQ
