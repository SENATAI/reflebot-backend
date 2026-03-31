# Reflebot System Overview

## Общая концепция

**Reflebot** — это backend-система для сбора рефлексий студентов с занятий и просмотра аналитики для преподавателей. Система построена на принципе **Backend-Driven Telegram Bot**, где вся бизнес-логика, состояния диалогов и генерация UI (кнопки, сообщения) происходит на бэкенде.

### Ключевая идея архитектуры

Telegram бот является **тонким клиентом** (thin client), который:
- Принимает события от пользователя (нажатия кнопок, текстовый ввод, файлы)
- Отправляет запросы на бэкенд
- Получает готовые ответы с сообщениями и кнопками
- Отображает их пользователю

Бэкенд полностью контролирует:
- Бизнес-логику всех операций
- Состояния многошаговых диалогов
- Генерацию сообщений и кнопок
- Авторизацию и права доступа
- Валидацию данных

---

## Технологический стек

- **FastAPI** - веб-фреймворк
- **SQLAlchemy 2.0** - ORM для работы с PostgreSQL
- **Alembic** - миграции БД
- **PostgreSQL** - основная БД
- **Pydantic** - валидация данных
- **UV** - менеджер зависимостей
- **Telegram Bot API file_id** - идентификаторы файлов для повторной отправки медиа

---

## Архитектурные слои (Clean Architecture)


### 1. Settings (Конфигурация)

Управление конфигурацией через Pydantic Settings с вложенными моделями:

```python
class Settings(BaseSettings):
    debug: bool
    base_url: str
    secret_key: str
    telegram_secret_token: str
    
    db: Db              # Настройки PostgreSQL
    
    model_config = SettingsConfigDict(
        env_prefix='REFLEBOT_',
        env_nested_delimiter='__'
    )
```

**Переменные окружения:**
```bash
REFLEBOT_DEBUG=true
REFLEBOT_DB__HOST=localhost
REFLEBOT_DB__PORT=5432
```

### 2. Models (Модели БД)

SQLAlchemy модели с UUID primary keys:

```python
class CourseSession(Base, TimestampMixin):
    __tablename__ = "course_sessions"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
```

**Ключевые особенности:**
- Все ID используют UUID для безопасности
- Миксин `TimestampMixin` добавляет `created_at` и `updated_at`
- Foreign keys с CASCADE для автоматического удаления связанных записей


### 3. Schemas (Pydantic схемы)

Валидация данных для API:

```python
class AdminBaseSchema(BaseModel):
    full_name: str = Field(..., max_length=255)
    telegram_username: str = Field(..., max_length=100)

class AdminCreateSchema(AdminBaseSchema, CreateBaseModel):
    pass

class AdminReadSchema(AdminBaseSchema):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**Соглашения:**
- `*BaseSchema` - общие поля
- `*CreateSchema` - для POST запросов
- `*UpdateSchema` - для PUT/PATCH запросов
- `*ReadSchema` - для ответов (включает id, timestamps)

### 4. Repositories (Слой данных)

Абстракция работы с БД:

```python
class AdminRepository(BaseRepositoryImpl[Admin, AdminCreateSchema, AdminUpdateSchema, AdminReadSchema]):
    async def get_by_telegram_id(self, telegram_id: int) -> AdminReadSchema | None:
        async with self.session as s:
            stmt = sa.select(self.model_type).where(self.model_type.telegram_id == telegram_id)
            result = await s.execute(stmt)
            return self.read_schema_type.model_validate(result.scalar_one_or_none())
```

**BaseRepositoryImpl предоставляет:**
- `get(id)`, `get_all()`, `create()`, `update()`, `delete()`
- `bulk_create()`, `bulk_update()`, `paginate()`


### 5. Services (Бизнес-логика)

Доменная логика и бизнес-правила:

```python
class AdminService:
    def __init__(self, repository: AdminRepositoryProtocol):
        self.repository = repository
    
    async def create_admin(self, data: AdminCreateSchema) -> AdminReadSchema:
        # Бизнес-валидация
        existing = await self.repository.get_by_telegram_username(data.telegram_username)
        if existing:
            raise ModelAlreadyExistsError(Admin, "telegram_username")
        
        return await self.repository.create(data)
```

### 6. Use Cases (Оркестрация)

Координация нескольких сервисов для выполнения пользовательского действия:

```python
class CreateCourseFromExcelUseCase:
    def __init__(self, course_service: CourseServiceProtocol, parser: FileParserProtocol):
        self.course_service = course_service
        self.parser = parser
    
    async def __call__(self, excel_file: BinaryIO, current_admin: AdminReadSchema):
        # 1. Парсинг файла
        course_name, lections_data = self.parser.parse(excel_file)
        
        # 2. Создание курса
        return await self.course_service.create_course_with_lections(course_name, lections_data)
```

### 7. Routers (HTTP эндпоинты)

Разделены по функциональности в папке `routers/`:

```
reflebot/apps/reflections/routers/
├── admin.py      # Управление администраторами
├── auth.py       # Аутентификация
├── actions.py    # Обработка кнопок и текста
└── course.py     # Управление курсами
```


---

## Система работы с Telegram ботом

### Backend-Driven подход

Бэкенд полностью управляет UI и логикой Telegram бота. Telegram бот — это просто транспорт для событий.

### Компоненты системы

#### 1. Сообщения (`telegram/messages.py`)

Все текстовые сообщения централизованы в одном файле:

```python
class TelegramMessages:
    @staticmethod
    def get_login_message(full_name: str, is_admin: bool, is_teacher: bool, is_student: bool) -> str:
        return "✅ Вы успешно зарегистрированы!..."
    
    @staticmethod
    def get_create_admin_request_fullname() -> str:
        return "👤 Введите ФИО администратора:"
```

**Расположение:** `reflebot/apps/reflections/telegram/messages.py`

**Правило:** Все сообщения должны быть в этом файле. Никаких хардкодных строк в роутерах или сервисах.

#### 2. Кнопки (`telegram/buttons.py`)

Генерация кнопок в зависимости от ролей пользователя:

```python
class TelegramButtons:
    ADMIN_CREATE_ADMIN = "admin_create_admin"
    ADMIN_CREATE_COURSE = "admin_create_course"
    
    @staticmethod
    def get_login_buttons(is_admin: bool, is_teacher: bool, is_student: bool) -> list[TelegramButton]:
        buttons = []
        if is_admin:
            buttons.extend([
                TelegramButton(text="➕ Создать администратора", action="admin_create_admin"),
                TelegramButton(text="📚 Создать курс", action="admin_create_course"),
            ])
        return buttons
```

**Расположение:** `reflebot/apps/reflections/telegram/buttons.py`


#### 3. Контекст пользователя (User Context)

Для многошаговых диалогов используется таблица `users` с полем `user_context`:

**Модель:**
```python
class User(Base, TimestampMixin):
    __tablename__ = "users"
    
    telegram_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    user_context: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
```

**Структура контекста:**
```json
{
  "action": "create_admin",
  "step": "awaiting_fullname",
  "data": {
    "fullname": "Иванов Иван Иванович"
  }
}
```

**Расположение:** Таблица `users` в PostgreSQL

**Сервис:** `ContextService` в `reflebot/apps/reflections/services/context.py`

### Workflow многошагового диалога

**Пример: Создание администратора**

1. **Пользователь нажимает кнопку "Создать администратора"**
   ```
   POST /api/reflections/actions/button/admin_create_admin
   Headers: X-Telegram-Id: 123456789
   ```
   
   Бэкенд:
   - Сохраняет контекст: `{"action": "create_admin", "step": "awaiting_fullname"}`
   - Возвращает:
   ```json
   {
     "message": "👤 Введите ФИО администратора:",
     "parse_mode": "HTML",
     "buttons": [],
     "awaiting_input": true
   }
   ```

2. **Пользователь вводит "Иванов Иван Иванович"**
   ```
   POST /api/reflections/actions/text
   Body: {"text": "Иванов Иван Иванович"}
   ```
   
   Бэкенд:
   - Читает контекст, видит `action="create_admin", step="awaiting_fullname"`
   - Сохраняет ФИО в `context.data`
   - Обновляет контекст: `{"action": "create_admin", "step": "awaiting_username", "data": {"fullname": "..."}}`
   - Возвращает:
   ```json
   {
     "message": "📝 Введите никнейм в Telegram (без @):",
     "awaiting_input": true
   }
   ```


3. **Пользователь вводит "ivanov_ivan"**
   ```
   POST /api/reflections/actions/text
   Body: {"text": "ivanov_ivan"}
   ```
   
   Бэкенд:
   - Читает контекст, видит все данные собраны
   - Создаёт администратора в БД
   - Очищает контекст: `user_context = null`
   - Возвращает:
   ```json
   {
     "message": "✅ Администратор Иванов Иван Иванович успешно создан!",
     "buttons": [
       {"text": "➕ Создать администратора", "action": "admin_create_admin"},
       {"text": "📚 Создать курс", "action": "admin_create_course"}
     ],
     "awaiting_input": false
   }
   ```

### Преимущества Backend-Driven подхода

✅ **Централизованная логика** - вся бизнес-логика на бэкенде, легко тестировать  
✅ **Персистентное состояние** - контекст в БД переживёт перезапуск бота  
✅ **Гибкость UI** - можно менять кнопки и сообщения без изменения бота  
✅ **Валидация** - все данные валидируются на бэкенде через Pydantic  
✅ **Авторизация** - права проверяются на каждом шаге  
✅ **Масштабируемость** - можно запустить несколько инстансов бота  

---

## Система хранения файлов

### Текущая логика для reflections

В текущем Telegram workflow модуль reflections не хранит бинарные файлы отдельно.
Для медиа сохраняется только Telegram `file_id`, который затем бот может использовать
для повторной отправки пользователю.

Модель `File` и модуль `apps/files` сохранены в проекте, но в текущем workflow
reflections не используются.

### Модуль apps/files

`apps/files` остаётся в кодовой базе как отдельный модуль и может быть использован позже
для отдельного файлового сценария.

**Модель File:**
```python
class File(Base, TimestampMixin):
    __tablename__ = "files"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    path: Mapped[str] = mapped_column(sa.String(256), unique=True)
    filename: Mapped[str] = mapped_column(sa.String(256))
    content_type: Mapped[str] = mapped_column(sa.String(256))
    size: Mapped[int] = mapped_column(sa.BigInteger)
```

### Интеграция с моделями

Вместо внешнего `file_id` из таблицы `files`, модели reflections теперь хранят
Telegram `file_id` напрямую:

```python
class LectionSession(Base, TimestampMixin):
    presentation_file_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    recording_file_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
```

**Преимущества:**
- бот может переотправлять файл по исходному Telegram `file_id`
- backend не обязан скачивать и повторно загружать файл
- модель ответа API остаётся простой для Telegram-клиента


### Workflow загрузки файла

1. **Пользователь загружает файл через Telegram бота**
2. **Бот получает от Telegram `file_id`**
3. **Бот отправляет на backend `telegram_file_id`:**
   ```
   POST /api/reflections/actions/file
   Content-Type: multipart/form-data
   Body: telegram_file_id=<telegram-file-id>
   ```

4. **Бэкенд:**
   - сохраняет `telegram_file_id` в связанной модели лекции или аналитики
   - возвращает обычный `ActionResponseSchema`

5. **При необходимости повторной отправки backend возвращает ссылку на Telegram-файл:**
   ```python
   response.files = [
       {"telegram_file_id": "BQACAgIAAxkBAAIB...", "kind": "presentation"}
   ]
   ```

6. **Бот переотправляет файл пользователю по этому `telegram_file_id`**

---

## Доменные модели

### Основные сущности

#### 1. Пользователи
- **Admin** - администраторы системы
- **Teacher** - преподаватели
- **Student** - студенты
- **User** - контекст диалога (для всех пользователей)

#### 2. Курсы и лекции
- **CourseSession** - сессия курса (семестр)
- **LectionSession** - конкретная лекция
- **Question** - вопросы к лекции

#### 3. Рефлексии
- **LectionReflection** - рефлексия студента по лекции
- **ReflectionVideo** - видео рефлексии (несколько на одну рефлексию)
- **LectionQA** - ответы на вопросы
- **QAVideo** - видео ответов на вопросы

#### 4. Связи
- **StudentCourse** - привязка студента к курсу
- **StudentLection** - привязка студента к лекции
- **TeacherCourse** - привязка преподавателя к курсу
- **TeacherLection** - привязка преподавателя к лекции


---

## Безопасность

### API Key защита

Все запросы требуют заголовок `X-Service-API-Key`:

```python
# middleware.py
if request.url.path not in ["/docs", "/redoc", "/openapi.json"]:
    api_key = request.headers.get("X-Service-API-Key")
    if not api_key or api_key != settings.telegram_secret_token:
        raise InvalidAPIKeyError()
```

### Авторизация администраторов

Для защищённых операций требуется `X-Telegram-Id`:

```python
async def get_current_admin(
    x_telegram_id: int = Header(...),
    admin_service: AdminServiceProtocol = Depends(get_admin_service)
) -> AdminReadSchema:
    admin = await admin_service.get_by_telegram_id(x_telegram_id)
    if not admin.is_active:
        raise PermissionDeniedError("Администратор неактивен")
    return admin
```

### Обработка ошибок

Все исключения наследуются от `CoreException` и имеют уникальный `error_code`:

```python
class ModelNotFoundException(CoreException):
    def __init__(self, model_type, model_id):
        super().__init__(
            status_code=404,
            detail=f"Unable to find the {model_type.__name__} with id {model_id}",
            error_code="MODEL_NOT_FOUND"
        )
```

**Коды ошибок:**
- `MISSING_API_KEY` (401) - отсутствует API ключ
- `INVALID_API_KEY` (403) - неверный API ключ
- `PERMISSION_DENIED` (403) - недостаточно прав
- `MODEL_NOT_FOUND` (404) - модель не найдена
- `MODEL_ALREADY_EXISTS` (409) - дубликат
- `VALIDATION_ERROR` (422) - ошибка валидации


---

## Парсеры файлов

Для обработки загружаемых файлов используется паттерн Strategy с DI.

### Базовый парсер

```python
class BaseFileParser(ABC):
    @abstractmethod
    def parse(self, file: BinaryIO) -> Any:
        pass
```

### Пример: CourseExcelParser

```python
class CourseExcelParser(BaseFileParser):
    def parse(self, file: BinaryIO) -> tuple[str, list[dict]]:
        # Парсинг Excel файла
        # Возвращает: (название_курса, список_лекций)
        pass
```

**Инжекция через DI:**
```python
def get_course_excel_parser() -> FileParserProtocol:
    return CourseExcelParser()

def get_create_course_use_case(
    parser: FileParserProtocol = Depends(get_course_excel_parser)
):
    return CreateCourseFromExcelUseCase(parser=parser)
```

**Расположение:** `reflebot/apps/reflections/parsers/`

---

## Dependency Injection

Все зависимости настроены в `depends.py`:

```python
# Приватные фабрики репозиториев (двойное подчеркивание)
def __get_admin_repository(session: AsyncSession = Depends(get_async_session)):
    return AdminRepository(session=session)

# Публичные фабрики сервисов
def get_admin_service(repository: AdminRepositoryProtocol = Depends(__get_admin_repository)):
    return AdminService(repository=repository)

# Фабрики use cases
def get_create_admin_use_case(admin_service: AdminServiceProtocol = Depends(get_admin_service)):
    return CreateAdminUseCase(admin_service=admin_service)

# DI алиасы для краткости
AdminServiceDep = Annotated[AdminServiceProtocol, Depends(get_admin_service)]
```

**Правила:**
- Репозитории - приватные (`__get_*`)
- Сервисы и use cases - публичные (`get_*`)
- Используйте алиасы для краткости в роутерах


---

## Поток данных в системе

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot (Thin Client)               │
│  - Получает события от пользователя                         │
│  - Отправляет HTTP запросы на бэкенд                        │
│  - Отображает сообщения и кнопки                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP (JSON)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Router (HTTP endpoints)                             │   │
│  │  - Валидация через Pydantic                         │   │
│  │  - Проверка API ключа (middleware)                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Use Case (оркестрация)                              │   │
│  │  - Авторизация (X-Telegram-Id)                      │   │
│  │  - Координация сервисов                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│              ┌─────────────┼─────────────┐                  │
│              ▼             ▼             ▼                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │   Service    │ │   Service    │ │   Adapter    │       │
│  │ (бизнес-     │ │ (бизнес-     │ │ (внешние     │       │
│  │  логика)     │ │  логика)     │ │  сервисы)    │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
│              │             │                                │
│              ▼             ▼                                │
│  ┌──────────────┐ ┌──────────────┐                         │
│  │ Repository   │ │ Repository   │                         │
│  │ (CRUD)       │ │ (CRUD)       │                         │
│  └──────────────┘ └──────────────┘                         │
│              │             │                                │
│              └──────┬──────┘                                │
│                     ▼                                       │
└─────────────────────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼
┌──────────────┐
│  PostgreSQL  │
│  (контекст,  │
│   пользовате-│
│   ли, курсы, │
│   telegram   │
│   file_id)   │
└──────────────┘
```


---

## Ключевые API эндпоинты

### Аутентификация

**POST** `/api/reflections/auth/{telegram_username}/login`
- Универсальный вход для Admin/Teacher/Student
- Обновляет `telegram_id` во всех найденных таблицах
- Возвращает роли, сообщение и кнопки

### Обработка действий бота

**POST** `/api/reflections/actions/button/{action}`
- Обработка нажатия кнопки
- Устанавливает контекст для многошагового диалога
- Возвращает сообщение и флаг `awaiting_input`

**POST** `/api/reflections/actions/text`
- Обработка текстового ввода
- Читает контекст из БД
- Выполняет действие в зависимости от `action` и `step`

### Работа с файлами

**POST** `/api/reflections/actions/file`
- Для Excel/CSV принимает бинарный файл
- Для презентации или записи лекции принимает `telegram_file_id`
- Возвращает `ActionResponseSchema`


---

## Структура проекта

```
reflebot/
├── .docs/                          # Документация
│   └── SYSTEM_OVERVIEW.md
├── migrations/                     # Alembic миграции БД
│   └── versions/
├── reflebot/                       # Основной пакет
│   ├── apps/                       # Бизнес-модули
│   │   ├── files/                  # Модуль работы с файлами
│   │   │   ├── models.py           # Модель File
│   │   │   ├── schemas.py          # Схемы файлов
│   │   │   ├── repositories/       # FileRepository
│   │   │   ├── services/           # FileService и связанные сервисы
│   │   │   └── depends.py          # DI для файлов
│   │   └── reflections/            # Модуль рефлексий
│   │       ├── models.py           # Все модели (Admin, Student, Course, etc.)
│   │       ├── schemas.py          # Pydantic схемы
│   │       ├── repositories/       # Репозитории для каждой модели
│   │       ├── services/           # Бизнес-логика
│   │       ├── use_cases/          # Use cases
│   │       ├── routers/            # HTTP эндпоинты Telegram workflow
│   │       │   ├── auth.py
│   │       │   └── actions.py
│   │       ├── telegram/           # Telegram UI компоненты
│   │       │   ├── messages.py     # Все сообщения
│   │       │   └── buttons.py      # Генерация кнопок
│   │       ├── parsers/            # Парсеры файлов
│   │       │   ├── base.py
│   │       │   └── course_excel.py
│   │       ├── router.py           # Главный роутер модуля
│   │       ├── depends.py          # DI конфигурация
│   │       ├── exceptions.py       # Доменные исключения
│   │       └── enums.py            # Перечисления
│   ├── core/                       # Общая инфраструктура
│   │   ├── adapters/               # Базовые HTTP клиенты
│   │   ├── repositories/           # BaseRepository
│   │   ├── clients/                # S3Client, Redis
│   │   ├── utils/                  # Утилиты
│   │   ├── db.py                   # Настройка БД
│   │   ├── models.py               # Базовые миксины
│   │   ├── schemas.py              # Базовые схемы
│   │   └── use_cases.py            # Базовый протокол use case
│   ├── main.py                     # Entry point
│   ├── bootstrap.py                # Фабрика приложения
│   ├── settings.py                 # Конфигурация
│   ├── middleware.py               # HTTP middleware
│   ├── exceptions.py               # Глобальные обработчики
│   └── router.py                   # Агрегация роутеров
├── scripts/                        # Утилиты
│   └── create_admin.py             # Создание первого админа
├── .env                            # Переменные окружения
├── pyproject.toml                  # Зависимости (UV)
├── alembic.ini                     # Конфигурация Alembic
├── AGENTS.md                       # Руководство для AI агентов
├── ARCHITECTURE.md                 # Архитектурная документация
└── API.md                          # API документация
```
