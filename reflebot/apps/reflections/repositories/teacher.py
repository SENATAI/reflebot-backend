"""
Репозиторий для работы с преподавателями.
"""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..models import Teacher
from ..schemas import TeacherCreateSchema, TeacherReadSchema, TeacherUpdateSchema


class TeacherRepositoryProtocol(
    BaseRepositoryProtocol[Teacher, TeacherReadSchema, TeacherCreateSchema, TeacherUpdateSchema]
):
    """Протокол репозитория преподавателей."""
    
    async def get_by_telegram_username(self, telegram_username: str) -> TeacherReadSchema | None:
        """Получить преподавателя по никнейму в Telegram."""
        ...
    
    async def update_telegram_id(
        self, telegram_username: str, telegram_id: int
    ) -> TeacherReadSchema:
        """Обновить telegram_id преподавателя по никнейму."""
        ...

    async def get_by_telegram_id(self, telegram_id: int) -> TeacherReadSchema | None:
        """Получить преподавателя по telegram_id."""
        ...
    
    async def get_or_create_by_name(self, full_name: str) -> TeacherReadSchema:
        """Получить или создать преподавателя по ФИО."""
        ...


class TeacherRepository(
    BaseRepositoryImpl[Teacher, TeacherReadSchema, TeacherCreateSchema, TeacherUpdateSchema],
    TeacherRepositoryProtocol,
):
    """Репозиторий для работы с преподавателями."""
    
    async def get_by_telegram_username(self, telegram_username: str) -> TeacherReadSchema | None:
        """Получить преподавателя по никнейму в Telegram."""
        async with self.session as s:
            stmt = sa.select(self.model_type).where(
                self.model_type.telegram_username == telegram_username
            )
            result = (await s.execute(stmt)).scalar_one_or_none()
            if not result:
                return None
            return self.read_schema_type.model_validate(result, from_attributes=True)
    
    async def update_telegram_id(
        self, telegram_username: str, telegram_id: int
    ) -> TeacherReadSchema:
        """Обновить telegram_id преподавателя по никнейму."""
        async with self.session as s, s.begin():
            stmt = (
                sa.update(self.model_type)
                .where(self.model_type.telegram_username == telegram_username)
                .values(telegram_id=telegram_id)
                .returning(self.model_type)
            )
            result = (await s.execute(stmt)).scalar_one_or_none()
            if not result:
                raise ModelFieldNotFoundException(
                    self.model_type, "telegram_username", telegram_username
                )
            return self.read_schema_type.model_validate(result, from_attributes=True)

    async def get_by_telegram_id(self, telegram_id: int) -> TeacherReadSchema | None:
        """Получить преподавателя по telegram_id."""
        async with self.session as s:
            stmt = sa.select(self.model_type).where(self.model_type.telegram_id == telegram_id)
            result = (await s.execute(stmt)).scalar_one_or_none()
            if not result:
                return None
            return self.read_schema_type.model_validate(result, from_attributes=True)
    
    async def get_or_create_by_name(self, full_name: str) -> TeacherReadSchema:
        """
        Получить или создать преподавателя по ФИО.
        
        Если преподаватель с таким ФИО существует, возвращает его.
        Иначе создаёт нового с username из ФИО.
        """
        async with self.session as s:
            # Пытаемся найти существующего
            stmt = sa.select(self.model_type).where(
                self.model_type.full_name == full_name
            )
            result = (await s.execute(stmt)).scalar_one_or_none()
            
            if result:
                return self.read_schema_type.model_validate(result, from_attributes=True)
        
        # Создаём нового
        # Генерируем username из ФИО (например: "Иванов Иван" -> "ivanov_ivan")
        username = full_name.lower().replace(' ', '_')
        
        teacher_data = TeacherCreateSchema(
            full_name=full_name,
            telegram_username=username,
            is_active=True,
        )
        
        return await self.create(teacher_data)
