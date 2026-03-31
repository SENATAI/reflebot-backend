"""
Use cases для автоматической доставки запросов рефлексии.
"""

import logging
from datetime import timedelta
from datetime import datetime, timezone
from typing import Protocol

from ..repositories.notification_delivery import NotificationDeliveryRepositoryProtocol
from ..repositories.student import StudentRepositoryProtocol
from ..schemas import ReflectionPromptCommandSchema
from ..services.notification_delivery import NotificationDeliveryServiceProtocol
from ..services.notification_publisher import NotificationCommandPublisherProtocol
from ..services.reflection_prompt_message import ReflectionPromptMessageServiceProtocol
from ..services.reflection_prompt_scan import ReflectionPromptScanServiceProtocol

logger = logging.getLogger(__name__)


class ScanDueReflectionPromptsUseCaseProtocol(Protocol):
    """Протокол scan use case."""

    async def __call__(self, now: datetime | None = None) -> int:
        """Создать pending доставки для due кандидатов."""
        ...


class PublishPendingReflectionPromptsUseCaseProtocol(Protocol):
    """Протокол use case публикации pending доставок."""

    async def __call__(self) -> int:
        """Опубликовать pending доставки в очередь бота."""
        ...


class RetryFailedReflectionPromptsUseCaseProtocol(Protocol):
    """Протокол use case retry failed доставок."""

    async def __call__(self) -> int:
        """Повторно опубликовать failed доставки."""
        ...


class ScanDueReflectionPromptsUseCase(ScanDueReflectionPromptsUseCaseProtocol):
    """Use case bounded scan и создания pending доставок."""

    def __init__(
        self,
        scan_service: ReflectionPromptScanServiceProtocol,
        notification_delivery_service: NotificationDeliveryServiceProtocol,
        scan_batch_size: int,
    ):
        self.scan_service = scan_service
        self.notification_delivery_service = notification_delivery_service
        self.scan_batch_size = scan_batch_size

    async def __call__(self, now: datetime | None = None) -> int:
        """Найти due кандидатов и создать недостающие pending доставки."""
        current_time = now or datetime.now(timezone.utc)
        logger.info(
            "Starting due reflection prompt scan.",
            extra={
                "scan_batch_size": self.scan_batch_size,
                "scan_time": current_time.isoformat(),
            },
        )
        candidates = await self.scan_service.find_due_candidates(
            now=current_time,
            limit=self.scan_batch_size,
        )
        logger.info(
            "Due reflection prompt candidates loaded.",
            extra={
                "candidates_count": len(candidates),
                "scan_batch_size": self.scan_batch_size,
            },
        )
        created = 0
        for candidate in candidates:
            delivery = await self.notification_delivery_service.create_if_missing(candidate)
            if delivery is not None:
                created += 1
        logger.info(
            "Due reflection prompt scan completed.",
            extra={
                "created_deliveries": created,
                "candidates_count": len(candidates),
            },
        )
        return created


class PublishPendingReflectionPromptsUseCase(PublishPendingReflectionPromptsUseCaseProtocol):
    """Use case публикации pending доставок в RabbitMQ."""

    def __init__(
        self,
        notification_delivery_repository: NotificationDeliveryRepositoryProtocol,
        notification_delivery_service: NotificationDeliveryServiceProtocol,
        student_repository: StudentRepositoryProtocol,
        message_service: ReflectionPromptMessageServiceProtocol,
        publisher: NotificationCommandPublisherProtocol,
        publish_batch_size: int,
    ):
        self.notification_delivery_repository = notification_delivery_repository
        self.notification_delivery_service = notification_delivery_service
        self.student_repository = student_repository
        self.message_service = message_service
        self.publisher = publisher
        self.publish_batch_size = publish_batch_size

    async def __call__(self) -> int:
        """Опубликовать pending batch доставок в очередь бота."""
        pending_deliveries = await self.notification_delivery_repository.get_pending_batch(
            self.publish_batch_size
        )
        logger.info(
            "Loaded pending reflection prompt deliveries.",
            extra={
                "batch_size": len(pending_deliveries),
                "publish_batch_size": self.publish_batch_size,
            },
        )
        published = 0
        for delivery in pending_deliveries:
            student = await self.student_repository.get(delivery.student_id)
            if student.telegram_id is None:
                continue
            message = await self.message_service.build_message(
                lection_session_id=delivery.lection_session_id,
                student_id=delivery.student_id,
            )
            command = ReflectionPromptCommandSchema(
                delivery_id=delivery.id,
                student_id=delivery.student_id,
                telegram_id=student.telegram_id,
                lection_session_id=delivery.lection_session_id,
                message_text=message.message_text,
                parse_mode=message.parse_mode,
                buttons=message.buttons,
                scheduled_for=delivery.scheduled_for,
            )
            try:
                await self.publisher.publish_reflection_prompt(command)
            except Exception:
                logger.exception(
                    "Failed to publish reflection prompt command.",
                    extra={
                        "delivery_id": str(delivery.id),
                        "student_id": str(delivery.student_id),
                        "lection_session_id": str(delivery.lection_session_id),
                    },
                )
                continue
            await self.notification_delivery_service.mark_queued(delivery.id)
            published += 1
            logger.info(
                "Pending reflection prompt moved to queued.",
                extra={
                    "delivery_id": str(delivery.id),
                    "student_id": str(delivery.student_id),
                    "lection_session_id": str(delivery.lection_session_id),
                    "status": "queued",
                },
            )
        return published


class RetryFailedReflectionPromptsUseCase(RetryFailedReflectionPromptsUseCaseProtocol):
    """Use case повторной публикации failed доставок."""

    def __init__(
        self,
        notification_delivery_repository: NotificationDeliveryRepositoryProtocol,
        notification_delivery_service: NotificationDeliveryServiceProtocol,
        student_repository: StudentRepositoryProtocol,
        message_service: ReflectionPromptMessageServiceProtocol,
        publisher: NotificationCommandPublisherProtocol,
        publish_batch_size: int,
        retry_failed_backoff_seconds: int = 300,
        retry_failed_max_attempts: int = 3,
    ):
        self.notification_delivery_repository = notification_delivery_repository
        self.notification_delivery_service = notification_delivery_service
        self.student_repository = student_repository
        self.message_service = message_service
        self.publisher = publisher
        self.publish_batch_size = publish_batch_size
        self.retry_failed_backoff_seconds = retry_failed_backoff_seconds
        self.retry_failed_max_attempts = retry_failed_max_attempts

    async def __call__(self) -> int:
        """Повторно опубликовать failed batch доставок."""
        retry_before = datetime.now(timezone.utc) - timedelta(
            seconds=self.retry_failed_backoff_seconds
        )
        failed_deliveries = await self.notification_delivery_repository.get_retryable_failed_batch_with_policy(
            limit=self.publish_batch_size,
            min_updated_at=retry_before,
            max_attempts=self.retry_failed_max_attempts,
        )
        logger.info(
            "Loaded failed reflection prompt deliveries for retry.",
            extra={
                "batch_size": len(failed_deliveries),
                "publish_batch_size": self.publish_batch_size,
                "retry_failed_max_attempts": self.retry_failed_max_attempts,
            },
        )
        published = 0
        for delivery in failed_deliveries:
            student = await self.student_repository.get(delivery.student_id)
            if student.telegram_id is None:
                continue
            message = await self.message_service.build_message(
                lection_session_id=delivery.lection_session_id,
                student_id=delivery.student_id,
            )
            command = ReflectionPromptCommandSchema(
                delivery_id=delivery.id,
                student_id=delivery.student_id,
                telegram_id=student.telegram_id,
                lection_session_id=delivery.lection_session_id,
                message_text=message.message_text,
                parse_mode=message.parse_mode,
                buttons=message.buttons,
                scheduled_for=delivery.scheduled_for,
            )
            try:
                await self.publisher.publish_reflection_prompt(command)
            except Exception:
                logger.exception(
                    "Failed to republish reflection prompt command.",
                    extra={
                        "delivery_id": str(delivery.id),
                        "student_id": str(delivery.student_id),
                        "lection_session_id": str(delivery.lection_session_id),
                        "attempts": delivery.attempts,
                    },
                )
                continue
            await self.notification_delivery_service.mark_queued(delivery.id)
            published += 1
            logger.info(
                "Failed reflection prompt moved back to queued.",
                extra={
                    "delivery_id": str(delivery.id),
                    "student_id": str(delivery.student_id),
                    "lection_session_id": str(delivery.lection_session_id),
                    "status": "queued",
                    "attempts": delivery.attempts,
                },
            )
        return published
