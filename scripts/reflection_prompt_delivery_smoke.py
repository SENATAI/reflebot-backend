"""
End-to-end smoke для reflection prompt delivery workflow.

Сценарий ожидает, что уже подняты:
- PostgreSQL
- RabbitMQ
- Celery Worker
- Celery Beat
- backend result consumer
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aio_pika
from aio_pika.exceptions import QueueEmpty
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from reflebot.apps.reflections.enums import NotificationDeliveryStatus
from reflebot.apps.reflections.models import (
    CourseSession,
    LectionSession,
    NotificationDelivery,
    Student,
    StudentLection,
)
from reflebot.apps.reflections.schemas import ReflectionPromptCommandSchema, ReflectionPromptResultEventSchema
from reflebot.core.db import AsyncSessionFactory
from reflebot.settings import settings


class SmokeFailure(RuntimeError):
    """Ошибка smoke-проверки."""


def log(message: str) -> None:
    """Напечатать шаг smoke-проверки."""
    print(f"[reflection-prompt-smoke] {message}", flush=True)


def require(condition: bool, message: str) -> None:
    """Проверить ожидаемое условие."""
    if not condition:
        raise SmokeFailure(message)


def now_utc() -> datetime:
    """Получить текущий UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SmokeFactory:
    """Фабрика данных smoke-проверки с безопасной очисткой."""

    course_ids: list[uuid.UUID] = field(default_factory=list)
    lection_ids: list[uuid.UUID] = field(default_factory=list)
    student_ids: list[uuid.UUID] = field(default_factory=list)

    async def create_course_with_lections(self) -> dict[str, uuid.UUID]:
        """Создать курс, две лекции и двух студентов для smoke."""
        current_time = now_utc()
        course_id = uuid.uuid4()
        success_lection_id = uuid.uuid4()
        failure_lection_id = uuid.uuid4()
        success_student_id = uuid.uuid4()
        failure_student_id = uuid.uuid4()

        async with AsyncSessionFactory() as session, session.begin():
            session.add(
                CourseSession(
                    id=course_id,
                    name=f"Reflection Prompt Smoke {course_id}",
                    started_at=current_time - timedelta(hours=3),
                    ended_at=current_time + timedelta(hours=1),
                )
            )
            session.add_all(
                [
                    LectionSession(
                        id=success_lection_id,
                        course_session_id=course_id,
                        topic="Smoke Success Topic",
                        started_at=current_time - timedelta(hours=2),
                        ended_at=current_time - timedelta(minutes=20),
                    ),
                    LectionSession(
                        id=failure_lection_id,
                        course_session_id=course_id,
                        topic="Smoke Failure Topic",
                        started_at=current_time - timedelta(hours=2),
                        ended_at=current_time - timedelta(minutes=15),
                    ),
                    Student(
                        id=success_student_id,
                        full_name="Smoke Success Student",
                        telegram_username=f"smoke_success_{success_student_id.hex[:8]}",
                        telegram_id=int(success_student_id.int % 10**12),
                        is_active=True,
                    ),
                    Student(
                        id=failure_student_id,
                        full_name="Smoke Failure Student",
                        telegram_username=f"smoke_failure_{failure_student_id.hex[:8]}",
                        telegram_id=int(failure_student_id.int % 10**12),
                        is_active=True,
                    ),
                ]
            )
            session.add_all(
                [
                    StudentLection(
                        id=uuid.uuid4(),
                        student_id=success_student_id,
                        lection_session_id=success_lection_id,
                    ),
                    StudentLection(
                        id=uuid.uuid4(),
                        student_id=failure_student_id,
                        lection_session_id=failure_lection_id,
                    ),
                ]
            )

        self.course_ids.append(course_id)
        self.lection_ids.extend([success_lection_id, failure_lection_id])
        self.student_ids.extend([success_student_id, failure_student_id])
        return {
            "success_lection_id": success_lection_id,
            "failure_lection_id": failure_lection_id,
            "success_student_id": success_student_id,
            "failure_student_id": failure_student_id,
        }

    async def get_delivery(
        self,
        *,
        lection_session_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> NotificationDelivery | None:
        """Получить delivery по связке лекция-студент."""
        async with AsyncSessionFactory() as session:
            stmt = sa.select(NotificationDelivery).where(
                NotificationDelivery.lection_session_id == lection_session_id,
                NotificationDelivery.student_id == student_id,
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def wait_for_status(
        self,
        *,
        lection_session_id: uuid.UUID,
        student_id: uuid.UUID,
        expected_status: NotificationDeliveryStatus,
        timeout_seconds: int = 20,
    ) -> NotificationDelivery:
        """Дождаться ожидаемого статуса delivery."""
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            delivery = await self.get_delivery(
                lection_session_id=lection_session_id,
                student_id=student_id,
            )
            if delivery is not None and delivery.status == expected_status:
                return delivery
            await asyncio.sleep(0.5)
        raise SmokeFailure(
            f"Не дождались статуса {expected_status} для lection={lection_session_id} student={student_id}"
        )

    async def cleanup(self) -> None:
        """Очистить только данные smoke-проверки."""
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
                await session.execute(sa.delete(Student).where(Student.id.in_(self.student_ids)))
            if self.course_ids:
                await session.execute(
                    sa.delete(CourseSession).where(CourseSession.id.in_(self.course_ids))
                )


class RabbitBotConsumerProbe:
    """Тестовый bot-consumer для smoke-проверки."""

    def __init__(self) -> None:
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.abc.AbstractChannel | None = None
        self.prompt_queue: aio_pika.abc.AbstractQueue | None = None
        self.result_exchange: aio_pika.abc.AbstractExchange | None = None

    async def start(self) -> None:
        """Подключиться к RabbitMQ и подготовить очереди."""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq.dsn)
        self.channel = await self.connection.channel()
        prompt_exchange = await self.channel.declare_exchange(
            settings.rabbitmq.notifications_exchange,
            type="direct",
            durable=True,
        )
        self.prompt_queue = await self.channel.declare_queue(
            settings.rabbitmq.reflection_prompt_queue,
            durable=True,
        )
        await self.prompt_queue.bind(
            prompt_exchange,
            routing_key=settings.rabbitmq.reflection_prompt_routing_key,
        )
        self.result_exchange = await self.channel.declare_exchange(
            settings.rabbitmq.notification_results_exchange,
            type="direct",
            durable=True,
        )
        await self.prompt_queue.purge()

    async def wait_for_commands(self, expected_count: int, timeout_seconds: int = 20) -> list[ReflectionPromptCommandSchema]:
        """Дождаться нужного количества команд для bot-consumer."""
        require(self.prompt_queue is not None, "Prompt queue не подготовлена")
        commands: list[ReflectionPromptCommandSchema] = []
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while len(commands) < expected_count and asyncio.get_running_loop().time() < deadline:
            try:
                message = await self.prompt_queue.get(timeout=1)
            except QueueEmpty:
                await asyncio.sleep(0.2)
                continue
            try:
                command = ReflectionPromptCommandSchema.model_validate_json(message.body)
                commands.append(command)
            finally:
                await message.ack()

        if len(commands) != expected_count:
            raise SmokeFailure(
                f"Ожидали {expected_count} команд в prompt queue, получили {len(commands)}"
            )
        return commands

    async def publish_result(self, payload: ReflectionPromptResultEventSchema) -> None:
        """Опубликовать result event от тестового bot-consumer."""
        require(self.result_exchange is not None, "Result exchange не подготовлен")
        await self.result_exchange.publish(
            aio_pika.Message(
                body=payload.model_dump_json().encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=settings.rabbitmq.delivery_result_routing_key,
        )

    async def close(self) -> None:
        """Закрыть RabbitMQ ресурсы."""
        if self.channel is not None:
            await self.channel.close()
        if self.connection is not None:
            await self.connection.close()


async def main() -> None:
    """Запустить живой E2E smoke reflection prompt workflow."""
    factory = SmokeFactory()
    probe = RabbitBotConsumerProbe()
    try:
        log("Подключаем тестовый bot-consumer probe к RabbitMQ.")
        await probe.start()

        log("Создаём тестовые курс, лекции и студентов в PostgreSQL.")
        entities = await factory.create_course_with_lections()

        log("Ждём команды send_reflection_prompt из RabbitMQ от Celery beat/worker.")
        commands = await probe.wait_for_commands(expected_count=2, timeout_seconds=20)
        require(
            {command.lection_session_id for command in commands}
            == {entities["success_lection_id"], entities["failure_lection_id"]},
            "В prompt queue пришли не те лекции, которые ожидались для smoke-проверки.",
        )
        for command in commands:
            require(command.event_type == "send_reflection_prompt", "Неверный event_type команды.")
            require(command.parse_mode == "HTML", "Ожидался parse_mode HTML.")
            require(len(command.buttons) == 1, "Ожидалась одна кнопка для старта рефлексии.")
            require(
                command.buttons[0].action
                == f"student_start_reflection:{command.lection_session_id}",
                "У prompt-команды неверный action кнопки записи кружка.",
            )
            require(
                "рефлекс" in command.message_text.lower(),
                "В тексте prompt-команды нет ожидаемого упоминания рефлексии.",
            )
            require(
                (
                    command.lection_session_id == entities["success_lection_id"]
                    and "Smoke Success Topic" in command.message_text
                )
                or (
                    command.lection_session_id == entities["failure_lection_id"]
                    and "Smoke Failure Topic" in command.message_text
                ),
                "В prompt-команде не совпала тема лекции с ожидаемой сущностью.",
            )

        log("Проверяем, что worker перевёл delivery в queued.")
        queued_success = await factory.wait_for_status(
            lection_session_id=entities["success_lection_id"],
            student_id=entities["success_student_id"],
            expected_status=NotificationDeliveryStatus.QUEUED,
        )
        queued_failure = await factory.wait_for_status(
            lection_session_id=entities["failure_lection_id"],
            student_id=entities["failure_student_id"],
            expected_status=NotificationDeliveryStatus.QUEUED,
        )

        log("Публикуем success и failure result events как тестовый bot-consumer.")
        await probe.publish_result(
            ReflectionPromptResultEventSchema(
                delivery_id=queued_success.id,
                success=True,
                sent_at=now_utc(),
                telegram_message_id=101,
                error=None,
            )
        )
        await probe.publish_result(
            ReflectionPromptResultEventSchema(
                delivery_id=queued_failure.id,
                success=False,
                sent_at=None,
                telegram_message_id=None,
                error="smoke bot failure",
            )
        )

        log("Ждём, пока backend result consumer обновит статусы в PostgreSQL.")
        sent_delivery = await factory.wait_for_status(
            lection_session_id=entities["success_lection_id"],
            student_id=entities["success_student_id"],
            expected_status=NotificationDeliveryStatus.SENT,
        )
        failed_delivery = await factory.wait_for_status(
            lection_session_id=entities["failure_lection_id"],
            student_id=entities["failure_student_id"],
            expected_status=NotificationDeliveryStatus.FAILED,
        )
        require(sent_delivery.sent_at is not None, "У успешной доставки не проставлен sent_at.")
        require(sent_delivery.attempts == 1, "У успешной доставки ожидалась 1 попытка.")
        require(failed_delivery.attempts == 1, "У failed доставки ожидалась 1 попытка.")
        require(
            failed_delivery.last_error == "smoke bot failure",
            "У failed доставки не сохранилась ошибка bot-consumer.",
        )

        log("E2E smoke успешно завершён.")
    finally:
        await probe.close()
        await factory.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
