# API Documentation - Admins

## Эндпоинты для работы с администраторами

**Важно:** Все запросы требуют заголовок `X-Service-API-Key` со значением из `REFLEBOT_TELEGRAM_SECRET_TOKEN`.

### 1. Создание администратора

**POST** `/api/reflections/admins/`

Создание нового администратора с ФИО и никнеймом в Telegram. **Требуется авторизация администратора.**

**Headers:**
- `X-Service-API-Key` (string, required) - API ключ для доступа к сервису
- `X-Telegram-Id` (integer, required) - Telegram ID существующего администратора

**Request Body:**
```json
{
  "full_name": "Иванов Иван Иванович",
  "telegram_username": "ivan_telegram",
  "telegram_id": null,
  "is_active": true
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "full_name": "Иванов Иван Иванович",
  "telegram_username": "ivan_telegram",
  "telegram_id": null,
  "is_active": true,
  "created_at": "2026-03-26T19:00:00Z",
  "updated_at": "2026-03-26T19:00:00Z"
}
```

**Пример curl:**
```bash
curl -X POST "http://localhost:8080/api/reflections/admins/" \
  -H "Content-Type: application/json" \
  -H "X-Service-API-Key: your-telegram-bot-token" \
  -H "X-Telegram-Id: 123456789" \
  -d '{
    "full_name": "Иванов Иван Иванович",
    "telegram_username": "ivan_telegram"
  }'
```

---

### 2. Вход пользователя (универсальный)

**POST** `/api/reflections/auth/{telegram_username}/login`

Универсальный вход для администратора/студента/преподавателя. Обновляет telegram_id во всех таблицах, где найден username.

**Path Parameters:**
- `telegram_username` (string) - Никнейм пользователя в Telegram

**Headers:**
- `X-Service-API-Key` (string, required) - API ключ для доступа к сервису

**Request Body:**
```json
{
  "telegram_id": 123456789
}
```

**Response (200 OK):**
```json
{
  "full_name": "Иванов Иван Иванович",
  "telegram_username": "ivan_telegram",
  "telegram_id": 123456789,
  "is_active": true,
  "is_admin": true,
  "is_teacher": false,
  "is_student": true,
  "message": "✅ Вы успешно зарегистрированы!\n\n👤 Иванов Иван Иванович\n\nВаши роли:\n• 👨‍💼 Администратор\n• 👨‍🎓 Студент\n\nВыберите действие из меню ниже.",
  "parse_mode": "HTML",
  "buttons": [
    {
      "text": "➕ Создать администратора",
      "action": "admin_create_admin"
    },
    {
      "text": "📚 Создать курс",
      "action": "admin_create_course"
    },
    {
      "text": "📋 Курсы",
      "action": "admin_view_courses"
    }
  ]
}
```

**Описание полей ответа:**
- `full_name` - ФИО пользователя
- `telegram_username` - Никнейм в Telegram
- `telegram_id` - ID в Telegram
- `is_active` - Активен ли пользователь
- `is_admin` - Найден ли в таблице администраторов
- `is_teacher` - Найден ли в таблице преподавателей
- `is_student` - Найден ли в таблице студентов
- `message` - Приветственное сообщение с перечислением ролей
- `parse_mode` - Режим парсинга сообщения для Telegram API (HTML, Markdown, MarkdownV2)
- `buttons` - Массив кнопок для Telegram бота (зависит от ролей пользователя)

**Кнопки в зависимости от ролей:**

Администратор:
- "➕ Создать администратора" (`admin_create_admin`)
- "📚 Создать курс" (`admin_create_course`)
- "📋 Курсы" (`admin_view_courses`)

Преподаватель:
- "📊 Аналитика" (`teacher_analytics`)
- "📅 Ближайшая лекция" (`teacher_next_lection`)

Студент:
- Кнопки не отображаются

**Примечание:** Один и тот же username может существовать в нескольких таблицах одновременно. Система обновит telegram_id во всех найденных записях.

**Пример curl:**
```bash
curl -X POST "http://localhost:8080/api/reflections/auth/ivan_telegram/login" \
  -H "Content-Type: application/json" \
  -H "X-Service-API-Key: your-telegram-bot-token" \
  -d '{
    "telegram_id": 123456789
  }'
```

---

## Эндпоинты для работы с действиями и текстовым вводом

**Важно:** Все запросы требуют заголовок `X-Service-API-Key` со значением из `REFLEBOT_TELEGRAM_SECRET_TOKEN`.

### 4. Обработка нажатия кнопки

**POST** `/api/reflections/actions/button/{action}`

Обработка нажатия кнопки пользователем. Устанавливает контекст для многошагового диалога.

**Path Parameters:**
- `action` (string) - Действие кнопки (например, `admin_create_admin`, `admin_create_course`)

**Headers:**
- `X-Service-API-Key` (string, required) - API ключ для доступа к сервису
- `X-Telegram-Id` (integer, required) - Telegram ID пользователя

**Response (200 OK):**
```json
{
  "message": "👤 Введите ФИО администратора:",
  "parse_mode": "HTML",
  "buttons": [],
  "awaiting_input": true
}
```

**Описание полей ответа:**
- `message` - Сообщение для пользователя с инструкцией
- `parse_mode` - Режим парсинга сообщения (HTML, Markdown, MarkdownV2)
- `buttons` - Массив кнопок (пустой, если ожидается текстовый ввод)
- `awaiting_input` - Флаг, что система ожидает текстовый ввод от пользователя

**Доступные действия:**
- `admin_create_admin` - Начать процесс создания администратора
- `admin_create_course` - Начать процесс создания курса
- `admin_view_courses` - Просмотр курсов (пока не реализовано)
- `teacher_analytics` - Аналитика преподавателя (пока не реализовано)
- `teacher_next_lection` - Ближайшая лекция (пока не реализовано)

**Пример curl:**
```bash
curl -X POST "http://localhost:8080/api/reflections/actions/button/admin_create_admin" \
  -H "X-Service-API-Key: your-telegram-bot-token" \
  -H "X-Telegram-Id: 123456789"
```

---

### 5. Обработка текстового ввода

**POST** `/api/reflections/actions/text`

Обработка текстового ввода от пользователя. Читает контекст пользователя и выполняет соответствующее действие.

**Headers:**
- `X-Service-API-Key` (string, required) - API ключ для доступа к сервису
- `X-Telegram-Id` (integer, required) - Telegram ID пользователя

**Request Body:**
```json
{
  "text": "Иванов Иван Иванович"
}
```

**Response (200 OK) - промежуточный шаг:**
```json
{
  "message": "📝 Введите никнейм в Telegram (без @):",
  "parse_mode": "HTML",
  "buttons": [],
  "awaiting_input": true
}
```

**Response (200 OK) - финальный шаг:**
```json
{
  "message": "✅ Администратор Иванов Иван Иванович успешно создан!",
  "parse_mode": "HTML",
  "buttons": [
    {
      "text": "➕ Создать администратора",
      "action": "admin_create_admin"
    },
    {
      "text": "📚 Создать курс",
      "action": "admin_create_course"
    },
    {
      "text": "📋 Курсы",
      "action": "admin_view_courses"
    }
  ],
  "awaiting_input": false
}
```

**Пример curl (первый шаг):**
```bash
# После нажатия кнопки "Создать администратора"
curl -X POST "http://localhost:8080/api/reflections/actions/text" \
  -H "Content-Type: application/json" \
  -H "X-Service-API-Key: your-telegram-bot-token" \
  -H "X-Telegram-Id: 123456789" \
  -d '{"text": "Иванов Иван Иванович"}'
```

**Пример curl (второй шаг):**
```bash
# После ввода ФИО
curl -X POST "http://localhost:8080/api/reflections/actions/text" \
  -H "Content-Type: application/json" \
  -H "X-Service-API-Key: your-telegram-bot-token" \
  -H "X-Telegram-Id: 123456789" \
  -d '{"text": "ivanov_ivan"}'
```

**Workflow создания администратора:**
1. Пользователь нажимает кнопку "Создать администратора" → `POST /actions/button/admin_create_admin`
2. Система устанавливает контекст и просит ввести ФИО → `awaiting_input: true`
3. Пользователь вводит ФИО → `POST /actions/text` с текстом
4. Система сохраняет ФИО и просит ввести username → `awaiting_input: true`
5. Пользователь вводит username → `POST /actions/text` с текстом
6. Система создаёт администратора, очищает контекст и возвращает кнопки → `awaiting_input: false`

---

## Ошибки

Все ошибки возвращаются в формате:
```json
{
  "detail": "Описание ошибки",
  "error_code": "ERROR_CODE"
}
```

### 401 Unauthorized

**Код ошибки:** `MISSING_API_KEY`

Отсутствует заголовок X-Service-API-Key.

```json
{
  "detail": "Отсутствует заголовок X-Service-API-Key",
  "error_code": "MISSING_API_KEY"
}
```

### 403 Forbidden (неверный API ключ)

**Код ошибки:** `INVALID_API_KEY`

Неверный API ключ в заголовке X-Service-API-Key.

```json
{
  "detail": "Неверный API ключ",
  "error_code": "INVALID_API_KEY"
}
```

### 403 Forbidden (нет прав администратора)

**Код ошибки:** `PERMISSION_DENIED`

Доступ запрещен. Администратор не найден или неактивен.

```json
{
  "detail": "Доступ запрещен: администратор не найден",
  "error_code": "PERMISSION_DENIED"
}
```

или

```json
{
  "detail": "Администратор неактивен",
  "error_code": "PERMISSION_DENIED"
}
```

### 404 Not Found

**Код ошибки:** `MODEL_FIELD_NOT_FOUND`

Пользователь с указанным никнеймом не найден ни в одной таблице.

```json
{
  "detail": "Unable to find the Admin with telegram_username equal to ivan_telegram.",
  "error_code": "MODEL_FIELD_NOT_FOUND"
}
```

### 409 Conflict

**Код ошибки:** `MODEL_ALREADY_EXISTS`

Администратор с таким никнеймом уже существует.

```json
{
  "detail": "Model Admin with telegram_username already exists: duplicate key for field: telegram_username",
  "error_code": "MODEL_ALREADY_EXISTS"
}
```

### Полный список кодов ошибок

| Код ошибки | HTTP статус | Описание |
|-----------|-------------|----------|
| `MISSING_API_KEY` | 401 | Отсутствует заголовок X-Service-API-Key |
| `INVALID_API_KEY` | 403 | Неверный API ключ |
| `PERMISSION_DENIED` | 403 | Недостаточно прав для выполнения действия |
| `MODEL_NOT_FOUND` | 404 | Модель не найдена по ID |
| `MODEL_FIELD_NOT_FOUND` | 404 | Модель не найдена по значению поля |
| `FILE_NOT_FOUND` | 404 | Файл не найден |
| `MODEL_ALREADY_EXISTS` | 409 | Модель с таким уникальным полем уже существует |
| `VALIDATION_ERROR` | 422 | Ошибка валидации данных |
| `SORTING_FIELD_NOT_FOUND` | 400 | Поле для сортировки не найдено |
| `UNAUTHORIZED` | 401 | Требуется аутентификация |
| `EXCEL_FILE_ERROR` | 400 | Ошибка чтения Excel файла |
| `EXCEL_FILE_FORMAT_ERROR` | 400 | Неверный формат Excel файла |
| `EXCEL_FILE_MISSING_COLUMN` | 400 | Отсутствует обязательная колонка в Excel |
| `EXCEL_FILE_EMPTY` | 400 | Excel файл пустой |
| `EXCEL_FILE_DATE_PARSE_ERROR` | 400 | Ошибка парсинга даты в Excel |

---

## Скрипт для создания администратора

Для создания **первого** администратора вручную через командную строку (когда в системе ещё нет админов):

```bash
uv run python scripts/create_admin.py "Иванов Иван Иванович" "ivan_telegram"
```

**Аргументы:**
1. ФИО администратора (в кавычках)
2. Никнейм в Telegram (без @)

**Пример вывода:**
```
✅ Администратор успешно создан:
   ID: 1
   ФИО: Иванов Иван Иванович
   Telegram: @ivan_telegram
   Активен: True
```

**Важно:** После создания первого администратора через скрипт, он должен выполнить вход через эндпоинт `/login`, чтобы установить свой `telegram_id`. После этого он сможет создавать других администраторов через API.

---

## Архитектура

### Слои

1. **Router** (`router.py`) - HTTP-эндпоинты
2. **Use Cases** (`use_cases/admin.py`) - Бизнес-логика приложения
3. **Services** (`services/admin.py`) - Доменная логика
4. **Repositories** (`repositories/admin.py`) - Доступ к данным
5. **Models** (`models.py`) - SQLAlchemy модели
6. **Schemas** (`schemas.py`) - Pydantic схемы валидации

### Dependency Injection

Все зависимости настроены в `depends.py`:

```python
from reflebot.apps.reflections.depends import (
    AdminServiceDep,
    CreateAdminUseCaseDep,
    AdminLoginUseCaseDep,
)
```

### Поток данных

```
HTTP Request
    ↓
Router (валидация через Pydantic)
    ↓
Use Case (оркестрация)
    ↓
Service (бизнес-логика)
    ↓
Repository (CRUD)
    ↓
Database
```


---

## Авторизация

Для выполнения защищённых операций (например, создание администратора) необходимо передавать `telegram_id` в заголовке `X-Telegram-Id`.

### Процесс первичной настройки:

1. Создать первого администратора через скрипт:
   ```bash
   uv run python scripts/create_admin.py "Главный Админ" "main_admin"
   ```

2. Выполнить вход для установки `telegram_id`:
   ```bash
   curl -X POST "http://localhost:8080/api/reflections/auth/main_admin/login" \
     -H "Content-Type: application/json" \
     -H "X-Service-API-Key: your-telegram-bot-token" \
     -d '{"telegram_id": 123456789}'
   ```
   
   Ответ:
   ```json
   {
     "full_name": "Главный Админ",
     "telegram_username": "main_admin",
     "telegram_id": 123456789,
     "is_active": true,
     "is_admin": true,
     "is_teacher": false,
     "is_student": false,
     "message": "✅ Вы успешно зарегистрированы!\n\n👤 Главный Админ\n\nВаши роли:\n• 👨‍💼 Администратор\n\nВыберите действие из меню ниже.",
     "parse_mode": "HTML",
     "buttons": [
       {
         "text": "➕ Создать администратора",
         "action": "admin_create_admin"
       },
       {
         "text": "📚 Создать курс",
         "action": "admin_create_course"
       },
       {
         "text": "📋 Курсы",
         "action": "admin_view_courses"
       }
     ]
   }
   ```

3. Теперь можно создавать других администраторов через API:
   ```bash
   curl -X POST "http://localhost:8080/api/reflections/admins/" \
     -H "Content-Type: application/json" \
     -H "X-Service-API-Key: your-telegram-bot-token" \
     -H "X-Telegram-Id: 123456789" \
     -d '{
       "full_name": "Новый Админ",
       "telegram_username": "new_admin"
     }'
   ```

### Проверка прав доступа

При каждом запросе с заголовком `X-Telegram-Id` система:
1. Ищет администратора с указанным `telegram_id`
2. Проверяет, что администратор активен (`is_active = true`)
3. Если проверка не пройдена - возвращает `403 Forbidden`


---

## Безопасность

### API Key защита

Все запросы к API требуют заголовок `X-Service-API-Key` со значением, совпадающим с `REFLEBOT_TELEGRAM_SECRET_TOKEN` из переменных окружения.

**Исключения (не требуют API ключ):**
- `/docs` - Swagger документация
- `/redoc` - ReDoc документация
- `/openapi.json` - OpenAPI спецификация
- `/docs.json` - JSON схема документации

**Настройка:**
```bash
# В .env файле
REFLEBOT_TELEGRAM_SECRET_TOKEN=your-secure-token-here
```

**Использование:**
Все запросы должны включать заголовок:
```
X-Service-API-Key: your-secure-token-here
```

**Ошибки:**
- `401 Unauthorized` - заголовок отсутствует
- `403 Forbidden` - неверное значение ключа


---

## Эндпоинты для работы с курсами

**Важно:** Все запросы требуют заголовок `X-Service-API-Key` со значением из `REFLEBOT_TELEGRAM_SECRET_TOKEN`.

### 3. Импорт курса из Excel файла

**POST** `/api/reflections/courses/import`

Создание курса с лекциями из Excel файла. Требуется telegram_id администратора в заголовке X-Telegram-Id.

**Headers:**
- `X-Service-API-Key` (string, required) - API ключ для доступа к сервису
- `X-Telegram-Id` (integer, required) - Telegram ID существующего администратора
- `Content-Type: multipart/form-data`

**Form Data:**
- `file` (file, required) - Excel файл (.xlsx) с данными курса

**Формат Excel файла:**

Файл должен содержать следующие колонки в первой строке:

| Название | Тема лекции | Дата | Время | Препод |
|----------|-------------|------|-------|--------|
| Инновации в бизнес моделях | Введение: что такое инновации | 4/5/2026 | 18:00–19:30 | Карлов Алексей Вадимович |
| Инновации в бизнес моделях | Типы бизнес-моделей | 4/12/2026 | 18:00–19:30 | Карлов Алексей Вадимович |

**Требования к колонкам:**
- `Название` - название курса (одинаковое для всех строк)
- `Тема лекции` - тема конкретной лекции
- `Дата` - дата лекции (форматы: MM/DD/YYYY, DD.MM.YYYY, YYYY-MM-DD)
- `Время` - время лекции в формате HH:MM–HH:MM или HH:MM-HH:MM (начало и конец)
- `Препод` - ФИО преподавателя

**Response (201 Created):**
```json
{
  "id": 1,
  "name": "Инновации в бизнес моделях",
  "started_at": "2026-04-05T18:00:00",
  "ended_at": "2026-05-31T19:30:00",
  "created_at": "2026-03-26T20:00:00Z",
  "updated_at": "2026-03-26T20:00:00Z"
}
```

**Примечания:**
- Даты курса (`started_at`, `ended_at`) определяются автоматически как самая ранняя и самая поздняя даты лекций
- Преподаватели создаются автоматически, если не существуют
- Для каждого преподавателя генерируется username из ФИО (например: "Иванов Иван" → "ivanov_ivan")

**Пример curl:**
```bash
curl -X POST "http://localhost:8080/api/reflections/courses/import" \
  -H "X-Service-API-Key: your-telegram-bot-token" \
  -H "X-Telegram-Id: 123456789" \
  -F "file=@course_data.xlsx"
```

**Ошибки Excel файла:**

| Код ошибки | Описание |
|-----------|----------|
| `EXCEL_FILE_ERROR` | Не удалось прочитать Excel файл |
| `EXCEL_FILE_FORMAT_ERROR` | Неверный формат файла (нет заголовков) |
| `EXCEL_FILE_MISSING_COLUMN` | Отсутствует обязательная колонка |
| `EXCEL_FILE_EMPTY` | Файл пустой или не содержит данных |
| `EXCEL_FILE_DATE_PARSE_ERROR` | Ошибка парсинга даты в конкретной строке |

**Пример ошибки:**
```json
{
  "detail": "Отсутствует обязательная колонка: Дата",
  "error_code": "EXCEL_FILE_MISSING_COLUMN"
}
```

или

```json
{
  "detail": "Ошибка парсинга даты в строке 3: Не удалось распарсить дату: invalid_date",
  "error_code": "EXCEL_FILE_DATE_PARSE_ERROR"
}
```
