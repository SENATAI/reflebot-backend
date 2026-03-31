"""
Celery entrypoints для workflow доставки запросов рефлексии.
"""

from __future__ import annotations

import asyncio
from typing import Any

from reflebot.celery_app import celery_app
from reflebot.core.db import AsyncSessionFactory
from reflebot.settings import settings

from ..repositories.lection import LectionSessionRepository
from ..repositories.notification_delivery import NotificationDeliveryRepository
from ..repositories.student import StudentRepository
from ..repositories.student_lection import StudentLectionRepository
from ..services.notification_delivery import NotificationDeliveryService
from ..services.notification_publisher import NotificationCommandPublisher
from ..services.reflection_prompt_message import ReflectionPromptMessageService
from ..services.reflection_prompt_scan import ReflectionPromptScanService
from ..use_cases.notification_delivery import (
    PublishPendingReflectionPromptsUseCase,
    RetryFailedReflectionPromptsUseCase,
    ScanDueReflectionPromptsUseCase,
)


def _run_async(coro: Any) -> Any:
    """Выполнить async-корутины из sync Celery task."""
    return asyncio.run(coro)


def _build_scan_use_case() -> ScanDueReflectionPromptsUseCase:
    session = AsyncSessionFactory()
    student_lection_repository = StudentLectionRepository(session=session)
    notification_delivery_repository = NotificationDeliveryRepository(session=session)
    scan_service = ReflectionPromptScanService(
        student_lection_repository=student_lection_repository,
        lookback_hours=settings.celery.scan_lookback_hours,
    )
    notification_delivery_service = NotificationDeliveryService(notification_delivery_repository)
    return ScanDueReflectionPromptsUseCase(
        scan_service=scan_service,
        notification_delivery_service=notification_delivery_service,
        scan_batch_size=settings.celery.scan_batch_size,
    )


def _build_publish_use_case() -> PublishPendingReflectionPromptsUseCase:
    session = AsyncSessionFactory()
    notification_delivery_repository = NotificationDeliveryRepository(session=session)
    student_repository = StudentRepository(session=session)
    lection_repository = LectionSessionRepository(session=session)
    notification_delivery_service = NotificationDeliveryService(notification_delivery_repository)
    message_service = ReflectionPromptMessageService(lection_repository=lection_repository)
    publisher = NotificationCommandPublisher(settings.rabbitmq)
    return PublishPendingReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=settings.celery.publish_batch_size,
    )


def _build_retry_use_case() -> RetryFailedReflectionPromptsUseCase:
    session = AsyncSessionFactory()
    notification_delivery_repository = NotificationDeliveryRepository(session=session)
    student_repository = StudentRepository(session=session)
    lection_repository = LectionSessionRepository(session=session)
    notification_delivery_service = NotificationDeliveryService(notification_delivery_repository)
    message_service = ReflectionPromptMessageService(lection_repository=lection_repository)
    publisher = NotificationCommandPublisher(settings.rabbitmq)
    return RetryFailedReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=settings.celery.publish_batch_size,
        retry_failed_backoff_seconds=settings.celery.retry_failed_backoff_seconds,
        retry_failed_max_attempts=settings.celery.retry_failed_max_attempts,
    )


@celery_app.task(name="reflections.scan_due_reflection_prompts")
def scan_due_reflection_prompts() -> dict[str, int]:
    """Создать pending доставки и попытаться сразу опубликовать новые записи."""
    created = _run_async(_build_scan_use_case()())
    published = 0
    if created > 0:
        published = _run_async(_build_publish_use_case()())
    return {"created": created, "published": published}


@celery_app.task(name="reflections.publish_pending_reflection_prompts")
def publish_pending_reflection_prompts() -> dict[str, int]:
    """Опубликовать pending доставки в очередь бота."""
    published = _run_async(_build_publish_use_case()())
    return {"published": published}


@celery_app.task(name="reflections.retry_failed_reflection_prompts")
def retry_failed_reflection_prompts() -> dict[str, int]:
    """Повторно опубликовать failed доставки."""
    republished = _run_async(_build_retry_use_case()())
    return {"republished": republished}
