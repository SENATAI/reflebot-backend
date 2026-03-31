"""
Consumer очереди результатов доставки уведомлений.
"""

from __future__ import annotations

import json
import logging
from typing import Awaitable, Callable, Protocol

from reflebot.settings import RabbitMQ
from ..schemas import ReflectionPromptResultEventSchema
from ..services.notification_delivery_result import NotificationDeliveryResultHandlerProtocol

logger = logging.getLogger(__name__)

ConnectFactory = Callable[[str], Awaitable[object]]


async def _default_connect_robust(dsn: str) -> object:
    """Ленивая загрузка aio-pika подключения."""
    import aio_pika

    return await aio_pika.connect_robust(dsn)


class DeliveryResultConsumerProtocol(Protocol):
    """Протокол consumer результата доставки."""

    async def handle_message(self, body: bytes | str | dict) -> None:
        """Обработать одно сообщение результата доставки."""
        ...

    async def start(self) -> None:
        """Запустить бесконечное чтение result queue."""
        ...


class DeliveryResultConsumer(DeliveryResultConsumerProtocol):
    """Consumer result queue для обновления статуса NotificationDelivery."""

    def __init__(
        self,
        rabbitmq: RabbitMQ,
        result_handler: NotificationDeliveryResultHandlerProtocol,
        connect_robust: ConnectFactory | None = None,
    ):
        self.rabbitmq = rabbitmq
        self.result_handler = result_handler
        self.connect_robust = connect_robust or _default_connect_robust

    async def handle_message(self, body: bytes | str | dict) -> None:
        """Распарсить payload и делегировать обновление статуса result handler'у."""
        if isinstance(body, bytes):
            raw_payload = json.loads(body.decode("utf-8"))
        elif isinstance(body, str):
            raw_payload = json.loads(body)
        else:
            raw_payload = body

        payload = ReflectionPromptResultEventSchema.model_validate(raw_payload)
        await self.result_handler.handle(payload)

    async def start(self) -> None:
        """Запустить чтение очереди результатов доставки."""
        connection = await self.connect_robust(self.rabbitmq.dsn)
        try:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                self.rabbitmq.notification_results_exchange,
                type="direct",
                durable=True,
            )
            queue = await channel.declare_queue(
                self.rabbitmq.delivery_result_queue,
                durable=True,
            )
            await queue.bind(
                exchange,
                routing_key=self.rabbitmq.delivery_result_routing_key,
            )
            logger.info(
                "Starting notification delivery result consumer.",
                extra={"queue": self.rabbitmq.delivery_result_queue},
            )
            async with queue.iterator() as iterator:
                async for message in iterator:
                    async with message.process():
                        try:
                            await self.handle_message(message.body)
                        except Exception:
                            logger.exception("Failed to process notification delivery result message.")
                            continue
        finally:
            close = getattr(connection, "close", None)
            if close is not None:
                await close()
