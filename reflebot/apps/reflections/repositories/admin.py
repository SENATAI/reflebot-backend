"""
Репозиторий для работы с администраторами.
"""

from typing import Protocol
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Self

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..models import Admin
from ..schemas import AdminCreateSchema, AdminReadSchema, AdminUpdateSchema


class AdminRepositoryProtocol(
    BaseRepositoryProtocol[Admin, AdminReadSchema, AdminCreateSchema, AdminUpdateSchema]
):
    """Протокол репозитория администраторов."""
    
    async def get_by_telegram_username(self, telegram_username: str) -> AdminReadSchema:
        """Получить администратора по никнейму в Telegram."""
        ...
    
    async def get_by_telegram_id(self, telegram_id: int) -> AdminReadSchema:
        """Получить администратора по ID в Telegram."""
        ...
    
    async def update_telegram_id(
        self, telegram_username: str, telegram_id: int
    ) -> AdminReadSchema:
        """Обновить telegram_id администратора по никнейму."""
        ...


class AdminRepository(
    BaseRepositoryImpl[Admin, AdminReadSchema, AdminCreateSchema, AdminUpdateSchema],
    AdminRepositoryProtocol,
):
    """Репозиторий для работы с администраторами."""

    async def _get_preferred_model_by_telegram_username(
        self,
        session: AsyncSession,
        telegram_username: str,
    ) -> Admin | None:
        """Получить предпочтительную запись по username при наличии дублей."""
        stmt = (
            sa.select(self.model_type)
            .where(self.model_type.telegram_username == telegram_username)
            .order_by(
                sa.case(
                    (self.model_type.telegram_id.is_not(None), 0),
                    else_=1,
                ),
                self.model_type.created_at.asc(),
                self.model_type.id.asc(),
            )
        )
        return (await session.execute(stmt)).scalars().first()
    
    async def get_by_telegram_username(self, telegram_username: str) -> AdminReadSchema:
        """Получить администратора по никнейму в Telegram."""
        async with self.session as s:
            result = await self._get_preferred_model_by_telegram_username(s, telegram_username)
            if not result:
                raise ModelFieldNotFoundException(
                    self.model_type, "telegram_username", telegram_username
                )
            return self.read_schema_type.model_validate(result, from_attributes=True)
    
    async def get_by_telegram_id(self, telegram_id: int) -> AdminReadSchema:
        """Получить администратора по ID в Telegram."""
        async with self.session as s:
            stmt = sa.select(self.model_type).where(
                self.model_type.telegram_id == telegram_id
            )
            result = (await s.execute(stmt)).scalar_one_or_none()
            if not result:
                raise ModelFieldNotFoundException(
                    self.model_type, "telegram_id", telegram_id
                )
            return self.read_schema_type.model_validate(result, from_attributes=True)
    
    async def update_telegram_id(
        self, telegram_username: str, telegram_id: int
    ) -> AdminReadSchema:
        """Обновить telegram_id администратора по никнейму."""
        async with self.session as s, s.begin():
            result = await self._get_preferred_model_by_telegram_username(s, telegram_username)
            if not result:
                raise ModelFieldNotFoundException(
                    self.model_type, "telegram_username", telegram_username
                )
            result.telegram_id = telegram_id
            await s.flush()
            return self.read_schema_type.model_validate(result, from_attributes=True)
