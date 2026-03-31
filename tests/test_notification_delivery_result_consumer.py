"""
Unit tests для result handler и result consumer доставок.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from reflebot.apps.reflections.enums import NotificationDeliveryStatus, NotificationDeliveryType
from reflebot.apps.reflections.consumers.delivery_result_consumer import DeliveryResultConsumer
from reflebot.apps.reflections.schemas import (
    NotificationDeliveryReadSchema,
    ReflectionPromptResultEventSchema,
)
from reflebot.apps.reflections.services.notification_delivery_result import (
    NotificationDeliveryResultHandler,
)
from reflebot.settings import RabbitMQ


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
async def test_notification_delivery_result_handler_marks_sent_on_success():
    service = AsyncMock()
    current = create_delivery_read(NotificationDeliveryStatus.QUEUED)
    sent = current.model_copy(update={"status": NotificationDeliveryStatus.SENT})
    service.get_by_id.return_value = current
    service.mark_sent.return_value = sent
    handler = NotificationDeliveryResultHandler(service)
    payload = ReflectionPromptResultEventSchema(
        delivery_id=current.id,
        success=True,
        sent_at=datetime.now(timezone.utc),
        telegram_message_id=123,
        error=None,
    )

    result = await handler.handle(payload)

    assert result.status == NotificationDeliveryStatus.SENT
    service.mark_sent.assert_called_once()


@pytest.mark.asyncio
async def test_notification_delivery_result_handler_ignores_late_failure_for_sent():
    service = AsyncMock()
    sent = create_delivery_read(NotificationDeliveryStatus.SENT)
    service.get_by_id.return_value = sent
    handler = NotificationDeliveryResultHandler(service)
    payload = ReflectionPromptResultEventSchema(
        delivery_id=sent.id,
        success=False,
        sent_at=None,
        telegram_message_id=None,
        error="late fail",
    )

    with patch(
        "reflebot.apps.reflections.services.notification_delivery_result.logger.warning"
    ) as warning_mock:
        result = await handler.handle(payload)

    assert result == sent
    service.mark_failed.assert_not_called()
    warning_mock.assert_called_once()


@pytest.mark.asyncio
async def test_notification_delivery_result_handler_ignores_duplicate_success_for_sent():
    service = AsyncMock()
    sent = create_delivery_read(NotificationDeliveryStatus.SENT)
    service.get_by_id.return_value = sent
    handler = NotificationDeliveryResultHandler(service)
    payload = ReflectionPromptResultEventSchema(
        delivery_id=sent.id,
        success=True,
        sent_at=datetime.now(timezone.utc),
        telegram_message_id=456,
        error=None,
    )

    with patch(
        "reflebot.apps.reflections.services.notification_delivery_result.logger.info"
    ) as info_mock:
        result = await handler.handle(payload)

    assert result == sent
    service.mark_sent.assert_not_called()
    info_mock.assert_called_once()


@pytest.mark.asyncio
async def test_notification_delivery_result_handler_marks_failed_and_logs_warning():
    service = AsyncMock()
    queued = create_delivery_read(NotificationDeliveryStatus.QUEUED)
    failed = queued.model_copy(
        update={
            "status": NotificationDeliveryStatus.FAILED,
            "attempts": 1,
            "last_error": "telegram failed",
        }
    )
    service.get_by_id.return_value = queued
    service.mark_failed.return_value = failed
    handler = NotificationDeliveryResultHandler(service)
    payload = ReflectionPromptResultEventSchema(
        delivery_id=queued.id,
        success=False,
        sent_at=None,
        telegram_message_id=None,
        error="telegram failed",
    )

    with patch(
        "reflebot.apps.reflections.services.notification_delivery_result.logger.warning"
    ) as warning_mock:
        result = await handler.handle(payload)

    assert result.status == NotificationDeliveryStatus.FAILED
    service.mark_failed.assert_called_once_with(queued.id, "telegram failed")
    warning_mock.assert_called_once()


@pytest.mark.asyncio
async def test_delivery_result_consumer_parses_payload_and_calls_handler():
    result_handler = AsyncMock()
    consumer = DeliveryResultConsumer(
        rabbitmq=RabbitMQ(),
        result_handler=result_handler,
    )
    payload = {
        "event_type": "reflection_prompt_result",
        "delivery_id": str(uuid.uuid4()),
        "success": True,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "telegram_message_id": 42,
        "error": None,
    }

    await consumer.handle_message(json.dumps(payload).encode("utf-8"))

    result_handler.handle.assert_called_once()


@pytest.mark.asyncio
async def test_delivery_result_consumer_start_declares_queue_and_processes_message():
    result_handler = AsyncMock()
    connection = AsyncMock()
    channel = AsyncMock()
    exchange = AsyncMock()
    connection.channel.return_value = channel
    channel.declare_exchange.return_value = exchange

    payload = {
        "event_type": "reflection_prompt_result",
        "delivery_id": str(uuid.uuid4()),
        "success": True,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "telegram_message_id": 77,
        "error": None,
    }

    class ProcessContext:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class MessageStub:
        def __init__(self, body: bytes):
            self.body = body

        def process(self):
            return ProcessContext()

    class IteratorStub:
        def __init__(self, messages: list[MessageStub]):
            self.messages = messages

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def __aiter__(self):
            self._iter = iter(self.messages)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class QueueStub:
        def __init__(self):
            self.bind = AsyncMock()

        def iterator(self):
            return IteratorStub([MessageStub(json.dumps(payload).encode("utf-8"))])

    queue = QueueStub()
    channel.declare_queue.return_value = queue

    async def connect_robust(_: str):
        return connection

    consumer = DeliveryResultConsumer(
        rabbitmq=RabbitMQ(),
        result_handler=result_handler,
        connect_robust=connect_robust,
    )

    await consumer.start()

    channel.declare_exchange.assert_called_once()
    channel.declare_queue.assert_called_once_with("backend.notification-results", durable=True)
    queue.bind.assert_called_once()
    result_handler.handle.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_delivery_result_consumer_start_logs_processing_error_and_continues():
    result_handler = AsyncMock()
    result_handler.handle.side_effect = [RuntimeError("boom"), None]
    connection = AsyncMock()
    channel = AsyncMock()
    exchange = AsyncMock()
    connection.channel.return_value = channel
    channel.declare_exchange.return_value = exchange

    payload = {
        "event_type": "reflection_prompt_result",
        "delivery_id": str(uuid.uuid4()),
        "success": True,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "telegram_message_id": 77,
        "error": None,
    }

    class ProcessContext:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class MessageStub:
        def __init__(self, body: bytes):
            self.body = body

        def process(self):
            return ProcessContext()

    class IteratorStub:
        def __init__(self, messages: list[MessageStub]):
            self.messages = messages

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def __aiter__(self):
            self._iter = iter(self.messages)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class QueueStub:
        def __init__(self):
            self.bind = AsyncMock()

        def iterator(self):
            body = json.dumps(payload).encode("utf-8")
            return IteratorStub([MessageStub(body), MessageStub(body)])

    queue = QueueStub()
    channel.declare_queue.return_value = queue

    async def connect_robust(_: str):
        return connection

    consumer = DeliveryResultConsumer(
        rabbitmq=RabbitMQ(),
        result_handler=result_handler,
        connect_robust=connect_robust,
    )

    with patch(
        "reflebot.apps.reflections.consumers.delivery_result_consumer.logger.exception"
    ) as logger_mock:
        await consumer.start()

    assert result_handler.handle.call_count == 2
    logger_mock.assert_called_once()
    connection.close.assert_called_once()
