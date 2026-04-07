"""
Unit tests для RabbitMQ publisher и Celery config.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import uuid

import pytest

from reflebot.apps.reflections.schemas import (
    ReflectionPromptCommandSchema,
    ReflectionPromptDeadlineUpdateCommandSchema,
)
from reflebot.apps.reflections.services.notification_publisher import (
    NotificationCommandPublisher,
    SimpleAMQPMessage,
)
from reflebot.apps.reflections.tasks import reflection_prompt as task_module
from reflebot.celery_app import build_celery_config, celery_app, create_celery_app
from reflebot.settings import CeleryConfig, Db, Minio, RabbitMQ, Settings


def build_settings() -> Settings:
    return Settings(
        debug=True,
        base_url="http://localhost:8080",
        secret_key="secret",
        telegram_secret_token="token",
        cors_origins="http://localhost:3000,http://localhost:5173",
        db=Db(
            host="localhost",
            port=5432,
            user="postgres",
            password="password",
            name="reflebot",
        ),
        minio=Minio(
            endpoint="http://localhost:9000",
            access_key="key",
            secret_key="secret",
            bucket_name="bucket",
            real_url="http://localhost:9000",
            url_to_change="http://minio:9000",
        ),
        rabbitmq=RabbitMQ(),
        celery=CeleryConfig(),
    )


@pytest.mark.asyncio
async def test_notification_command_publisher_declares_exchange_and_queue():
    connection = AsyncMock()
    channel = AsyncMock()
    exchange = AsyncMock()
    queue = AsyncMock()
    connection.channel.return_value = channel
    channel.declare_exchange.return_value = exchange
    channel.declare_queue.return_value = queue

    async def connect_robust(_: str):
        return connection

    publisher = NotificationCommandPublisher(
        rabbitmq=RabbitMQ(),
        connect_robust=connect_robust,
        message_factory=lambda body: SimpleAMQPMessage(body=body),
    )
    payload = ReflectionPromptCommandSchema(
        delivery_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        telegram_id=12345,
        lection_session_id=uuid.uuid4(),
        message_text="hello",
        parse_mode="HTML",
        buttons=[],
        scheduled_for=datetime.now(timezone.utc),
    )

    await publisher.publish_reflection_prompt(payload)

    channel.declare_exchange.assert_called_once()
    channel.declare_queue.assert_called_once_with("bot.reflection-prompts", durable=True)
    queue.bind.assert_called_once()
    exchange.publish.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_notification_command_publisher_publishes_deadline_update_command():
    connection = AsyncMock()
    channel = AsyncMock()
    exchange = AsyncMock()
    queue = AsyncMock()
    connection.channel.return_value = channel
    channel.declare_exchange.return_value = exchange
    channel.declare_queue.return_value = queue

    async def connect_robust(_: str):
        return connection

    publisher = NotificationCommandPublisher(
        rabbitmq=RabbitMQ(),
        connect_robust=connect_robust,
        message_factory=lambda body: SimpleAMQPMessage(body=body),
    )
    payload = ReflectionPromptDeadlineUpdateCommandSchema(
        delivery_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        telegram_id=12345,
        telegram_message_id=777,
        lection_session_id=uuid.uuid4(),
        message_text="expired",
        parse_mode="HTML",
        buttons=[],
    )

    await publisher.publish_reflection_prompt_deadline_update(payload)

    channel.declare_exchange.assert_called_once()
    channel.declare_queue.assert_called_once_with("bot.reflection-prompts", durable=True)
    queue.bind.assert_called_once()
    exchange.publish.assert_called_once()
    connection.close.assert_called_once()


def test_build_celery_config_uses_rabbitmq_dsn_and_schedule():
    settings_obj = build_settings()

    config = build_celery_config(settings_obj)

    assert config["broker_url"] == settings_obj.rabbitmq.dsn
    assert config["task_default_queue"] == settings_obj.celery.task_default_queue
    assert "scan_due_reflection_prompts" in config["beat_schedule"]
    assert "retry_failed_reflection_prompts" in config["beat_schedule"]
    assert "publish_expired_reflection_prompt_updates" in config["beat_schedule"]


def test_create_celery_app_returns_configured_shim_when_celery_missing():
    settings_obj = build_settings()

    app = create_celery_app(settings_obj)

    assert app.conf["broker_url"] == settings_obj.rabbitmq.dsn
    assert app.conf["task_default_queue"] == settings_obj.celery.task_default_queue


def test_scan_due_reflection_prompts_task_returns_created_and_published_counts(monkeypatch):
    class ScanUseCase:
        async def __call__(self):
            return 2

    class PublishUseCase:
        async def __call__(self):
            return 2

    monkeypatch.setattr(task_module, "_build_scan_use_case", lambda: ScanUseCase())
    monkeypatch.setattr(task_module, "_build_publish_use_case", lambda: PublishUseCase())

    result = task_module.scan_due_reflection_prompts()

    assert result == {"created": 2, "published": 2}


def test_celery_app_registers_reflection_prompt_tasks():
    assert "reflections.scan_due_reflection_prompts" in celery_app.tasks
    assert "reflections.publish_pending_reflection_prompts" in celery_app.tasks
    assert "reflections.retry_failed_reflection_prompts" in celery_app.tasks
    assert "reflections.publish_expired_reflection_prompt_updates" in celery_app.tasks
