import os
from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

__all__ = (
    'get_settings',
    'Settings',
    'settings',
)


class Db(BaseModel):
    """
    Настройки для подключения к базе данных.
    """

    host: str
    port: int
    user: str
    password: str
    name: str
    scheme: str = 'public'

    provider: str = 'postgresql+psycopg_async'

    @property
    def dsn(self) -> str:
        return f'{self.provider}://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}'


class Minio(BaseModel):
    """
    Настройки для MinIO S3.
    """

    endpoint: str
    access_key: str
    secret_key: str
    bucket_name: str
    real_url: str
    url_to_change: str
    standart_path: str = "files"


class RabbitMQ(BaseModel):
    """
    Настройки для RabbitMQ.
    """

    host: str = "localhost"
    port: int = 5672
    user: str = "guest"
    password: str = "guest"
    vhost: str = "/"
    default_queue: str = "celery"
    reflection_prompt_queue: str = "bot.reflection-prompts"
    delivery_result_queue: str = "backend.notification-results"
    notifications_exchange: str = "reflebot.notifications"
    notification_results_exchange: str = "reflebot.notification-results"
    reflection_prompt_routing_key: str = "reflection_prompt.send"
    delivery_result_routing_key: str = "reflection_prompt.result"

    @property
    def dsn(self) -> str:
        vhost = self.vhost if self.vhost.startswith("/") else f"/{self.vhost}"
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}{vhost}"


class CeleryConfig(BaseModel):
    """
    Настройки для Celery.
    """

    task_default_queue: str = "celery"
    beat_schedule_scan_interval_seconds: int = 60
    scan_batch_size: int = 500
    publish_batch_size: int = 500
    retry_failed_interval_seconds: int = 300
    retry_failed_backoff_seconds: int = 300
    retry_failed_max_attempts: int = 3
    task_time_limit: int = 60
    task_soft_time_limit: int = 45
    scan_lookback_hours: int = 168


class Settings(BaseSettings):
    """
    Настройки модели.
    """

    debug: bool
    base_url: str
    base_dir: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    secret_key: str
    telegram_secret_token: str
    telegram_bot_username: str | None = None
    default_deadline: int = 24
    cors_origins: Annotated[list[str], NoDecode]
    

    @field_validator('cors_origins', mode='before')
    @classmethod
    def decode_cors_origins(cls, v: str) -> list[str]:
        return v.split(',')

    db: Db
    minio: Minio
    rabbitmq: RabbitMQ = Field(default_factory=RabbitMQ)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)


    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_nested_delimiter='__',
        case_sensitive=False,
        extra='ignore',
        env_prefix='REFLEBOT_',
    )


def get_settings():
    return Settings()  # type: ignore


settings = get_settings()

SettingsService = Annotated[Settings, Depends(get_settings)]
