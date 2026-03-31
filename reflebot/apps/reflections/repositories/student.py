"""
Репозиторий для работы со студентами.
"""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..models import Student
from ..schemas import StudentCreateSchema, StudentReadSchema, StudentUpdateSchema


class StudentRepositoryProtocol(
    BaseRepositoryProtocol[Student, StudentReadSchema, StudentCreateSchema, StudentUpdateSchema]
):
    """Протокол репозитория студентов."""
    
    async def get_by_telegram_username(self, telegram_username: str) -> StudentReadSchema | None:
        """Получить студента по никнейму в Telegram."""
        ...
    
    async def update_telegram_id(
        self, telegram_username: str, telegram_id: int
    ) -> StudentReadSchema:
        """Обновить telegram_id студента по никнейму."""
        ...

    async def get_by_telegram_id(self, telegram_id: int) -> StudentReadSchema | None:
        """Получить студента по telegram_id."""
        ...


class StudentRepository(
    BaseRepositoryImpl[Student, StudentReadSchema, StudentCreateSchema, StudentUpdateSchema],
    StudentRepositoryProtocol,
):
    """Репозиторий для работы со студентами."""
    
    async def get_by_telegram_username(self, telegram_username: str) -> StudentReadSchema | None:
        """Получить студента по никнейму в Telegram."""
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
    ) -> StudentReadSchema:
        """Обновить telegram_id студента по никнейму."""
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

    async def get_by_telegram_id(self, telegram_id: int) -> StudentReadSchema | None:
        """Получить студента по telegram_id."""
        async with self.session as s:
            stmt = sa.select(self.model_type).where(self.model_type.telegram_id == telegram_id)
            result = (await s.execute(stmt)).scalar_one_or_none()
            if not result:
                return None
            return self.read_schema_type.model_validate(result, from_attributes=True)
