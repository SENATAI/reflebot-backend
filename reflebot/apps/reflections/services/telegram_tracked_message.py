"""
Сервис для отслеживаемых Telegram-сообщений.
"""

import uuid
from datetime import datetime
from typing import Protocol

from reflebot.core.utils.exceptions import ModelFieldNotFoundException, ValidationError
from ..enums import NotificationDeliveryType
from ..models import Student
from ..schemas import TelegramTrackedMessageCreateSchema, TelegramTrackedMessageReadSchema
from ..repositories.notification_delivery import NotificationDeliveryRepositoryProtocol
from ..repositories.student import StudentRepositoryProtocol
from ..repositories.telegram_tracked_message import TelegramTrackedMessageRepositoryProtocol


class TelegramTrackedMessageServiceProtocol(Protocol):
    """Протокол сервиса отслеживаемых Telegram-сообщений."""

    REFLECTION_STATUS_KIND: str

    @staticmethod
    def build_reflection_status_tracking_key(lection_id: uuid.UUID | str) -> str:
        """Построить tracking key для активного статуса рефлексии."""
        ...

    async def track_message_delivery(
        self,
        telegram_id: int,
        tracking_key: str,
        telegram_message_id: int,
    ) -> TelegramTrackedMessageReadSchema:
        """Сохранить telegram_message_id trackable-сообщения."""
        ...

    async def get_deadline_update_batch(
        self,
        limit: int,
        deadline_before: datetime,
    ) -> list[TelegramTrackedMessageReadSchema]:
        """Получить trackable-сообщения, требующие обновления после дедлайна."""
        ...

    async def mark_deadline_message_updated(
        self,
        tracked_message_id: uuid.UUID,
        updated_at: datetime,
    ) -> TelegramTrackedMessageReadSchema:
        """Отметить trackable-сообщение как обновлённое после дедлайна."""
        ...


class TelegramTrackedMessageService(TelegramTrackedMessageServiceProtocol):
    """Сервис отслеживаемых Telegram-сообщений."""

    REFLECTION_STATUS_KIND = "reflection_status"
    REFLECTION_STATUS_PREFIX = "reflection_status:"

    def __init__(
        self,
        repository: TelegramTrackedMessageRepositoryProtocol,
        student_repository: StudentRepositoryProtocol,
        notification_delivery_repository: NotificationDeliveryRepositoryProtocol,
    ):
        self.repository = repository
        self.student_repository = student_repository
        self.notification_delivery_repository = notification_delivery_repository

    @staticmethod
    def build_reflection_status_tracking_key(lection_id: uuid.UUID | str) -> str:
        """Построить tracking key для активного статуса рефлексии."""
        return f"{TelegramTrackedMessageService.REFLECTION_STATUS_PREFIX}{lection_id}"

    async def track_message_delivery(
        self,
        telegram_id: int,
        tracking_key: str,
        telegram_message_id: int,
    ) -> TelegramTrackedMessageReadSchema:
        """Сохранить telegram_message_id trackable-сообщения."""
        lection_id = self._parse_reflection_status_tracking_key(tracking_key)
        student = await self.student_repository.get_by_telegram_id(telegram_id)
        if student is None:
            raise ModelFieldNotFoundException(Student, "telegram_id", telegram_id)
        delivery = await self.notification_delivery_repository.get_or_none_by_unique(
            lection_session_id=lection_id,
            student_id=student.id,
            notification_type=NotificationDeliveryType.REFLECTION_PROMPT,
        )
        if delivery is None:
            raise ValidationError(
                "tracking_key",
                "Не найдена исходная доставка рефлексии для отслеживаемого сообщения.",
            )
        return await self.repository.upsert(
            TelegramTrackedMessageCreateSchema(
                telegram_id=telegram_id,
                telegram_message_id=telegram_message_id,
                student_id=student.id,
                lection_session_id=lection_id,
                notification_delivery_id=delivery.id,
                kind=self.REFLECTION_STATUS_KIND,
            )
        )

    async def get_deadline_update_batch(
        self,
        limit: int,
        deadline_before: datetime,
    ) -> list[TelegramTrackedMessageReadSchema]:
        """Получить trackable-сообщения, требующие обновления после дедлайна."""
        return await self.repository.get_deadline_update_batch(
            limit=limit,
            deadline_before=deadline_before,
            kind=self.REFLECTION_STATUS_KIND,
        )

    async def mark_deadline_message_updated(
        self,
        tracked_message_id: uuid.UUID,
        updated_at: datetime,
    ) -> TelegramTrackedMessageReadSchema:
        """Отметить trackable-сообщение как обновлённое после дедлайна."""
        return await self.repository.mark_deadline_message_updated(tracked_message_id, updated_at)

    def _parse_reflection_status_tracking_key(self, tracking_key: str) -> uuid.UUID:
        """Распарсить tracking key активного статуса рефлексии."""
        if not tracking_key.startswith(self.REFLECTION_STATUS_PREFIX):
            raise ValidationError("tracking_key", "Неподдерживаемый tracking key.")
        raw_lection_id = tracking_key.removeprefix(self.REFLECTION_STATUS_PREFIX)
        try:
            return uuid.UUID(raw_lection_id)
        except ValueError as exc:
            raise ValidationError("tracking_key", "Некорректный tracking key.") from exc
