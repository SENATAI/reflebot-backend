# Telegram Bot API для Reflebot Backend

## Назначение

Этот документ описывает, как Telegram-бот должен работать с backend `Reflebot`.

Backend построен по принципу `backend-driven workflow`:

- backend сам решает, какой экран и какие кнопки показать дальше
- backend сам хранит многошаговый контекст пользователя
- bot не должен дублировать бизнес-логику в себе
- bot должен в основном быть транспортом между Telegram и backend

Иными словами: бот отправляет события в backend, а backend возвращает готовый текст, кнопки и признак того, что ждёт следующий ввод.

---

## Базовый URL

Во всех примерах ниже используется:

```text
http://127.0.0.1:8080
```

API модуля:

```text
/api/reflections
```

Итого полный префикс:

```text
http://127.0.0.1:8080/api/reflections
```

---

## Какие endpoint'ы использовать

У backend для Telegram workflow должны использоваться только 4 endpoint'а:

- `POST /api/reflections/auth/{telegram_username}/login`
- `POST /api/reflections/actions/button/{action}`
- `POST /api/reflections/actions/text`
- `POST /api/reflections/actions/file`

Других рабочих endpoint'ов для Telegram-бота больше нет и использовать их не нужно.

---

## Обязательные заголовки

### 1. `X-Service-API-Key`

Обязателен для всех запросов к API, кроме:

- `/docs`
- `/redoc`
- `/openapi.json`
- `/docs.json`

Значение должно совпадать с `REFLEBOT_TELEGRAM_SECRET_TOKEN`.

Пример:

```http
X-Service-API-Key: your-telegram-secret-token
```

Если заголовок отсутствует, backend вернёт:

```json
{
  "detail": "Отсутствует заголовок X-Service-API-Key",
  "error_code": "MISSING_API_KEY"
}
```

Если API key неверный:

```json
{
  "detail": "Неверный API ключ",
  "error_code": "INVALID_API_KEY"
}
```

### 2. `X-Telegram-Id`

Нужен для всех action endpoint'ов:

- `POST /actions/button/{action}`
- `POST /actions/text`
- `POST /actions/file`

Это реальный `telegram_id` пользователя из Telegram.

Пример:

```http
X-Telegram-Id: 123456789
```

Для login endpoint этот заголовок не нужен, потому что `telegram_id` приходит в JSON body.

---

## Общий формат ответа от backend

### Для `login`

`POST /auth/{telegram_username}/login` возвращает:

```json
{
  "full_name": "Иванов Иван",
  "telegram_username": "ivanov",
  "telegram_id": 123456789,
  "is_active": true,
  "is_admin": true,
  "is_teacher": false,
  "is_student": true,
  "message": "Текст для пользователя",
  "parse_mode": "HTML",
  "buttons": [
    {
      "text": "➕ Создать администратора",
      "action": "admin_create_admin"
    }
  ],
  "awaiting_input": false
}
```

### Для `button`, `text`, `file`

Все action endpoint'ы возвращают единый контракт:

```json
{
  "message": "Текст для пользователя",
  "parse_mode": "HTML",
  "buttons": [
    {
      "text": "◀️ Назад",
      "action": "back"
    }
  ],
  "files": [
    {
      "telegram_file_id": "BQACAgIAAxkBAAIB...",
      "kind": "presentation"
    }
  ],
  "dialog_messages": [
    {
      "message": "❓ <b>Вопрос</b>\n\nЧто было самым полезным?",
      "parse_mode": "HTML",
      "files": []
    },
    {
      "message": null,
      "parse_mode": "HTML",
      "files": [
        {
          "telegram_file_id": "BAACAgIAAxkBAAIB...",
          "kind": "qa_video"
        }
      ]
    }
  ],
  "awaiting_input": true
}
```

### Что означает каждый параметр

- `message` — текст, который бот должен показать пользователю
- `parse_mode` — режим форматирования Telegram, обычно `HTML`
- `buttons` — inline-кнопки, которые нужно отрисовать
- `files` — список Telegram `file_id`, которые бот может переотправить пользователю
- `dialog_messages` — последовательность дополнительных сообщений, которые бот должен отправить по порядку
- `awaiting_input` — backend ждёт следующий пользовательский ввод

---

## Как бот должен рендерить ответ

### Сообщение

Бот должен отправлять или редактировать сообщение, используя:

- `text = response.message`
- `parse_mode = response.parse_mode`

Если `dialog_messages` не пустой, бот должен:

1. сначала отправить обычный `response.message`
2. если в `response.files` есть элементы, отправить каждый `telegram_file_id` как отдельное Telegram media message
3. потом последовательно пройти по `dialog_messages`
4. для каждого элемента:
   - если есть `message`, отправить текстовое сообщение
   - если есть `files`, отправить каждый `telegram_file_id` как отдельный Telegram media message

Нюанс:

- `dialog_messages[i].message` может быть `null`
- это означает, что на этом шаге нужно отправить только файлы из `dialog_messages[i].files`

Это нужно для экранов, где backend отдаёт уже готовый “диалог” из текста и кружков.

Если `dialog_messages` пустой, но `files` не пустой, бот всё равно должен:

1. показать `response.message`
2. затем отправить файлы из `response.files`

Важно:

- кнопки `response.buttons` относятся только к основному `response.message`
- элементы `dialog_messages` не нужно пытаться редактировать через одно и то же Telegram message
- для экранов с историей рефлексии удобнее отправлять новые сообщения по порядку, а не пытаться упаковать всё в одно

### Кнопки

Каждый элемент массива `buttons` надо превращать в Telegram inline button:

- `button.text` → `text`
- `button.action` → `callback_data`

Пример:

```json
{
  "text": "📊 Аналитика",
  "action": "teacher_analytics"
}
```

должен стать:

```python
InlineKeyboardButton(text="📊 Аналитика", callback_data="teacher_analytics")
```

### Важное правило по `action`

Бот не должен разбирать или придумывать `action` сам.

Правильная стратегия:

- взять `buttons[].action` из ответа backend
- передать его обратно в `POST /actions/button/{action}` без изменений

Некоторые `action` статические:

- `admin_create_admin`
- `admin_create_course`
- `teacher_analytics`
- `back`

Некоторые динамические и содержат идентификаторы:

- `lection_info:<lection_id>`
- `analytics_select_course:<course_id>`
- `analytics_view_reflection:<student_id>:<lection_id>`
- `student_start_reflection:<lection_id>`

Поэтому `action` надо считать непрозрачной строкой и не хардкодить логику на стороне бота.

### Файлы

Если backend вернул непустой массив `files`, бот должен использовать эти значения
для повторной отправки файлов через Telegram Bot API.

Пример:

```json
{
  "telegram_file_id": "BQACAgIAAxkBAAIB...",
  "kind": "recording"
}
```

Обычно это означает, что бот должен сделать `sendDocument`/`sendVideo` с этим `file_id`.

---

## Как работает жизненный цикл пользователя

### 1. Пользователь пишет `/start`

Бот должен:

1. взять `telegram_id`
2. взять `telegram_username`
3. убрать ведущий `@`, если он есть
4. вызвать login endpoint
5. показать пользователю `message` и `buttons`

Запрос:

```http
POST /api/reflections/auth/Syrnick/login
X-Service-API-Key: your-token
Content-Type: application/json
```

```json
{
  "telegram_id": 123456789
}
```

Что делает backend при login:

- ищет пользователя по `telegram_username` в `Admin`
- ищет пользователя по `telegram_username` в `Student`
- ищет пользователя по `telegram_username` в `Teacher`
- если находит, обновляет `telegram_id` во всех найденных ролях
- возвращает список ролей, приветственное сообщение и стартовые кнопки

### 2. Пользователь нажимает inline-кнопку

Бот должен:

1. взять `callback_data`
2. вызвать `POST /actions/button/{action}`
3. передать `X-Telegram-Id`
4. показать новый ответ backend

Пример:

```http
POST /api/reflections/actions/button/admin_create_course
X-Service-API-Key: your-token
X-Telegram-Id: 123456789
```

Backend вернёт следующий экран.

### 3. Backend вернул `awaiting_input = true`

Это означает, что backend теперь ждёт следующий ввод пользователя.

Дальше бот должен просто передать следующий update:

- если пользователь прислал текст — в `POST /actions/text`
- если пользователь прислал документ/файл — в `POST /actions/file`

### 4. Пользователь отправил текст

Запрос:

```http
POST /api/reflections/actions/text
X-Service-API-Key: your-token
X-Telegram-Id: 123456789
Content-Type: application/json
```

```json
{
  "text": "Иванов Иван Иванович"
}
```

### 5. Пользователь отправил файл

Тут есть два сценария.

#### Сценарий A. Пользователь отправил `xlsx/csv`

Для импорта курса и загрузки студентов backend всё ещё принимает реальный бинарный файл.

Бот должен:

1. скачать файл из Telegram к себе
2. отправить его в backend как `multipart/form-data`

Запрос:

```http
POST /api/reflections/actions/file
X-Service-API-Key: your-token
X-Telegram-Id: 123456789
Content-Type: multipart/form-data
```

Поле формы:

- `file` — бинарный файл

Пример `curl`:

```bash
curl -X POST "http://127.0.0.1:8080/api/reflections/actions/file" \
  -H "X-Service-API-Key: your-token" \
  -H "X-Telegram-Id: 123456789" \
  -F "file=@course.xlsx"
```

#### Сценарий B. Пользователь отправил Telegram-медиа для лекции

Для презентации и записи лекции backend больше не требует бинарник.
Нужно передать именно Telegram `file_id`.

Пример:

```bash
curl -X POST "http://127.0.0.1:8080/api/reflections/actions/file" \
  -H "X-Service-API-Key: your-token" \
  -H "X-Telegram-Id: 123456789" \
  -F "telegram_file_id=BQACAgIAAxkBAAIB..."
```

#### Сценарий C. Пользователь отправил кружок для рефлексии

Для student reflection workflow backend тоже принимает `telegram_file_id`
через этот же endpoint.

Бот может не передавать бинарный файл, если у него уже есть Telegram `file_id`
от `video_note`.

Пример:

```bash
curl -X POST "http://127.0.0.1:8080/api/reflections/actions/file" \
  -H "X-Service-API-Key: your-token" \
  -H "X-Telegram-Id: 123456789" \
  -F "telegram_file_id=BAACAgIAAxkBAAIB..."
```

Итого по `/actions/file` правило такое:

- `file` обязателен только для `xlsx` и `csv`
- `telegram_file_id` обязателен для:
  - презентации лекции
  - записи лекции
  - student `video_note` в workflow рефлексии
- для Telegram-медиа бот не должен сначала скачивать файл, если ему уже известен `file_id`

---

## Как бот должен работать с `awaiting_input`

`awaiting_input` означает только то, что backend ждёт следующий пользовательский шаг.

Он не уточняет тип ввода. Поэтому правило такое:

- если следующий update содержит текст, слать `/actions/text`
- если следующий update содержит файл, слать `/actions/file`

Backend сам знает текущий контекст пользователя и сам решает, подходит ли такой ввод для текущего шага.

### Рекомендация

Бот может локально запоминать последнее значение `awaiting_input` для пользователя, но это не обязательно.

Почему это не обязательно:

- backend хранит контекст у себя
- даже если бот перезапустился, backend всё равно знает активный шаг пользователя

Самый простой надёжный вариант:

- `/start` → всегда `login`
- `callback_query` → всегда `/actions/button/{action}`
- обычный пользовательский текст → `/actions/text`
- документ/файл → `/actions/file`

Для student reflection workflow это означает:

- стартовая inline-кнопка приходит от backend как `student_start_reflection:<lection_id>`
- после неё backend возвращает `awaiting_input=true`
- следующий `video_note` бот отправляет в `/actions/file`

---

## Главное правило интеграции

Bot не должен сам решать:

- какой сейчас экран
- какая следующая кнопка
- какой следующий шаг wizard'а
- к какому курсу/лекции относится пользователь
- как работает навигация `Назад`

Всё это уже управляется backend через:

- `message`
- `buttons`
- `awaiting_input`
- серверный `user_context`

---

## Стартовое меню по ролям

После успешного login backend сам вернёт нужные кнопки.

### Если пользователь администратор

Будут кнопки:

- `➕ Создать администратора`
- `📚 Создать курс`

### Если пользователь преподаватель

Будут кнопки:

- `📊 Аналитика`
- `📅 Ближайшая лекция`

### Если пользователь только студент

Кнопок не будет.

Если у пользователя несколько ролей, backend вернёт объединённый набор кнопок.

---

## Что умеет workflow через эти endpoint'ы

Через 4 endpoint'а выше backend уже покрывает весь основной Telegram сценарий:

- login по `telegram_username`
- создание администратора
- создание курса из Excel
- просмотр спаршенных лекций
- изменение темы лекции
- изменение даты и времени лекции
- управление вопросами лекции
- загрузку презентации
- получение Telegram `file_id` презентации
- student reflection workflow с кружками по лекции и по вопросам

### Student Reflection Workflow

Когда bot-consumer получает RabbitMQ команду `send_reflection_prompt`, он должен
отправить студенту:

- `message_text`
- `buttons`

Сейчас backend добавляет в это сообщение кнопку:

- `text = "🎥 Записать кружок"`
- `action = "student_start_reflection:<lection_id>"`

Дальше lifecycle такой:

1. студент нажимает `student_start_reflection:<lection_id>`
2. bot отправляет `POST /actions/button/{action}`
3. backend отвечает `Записывайте кружок, я вас слушаю.` и `awaiting_input=true`
4. bot ждёт `video_note` и передаёт его в `POST /actions/file` через `telegram_file_id`
5. backend отвечает `Кружок записан, что хотите сделать?`
6. backend возвращает кнопки:
   - `Отправить рефлексию`
   - `Удалить кружок`
   - `Добавить ещё один кружок`
7. если у лекции есть вопросы, backend задаёт их по одному и повторяет ту же механику
8. после последнего вопроса backend отвечает:
   - `Вопросов больше нет. Спасибо за рефлексию.`

Дополнительные правила этого workflow:

- `Удалить кружок` удаляет только последний кружок текущего draft
- если после удаления текущий draft пуст, backend возвращает исходный prompt с кнопкой `🎥 Записать кружок`
- после `Отправить рефлексию` backend сохраняет общую рефлексию в `LectionReflection` и `ReflectionVideo`
- затем, если у лекции есть вопросы, backend последовательно переводит пользователя в ответы по вопросам
- каждый ответ на вопрос тоже собирается из одного или нескольких кружков
- после завершения всех вопросов backend сохраняет ответы в `LectionQA` и `QAVideo`
- финальное сообщение `Вопросов больше нет. Спасибо за рефлексию.` приходит без кнопок

В этом сценарии бот не хранит своё состояние:

- backend держит draft в `User.user_context`
- бот только пересылает `button` и `telegram_file_id`
- загрузку записи лекции
- получение Telegram `file_id` записи лекции
- привязку преподавателя к курсу
- привязку студентов к курсу из CSV
- просмотр аналитики преподавателем
- просмотр ближайшей лекции преподавателя
- пагинацию и навигацию `Назад`

---

## Особенность скачивания файлов

Сейчас backend не отдаёт бинарный файл прямо в API-ответе action endpoint'ов.

При нажатии на:

- скачать презентацию
- скачать запись лекции

backend возвращает обычный `ActionResponseSchema`, но в поле `files` кладёт Telegram `file_id`.

Пример:

```json
{
  "message": "Файл готов к отправке ботом.",
  "files": [
    {
      "telegram_file_id": "BQACAgIAAxkBAAIB...",
      "kind": "presentation"
    }
  ]
}
```

Дальше бот должен использовать этот `telegram_file_id` для повторной отправки файла через Telegram API.

---

## Форматы пользовательского ввода

### Login

`telegram_username`:

- передаётся в path
- рекомендуется перед отправкой убрать `@`

`telegram_id`:

- передаётся в JSON body

### Text input

Формат:

```json
{
  "text": "..."
}
```

### File input

Формат:

- `multipart/form-data`
- поле `file` для `xlsx/csv`
- поле `telegram_file_id` для Telegram-медиа лекции

Backend сам определяет, что это за файл в текущем шаге:

- `xlsx` для курса
- `csv` для студентов
- `telegram_file_id` для презентации
- `telegram_file_id` для записи лекции
- `telegram_file_id` для student `video_note`

---

## Экран аналитики с диалогом рефлексии

Для действий вида:

- `analytics_view_reflection:<student_id>:<lection_id>`

backend может вернуть не только `message`, но и полноценный `dialog_messages`.

Что делает backend сейчас:

- в `message` кладёт шапку с информацией о студенте и лекции
- в `dialog_messages` кладёт уже готовую последовательность сообщений
- сначала идут кружки общей рефлексии по лекции
- затем перед каждым блоком ответов идёт текст `❓ Вопрос`
- после этого идут кружки ответа именно на этот вопрос

Порядок внутри `dialog_messages` уже подготовлен backend и должен сохраняться ботом без изменений.

Боту не нужно:

- самостоятельно сортировать кружки
- группировать их по вопросам
- подставлять текст вопросов вручную

Нужно просто последовательно отправить то, что вернул backend.

---

## Ошибки

### Формат ошибок

Ошибки возвращаются в JSON:

```json
{
  "detail": "Описание ошибки",
  "error_code": "ERROR_CODE"
}
```

### На что боту стоит реагировать

- `401 MISSING_API_KEY` — проблема конфигурации бота
- `403 INVALID_API_KEY` — неправильный секрет
- `404 MODEL_FIELD_NOT_FOUND` на login — пользователь с таким username не зарегистрирован
- `403 PERMISSION_DENIED` — у роли нет доступа к действию
- `422 VALIDATION_ERROR` — неверные данные

### Практическая рекомендация

Если backend вернул не `2xx`, боту лучше:

- залогировать `status_code`, `detail`, `error_code`
- показать пользователю безопасное сообщение
- не пытаться самостоятельно “додумать”, что backend имел в виду

---

## Рекомендуемая схема работы бота

### На `/start`

1. получить `telegram_username`
2. вызвать `POST /auth/{telegram_username}/login`
3. отправить `message`
4. отрисовать `buttons`

### На `callback_query`

1. взять `callback_data`
2. вызвать `POST /actions/button/{action}`
3. обновить интерфейс из ответа

### На обычный текст

1. вызвать `POST /actions/text`
2. показать новый экран из ответа

### На документ

1. скачать файл из Telegram
2. вызвать `POST /actions/file`
3. показать новый экран из ответа

---

## Минимальный рабочий пример запросов

### Login

```bash
curl -X POST "http://127.0.0.1:8080/api/reflections/auth/Syrnick/login" \
  -H "X-Service-API-Key: your-token" \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123456789}'
```

### Button action

```bash
curl -X POST "http://127.0.0.1:8080/api/reflections/actions/button/admin_create_course" \
  -H "X-Service-API-Key: your-token" \
  -H "X-Telegram-Id: 123456789"
```

### Text input

```bash
curl -X POST "http://127.0.0.1:8080/api/reflections/actions/text" \
  -H "X-Service-API-Key: your-token" \
  -H "X-Telegram-Id: 123456789" \
  -H "Content-Type: application/json" \
  -d '{"text": "Иванов Иван Иванович"}'
```

### File input

```bash
curl -X POST "http://127.0.0.1:8080/api/reflections/actions/file" \
  -H "X-Service-API-Key: your-token" \
  -H "X-Telegram-Id: 123456789" \
  -F "file=@students.csv"
```

---

## Что важно не делать в Telegram-боте

- не хардкодить меню и переходы
- не дублировать серверную навигацию `Назад`
- не разбирать `action` вручную, если в этом нет крайней необходимости
- не пытаться хранить единственный источник правды о wizard state на стороне бота
- не использовать удалённые старые endpoint'ы

Правильная модель:

- backend = источник правды
- bot = транспорт, рендер и интеграция с Telegram API

---

## OpenAPI

Для отладки можно использовать:

- `/docs`
- `/redoc`
- `/openapi.json`

Но в production-логике Telegram-бот должен работать только через 4 endpoint'а, перечисленные в начале документа.
