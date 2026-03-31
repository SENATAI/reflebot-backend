"""
Integration tests for notification delivery workflow with PostgreSQL and RabbitMQ.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import aio_pika
import pytest
import pytest_asyncio
import sqlalchemy as sa

from reflebot.apps.reflections.consumers.delivery_result_consumer import DeliveryResultConsumer
from reflebot.apps.reflections.datetime_utils import calculate_lection_deadline
from reflebot.apps.reflections.enums import NotificationDeliveryStatus
from reflebot.apps.reflections.models import (
    CourseSession,
    LectionSession,
    NotificationDelivery,
    Student,
    StudentLection,
)
from reflebot.apps.reflections.repositories.lection import LectionSessionRepository
from reflebot.apps.reflections.repositories.notification_delivery import NotificationDeliveryRepository
from reflebot.apps.reflections.repositories.student_lection import StudentLectionRepository
from reflebot.apps.reflections.schemas import ReflectionPromptCommandSchema, ReflectionPromptResultEventSchema
from reflebot.apps.reflections.services.notification_delivery import NotificationDeliveryService
from reflebot.apps.reflections.services.notification_delivery_result import (
    NotificationDeliveryResultHandler,
)
from reflebot.apps.reflections.services.reflection_prompt_scan import ReflectionPromptScanService
from reflebot.apps.reflections.tasks.reflection_prompt import publish_pending_reflection_prompts
from reflebot.apps.reflections.use_cases.notification_delivery import ScanDueReflectionPromptsUseCase
from reflebot.core.db import AsyncSessionFactory
from reflebot.settings import settings

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _telegram_id() -> int:
    return int(uuid.uuid4().int % 10**12)


@dataclass(slots=True)
class RabbitMQResources:
    connection: aio_pika.RobustConnection
    channel: aio_pika.abc.AbstractChannel
    prompt_exchange: aio_pika.abc.AbstractExchange
    prompt_queue: aio_pika.abc.AbstractQueue
    result_exchange: aio_pika.abc.AbstractExchange
    result_queue: aio_pika.abc.AbstractQueue

    async def get_prompt_command(self) -> ReflectionPromptCommandSchema:
        message = await self.prompt_queue.get(timeout=5)
        try:
            return ReflectionPromptCommandSchema.model_validate_json(message.body)
        finally:
            await message.ack()

    async def publish_result_event(self, payload: ReflectionPromptResultEventSchema) -> None:
        body = payload.model_dump_json().encode("utf-8")
        await self.result_exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=settings.rabbitmq.delivery_result_routing_key,
        )

    async def get_result_body(self) -> bytes:
        message = await self.result_queue.get(timeout=5)
        try:
            return message.body
        finally:
            await message.ack()


@dataclass(slots=True)
class IntegrationFactory:
    course_ids: list[uuid.UUID] = field(default_factory=list)
    lection_ids: list[uuid.UUID] = field(default_factory=list)
    student_ids: list[uuid.UUID] = field(default_factory=list)

    async def create_course_with_lections(
        self,
        lection_specs: list[dict[str, datetime | str]],
    ) -> tuple[uuid.UUID, list[uuid.UUID]]:
        course_id = uuid.uuid4()
        lection_ids = [uuid.uuid4() for _ in lection_specs]
        started_at = min(spec["started_at"] for spec in lection_specs)
        ended_at = max(spec["ended_at"] for spec in lection_specs)

        async with AsyncSessionFactory() as session, session.begin():
            course = CourseSession(
                id=course_id,
                name=f"Integration Course {course_id}",
                started_at=started_at,
                ended_at=ended_at,
            )
            session.add(course)
            for lection_id, spec in zip(lection_ids, lection_specs, strict=True):
                session.add(
                    LectionSession(
                        id=lection_id,
                        course_session_id=course_id,
                        topic=str(spec["topic"]),
                        started_at=spec["started_at"],
                        ended_at=spec["ended_at"],
                        deadline=calculate_lection_deadline(
                            spec["ended_at"],
                            settings.default_deadline,
                        ),
                    )
                )

        self.course_ids.append(course_id)
        self.lection_ids.extend(lection_ids)
        return course_id, lection_ids

    async def create_student(
        self,
        *,
        telegram_id: int | None = None,
        is_active: bool = True,
    ) -> uuid.UUID:
        student_id = uuid.uuid4()
        async with AsyncSessionFactory() as session, session.begin():
            session.add(
                Student(
                    id=student_id,
                    full_name=f"Integration Student {student_id}",
                    telegram_username=f"student_{student_id.hex[:8]}",
                    telegram_id=telegram_id,
                    is_active=is_active,
                )
            )

        self.student_ids.append(student_id)
        return student_id

    async def attach_student_to_lection(
        self,
        *,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        async with AsyncSessionFactory() as session, session.begin():
            session.add(
                StudentLection(
                    id=uuid.uuid4(),
                    student_id=student_id,
                    lection_session_id=lection_session_id,
                    created_at=created_at or _now(),
                    updated_at=updated_at or created_at or _now(),
                )
            )

    async def update_lection_ended_at(self, lection_session_id: uuid.UUID, ended_at: datetime) -> None:
        async with AsyncSessionFactory() as session, session.begin():
            await session.execute(
                sa.update(LectionSession)
                .where(LectionSession.id == lection_session_id)
                .values(
                    ended_at=ended_at,
                    deadline=calculate_lection_deadline(ended_at, settings.default_deadline),
                )
            )

    async def get_delivery(
        self,
        *,
        lection_session_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> NotificationDelivery | None:
        async with AsyncSessionFactory() as session:
            stmt = sa.select(NotificationDelivery).where(
                NotificationDelivery.lection_session_id == lection_session_id,
                NotificationDelivery.student_id == student_id,
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def list_deliveries(self) -> list[NotificationDelivery]:
        async with AsyncSessionFactory() as session:
            stmt = sa.select(NotificationDelivery).where(
                NotificationDelivery.student_id.in_(self.student_ids)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def cleanup(self) -> None:
        async with AsyncSessionFactory() as session, session.begin():
            if self.lection_ids:
                await session.execute(
                    sa.delete(NotificationDelivery).where(
                        NotificationDelivery.lection_session_id.in_(self.lection_ids)
                    )
                )
                await session.execute(
                    sa.delete(StudentLection).where(
                        StudentLection.lection_session_id.in_(self.lection_ids)
                    )
                )
                await session.execute(
                    sa.delete(LectionSession).where(LectionSession.id.in_(self.lection_ids))
                )
            if self.student_ids:
                await session.execute(
                    sa.delete(Student).where(Student.id.in_(self.student_ids))
                )
            if self.course_ids:
                await session.execute(
                    sa.delete(CourseSession).where(CourseSession.id.in_(self.course_ids))
                )


def build_scan_use_case(*, scan_batch_size: int) -> ScanDueReflectionPromptsUseCase:
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
        scan_batch_size=scan_batch_size,
    )


def build_result_consumer() -> DeliveryResultConsumer:
    session = AsyncSessionFactory()
    notification_delivery_repository = NotificationDeliveryRepository(session=session)
    notification_delivery_service = NotificationDeliveryService(notification_delivery_repository)
    result_handler = NotificationDeliveryResultHandler(notification_delivery_service)
    return DeliveryResultConsumer(
        rabbitmq=settings.rabbitmq,
        result_handler=result_handler,
    )


@pytest_asyncio.fixture
async def rabbitmq_resources() -> RabbitMQResources:
    original_notifications_exchange = settings.rabbitmq.notifications_exchange
    original_notification_results_exchange = settings.rabbitmq.notification_results_exchange
    original_prompt_routing_key = settings.rabbitmq.reflection_prompt_routing_key
    original_result_routing_key = settings.rabbitmq.delivery_result_routing_key
    original_prompt_queue = settings.rabbitmq.reflection_prompt_queue
    original_result_queue = settings.rabbitmq.delivery_result_queue
    test_suffix = uuid.uuid4().hex[:8]
    settings.rabbitmq.notifications_exchange = (
        f"{original_notifications_exchange}.test.{test_suffix}"
    )
    settings.rabbitmq.notification_results_exchange = (
        f"{original_notification_results_exchange}.test.{test_suffix}"
    )
    settings.rabbitmq.reflection_prompt_routing_key = (
        f"{original_prompt_routing_key}.test.{test_suffix}"
    )
    settings.rabbitmq.delivery_result_routing_key = (
        f"{original_result_routing_key}.test.{test_suffix}"
    )
    settings.rabbitmq.reflection_prompt_queue = f"{original_prompt_queue}.test.{test_suffix}"
    settings.rabbitmq.delivery_result_queue = f"{original_result_queue}.test.{test_suffix}"

    connection = await aio_pika.connect_robust(settings.rabbitmq.dsn)
    channel = await connection.channel()
    prompt_exchange = await channel.declare_exchange(
        settings.rabbitmq.notifications_exchange,
        type="direct",
        durable=True,
    )
    prompt_queue = await channel.declare_queue(
        settings.rabbitmq.reflection_prompt_queue,
        durable=True,
    )
    await prompt_queue.bind(
        prompt_exchange,
        routing_key=settings.rabbitmq.reflection_prompt_routing_key,
    )
    result_exchange = await channel.declare_exchange(
        settings.rabbitmq.notification_results_exchange,
        type="direct",
        durable=True,
    )
    result_queue = await channel.declare_queue(
        settings.rabbitmq.delivery_result_queue,
        durable=True,
    )
    await result_queue.bind(
        result_exchange,
        routing_key=settings.rabbitmq.delivery_result_routing_key,
    )
    await prompt_queue.purge()
    await result_queue.purge()

    resources = RabbitMQResources(
        connection=connection,
        channel=channel,
        prompt_exchange=prompt_exchange,
        prompt_queue=prompt_queue,
        result_exchange=result_exchange,
        result_queue=result_queue,
    )
    try:
        yield resources
    finally:
        await prompt_queue.purge()
        await result_queue.purge()
        await prompt_queue.unbind(
            prompt_exchange,
            routing_key=settings.rabbitmq.reflection_prompt_routing_key,
        )
        await result_queue.unbind(
            result_exchange,
            routing_key=settings.rabbitmq.delivery_result_routing_key,
        )
        await prompt_queue.delete(if_unused=False, if_empty=False)
        await result_queue.delete(if_unused=False, if_empty=False)
        await channel.close()
        await connection.close()
        settings.rabbitmq.notifications_exchange = original_notifications_exchange
        settings.rabbitmq.notification_results_exchange = original_notification_results_exchange
        settings.rabbitmq.reflection_prompt_routing_key = original_prompt_routing_key
        settings.rabbitmq.delivery_result_routing_key = original_result_routing_key
        settings.rabbitmq.reflection_prompt_queue = original_prompt_queue
        settings.rabbitmq.delivery_result_queue = original_result_queue


@pytest_asyncio.fixture
async def integration_factory(rabbitmq_resources: RabbitMQResources) -> IntegrationFactory:
    factory = IntegrationFactory()
    try:
        yield factory
    finally:
        await factory.cleanup()


@pytest.mark.asyncio
async def test_integration_delivery_workflow_marks_sent_after_result_event(
    integration_factory: IntegrationFactory,
    rabbitmq_resources: RabbitMQResources,
):
    now = _now()
    _, lection_ids = await integration_factory.create_course_with_lections(
        [
            {
                "topic": "Integration Success Topic",
                "started_at": now - timedelta(hours=2),
                "ended_at": now - timedelta(minutes=30),
            }
        ]
    )
    student_id = await integration_factory.create_student(telegram_id=_telegram_id())
    await integration_factory.attach_student_to_lection(
        student_id=student_id,
        lection_session_id=lection_ids[0],
    )

    created = await build_scan_use_case(scan_batch_size=50)(now=now)

    assert created == 1
    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    assert delivery.status == NotificationDeliveryStatus.PENDING

    publish_result = await asyncio.to_thread(publish_pending_reflection_prompts)

    assert publish_result == {"published": 1}
    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    assert delivery.status == NotificationDeliveryStatus.QUEUED

    command = await rabbitmq_resources.get_prompt_command()
    assert command.delivery_id == delivery.id
    assert command.student_id == student_id
    assert command.lection_session_id == lection_ids[0]
    assert command.event_type == "send_reflection_prompt"

    result_event = ReflectionPromptResultEventSchema(
        delivery_id=delivery.id,
        success=True,
        sent_at=_now(),
        telegram_message_id=101,
        error=None,
    )
    await rabbitmq_resources.publish_result_event(result_event)
    body = await rabbitmq_resources.get_result_body()
    consumer = build_result_consumer()
    await consumer.handle_message(body)

    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    assert delivery.status == NotificationDeliveryStatus.SENT
    assert delivery.sent_at is not None
    assert delivery.attempts == 1


@pytest.mark.asyncio
async def test_integration_delivery_workflow_marks_failed_after_error_result_event(
    integration_factory: IntegrationFactory,
    rabbitmq_resources: RabbitMQResources,
):
    now = _now()
    _, lection_ids = await integration_factory.create_course_with_lections(
        [
            {
                "topic": "Integration Failure Topic",
                "started_at": now - timedelta(hours=2),
                "ended_at": now - timedelta(minutes=20),
            }
        ]
    )
    student_id = await integration_factory.create_student(telegram_id=_telegram_id())
    await integration_factory.attach_student_to_lection(
        student_id=student_id,
        lection_session_id=lection_ids[0],
    )

    created = await build_scan_use_case(scan_batch_size=50)(now=now)

    assert created == 1
    publish_result = await asyncio.to_thread(publish_pending_reflection_prompts)
    assert publish_result == {"published": 1}

    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    command = await rabbitmq_resources.get_prompt_command()
    assert command.delivery_id == delivery.id

    result_event = ReflectionPromptResultEventSchema(
        delivery_id=delivery.id,
        success=False,
        sent_at=None,
        telegram_message_id=None,
        error="telegram temporary failure",
    )
    await rabbitmq_resources.publish_result_event(result_event)
    body = await rabbitmq_resources.get_result_body()
    consumer = build_result_consumer()
    await consumer.handle_message(body)

    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    assert delivery.status == NotificationDeliveryStatus.FAILED
    assert delivery.last_error == "telegram temporary failure"
    assert delivery.attempts == 1


@pytest.mark.asyncio
async def test_integration_late_attached_student_gets_delivery_for_old_lection(
    integration_factory: IntegrationFactory,
):
    now = _now()
    old_ended_at = now - timedelta(hours=settings.celery.scan_lookback_hours + 24)
    _, lection_ids = await integration_factory.create_course_with_lections(
        [
            {
                "topic": "Late Attached Topic",
                "started_at": old_ended_at - timedelta(hours=2),
                "ended_at": old_ended_at,
            }
        ]
    )
    student_id = await integration_factory.create_student(telegram_id=_telegram_id())
    await integration_factory.attach_student_to_lection(
        student_id=student_id,
        lection_session_id=lection_ids[0],
        created_at=now,
        updated_at=now,
    )

    created = await build_scan_use_case(scan_batch_size=50)(now=now)

    assert created == 1
    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    assert delivery.status == NotificationDeliveryStatus.PENDING


@pytest.mark.asyncio
async def test_integration_old_lection_with_old_attachment_still_gets_delivery(
    integration_factory: IntegrationFactory,
):
    now = _now()
    old_ended_at = now - timedelta(hours=settings.celery.scan_lookback_hours + 24)
    _, lection_ids = await integration_factory.create_course_with_lections(
        [
            {
                "topic": "Old Historical Topic",
                "started_at": old_ended_at - timedelta(hours=2),
                "ended_at": old_ended_at,
            }
        ]
    )
    student_id = await integration_factory.create_student(telegram_id=_telegram_id())
    historical_attached_at = old_ended_at - timedelta(hours=1)
    await integration_factory.attach_student_to_lection(
        student_id=student_id,
        lection_session_id=lection_ids[0],
        created_at=historical_attached_at,
        updated_at=historical_attached_at,
    )

    created = await build_scan_use_case(scan_batch_size=50)(now=now)

    assert created == 1
    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    assert delivery.status == NotificationDeliveryStatus.PENDING


@pytest.mark.asyncio
async def test_integration_changed_ended_at_triggers_delivery_after_move_to_past(
    integration_factory: IntegrationFactory,
):
    now = _now()
    _, lection_ids = await integration_factory.create_course_with_lections(
        [
            {
                "topic": "Changed Ended At Topic",
                "started_at": now - timedelta(hours=1),
                "ended_at": now + timedelta(hours=2),
            }
        ]
    )
    student_id = await integration_factory.create_student(telegram_id=_telegram_id())
    await integration_factory.attach_student_to_lection(
        student_id=student_id,
        lection_session_id=lection_ids[0],
    )

    created_before = await build_scan_use_case(scan_batch_size=50)(now=now)

    assert created_before == 0

    moved_to_past = now - timedelta(minutes=10)
    await integration_factory.update_lection_ended_at(lection_ids[0], moved_to_past)

    created_after = await build_scan_use_case(scan_batch_size=50)(now=now)

    assert created_after == 1
    delivery = await integration_factory.get_delivery(
        lection_session_id=lection_ids[0],
        student_id=student_id,
    )
    assert delivery is not None
    assert delivery.scheduled_for.replace(microsecond=0) == moved_to_past.replace(microsecond=0)


@pytest.mark.asyncio
async def test_integration_bounded_scan_prioritizes_oldest_historical_dataset(
    integration_factory: IntegrationFactory,
):
    now = _now()
    old_cutoff = now - timedelta(hours=settings.celery.scan_lookback_hours + 24)
    old_specs = [
        {
            "topic": f"Historical Topic {index}",
            "started_at": old_cutoff - timedelta(hours=3, minutes=index),
            "ended_at": old_cutoff - timedelta(hours=1, minutes=index),
        }
        for index in range(30)
    ]
    recent_specs = [
        {
            "topic": f"Recent Topic {index}",
            "started_at": now - timedelta(hours=2, minutes=index),
            "ended_at": now - timedelta(minutes=15 + index),
        }
        for index in range(8)
    ]
    _, old_lection_ids = await integration_factory.create_course_with_lections(old_specs)
    _, recent_lection_ids = await integration_factory.create_course_with_lections(recent_specs)
    student_id = await integration_factory.create_student(telegram_id=_telegram_id())

    historical_created_at = now - timedelta(hours=settings.celery.scan_lookback_hours + 12)
    for lection_id in old_lection_ids:
        await integration_factory.attach_student_to_lection(
            student_id=student_id,
            lection_session_id=lection_id,
            created_at=historical_created_at,
            updated_at=historical_created_at,
        )
    for lection_id in recent_lection_ids:
        await integration_factory.attach_student_to_lection(
            student_id=student_id,
            lection_session_id=lection_id,
        )

    created = await build_scan_use_case(scan_batch_size=5)(now=now)

    assert created == 5
    deliveries = await integration_factory.list_deliveries()
    assert len(deliveries) == 5
    old_set = set(old_lection_ids)
    assert all(delivery.lection_session_id in old_set for delivery in deliveries)
