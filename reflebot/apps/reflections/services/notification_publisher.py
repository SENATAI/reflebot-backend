"""
Publisher команд доставки уведомлений в RabbitMQ.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from reflebot.settings import RabbitMQ
from ..schemas import (
    CourseBroadcastCommandSchema,
    ReflectionPromptCommandSchema,
    ReflectionPromptDeadlineUpdateCommandSchema,
)

logger = logging.getLogger(__name__)


class NotificationCommandPublisherProtocol(Protocol):
    """Протокол publisher команд для bot-consumer."""

    async def publish_reflection_prompt(self, payload: ReflectionPromptCommandSchema) -> None:
        """Опубликовать команду send_reflection_prompt."""
        ...

    async def publish_reflection_prompt_deadline_update(
        self,
        payload: ReflectionPromptDeadlineUpdateCommandSchema,
    ) -> None:
        """Опубликовать команду update_reflection_prompt."""
        ...

    async def publish_course_message(self, payload: CourseBroadcastCommandSchema) -> None:
        """Опубликовать команду send_course_message."""
        ...


ConnectFactory = Callable[[str], Awaitable[object]]
MessageFactory = Callable[[bytes], object]


@dataclass(slots=True)
class SimpleAMQPMessage:
    """Простой message-object для тестов и fallback-режима."""

    body: bytes
    content_type: str = "application/json"
    delivery_mode: str = "persistent"


async def _default_connect_robust(dsn: str) -> object:
    """Ленивая загрузка aio-pika подключения."""
    try:
        import aio_pika
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise RuntimeError("aio-pika is required to publish notification commands.") from exc
    return await aio_pika.connect_robust(dsn)


def _default_message_factory(body: bytes) -> object:
    """Ленивая сборка AMQP-сообщения."""
    try:
        import aio_pika
    except ImportError:  # pragma: no cover - зависит от окружения
        return SimpleAMQPMessage(body=body)
    return aio_pika.Message(
        body=body,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )


class NotificationCommandPublisher(NotificationCommandPublisherProtocol):
    """Publisher команд доставки уведомлений в RabbitMQ."""

    def __init__(
        self,
        rabbitmq: RabbitMQ,
        connect_robust: ConnectFactory | None = None,
        message_factory: MessageFactory | None = None,
    ):
        self.rabbitmq = rabbitmq
        self.connect_robust = connect_robust or _default_connect_robust
        self.message_factory = message_factory or _default_message_factory

    async def publish_reflection_prompt(self, payload: ReflectionPromptCommandSchema) -> None:
        """Опубликовать команду send_reflection_prompt в очередь бота."""
        await self._publish_command(
            payload=payload,
            log_action="reflection prompt",
            extra={
                "delivery_id": str(payload.delivery_id),
                "student_id": str(payload.student_id),
                "lection_session_id": str(payload.lection_session_id),
                "telegram_id": payload.telegram_id,
            },
        )

    async def publish_reflection_prompt_deadline_update(
        self,
        payload: ReflectionPromptDeadlineUpdateCommandSchema,
    ) -> None:
        """Опубликовать команду update_reflection_prompt в очередь бота."""
        await self._publish_command(
            payload=payload,
            log_action="reflection prompt deadline update",
            extra={
                "delivery_id": str(payload.delivery_id),
                "student_id": str(payload.student_id),
                "lection_session_id": str(payload.lection_session_id),
                "telegram_id": payload.telegram_id,
                "telegram_message_id": payload.telegram_message_id,
            },
        )

    async def publish_course_message(self, payload: CourseBroadcastCommandSchema) -> None:
        """Опубликовать команду send_course_message в очередь бота."""
        await self._publish_command(
            payload=payload,
            log_action="course message",
            extra={
                "course_id": str(payload.course_id),
                "student_id": str(payload.student_id),
                "telegram_id": payload.telegram_id,
            },
        )

    async def _publish_command(
        self,
        payload: (
            ReflectionPromptCommandSchema
            | ReflectionPromptDeadlineUpdateCommandSchema
            | CourseBroadcastCommandSchema
        ),
        log_action: str,
        extra: dict[str, object],
    ) -> None:
        """Опубликовать bot-команду в очередь."""
        body = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")
        logger.info(
            "Publishing %s command.",
            log_action,
            extra=extra,
        )
        connection = await self.connect_robust(self.rabbitmq.dsn)
        try:
            channel = await connection.channel(publisher_confirms=True)
            exchange = await channel.declare_exchange(
                self.rabbitmq.notifications_exchange,
                type="direct",
                durable=True,
            )
            queue = await channel.declare_queue(
                self.rabbitmq.reflection_prompt_queue,
                durable=True,
            )
            await queue.bind(
                exchange,
                routing_key=self.rabbitmq.reflection_prompt_routing_key,
            )
            message = self.message_factory(body)
            await exchange.publish(
                message,
                routing_key=self.rabbitmq.reflection_prompt_routing_key,
            )
            logger.info(
                "%s command published.",
                log_action.capitalize(),
                extra=extra,
            )
        finally:
            close = getattr(connection, "close", None)
            if close is not None:
                await close()
