"""
Entrypoint для запуска backend result consumer.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from reflebot.apps.reflections.consumers.delivery_result_consumer import DeliveryResultConsumer
from reflebot.apps.reflections.repositories.notification_delivery import NotificationDeliveryRepository
from reflebot.apps.reflections.services.notification_delivery import NotificationDeliveryService
from reflebot.apps.reflections.services.notification_delivery_result import (
    NotificationDeliveryResultHandler,
)
from reflebot.core.db import AsyncSessionFactory
from reflebot.settings import settings


def build_consumer() -> DeliveryResultConsumer:
    """Собрать consumer результатов доставки без FastAPI DI."""
    session = AsyncSessionFactory()
    repository = NotificationDeliveryRepository(session=session)
    delivery_service = NotificationDeliveryService(repository)
    result_handler = NotificationDeliveryResultHandler(delivery_service)
    return DeliveryResultConsumer(
        rabbitmq=settings.rabbitmq,
        result_handler=result_handler,
    )


async def main() -> None:
    """Запустить бесконечный consumer result queue."""
    consumer = build_consumer()
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
