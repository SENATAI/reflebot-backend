"""
Celery app для фоновых задач Reflebot.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from reflebot.settings import Settings, settings

try:  # pragma: no cover - зависит от окружения
    from celery import Celery as _Celery
except ImportError:  # pragma: no cover - зависит от окружения
    _Celery = None


def build_celery_config(settings_obj: Settings) -> dict[str, Any]:
    """Собрать конфигурацию Celery из Settings."""
    return {
        "broker_url": settings_obj.rabbitmq.dsn,
        "task_default_queue": settings_obj.celery.task_default_queue,
        "task_time_limit": settings_obj.celery.task_time_limit,
        "task_soft_time_limit": settings_obj.celery.task_soft_time_limit,
        "beat_schedule": {
            "scan_due_reflection_prompts": {
                "task": "reflections.scan_due_reflection_prompts",
                "schedule": settings_obj.celery.beat_schedule_scan_interval_seconds,
            },
            "retry_failed_reflection_prompts": {
                "task": "reflections.retry_failed_reflection_prompts",
                "schedule": settings_obj.celery.retry_failed_interval_seconds,
            },
            "publish_expired_reflection_prompt_updates": {
                "task": "reflections.publish_expired_reflection_prompt_updates",
                "schedule": settings_obj.celery.deadline_update_interval_seconds,
            },
        },
    }


@dataclass(slots=True)
class CeleryTaskShim:
    """Упрощённый shim для отсутствующего celery в unit-тестах."""

    conf: dict[str, Any] = field(default_factory=dict)

    def task(self, *decorator_args: Any, **decorator_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Вернуть no-op декоратор с интерфейсом task."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            setattr(func, "delay", func)
            setattr(func, "task_name", decorator_kwargs.get("name"))
            return func

        return decorator


def create_celery_app(settings_obj: Settings = settings) -> Any:
    """Создать Celery app или fallback shim."""
    config = build_celery_config(settings_obj)
    if _Celery is None:
        shim = CeleryTaskShim()
        shim.conf.update(config)
        return shim

    celery_app = _Celery(
        "reflebot",
        broker=settings_obj.rabbitmq.dsn,
    )
    celery_app.conf.update(config)
    return celery_app


celery_app = create_celery_app()


def _register_task_modules() -> None:
    """Импортировать Celery task-модули, чтобы worker видел зарегистрированные задачи."""
    from reflebot.apps.reflections.tasks import reflection_prompt  # noqa: F401


_register_task_modules()
