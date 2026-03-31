"""
Unit tests для use cases доставки уведомлений.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from unittest.mock import patch
import uuid

import pytest

from reflebot.apps.reflections.enums import NotificationDeliveryStatus, NotificationDeliveryType
from reflebot.apps.reflections.schemas import (
    NotificationDeliveryReadSchema,
    ReflectionPromptCandidateSchema,
)
from reflebot.apps.reflections.use_cases.notification_delivery import (
    PublishPendingReflectionPromptsUseCase,
    RetryFailedReflectionPromptsUseCase,
    ScanDueReflectionPromptsUseCase,
)


def create_delivery_read(status: NotificationDeliveryStatus) -> NotificationDeliveryReadSchema:
    now = datetime.now(timezone.utc)
    return NotificationDeliveryReadSchema(
        id=uuid.uuid4(),
        lection_session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        type=NotificationDeliveryType.REFLECTION_PROMPT,
        scheduled_for=now,
        status=status,
        sent_at=None,
        attempts=0,
        last_error=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_scan_due_reflection_prompts_use_case_creates_new_deliveries():
    scan_service = AsyncMock()
    notification_delivery_service = AsyncMock()
    scan_service.find_due_candidates.return_value = [
        ReflectionPromptCandidateSchema(
            lection_session_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            telegram_id=111,
            scheduled_for=datetime.now(timezone.utc),
        ),
        ReflectionPromptCandidateSchema(
            lection_session_id=uuid.uuid4(),
            student_id=uuid.uuid4(),
            telegram_id=222,
            scheduled_for=datetime.now(timezone.utc),
        ),
    ]
    notification_delivery_service.create_if_missing.side_effect = [object(), None]
    use_case = ScanDueReflectionPromptsUseCase(
        scan_service=scan_service,
        notification_delivery_service=notification_delivery_service,
        scan_batch_size=100,
    )

    created = await use_case()

    assert created == 1


@pytest.mark.asyncio
async def test_publish_pending_reflection_prompts_use_case_marks_queued_after_publish():
    notification_delivery_repository = AsyncMock()
    notification_delivery_service = AsyncMock()
    student_repository = AsyncMock()
    message_service = AsyncMock()
    publisher = AsyncMock()
    pending = create_delivery_read(NotificationDeliveryStatus.PENDING)
    notification_delivery_repository.get_pending_batch.return_value = [pending]
    student_repository.get.return_value = type("StudentStub", (), {"telegram_id": 555})()
    message_service.build_message.return_value = type(
        "MessageStub",
        (),
        {"message_text": "hello", "parse_mode": "HTML", "buttons": []},
    )()
    use_case = PublishPendingReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=100,
    )

    published = await use_case()

    assert published == 1
    publisher.publish_reflection_prompt.assert_called_once()
    notification_delivery_service.mark_queued.assert_called_once_with(pending.id)


@pytest.mark.asyncio
async def test_retry_failed_reflection_prompts_use_case_republishes_failed_delivery():
    notification_delivery_repository = AsyncMock()
    notification_delivery_service = AsyncMock()
    student_repository = AsyncMock()
    message_service = AsyncMock()
    publisher = AsyncMock()
    failed = create_delivery_read(NotificationDeliveryStatus.FAILED)
    notification_delivery_repository.get_retryable_failed_batch_with_policy.return_value = [failed]
    student_repository.get.return_value = type("StudentStub", (), {"telegram_id": 777})()
    message_service.build_message.return_value = type(
        "MessageStub",
        (),
        {"message_text": "retry", "parse_mode": "HTML", "buttons": []},
    )()
    use_case = RetryFailedReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=100,
    )

    published = await use_case()

    assert published == 1
    publisher.publish_reflection_prompt.assert_called_once()
    notification_delivery_service.mark_queued.assert_called_once_with(failed.id)


@pytest.mark.asyncio
async def test_retry_failed_reflection_prompts_keeps_failed_on_republish_error():
    notification_delivery_repository = AsyncMock()
    notification_delivery_service = AsyncMock()
    student_repository = AsyncMock()
    message_service = AsyncMock()
    publisher = AsyncMock()
    failed = create_delivery_read(NotificationDeliveryStatus.FAILED)
    notification_delivery_repository.get_retryable_failed_batch_with_policy.return_value = [failed]
    student_repository.get.return_value = type("StudentStub", (), {"telegram_id": 777})()
    message_service.build_message.return_value = type(
        "MessageStub",
        (),
        {"message_text": "retry", "parse_mode": "HTML", "buttons": []},
    )()
    publisher.publish_reflection_prompt.side_effect = RuntimeError("broker down")
    use_case = RetryFailedReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=100,
    )

    with patch("reflebot.apps.reflections.use_cases.notification_delivery.logger.exception") as logger_mock:
        published = await use_case()

    assert published == 0
    notification_delivery_service.mark_queued.assert_not_called()
    logger_mock.assert_called_once()


@pytest.mark.asyncio
async def test_publish_pending_reflection_prompts_logs_error_and_keeps_pending_on_publish_failure():
    notification_delivery_repository = AsyncMock()
    notification_delivery_service = AsyncMock()
    student_repository = AsyncMock()
    message_service = AsyncMock()
    publisher = AsyncMock()
    pending = create_delivery_read(NotificationDeliveryStatus.PENDING)
    notification_delivery_repository.get_pending_batch.return_value = [pending]
    student_repository.get.return_value = type("StudentStub", (), {"telegram_id": 555})()
    message_service.build_message.return_value = type(
        "MessageStub",
        (),
        {"message_text": "hello", "parse_mode": "HTML", "buttons": []},
    )()
    publisher.publish_reflection_prompt.side_effect = RuntimeError("broker down")
    use_case = PublishPendingReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=100,
    )

    with patch("reflebot.apps.reflections.use_cases.notification_delivery.logger.exception") as logger_mock:
        published = await use_case()

    assert published == 0
    notification_delivery_service.mark_queued.assert_not_called()
    logger_mock.assert_called_once()


@pytest.mark.asyncio
async def test_retry_failed_reflection_prompts_use_case_uses_retry_policy():
    notification_delivery_repository = AsyncMock()
    notification_delivery_service = AsyncMock()
    student_repository = AsyncMock()
    message_service = AsyncMock()
    publisher = AsyncMock()
    notification_delivery_repository.get_retryable_failed_batch_with_policy.return_value = []
    use_case = RetryFailedReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=50,
        retry_failed_backoff_seconds=600,
        retry_failed_max_attempts=4,
    )

    published = await use_case()

    assert published == 0
    kwargs = notification_delivery_repository.get_retryable_failed_batch_with_policy.call_args.kwargs
    assert kwargs["limit"] == 50
    assert kwargs["max_attempts"] == 4
    assert kwargs["min_updated_at"] is not None
