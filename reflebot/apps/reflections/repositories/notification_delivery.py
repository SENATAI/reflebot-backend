"""
Репозиторий для работы с доставками уведомлений.
"""

import uuid
from datetime import datetime
from typing import Protocol

import sqlalchemy as sa

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..enums import NotificationDeliveryStatus, NotificationDeliveryType
from ..models import LectionSession, NotificationDelivery
from ..schemas import (
    NotificationDeliveryCreateSchema,
    NotificationDeliveryReadSchema,
    NotificationDeliveryUpdateSchema,
)


class NotificationDeliveryRepositoryProtocol(
    BaseRepositoryProtocol[
        NotificationDelivery,
        NotificationDeliveryReadSchema,
        NotificationDeliveryCreateSchema,
        NotificationDeliveryUpdateSchema,
    ]
):
    """Протокол репозитория доставок уведомлений."""

    async def get_or_none_by_unique(
        self,
        lection_session_id: uuid.UUID,
        student_id: uuid.UUID,
        notification_type: NotificationDeliveryType,
    ) -> NotificationDeliveryReadSchema | None:
        """Получить доставку по уникальной комбинации."""
        ...

    async def get_pending_batch(self, limit: int) -> list[NotificationDeliveryReadSchema]:
        """Получить batch доставок со статусом pending."""
        ...

    async def get_deadline_update_batch(
        self,
        limit: int,
        deadline_before: datetime,
    ) -> list[NotificationDeliveryReadSchema]:
        """Получить batch sent доставок, требующих обновления prompt после дедлайна."""
        ...

    async def get_retryable_failed_batch(self, limit: int) -> list[NotificationDeliveryReadSchema]:
        """Получить batch доставок со статусом failed."""
        ...

    async def get_retryable_failed_batch_with_policy(
        self,
        limit: int,
        min_updated_at: datetime | None = None,
        max_attempts: int | None = None,
    ) -> list[NotificationDeliveryReadSchema]:
        """Получить batch failed доставок с учетом retry policy."""
        ...

    async def mark_queued(self, delivery_id: uuid.UUID) -> NotificationDeliveryReadSchema:
        """Перевести доставку в queued."""
        ...

    async def mark_sent(
        self,
        delivery_id: uuid.UUID,
        sent_at: datetime,
        telegram_message_id: int | None = None,
    ) -> NotificationDeliveryReadSchema:
        """Перевести доставку в sent."""
        ...

    async def mark_deadline_message_updated(
        self,
        delivery_id: uuid.UUID,
        updated_at: datetime,
    ) -> NotificationDeliveryReadSchema:
        """Отметить, что prompt был обновлён после дедлайна."""
        ...

    async def mark_failed(self, delivery_id: uuid.UUID, error: str) -> NotificationDeliveryReadSchema:
        """Перевести доставку в failed."""
        ...


class NotificationDeliveryRepository(
    BaseRepositoryImpl[
        NotificationDelivery,
        NotificationDeliveryReadSchema,
        NotificationDeliveryCreateSchema,
        NotificationDeliveryUpdateSchema,
    ],
    NotificationDeliveryRepositoryProtocol,
):
    """Репозиторий для работы с доставками уведомлений."""

    async def get_or_none_by_unique(
        self,
        lection_session_id: uuid.UUID,
        student_id: uuid.UUID,
        notification_type: NotificationDeliveryType,
    ) -> NotificationDeliveryReadSchema | None:
        """Получить доставку по уникальной комбинации."""
        async with self.session as s:
            stmt = sa.select(self.model_type).where(
                self.model_type.lection_session_id == lection_session_id,
                self.model_type.student_id == student_id,
                self.model_type.type == notification_type,
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                return None
            return self.read_schema_type.model_validate(model, from_attributes=True)

    async def get_pending_batch(self, limit: int) -> list[NotificationDeliveryReadSchema]:
        """Получить batch доставок со статусом pending."""
        async with self.session as s:
            stmt = (
                sa.select(self.model_type)
                .where(
                    self.model_type.type == NotificationDeliveryType.REFLECTION_PROMPT,
                    self.model_type.status == NotificationDeliveryStatus.PENDING,
                )
                .order_by(self.model_type.scheduled_for.asc(), self.model_type.created_at.asc())
                .limit(limit)
            )
            models = (await s.execute(stmt)).scalars().all()
            return [self.read_schema_type.model_validate(model, from_attributes=True) for model in models]

    async def get_deadline_update_batch(
        self,
        limit: int,
        deadline_before: datetime,
    ) -> list[NotificationDeliveryReadSchema]:
        """Получить batch sent доставок, требующих обновления prompt после дедлайна."""
        async with self.session as s:
            stmt = (
                sa.select(self.model_type)
                .join(LectionSession, LectionSession.id == self.model_type.lection_session_id)
                .where(
                    self.model_type.type == NotificationDeliveryType.REFLECTION_PROMPT,
                    self.model_type.status == NotificationDeliveryStatus.SENT,
                    self.model_type.telegram_message_id.is_not(None),
                    self.model_type.deadline_message_updated_at.is_(None),
                    LectionSession.deadline <= deadline_before,
                )
                .order_by(self.model_type.sent_at.asc().nullsfirst(), self.model_type.created_at.asc())
                .limit(limit)
            )
            models = (await s.execute(stmt)).scalars().all()
            return [self.read_schema_type.model_validate(model, from_attributes=True) for model in models]

    async def get_retryable_failed_batch(self, limit: int) -> list[NotificationDeliveryReadSchema]:
        """Получить batch доставок со статусом failed."""
        return await self.get_retryable_failed_batch_with_policy(limit=limit)

    async def get_retryable_failed_batch_with_policy(
        self,
        limit: int,
        min_updated_at: datetime | None = None,
        max_attempts: int | None = None,
    ) -> list[NotificationDeliveryReadSchema]:
        """Получить batch failed доставок с учетом retry policy."""
        async with self.session as s:
            conditions: list[sa.ColumnElement[bool]] = [
                self.model_type.type == NotificationDeliveryType.REFLECTION_PROMPT,
                self.model_type.status == NotificationDeliveryStatus.FAILED,
            ]
            if min_updated_at is not None:
                conditions.append(self.model_type.updated_at <= min_updated_at)
            if max_attempts is not None:
                conditions.append(self.model_type.attempts < max_attempts)

            stmt = (
                sa.select(self.model_type)
                .where(*conditions)
                .order_by(self.model_type.updated_at.asc(), self.model_type.created_at.asc())
                .limit(limit)
            )
            models = (await s.execute(stmt)).scalars().all()
            return [self.read_schema_type.model_validate(model, from_attributes=True) for model in models]

    async def mark_queued(self, delivery_id: uuid.UUID) -> NotificationDeliveryReadSchema:
        """Перевести доставку в queued."""
        async with self.session as s, s.begin():
            stmt = (
                sa.update(self.model_type)
                .where(self.model_type.id == delivery_id)
                .values(
                    status=NotificationDeliveryStatus.QUEUED,
                    last_error=None,
                )
                .returning(self.model_type)
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                raise ModelFieldNotFoundException(self.model_type, "id", delivery_id)
            return self.read_schema_type.model_validate(model, from_attributes=True)

    async def mark_sent(
        self,
        delivery_id: uuid.UUID,
        sent_at: datetime,
        telegram_message_id: int | None = None,
    ) -> NotificationDeliveryReadSchema:
        """Перевести доставку в sent и увеличить attempts."""
        async with self.session as s, s.begin():
            stmt = (
                sa.update(self.model_type)
                .where(self.model_type.id == delivery_id)
                .values(
                    status=NotificationDeliveryStatus.SENT,
                    sent_at=sent_at,
                    telegram_message_id=telegram_message_id,
                    attempts=self.model_type.attempts + 1,
                    last_error=None,
                )
                .returning(self.model_type)
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                raise ModelFieldNotFoundException(self.model_type, "id", delivery_id)
            return self.read_schema_type.model_validate(model, from_attributes=True)

    async def mark_deadline_message_updated(
        self,
        delivery_id: uuid.UUID,
        updated_at: datetime,
    ) -> NotificationDeliveryReadSchema:
        """Отметить, что prompt был обновлён после дедлайна."""
        async with self.session as s, s.begin():
            stmt = (
                sa.update(self.model_type)
                .where(self.model_type.id == delivery_id)
                .values(deadline_message_updated_at=updated_at)
                .returning(self.model_type)
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                raise ModelFieldNotFoundException(self.model_type, "id", delivery_id)
            return self.read_schema_type.model_validate(model, from_attributes=True)

    async def mark_failed(self, delivery_id: uuid.UUID, error: str) -> NotificationDeliveryReadSchema:
        """Перевести доставку в failed и увеличить attempts."""
        async with self.session as s, s.begin():
            stmt = (
                sa.update(self.model_type)
                .where(self.model_type.id == delivery_id)
                .values(
                    status=NotificationDeliveryStatus.FAILED,
                    attempts=self.model_type.attempts + 1,
                    last_error=error,
                )
                .returning(self.model_type)
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                raise ModelFieldNotFoundException(self.model_type, "id", delivery_id)
            return self.read_schema_type.model_validate(model, from_attributes=True)
