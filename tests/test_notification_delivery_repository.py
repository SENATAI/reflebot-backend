"""
Unit tests для NotificationDeliveryRepository.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
import uuid

import pytest

from reflebot.apps.reflections.enums import NotificationDeliveryStatus, NotificationDeliveryType
from reflebot.apps.reflections.models import NotificationDelivery
from reflebot.apps.reflections.repositories.notification_delivery import NotificationDeliveryRepository


def configure_session(session: AsyncMock) -> None:
    entered_session = AsyncMock()
    session.__aenter__.return_value = entered_session
    session.__aexit__.return_value = None
    begin_cm = AsyncMock()
    begin_cm.__aenter__.return_value = None
    begin_cm.__aexit__.return_value = None
    entered_session.begin = Mock(return_value=begin_cm)
    entered_session.execute = session.execute


def create_delivery_model(status: NotificationDeliveryStatus) -> NotificationDelivery:
    now = datetime.now(timezone.utc)
    model = NotificationDelivery(
        id=uuid.uuid4(),
        lection_session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        type=NotificationDeliveryType.REFLECTION_PROMPT,
        scheduled_for=now,
        status=status,
        sent_at=None,
        attempts=0,
        last_error=None,
    )
    model.created_at = now
    model.updated_at = now
    return model


@pytest.mark.asyncio
async def test_notification_delivery_repository_get_or_none_by_unique_returns_none():
    session = AsyncMock()
    configure_session(session)
    repository = NotificationDeliveryRepository(session=session)
    execute_result = Mock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute.return_value = execute_result

    result = await repository.get_or_none_by_unique(
        uuid.uuid4(),
        uuid.uuid4(),
        NotificationDeliveryType.REFLECTION_PROMPT,
    )

    assert result is None


@pytest.mark.asyncio
async def test_notification_delivery_repository_get_pending_batch_returns_models():
    session = AsyncMock()
    configure_session(session)
    repository = NotificationDeliveryRepository(session=session)
    execute_result = Mock()
    execute_result.scalars.return_value.all.return_value = [
        create_delivery_model(NotificationDeliveryStatus.PENDING),
    ]
    session.execute.return_value = execute_result

    result = await repository.get_pending_batch(limit=5)

    assert len(result) == 1
    assert result[0].status == NotificationDeliveryStatus.PENDING


@pytest.mark.asyncio
async def test_notification_delivery_repository_mark_queued_returns_updated_model():
    session = AsyncMock()
    configure_session(session)
    repository = NotificationDeliveryRepository(session=session)
    execute_result = Mock()
    updated_model = create_delivery_model(NotificationDeliveryStatus.QUEUED)
    execute_result.scalar_one_or_none.return_value = updated_model
    session.execute.return_value = execute_result

    result = await repository.mark_queued(updated_model.id)

    assert result.status == NotificationDeliveryStatus.QUEUED


@pytest.mark.asyncio
async def test_notification_delivery_repository_mark_failed_returns_updated_model():
    session = AsyncMock()
    configure_session(session)
    repository = NotificationDeliveryRepository(session=session)
    execute_result = Mock()
    updated_model = create_delivery_model(NotificationDeliveryStatus.FAILED)
    updated_model.last_error = "error"
    updated_model.attempts = 1
    execute_result.scalar_one_or_none.return_value = updated_model
    session.execute.return_value = execute_result

    result = await repository.mark_failed(updated_model.id, "error")

    assert result.status == NotificationDeliveryStatus.FAILED
    assert result.last_error == "error"
