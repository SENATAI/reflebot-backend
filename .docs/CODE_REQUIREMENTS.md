# Требования к написанию кода

Этот документ описывает обязательные требования и best practices для написания кода в проекте Reflebot.

---

## Архитектурные требования

### 1. Обязательная цепочка вызовов: Use Case → Service → Repository

**КРИТИЧЕСКИ ВАЖНО:** Всегда следуйте строгой иерархии слоёв Clean Architecture.

```python
# ❌ НЕПРАВИЛЬНО - роутер напрямую вызывает repository
@router.post("/admins/")
async def create_admin(data: AdminCreateSchema, repo: AdminRepositoryDep):
    return await repo.create(data)

# ❌ НЕПРАВИЛЬНО - use case напрямую вызывает repository
class CreateAdminUseCase:
    def __init__(self, repository: AdminRepositoryProtocol):
        self.repository = repository
    
    async def __call__(self, data: AdminCreateSchema):
        return await self.repository.create(data)

# ✅ ПРАВИЛЬНО - полная цепочка Router → Use Case → Service → Repository
@router.post("/admins/")
async def create_admin(data: AdminCreateSchema, use_case: CreateAdminUseCaseDep):
    return await use_case(data)

class CreateAdminUseCase:
    def __init__(self, admin_service: AdminServiceProtocol):
        self.admin_service = admin_service
    
    async def __call__(self, data: AdminCreateSchema):
        return await self.admin_service.create_admin(data)

class AdminService:
    def __init__(self, repository: AdminRepositoryProtocol):
        self.repository = repository
    
    async def create_admin(self, data: AdminCreateSchema):
        # Бизнес-логика и валидация
        existing = await self.repository.get_by_telegram_username(data.telegram_username)
        if existing:
            raise ModelAlreadyExistsError(Admin, "telegram_username")
        
        return await self.repository.create(data)
```

**Почему это важно:**
- Use Case координирует несколько сервисов
- Service содержит бизнес-логику и валидацию
- Repository отвечает только за работу с БД
- Легко тестировать каждый слой отдельно
- Легко переиспользовать сервисы в разных use cases

---

## Авторизация и права доступа

### 2. Обязательная проверка прав доступа

**КРИТИЧЕСКИ ВАЖНО:** Всегда проверяйте права доступа пользователя на основе его роли.

```python
# ✅ ПРАВИЛЬНО - проверка прав администратора через dependency
from fastapi import Header

async def get_current_admin(
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
    admin_service: AdminServiceProtocol = Depends(get_admin_service)
) -> AdminReadSchema:
    """Получить текущего администратора по telegram_id из заголовка."""
    admin = await admin_service.get_by_telegram_id(x_telegram_id)
    if not admin:
        raise PermissionDeniedError("Только администраторы могут выполнить это действие")
    if not admin.is_active:
        raise PermissionDeniedError("Администратор неактивен")
    return admin

# Использование в роутере
@router.post("/admins/", response_model=AdminReadSchema)
async def create_admin(
    data: AdminCreateSchema,
    use_case: CreateAdminUseCaseDep,
    current_admin: Annotated[AdminReadSchema, Depends(get_current_admin)]
):
    return await use_case(data, current_admin)
```

**Правила проверки прав:**
- Всегда получайте `telegram_id` из заголовка `X-Telegram-Id`
- Проверяйте роль пользователя (admin, teacher, student)
- Проверяйте статус `is_active`
- Используйте dependency injection для проверки прав
- Выбрасывайте `PermissionDeniedError` при отсутствии прав

**Примеры проверок для разных ролей:**

```python
# Проверка прав преподавателя
async def get_current_teacher(
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
    teacher_service: TeacherServiceProtocol = Depends(get_teacher_service)
) -> TeacherReadSchema:
    teacher = await teacher_service.get_by_telegram_id(x_telegram_id)
    if not teacher or not teacher.is_active:
        raise PermissionDeniedError("Только активные преподаватели могут выполнить это действие")
    return teacher

# Проверка прав студента
async def get_current_student(
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
    student_service: StudentServiceProtocol = Depends(get_student_service)
) -> StudentReadSchema:
    student = await student_service.get_by_telegram_id(x_telegram_id)
    if not student or not student.is_active:
        raise PermissionDeniedError("Только активные студенты могут выполнить это действие")
    return student

# Проверка владения ресурсом
async def check_reflection_ownership(
    reflection_id: uuid.UUID,
    current_student: StudentReadSchema,
    reflection_service: ReflectionServiceProtocol
):
    reflection = await reflection_service.get_by_id(reflection_id)
    if reflection.student_id != current_student.id:
        raise PermissionDeniedError("Вы можете редактировать только свои рефлексии")
```

---

## Telegram UI компоненты

### 3. Централизация сообщений и кнопок

**КРИТИЧЕСКИ ВАЖНО:** Все сообщения и кнопки должны быть в отдельных файлах для удобного редактирования.

#### Сообщения (`telegram/messages.py`)

```python
# ✅ ПРАВИЛЬНО - все сообщения в одном файле
class TelegramMessages:
    @staticmethod
    def get_login_message(full_name: str, is_admin: bool, is_teacher: bool, is_student: bool) -> str:
        roles = []
        if is_admin:
            roles.append("Администратор")
        if is_teacher:
            roles.append("Преподаватель")
        if is_student:
            roles.append("Студент")
        
        roles_text = ", ".join(roles)
        return f"✅ Добро пожаловать, {full_name}!\n\nВаши роли: {roles_text}"
    
    @staticmethod
    def get_create_admin_request_fullname() -> str:
        return "👤 Введите ФИО администратора:"
    
    @staticmethod
    def get_create_admin_request_username() -> str:
        return "📝 Введите никнейм в Telegram (без @):"
    
    @staticmethod
    def get_admin_created_success(full_name: str) -> str:
        return f"✅ Администратор {full_name} успешно создан!"

# ❌ НЕПРАВИЛЬНО - хардкод сообщений в роутерах
@router.post("/actions/button/{action}")
async def handle_button(action: str):
    return ActionResponseSchema(
        message="👤 Введите ФИО администратора:",  # ❌ Хардкод!
        awaiting_input=True
    )
```

#### Кнопки (`telegram/buttons.py`)

```python
# ✅ ПРАВИЛЬНО - все кнопки и их actions в одном файле
class TelegramButtons:
    # Константы для actions
    ADMIN_CREATE_ADMIN = "admin_create_admin"
    ADMIN_CREATE_COURSE = "admin_create_course"
    TEACHER_VIEW_COURSES = "teacher_view_courses"
    STUDENT_SUBMIT_REFLECTION = "student_submit_reflection"
    
    @staticmethod
    def get_login_buttons(is_admin: bool, is_teacher: bool, is_student: bool) -> list[TelegramButtonSchema]:
        buttons = []
        
        if is_admin:
            buttons.extend([
                TelegramButtonSchema(text="➕ Создать администратора", action=TelegramButtons.ADMIN_CREATE_ADMIN),
                TelegramButtonSchema(text="📚 Создать курс", action=TelegramButtons.ADMIN_CREATE_COURSE),
            ])
        
        if is_teacher:
            buttons.append(
                TelegramButtonSchema(text="📖 Мои курсы", action=TelegramButtons.TEACHER_VIEW_COURSES)
            )
        
        if is_student:
            buttons.append(
                TelegramButtonSchema(text="✍️ Отправить рефлексию", action=TelegramButtons.STUDENT_SUBMIT_REFLECTION)
            )
        
        return buttons

# ❌ НЕПРАВИЛЬНО - создание кнопок в роутере
@router.post("/auth/{telegram_username}/login")
async def login(telegram_username: str):
    buttons = [
        {"text": "➕ Создать администратора", "action": "admin_create_admin"}  # ❌ Хардкод!
    ]
```

**Преимущества централизации:**
- Легко изменить текст всех сообщений в одном месте
- Легко добавить поддержку нескольких языков
- Легко найти все сообщения и кнопки
- Избегаем дублирования текстов
- Единый стиль оформления

---

## Асинхронность

### 4. Все операции должны быть асинхронными

**КРИТИЧЕСКИ ВАЖНО:** Все операции с БД, внешними API и I/O должны быть асинхронными.

```python
# ✅ ПРАВИЛЬНО - асинхронные методы
class AdminService:
    async def create_admin(self, data: AdminCreateSchema) -> AdminReadSchema:
        existing = await self.repository.get_by_telegram_username(data.telegram_username)
        if existing:
            raise ModelAlreadyExistsError(Admin, "telegram_username")
        return await self.repository.create(data)
    
    async def get_by_telegram_id(self, telegram_id: int) -> AdminReadSchema | None:
        return await self.repository.get_by_telegram_id(telegram_id)

# ✅ ПРАВИЛЬНО - асинхронные роутеры
@router.post("/admins/")
async def create_admin(data: AdminCreateSchema, use_case: CreateAdminUseCaseDep):
    return await use_case(data)

# ❌ НЕПРАВИЛЬНО - синхронные методы
class AdminService:
    def create_admin(self, data: AdminCreateSchema) -> AdminReadSchema:  # ❌ Не async!
        existing = self.repository.get_by_telegram_username(data.telegram_username)  # ❌ Нет await!
        return self.repository.create(data)
```

**Правила асинхронности:**
- Все методы сервисов должны быть `async`
- Все методы репозиториев должны быть `async`
- Все роутеры должны быть `async`
- Всегда используйте `await` для асинхронных вызовов
- Используйте `async with` для контекстных менеджеров

---

## Импорты

### 5. Порядок и расположение импортов

**КРИТИЧЕСКИ ВАЖНО:** Импорты всегда должны быть в самом начале файла в строгом порядке.

```python
# ✅ ПРАВИЛЬНО - импорты в начале файла в правильном порядке

# 1. Стандартная библиотека Python
import uuid
import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Protocol
from typing_extensions import Self

# 2. Сторонние пакеты (FastAPI, SQLAlchemy, Pydantic и т.д.)
from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

# 3. Локальные импорты из core
from reflebot.core.db import Base, get_async_session
from reflebot.core.models import TimestampMixin
from reflebot.core.schemas import CreateBaseModel, UpdateBaseModel
from reflebot.core.utils.exceptions import ModelNotFoundException, PermissionDeniedError

# 4. Локальные импорты из текущего модуля
from ..models import Admin, Student, Teacher
from ..schemas import AdminCreateSchema, AdminReadSchema
from ..repositories.admin import AdminRepositoryProtocol
from .context import ContextServiceProtocol

# ❌ НЕПРАВИЛЬНО - импорты в середине файла
class AdminService:
    def __init__(self, repository):
        self.repository = repository

from ..models import Admin  # ❌ Импорт не в начале файла!

# ❌ НЕПРАВИЛЬНО - неправильный порядок импортов
from ..models import Admin  # ❌ Локальные импорты должны быть после сторонних!
from fastapi import APIRouter
import uuid
```

**Правила импортов:**
1. Импорты всегда в начале файла (после docstring модуля)
2. Порядок: стандартная библиотека → сторонние пакеты → локальные импорты
3. Пустая строка между группами импортов
4. Используйте абсолютные импорты для локальных пакетов
5. Один импорт на строку (кроме логически связанных)

---

## Оптимизация запросов к БД

### 6. Использование bulk-операций вместо циклов

**КРИТИЧЕСКИ ВАЖНО:** Никогда не создавайте записи в БД в цикле. Используйте bulk-операции.

#### Создание записей

```python
# ❌ НЕПРАВИЛЬНО - создание в цикле (N запросов к БД)
async def create_students(students_data: list[StudentCreateSchema]):
    created_students = []
    for student_data in students_data:
        student = await student_repository.create(student_data)  # ❌ N запросов!
        created_students.append(student)
    return created_students

# ✅ ПРАВИЛЬНО - bulk_create (1 запрос к БД)
async def create_students(students_data: list[StudentCreateSchema]):
    return await student_repository.bulk_create(students_data)
```

#### Получение записей

```python
# ❌ НЕПРАВИЛЬНО - получение в цикле (N запросов к БД)
async def get_students(student_ids: list[uuid.UUID]):
    students = []
    for student_id in student_ids:
        student = await student_repository.get(student_id)  # ❌ N запросов!
        students.append(student)
    return students

# ✅ ПРАВИЛЬНО - get_by_ids (1 запрос к БД)
async def get_students(student_ids: list[uuid.UUID]):
    return await student_repository.get_by_ids(student_ids)
```

#### Обновление записей

```python
# ❌ НЕПРАВИЛЬНО - обновление в цикле (N запросов к БД)
async def update_students(updates: list[StudentUpdateSchema]):
    updated_students = []
    for update_data in updates:
        student = await student_repository.update(update_data)  # ❌ N запросов!
        updated_students.append(student)
    return updated_students

# ✅ ПРАВИЛЬНО - bulk_update (1 запрос к БД)
async def update_students(updates: list[StudentUpdateSchema]):
    return await student_repository.bulk_update(updates)
```

#### Удаление записей

```python
# ❌ НЕПРАВИЛЬНО - удаление в цикле (N запросов к БД)
async def delete_students(student_ids: list[uuid.UUID]):
    for student_id in student_ids:
        await student_repository.delete(student_id)  # ❌ N запросов!

# ✅ ПРАВИЛЬНО - bulk_delete или delete с IN (1 запрос к БД)
async def delete_students(student_ids: list[uuid.UUID]):
    async with self.session as s, s.begin():
        stmt = delete(Student).where(Student.id.in_(student_ids))
        await s.execute(stmt)
```

**Доступные bulk-методы в BaseRepositoryImpl:**
- `bulk_create(schemas: list[CreateSchema])` - создание нескольких записей
- `bulk_update(schemas: list[UpdateSchema])` - обновление нескольких записей
- `get_by_ids(ids: list[UUID])` - получение нескольких записей по ID

**Почему это важно:**
- Производительность: 1 запрос вместо N запросов
- Меньше нагрузка на БД
- Быстрее выполнение операций
- Меньше сетевых round-trips

---

## Примеры правильного кода

### Пример 1: Создание курса с лекциями

```python
# ✅ ПРАВИЛЬНО - использование bulk_create
class CourseService:
    async def create_course_with_lections(
        self,
        course_name: str,
        lections_data: list[dict]
    ) -> CourseSessionReadSchema:
        # 1. Создаём курс
        course = await self.course_repository.create(
            CourseSessionCreateSchema(
                name=course_name,
                started_at=lections_data[0]["started_at"],
                ended_at=lections_data[-1]["ended_at"]
            )
        )
        
        # 2. Подготавливаем данные для bulk_create
        lection_schemas = [
            LectionSessionCreateSchema(
                course_session_id=course.id,
                topic=lection["topic"],
                started_at=lection["started_at"],
                ended_at=lection["ended_at"]
            )
            for lection in lections_data
        ]
        
        # 3. Создаём все лекции одним запросом
        await self.lection_repository.bulk_create(lection_schemas)
        
        return course
```

### Пример 2: Проверка прав и создание администратора

```python
# ✅ ПРАВИЛЬНО - полная цепочка с проверкой прав
@router.post("/admins/", response_model=AdminReadSchema, status_code=status.HTTP_201_CREATED)
async def create_admin(
    data: AdminCreateSchema,
    use_case: CreateAdminUseCaseDep,
    current_admin: CurrentAdminDep  # Проверка прав через dependency
) -> AdminReadSchema:
    return await use_case(data, current_admin)

class CreateAdminUseCase:
    def __init__(self, admin_service: AdminServiceProtocol):
        self.admin_service = admin_service
    
    async def __call__(
        self,
        data: AdminCreateSchema,
        current_admin: AdminReadSchema
    ) -> AdminReadSchema:
        # Use case координирует вызов сервиса
        return await self.admin_service.create_admin(data)

class AdminService:
    def __init__(self, repository: AdminRepositoryProtocol):
        self.repository = repository
    
    async def create_admin(self, data: AdminCreateSchema) -> AdminReadSchema:
        # Бизнес-логика: проверка на дубликат
        existing = await self.repository.get_by_telegram_username(data.telegram_username)
        if existing:
            raise ModelAlreadyExistsError(Admin, "telegram_username")
        
        # Создание через repository
        return await self.repository.create(data)
```

### Пример 3: Многошаговый диалог с централизованными сообщениями

```python
# ✅ ПРАВИЛЬНО - использование TelegramMessages
@router.post("/actions/button/{action}")
async def handle_button_click(
    action: str,
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
    context_service: ContextServiceDep = Depends(get_context_service),
    current_admin: CurrentAdminDep = Depends(get_current_admin)
) -> ActionResponseSchema:
    if action == TelegramButtons.ADMIN_CREATE_ADMIN:
        # Устанавливаем контекст
        await context_service.set_context(
            x_telegram_id,
            action="create_admin",
            step="awaiting_fullname"
        )
        
        # Используем централизованное сообщение
        return ActionResponseSchema(
            message=TelegramMessages.get_create_admin_request_fullname(),
            parse_mode="HTML",
            buttons=[],
            awaiting_input=True
        )
```

---

## Чеклист перед коммитом

Перед коммитом кода убедитесь, что:

- [ ] Используется полная цепочка Use Case → Service → Repository
- [ ] Проверены права доступа через `X-Telegram-Id` заголовок
- [ ] Все сообщения вынесены в `telegram/messages.py`
- [ ] Все кнопки вынесены в `telegram/buttons.py`
- [ ] Все методы асинхронные (`async`/`await`)
- [ ] Импорты в начале файла в правильном порядке
- [ ] Используются bulk-операции вместо циклов с запросами к БД
- [ ] Все ID используют UUID
- [ ] Используются доменные исключения с `error_code`
- [ ] Добавлены docstrings на русском языке
- [ ] Код следует Clean Architecture принципам

---

## Дополнительные ресурсы

- [AGENTS.md](../AGENTS.md) - Полное руководство по стилю кода
- [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) - Обзор архитектуры системы
- [ARCHITECTURE.md](../ARCHITECTURE.md) - Детальная архитектурная документация
- [API.md](../API.md) - Документация API эндпоинтов
