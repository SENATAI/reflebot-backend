"""
Сервис для работы с доставками уведомлений.
"""

import uuid
from datetime import datetime
from typing import Protocol

from ..enums import NotificationDeliveryStatus, NotificationDeliveryType
from ..repositories.notification_delivery import NotificationDeliveryRepositoryProtocol
from ..schemas import (
    NotificationDeliveryCreateSchema,
    NotificationDeliveryReadSchema,
    ReflectionPromptCandidateSchema,
)


class NotificationDeliveryServiceProtocol(Protocol):
    """Протокол сервиса доставок уведомлений."""

    async def get_by_id(self, delivery_id: uuid.UUID) -> NotificationDeliveryReadSchema:
        """Получить доставку по идентификатору."""
        ...

    async def create_if_missing(
        self,
        candidate: ReflectionPromptCandidateSchema,
    ) -> NotificationDeliveryReadSchema | None:
        """Создать доставку, если она ещё не существует."""
        ...

    async def mark_queued(self, delivery_id: uuid.UUID) -> NotificationDeliveryReadSchema:
        """Перевести доставку в queued."""
        ...

    async def mark_sent(
        self,
        delivery_id: uuid.UUID,
        sent_at: datetime,
    ) -> NotificationDeliveryReadSchema:
        """Перевести доставку в sent."""
        ...

    async def mark_failed(self, delivery_id: uuid.UUID, error: str) -> NotificationDeliveryReadSchema:
        """Перевести доставку в failed."""
        ...


class NotificationDeliveryService(NotificationDeliveryServiceProtocol):
    """Сервис для работы с доставками уведомлений."""

    def __init__(self, repository: NotificationDeliveryRepositoryProtocol):
        self.repository = repository

    async def get_by_id(self, delivery_id: uuid.UUID) -> NotificationDeliveryReadSchema:
        """Получить доставку по идентификатору."""
        return await self.repository.get(delivery_id)

    async def create_if_missing(
        self,
        candidate: ReflectionPromptCandidateSchema,
    ) -> NotificationDeliveryReadSchema | None:
        """Создать доставку только при отсутствии записи с тем же уникальным ключом."""
        existing = await self.repository.get_or_none_by_unique(
            lection_session_id=candidate.lection_session_id,
            student_id=candidate.student_id,
            notification_type=NotificationDeliveryType.REFLECTION_PROMPT,
        )
        if existing is not None:
            return None

        create_schema = NotificationDeliveryCreateSchema(
            lection_session_id=candidate.lection_session_id,
            student_id=candidate.student_id,
            type=NotificationDeliveryType.REFLECTION_PROMPT,
            scheduled_for=candidate.scheduled_for,
            status=NotificationDeliveryStatus.PENDING,
            sent_at=None,
            attempts=0,
            last_error=None,
        )
        return await self.repository.create(create_schema)

    async def mark_queued(self, delivery_id: uuid.UUID) -> NotificationDeliveryReadSchema:
        """Перевести доставку в queued."""
        current = await self.repository.get(delivery_id)
        if current.status == NotificationDeliveryStatus.SENT:
            return current
        return await self.repository.mark_queued(delivery_id)

    async def mark_sent(
        self,
        delivery_id: uuid.UUID,
        sent_at: datetime,
    ) -> NotificationDeliveryReadSchema:
        """Перевести доставку в sent."""
        current = await self.repository.get(delivery_id)
        if current.status == NotificationDeliveryStatus.SENT:
            return current
        return await self.repository.mark_sent(delivery_id, sent_at)

    async def mark_failed(self, delivery_id: uuid.UUID, error: str) -> NotificationDeliveryReadSchema:
        """Перевести доставку в failed, если она ещё не стала sent."""
        current = await self.repository.get(delivery_id)
        if current.status == NotificationDeliveryStatus.SENT:
            return current
        return await self.repository.mark_failed(delivery_id, error)
