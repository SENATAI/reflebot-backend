# AGENTS.md – Reflebot Backend Service

## Обзор

Этот документ предоставляет AI-агентам необходимые команды и руководство по стилю кода для эффективной работы с бэкендом **Reflebot** — системой сбора данных рефлексии студентов с занятий и просмотра для учителей. Проект построен на FastAPI с использованием многослойной Clean Architecture.

---

## Команды сборки / линтинга / тестирования

### Запуск приложения

```bash
# Development-сервер с hot-reload
uv run granian reflebot.main:app --interface asgi --host 0.0.0.0 --port 8080 --reload

# Быстрый запуск через скрипт
./run.sh
```

### Управление зависимостями (uv)

```bash
# Установка всех зависимостей
uv sync

# Добавление production-зависимости
uv add <package-name>

# Добавление dev-зависимости
uv add --dev <package-name>

# Выполнение команды внутри виртуального окружения
uv run <command>
```

### Миграции базы данных (Alembic)

```bash
# Автогенерация новой миграции после изменения моделей
uv run alembic revision --autogenerate -m "<краткое описание>"

# Применение всех pending-миграций
uv run alembic upgrade head

# Откат последней миграции
uv run alembic downgrade -1

# Просмотр истории миграций
uv run alembic history
```

### Тестирование (если настроено)

```bash
# Запуск всех тестов
uv run pytest

# Запуск конкретного файла
uv run pytest tests/<path>/test_file.py

# Запуск конкретной функции
uv run pytest tests/<path>/test_file.py::test_function_name -v

# С покрытием кода
uv run pytest --cov=reflebot
```

---

## Руководство по стилю кода

### 1. Импорты

* **Порядок** – стандартная библиотека → сторонние пакеты → локальные импорты
* **Один импорт на строку**, если не группируются логически
* Используйте абсолютные импорты для локальных пакетов

```python
# Стандартная библиотека
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

# Сторонние пакеты
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

# Локальные импорты (абсолютные)
from reflebot.core.db import Base
from reflebot.settings import settings
from reflebot.core.schemas import CreateBaseModel, UpdateBaseModel
```

### 2. Форматирование

* **Максимальная длина строки:** 100 символов
* **Trailing commas** в многострочных коллекциях
* **Пустые строки** – две между определениями верхнего уровня, одна между методами класса
* **Перенос строки в конце файла** – обязателен

### 3. Типизация

* Используйте современный синтаксис Python 3.13+: `list[int]`, `dict[str, Any]`, `str | None`
* Используйте `Annotated` для FastAPI-зависимостей:

```python
Session = Annotated[AsyncSession, Depends(get_async_session)]
```

* Используйте `Mapped[T]` для SQLAlchemy-колонок
* Используйте `Self` из `typing_extensions` для fluent API
* **Все ID используют UUID** вместо int для безопасности и распределённых систем:

```python
import uuid
from sqlalchemy.dialects.postgresql import UUID

class MyModel(Base):
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

### 4. Соглашения об именовании

| Элемент | Соглашение |
|---------|------------|
| Файлы | `snake_case.py` |
| Классы | `PascalCase` |
| Функции / Методы | `snake_case` |
| Переменные | `snake_case` |
| Константы | `UPPER_SNAKE_CASE` |
| Приватные хелперы в `depends.py` | `__get_<name>_repository` (двойное подчеркивание) |
| Pydantic-схемы | `<Entity>BaseSchema`, `<Entity>CreateSchema`, `<Entity>UpdateSchema`, `<Entity>ReadSchema` |
| Протоколы | `<Entity>RepositoryProtocol`, `<Entity>ServiceProtocol` |
| DI-алиасы | `<Entity>Dep` (например, `UserServiceDep`) |

### 5. Pydantic-схемы

* Наследуйтесь от базовых моделей (`CreateBaseModel`, `UpdateBaseModel`)
* Настройте `model_config = ConfigDict(from_attributes=True)` для ORM-совместимости
* Используйте `Field(...)` для валидации

```python
class ReflectionBaseSchema(BaseModel):
    content: str = Field(..., max_length=2000)
    rating: int = Field(..., ge=1, le=5)
    is_anonymous: bool = True

class ReflectionCreateSchema(ReflectionBaseSchema, CreateBaseModel):
    student_id: int
    lesson_id: int

class ReflectionReadSchema(ReflectionBaseSchema):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

### 6. SQLAlchemy-модели

* Наследуйтесь от `Base` и миксинов (например, `TimestampMixin`)
* Используйте `Mapped` с `mapped_column` для колонок
* Явно определяйте `__tablename__`
* **Все ID используют UUID** с автогенерацией

```python
import uuid
from sqlalchemy.dialects.postgresql import UUID
from reflebot.core.db import Base
from reflebot.core.models import TimestampMixin

class Reflection(Base, TimestampMixin):
    __tablename__ = "reflections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    rating: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), sa.ForeignKey("students.id"))
```

### 7. Обработка ошибок

* Все кастомные исключения наследуются от `CoreException`
* Каждое исключение имеет уникальный `error_code`
* Выбрасывайте **доменные** исключения, никогда не используйте generic `HTTPException`
* Регистрируйте обработчики в `reflebot.exceptions`

```python
from reflebot.core.utils.exceptions import ModelNotFoundException, PermissionDeniedError

if not reflection:
    raise ModelNotFoundException(Reflection, reflection_id)
    # Вернёт: {"detail": "...", "error_code": "MODEL_NOT_FOUND"}

if not user.can_view_reflection:
    raise PermissionDeniedError("Недостаточно прав для просмотра рефлексии")
    # Вернёт: {"detail": "...", "error_code": "PERMISSION_DENIED"}
```

**Доступные исключения и их коды:**
- `ModelNotFoundException` → `MODEL_NOT_FOUND` (404)
- `ModelFieldNotFoundException` → `MODEL_FIELD_NOT_FOUND` (404)
- `PermissionDeniedError` → `PERMISSION_DENIED` (403)
- `ModelAlreadyExistsError` → `MODEL_ALREADY_EXISTS` (409)
- `ValidationError` → `VALIDATION_ERROR` (422)
- `SortingFieldNotFoundError` → `SORTING_FIELD_NOT_FOUND` (400)
- `FileNotFound` → `FILE_NOT_FOUND` (404)
- `UnauthorizedError` → `UNAUTHORIZED` (401)
- `InvalidAPIKeyError` → `INVALID_API_KEY` (403)

### 8. Dependency Injection (FastAPI)

* Держите получение репозиториев приватным (двойное подчеркивание)
* Публично экспортируйте фабрики сервисов
* Создавайте аннотированные DI-типы для краткости

```python
from fastapi import Depends
from reflebot.core.db import AsyncSession, get_async_session

# Приватная фабрика репозитория
def __get_reflection_repository(
    session: AsyncSession = Depends(get_async_session)
) -> ReflectionRepositoryProtocol:
    return ReflectionRepository(session)

# Публичная фабрика сервиса
def get_reflection_service(
    repo: ReflectionRepositoryProtocol = Depends(__get_reflection_repository)
) -> ReflectionServiceProtocol:
    return ReflectionService(repo)

# DI-алиас для использования в роутерах
ReflectionServiceDep = Annotated[ReflectionServiceProtocol, Depends(get_reflection_service)]
```

### 9. Асинхронные паттерны

* Все операции с БД **асинхронные**
* Используйте `async with self.session as s:` для одной операции
* Используйте `async with self.session as s, s.begin():` для транзакций

```python
async def create(self, data: ReflectionCreateSchema) -> ReflectionReadSchema:
    async with self.session as s, s.begin():
        stmt = sa.insert(self.model_type).values(**data.model_dump()).returning(self.model_type)
        model = (await s.execute(stmt)).scalar_one()
        return self.read_schema_type.model_validate(model, from_attributes=True)
```

### 10. Docstrings

* **Язык:** Русский (соглашение проекта)
* Краткое описание в одно предложение, затем опциональные детали

```python
class ReflectionService:
    """
    Сервис для управления рефлексиями студентов.
    
    Предоставляет методы создания, обновления и просмотра рефлексий.
    """
    
    async def get_by_lesson(self, lesson_id: int) -> list[ReflectionReadSchema]:
        """Получить все рефлексии для конкретного занятия."""
        return await self.repository.get_by_lesson(lesson_id)
```

### 11. Переменные окружения

* Префикс всех переменных: `REFLEBOT_`
* Вложенная конфигурация использует двойное подчеркивание (`__`)
* Определяются в `reflebot/settings.py` через Pydantic `BaseSettings`
* Никогда не коммитьте реальные секреты; используйте `.env.example` для плейсхолдеров

```bash
# Пример .env
REFLEBOT_DEBUG=true
REFLEBOT_BASE_URL=http://localhost:8080
REFLEBOT_SECRET_KEY=your-secret-key
REFLEBOT_TELEGRAM_SECRET_TOKEN=your-telegram-bot-token

REFLEBOT_DB__HOST=localhost
REFLEBOT_DB__PORT=5432
REFLEBOT_DB__USER=postgres
REFLEBOT_DB__PASSWORD=password
REFLEBOT_DB__NAME=reflebot
REFLEBOT_DB__SCHEME=public

REFLEBOT_CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 12. API Key защита

* Все API запросы требуют заголовок `X-Service-API-Key`
* Значение должно совпадать с `REFLEBOT_TELEGRAM_SECRET_TOKEN`
* Исключения: `/docs`, `/redoc`, `/openapi.json` (документация)
* Middleware проверяет ключ автоматически для всех эндпоинтов

```python
# Пример запроса с API ключом
curl -X POST "http://localhost:8080/api/reflections/auth/username/login" \
  -H "Content-Type: application/json" \
  -H "X-Service-API-Key: your-telegram-bot-token" \
  -d '{"telegram_id": 123456789}'
```

---

## Архитектурные слои

Проект следует Clean Architecture с четким разделением ответственности:

### Структура модуля приложения

```
reflebot/apps/<module_name>/
├── adapters/           # HTTP-клиенты для внешних сервисов
├── events/             # Обработчики событий и publishers
├── parsers/            # Парсеры файлов (наследуются от BaseFileParser)
│   ├── __init__.py
│   ├── base.py         # Абстрактный базовый парсер
│   └── course_excel.py # Парсер Excel файлов курсов
├── repositories/       # Слой доступа к данным
├── routers/            # HTTP-эндпоинты (разделены по функциональности)
│   ├── __init__.py
│   ├── admin.py        # Роутер для администраторов
│   ├── auth.py         # Роутер для аутентификации
│   └── ...             # Другие роутеры
├── services/           # Бизнес-логика
├── use_cases/          # Use cases приложения
├── models.py           # SQLAlchemy-модели
├── schemas.py          # Pydantic-схемы
├── router.py           # Главный роутер (агрегирует роутеры из routers/)
├── depends.py          # Dependency injection
├── exceptions.py       # Доменные исключения
└── enums.py            # Доменные перечисления
```

### Поток данных

```
HTTP Request
    ↓
Router (валидация, аутентификация)
    ↓
Use Case (авторизация, оркестрация)
    ↓
Service (бизнес-логика)
    ↓
Repository (CRUD операции)
    ↓
Database
```

### Ключевые принципы

1. **Dependency Inversion** – зависимости через протоколы, не конкретные реализации
2. **Single Responsibility** – каждый слой имеет одну причину для изменения
3. **Dependency Injection** – все зависимости инжектятся через FastAPI DI
4. **Protocol-based Design** – определяйте интерфейсы (Protocols) перед реализацией

---

## Дополнительные правила

* Агенты **никогда** не должны коммитить файл `.env` или другие секреты
* Все изменения кода должны сопровождаться соответствующими тестами (если применимо)
* Тесты должны проходить перед коммитом
* Используйте `getDiagnostics` для проверки синтаксических и типовых ошибок
* При переименовании символов используйте `semanticRename` для автоматического обновления ссылок
* При перемещении файлов используйте `smartRelocate` для автоматического обновления импортов

---

## Базовые классы и утилиты

### BaseRepositoryImpl

Предоставляет стандартные CRUD-операции:

* `get(id)` – получить по ID
* `get_or_none(id)` – получить по ID или None
* `get_by_ids(ids)` – получить несколько по ID
* `get_all()` – получить все записи
* `paginate(...)` – пагинация с поиском и сортировкой
* `create(schema)` – создать одну запись
* `bulk_create(schemas)` – создать несколько записей
* `update(schema)` – обновить запись
* `bulk_update(schemas)` – обновить несколько записей
* `upsert(schema)` – создать или обновить
* `delete(id)` – удалить по ID

### BaseHttpClientImpl

Базовый HTTP-клиент для взаимодействия с внешними сервисами:

* Автоматическая обработка токенов через `ServiceTokenManager`
* Типобезопасные запросы с `response_model`
* Обработка ошибок с кастомными `error_model`
* Поддержка таймаутов и retry-логики

### Миксины моделей

* `CreationTimeMixin` – добавляет `created_at`
* `TimestampMixin` – добавляет `created_at` и `updated_at`

---

*Этот AGENTS.md файл предоставляет агентам быстрое и практичное руководство, охватывающее все критические аспекты разработки в бэкенде Reflebot.*


---

## Коды ошибок

Все исключения возвращают JSON с полями `detail` и `error_code`:

```json
{
  "detail": "Описание ошибки",
  "error_code": "ERROR_CODE"
}
```

### Таблица кодов ошибок

| Код ошибки | HTTP статус | Класс исключения | Описание |
|-----------|-------------|------------------|----------|
| `MISSING_API_KEY` | 401 | Middleware | Отсутствует заголовок X-Service-API-Key |
| `UNAUTHORIZED` | 401 | `UnauthorizedError` | Требуется аутентификация |
| `INVALID_API_KEY` | 403 | `InvalidAPIKeyError` | Неверный API ключ |
| `PERMISSION_DENIED` | 403 | `PermissionDeniedError` | Недостаточно прав |
| `SORTING_FIELD_NOT_FOUND` | 400 | `SortingFieldNotFoundError` | Поле для сортировки не найдено |
| `MODEL_NOT_FOUND` | 404 | `ModelNotFoundException` | Модель не найдена по ID |
| `MODEL_FIELD_NOT_FOUND` | 404 | `ModelFieldNotFoundException` | Модель не найдена по полю |
| `FILE_NOT_FOUND` | 404 | `FileNotFound` | Файл не найден |
| `MODEL_ALREADY_EXISTS` | 409 | `ModelAlreadyExistsError` | Дубликат уникального поля |
| `VALIDATION_ERROR` | 422 | `ValidationError` | Ошибка валидации данных |

### Примеры использования

```python
# 404 - Модель не найдена
from reflebot.core.utils.exceptions import ModelNotFoundException
raise ModelNotFoundException(User, user_id)
# → {"detail": "Unable to find the User with id 123.", "error_code": "MODEL_NOT_FOUND"}

# 404 - Модель не найдена по полю
from reflebot.core.utils.exceptions import ModelFieldNotFoundException
raise ModelFieldNotFoundException(User, "email", "test@example.com")
# → {"detail": "Unable to find the User with email equal to test@example.com.", "error_code": "MODEL_FIELD_NOT_FOUND"}

# 403 - Недостаточно прав
from reflebot.core.utils.exceptions import PermissionDeniedError
raise PermissionDeniedError("Только администраторы могут выполнить это действие")
# → {"detail": "Только администраторы могут выполнить это действие", "error_code": "PERMISSION_DENIED"}

# 409 - Дубликат
from reflebot.core.utils.exceptions import ModelAlreadyExistsError
raise ModelAlreadyExistsError(User, "email", "Email already registered")
# → {"detail": "Model User with email already exists: Email already registered", "error_code": "MODEL_ALREADY_EXISTS"}

# 422 - Валидация
from reflebot.core.utils.exceptions import ValidationError
raise ValidationError("age", "Age must be greater than 0")
# → {"detail": "Validation error in age: Age must be greater than 0", "error_code": "VALIDATION_ERROR"}
```

---

*Этот AGENTS.md файл предоставляет агентам быстрое и практичное руководство, охватывающее все критические аспекты разработки в бэкенде Reflebot.*


## Организация роутеров

Роутеры разделены по функциональности в папке `routers/`:

```
reflebot/apps/reflections/
├── routers/
│   ├── __init__.py
│   ├── admin.py        # Эндпоинты для администраторов
│   ├── auth.py         # Эндпоинты для аутентификации
│   ├── actions.py      # Обработка кнопок и текстового ввода
│   └── ...             # Другие роутеры
└── router.py           # Главный роутер (агрегирует все)
```

**Пример структуры:**

```python
# routers/admin.py
from fastapi import APIRouter, status
from ..schemas import AdminCreateSchema, AdminReadSchema
from ..depends import CreateAdminUseCaseDep, CurrentAdminDep

router = APIRouter(prefix="/admins", tags=["Admins"])

@router.post("/", response_model=AdminReadSchema, status_code=status.HTTP_201_CREATED)
async def create_admin(
    data: AdminCreateSchema,
    use_case: CreateAdminUseCaseDep,
    current_admin: CurrentAdminDep,
) -> AdminReadSchema:
    return await use_case(data, current_admin)
```

```python
# router.py (главный роутер модуля)
from fastapi import APIRouter
from .routers import admin, auth, actions

router = APIRouter(prefix="/api/reflections", tags=["Reflections"])
router.include_router(admin.router)
router.include_router(auth.router)
router.include_router(actions.router)
```

**Правила:**
- Один роутер = одна функциональная область (admin, auth, students, teachers и т.д.)
- Используйте префиксы и теги для группировки в документации
- Главный `router.py` только агрегирует роутеры, не содержит эндпоинтов


## Система контекста пользователя

Для многошаговых диалогов используется таблица `User` с полем `user_context`:

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"
    
    telegram_id: Mapped[int] = mapped_column(primary_key=True)
    user_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

**Структура user_context:**
```json
{
  "action": "create_admin",
  "step": "awaiting_fullname",
  "data": {
    "fullname": "Иванов Иван Иванович"
  }
}
```

**Workflow:**
1. Пользователь нажимает кнопку → `POST /actions/button/{action}`
2. Бэкенд устанавливает контекст и возвращает инструкцию с `awaiting_input: true`
3. Пользователь вводит текст → `POST /actions/text`
4. Бэкенд читает контекст, обрабатывает ввод, обновляет контекст или завершает действие
5. При завершении контекст очищается и возвращаются обычные кнопки

**Сервисы:**
- `ContextService` - управление контекстом пользователя (get, set, update, clear)
- `UserRepository` - CRUD операции с таблицей users

**Преимущества:**
- Состояние персистентно (переживёт перезапуск бота)
- Бэкенд контролирует весь процесс
- Легко добавлять валидацию на каждом шаге
- Можно делать откат (отмену действия)


## Работа с файлами

Для работы с файлами используется модуль `apps/files` с интеграцией MinIO S3:

**Модель File:**
```python
class File(Base, TimestampMixin):
    __tablename__ = "files"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path: Mapped[str] = mapped_column(sa.String(256), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
```

**Использование в моделях:**
Вместо хранения путей к файлам, храните только `file_id` с foreign key на таблицу `files`:

```python
class LectionSession(Base, TimestampMixin):
    __tablename__ = "lection_sessions"
    
    presentation_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True
    )
    recording_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True
    )
```

**Работа с файлами в сервисах:**
```python
from reflebot.apps.files.depends import FileServiceDep
from fastapi import UploadFile

# Загрузка файла
async def upload_presentation(file: UploadFile, file_service: FileServiceDep):
    result = await file_service.upload_file(file, custom_path="presentations")
    # result.file_id - сохраняем в БД
    # result.url - presigned URL для доступа
    return result.file_id

# Получение URL файла
async def get_presentation_url(file_id: uuid.UUID, file_service: FileServiceDep):
    url = await file_service.get_file_url(file_id, expires_in=3600)
    return url

# Удаление файла
async def delete_presentation(file_id: uuid.UUID, file_service: FileServiceDep):
    success = await file_service.delete_file(file_id)
    return success
```

**Преимущества:**
- Централизованное управление файлами
- Автоматическая генерация presigned URLs
- Метаданные файлов в БД
- Cascade delete при удалении записей


## Парсеры файлов

Парсеры используются для обработки загружаемых файлов (Excel, CSV и т.д.) и инжектятся через DI.

### Структура

```
reflebot/apps/<module>/parsers/
├── __init__.py
├── base.py              # Абстрактный базовый парсер
└── course_excel.py      # Конкретная реализация
```

### Базовый парсер

Все парсеры наследуются от `BaseFileParser` и реализуют метод `parse`:

```python
# parsers/base.py
from abc import ABC, abstractmethod
from typing import BinaryIO, Any

class BaseFileParser(ABC):
    """Базовый абстрактный класс для парсеров файлов."""
    
    @abstractmethod
    def parse(self, file: BinaryIO) -> Any:
        """
        Парсинг файла.
        
        Args:
            file: Бинарный файл для парсинга
        
        Returns:
            Результат парсинга (зависит от конкретного парсера)
        """
        pass
```

### Конкретная реализация

```python
# parsers/course_excel.py
from .base import BaseFileParser
from ..exceptions import ExcelFileError

class CourseExcelParser(BaseFileParser):
    """Парсер Excel файлов с данными курсов."""
    
    def parse(self, file: BinaryIO) -> tuple[str, list[dict]]:
        """Парсинг Excel файла с курсами."""
        try:
            # Логика парсинга
            return course_name, lections_data
        except Exception as e:
            raise ExcelFileError(f"Ошибка парсинга: {str(e)}")
```

### Dependency Injection

Парсеры инжектятся в use cases через DI:

```python
# depends.py
from .parsers.course_excel import CourseExcelParser
from .parsers.base import FileParserProtocol

def get_course_excel_parser() -> FileParserProtocol:
    """Получить парсер Excel файлов курсов."""
    return CourseExcelParser()

def get_create_course_from_excel_use_case(
    course_service: CourseServiceProtocol = Depends(get_course_service),
    parser: FileParserProtocol = Depends(get_course_excel_parser),
) -> CreateCourseFromExcelUseCaseProtocol:
    """Получить use case создания курса из Excel."""
    return CreateCourseFromExcelUseCase(
        course_service=course_service,
        parser=parser,
    )
```

### Use Case с парсером

```python
# use_cases/course.py
class CreateCourseFromExcelUseCase:
    """Use case для создания курса из Excel файла."""
    
    def __init__(
        self,
        course_service: CourseServiceProtocol,
        parser: FileParserProtocol,  # Инжектированный парсер
    ):
        self.course_service = course_service
        self.parser = parser
    
    async def __call__(self, excel_file: BinaryIO, current_admin: AdminReadSchema):
        # Используем инжектированный парсер
        course_name, lections_data = self.parser.parse(excel_file)
        
        # Создаём курс
        return await self.course_service.create_course_with_lections(
            course_name, lections_data
        )
```

### Правила

- Все парсеры наследуются от `BaseFileParser`
- Метод `parse` принимает только `BinaryIO` файл
- Парсеры инжектятся через DI, не создаются напрямую в use cases
- Используйте кастомные исключения для ошибок парсинга
- Один парсер = один тип файла/формат
