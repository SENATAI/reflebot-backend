"""
Репозиторий для отслеживаемых Telegram-сообщений.
"""

import uuid
from datetime import datetime
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..models import LectionSession, TelegramTrackedMessage
from ..schemas import (
    TelegramTrackedMessageCreateSchema,
    TelegramTrackedMessageReadSchema,
)


class TelegramTrackedMessageRepositoryProtocol(Protocol):
    """Протокол репозитория отслеживаемых Telegram-сообщений."""

    async def upsert(
        self,
        data: TelegramTrackedMessageCreateSchema,
    ) -> TelegramTrackedMessageReadSchema:
        """Создать или обновить отслеживаемое сообщение."""
        ...

    async def get_deadline_update_batch(
        self,
        limit: int,
        deadline_before: datetime,
        kind: str,
    ) -> list[TelegramTrackedMessageReadSchema]:
        """Получить batch сообщений, которые нужно обновить после дедлайна."""
        ...

    async def mark_deadline_message_updated(
        self,
        tracked_message_id: uuid.UUID,
        updated_at: datetime,
    ) -> TelegramTrackedMessageReadSchema:
        """Отметить, что update-команда после дедлайна уже отправлена."""
        ...


class TelegramTrackedMessageRepository(TelegramTrackedMessageRepositoryProtocol):
    """Репозиторий отслеживаемых Telegram-сообщений."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.model_type = TelegramTrackedMessage
        self.read_schema_type = TelegramTrackedMessageReadSchema

    async def upsert(
        self,
        data: TelegramTrackedMessageCreateSchema,
    ) -> TelegramTrackedMessageReadSchema:
        """Создать или обновить отслеживаемое сообщение по delivery+kind."""
        payload = data.model_dump(exclude_none=True)
        async with self.session as s, s.begin():
            stmt = (
                insert(self.model_type)
                .values(**payload)
                .on_conflict_do_update(
                    constraint="uq_telegram_tracked_messages_delivery_kind",
                    set_={
                        "telegram_id": payload["telegram_id"],
                        "telegram_message_id": payload["telegram_message_id"],
                        "student_id": payload["student_id"],
                        "lection_session_id": payload["lection_session_id"],
                        "deadline_message_updated_at": payload.get("deadline_message_updated_at"),
                    },
                )
                .returning(self.model_type)
            )
            model = (await s.execute(stmt)).scalar_one()
            return self.read_schema_type.model_validate(model, from_attributes=True)

    async def get_deadline_update_batch(
        self,
        limit: int,
        deadline_before: datetime,
        kind: str,
    ) -> list[TelegramTrackedMessageReadSchema]:
        """Получить batch активных trackable-сообщений после дедлайна."""
        async with self.session as s:
            stmt = (
                sa.select(self.model_type)
                .join(LectionSession, LectionSession.id == self.model_type.lection_session_id)
                .where(
                    self.model_type.kind == kind,
                    self.model_type.deadline_message_updated_at.is_(None),
                    LectionSession.deadline <= deadline_before,
                )
                .order_by(self.model_type.created_at.asc())
                .limit(limit)
            )
            models = (await s.execute(stmt)).scalars().all()
            return [self.read_schema_type.model_validate(model, from_attributes=True) for model in models]

    async def mark_deadline_message_updated(
        self,
        tracked_message_id: uuid.UUID,
        updated_at: datetime,
    ) -> TelegramTrackedMessageReadSchema:
        """Отметить, что update-команда по trackable-сообщению уже отправлена."""
        async with self.session as s, s.begin():
            stmt = (
                sa.update(self.model_type)
                .where(self.model_type.id == tracked_message_id)
                .values(deadline_message_updated_at=updated_at)
                .returning(self.model_type)
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                raise ModelFieldNotFoundException(self.model_type, "id", tracked_message_id)
            return self.read_schema_type.model_validate(model, from_attributes=True)
