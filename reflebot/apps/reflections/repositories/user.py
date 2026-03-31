"""
Репозиторий для работы с пользователями (контекст диалога).
"""

from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from reflebot.core.repositories.base_repository import BaseRepositoryImpl
from ..models import User
from ..schemas import UserReadSchema, UserCreateSchema, UserUpdateSchema


class UserRepositoryProtocol(Protocol):
    """Протокол репозитория пользователей."""
    
    async def get_by_telegram_id(self, telegram_id: int) -> UserReadSchema | None:
        """Получить пользователя по telegram_id."""
        ...
    
    async def upsert_context(self, telegram_id: int, context: dict | None) -> UserReadSchema:
        """Создать или обновить контекст пользователя."""
        ...
    
    async def clear_context(self, telegram_id: int) -> UserReadSchema | None:
        """Очистить контекст пользователя."""
        ...


class UserRepository(
    BaseRepositoryImpl[User, UserReadSchema, UserCreateSchema, UserUpdateSchema],
    UserRepositoryProtocol,
):
    """Репозиторий для работы с пользователями."""
    
    async def get_by_telegram_id(self, telegram_id: int) -> UserReadSchema | None:
        """Получить пользователя по telegram_id."""
        async with self.session as s:
            stmt = sa.select(self.model_type).where(self.model_type.telegram_id == telegram_id)
            result = await s.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model is None:
                return None
            
            return self.read_schema_type.model_validate(model, from_attributes=True)
    
    async def upsert_context(self, telegram_id: int, context: dict | None) -> UserReadSchema:
        """Создать или обновить контекст пользователя."""
        async with self.session as s, s.begin():
            # Проверяем существование
            stmt = sa.select(self.model_type).where(self.model_type.telegram_id == telegram_id)
            result = await s.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Обновляем
                stmt = (
                    sa.update(self.model_type)
                    .where(self.model_type.telegram_id == telegram_id)
                    .values(user_context=context)
                    .returning(self.model_type)
                )
            else:
                # Создаём
                stmt = (
                    sa.insert(self.model_type)
                    .values(telegram_id=telegram_id, user_context=context)
                    .returning(self.model_type)
                )
            
            result = await s.execute(stmt)
            model = result.scalar_one()
            return self.read_schema_type.model_validate(model, from_attributes=True)
    
    async def clear_context(self, telegram_id: int) -> UserReadSchema | None:
        """Очистить контекст пользователя."""
        return await self.upsert_context(telegram_id, None)
