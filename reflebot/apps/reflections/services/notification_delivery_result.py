"""
Сервис обработки результатов доставки уведомлений.
"""

import logging
from datetime import datetime, timezone
from typing import Protocol

from ..enums import NotificationDeliveryStatus
from ..schemas import NotificationDeliveryReadSchema, ReflectionPromptResultEventSchema
from .notification_delivery import NotificationDeliveryServiceProtocol

logger = logging.getLogger(__name__)


class NotificationDeliveryResultHandlerProtocol(Protocol):
    """Протокол обработчика результата доставки."""

    async def handle(
        self,
        payload: ReflectionPromptResultEventSchema,
    ) -> NotificationDeliveryReadSchema:
        """Обработать result event доставки."""
        ...


class NotificationDeliveryResultHandler(NotificationDeliveryResultHandlerProtocol):
    """Обработчик result event для обновления статуса доставки."""

    def __init__(self, notification_delivery_service: NotificationDeliveryServiceProtocol):
        self.notification_delivery_service = notification_delivery_service

    async def handle(
        self,
        payload: ReflectionPromptResultEventSchema,
    ) -> NotificationDeliveryReadSchema:
        """Обновить статус доставки на основе результата bot-consumer."""
        current = await self.notification_delivery_service.get_by_id(payload.delivery_id)

        if current.status == NotificationDeliveryStatus.SENT and payload.success:
            logger.info(
                "Ignoring duplicate success result for already sent delivery.",
                extra={"delivery_id": str(payload.delivery_id), "status": current.status},
            )
            return current

        if current.status == NotificationDeliveryStatus.SENT and not payload.success:
            logger.warning(
                "Ignoring late failure result for already sent delivery.",
                extra={"delivery_id": str(payload.delivery_id), "status": current.status},
            )
            return current

        if payload.success:
            sent_at = payload.sent_at or datetime.now(timezone.utc)
            result = await self.notification_delivery_service.mark_sent(payload.delivery_id, sent_at)
            logger.info(
                "Notification delivery marked as sent.",
                extra={
                    "delivery_id": str(payload.delivery_id),
                    "status": result.status,
                    "sent_at": sent_at.isoformat(),
                },
            )
            return result

        error = payload.error or "Unknown delivery error"
        result = await self.notification_delivery_service.mark_failed(payload.delivery_id, error)
        logger.warning(
            "Notification delivery marked as failed.",
            extra={
                "delivery_id": str(payload.delivery_id),
                "status": result.status,
                "error": error,
            },
        )
        return result
