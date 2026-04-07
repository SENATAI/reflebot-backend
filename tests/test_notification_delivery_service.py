"""
Unit tests для сервисов доставки уведомлений.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from reflebot.apps.reflections.enums import NotificationDeliveryStatus, NotificationDeliveryType
from reflebot.apps.reflections.schemas import (
    LectionSessionReadSchema,
    NotificationDeliveryReadSchema,
    ReflectionPromptCandidateSchema,
)
from reflebot.apps.reflections.services.notification_delivery import NotificationDeliveryService
from reflebot.apps.reflections.services.reflection_prompt_message import ReflectionPromptMessageService
from reflebot.apps.reflections.telegram.buttons import TelegramButtons


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
async def test_notification_delivery_service_create_if_missing_creates_pending():
    repository = AsyncMock()
    repository.get_or_none_by_unique.return_value = None
    pending_delivery = create_delivery_read(NotificationDeliveryStatus.PENDING)
    repository.create.return_value = pending_delivery
    service = NotificationDeliveryService(repository)

    candidate = ReflectionPromptCandidateSchema(
        lection_session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        telegram_id=123,
        scheduled_for=datetime.now(timezone.utc),
    )

    result = await service.create_if_missing(candidate)

    assert result == pending_delivery
    create_schema = repository.create.call_args[0][0]
    assert create_schema.status == NotificationDeliveryStatus.PENDING
    assert create_schema.type == NotificationDeliveryType.REFLECTION_PROMPT


@pytest.mark.asyncio
async def test_notification_delivery_service_create_if_missing_is_idempotent():
    repository = AsyncMock()
    existing_delivery = create_delivery_read(NotificationDeliveryStatus.QUEUED)
    repository.get_or_none_by_unique.return_value = existing_delivery
    service = NotificationDeliveryService(repository)

    candidate = ReflectionPromptCandidateSchema(
        lection_session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        telegram_id=123,
        scheduled_for=datetime.now(timezone.utc),
    )

    result = await service.create_if_missing(candidate)

    assert result is None
    repository.create.assert_not_called()


@pytest.mark.asyncio
async def test_notification_delivery_service_mark_sent_is_idempotent_for_sent():
    repository = AsyncMock()
    sent_delivery = create_delivery_read(NotificationDeliveryStatus.SENT)
    repository.get.return_value = sent_delivery
    service = NotificationDeliveryService(repository)

    result = await service.mark_sent(sent_delivery.id, datetime.now(timezone.utc))

    assert result == sent_delivery
    repository.mark_sent.assert_not_called()


@pytest.mark.asyncio
async def test_notification_delivery_service_mark_sent_passes_telegram_message_id():
    repository = AsyncMock()
    queued_delivery = create_delivery_read(NotificationDeliveryStatus.QUEUED)
    sent_delivery = queued_delivery.model_copy(update={"status": NotificationDeliveryStatus.SENT})
    repository.get.return_value = queued_delivery
    repository.mark_sent.return_value = sent_delivery
    service = NotificationDeliveryService(repository)

    result = await service.mark_sent(
        queued_delivery.id,
        datetime.now(timezone.utc),
        telegram_message_id=321,
    )

    assert result == sent_delivery
    repository.mark_sent.assert_awaited_once()
    assert repository.mark_sent.call_args.args[2] == 321


@pytest.mark.asyncio
async def test_notification_delivery_service_ignores_fail_for_sent_delivery():
    repository = AsyncMock()
    sent_delivery = create_delivery_read(NotificationDeliveryStatus.SENT)
    repository.get.return_value = sent_delivery
    service = NotificationDeliveryService(repository)

    result = await service.mark_failed(sent_delivery.id, "late fail")

    assert result == sent_delivery
    repository.mark_failed.assert_not_called()


@pytest.mark.asyncio
async def test_reflection_prompt_message_service_includes_lection_topic():
    lection_repository = AsyncMock()
    now = datetime.now(timezone.utc)
    lection_repository.get.return_value = LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic="Математический анализ",
        presentation_file_id=None,
        recording_file_id=None,
        started_at=now,
        ended_at=now,
        deadline=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )
    service = ReflectionPromptMessageService(lection_repository)

    message = await service.build_message(uuid.uuid4(), uuid.uuid4())

    assert "Математический анализ" in message.message_text
    assert "рефлексию" in message.message_text
    assert "Дедлайн" in message.message_text
    assert message.parse_mode == "HTML"
    assert len(message.buttons) == 1
    assert message.buttons[0].action.startswith("student_start_reflection:")


@pytest.mark.asyncio
async def test_reflection_prompt_message_service_returns_expired_status_for_late_join():
    lection_repository = AsyncMock()
    now = datetime.now(timezone.utc)
    lection_repository.get.return_value = LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic="Математический анализ",
        presentation_file_id=None,
        recording_file_id=None,
        started_at=now - timedelta(days=2, hours=1),
        ended_at=now - timedelta(days=2),
        deadline=now - timedelta(hours=2),
        created_at=now,
        updated_at=now,
    )
    service = ReflectionPromptMessageService(lection_repository)

    message = await service.build_message(uuid.uuid4(), uuid.uuid4())

    assert "Кружки/видео по этой лекции не записаны" in message.message_text
    assert "техподдержку" in message.message_text
    assert len(message.buttons) == 1
    assert message.buttons[0].url == TelegramButtons.TECH_SUPPORT_URL
