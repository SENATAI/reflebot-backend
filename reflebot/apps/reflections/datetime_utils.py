"""
Утилиты нормализации datetime для workflow лекций.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

REFLECTIONS_LOCAL_TIMEZONE = ZoneInfo("Europe/Moscow")


def ensure_utc_datetime(value: datetime) -> datetime:
    """
    Привести datetime к UTC.

    Если timezone отсутствует, считается, что пользователь ввёл время
    в локальной зоне проекта Europe/Moscow.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=REFLECTIONS_LOCAL_TIMEZONE)
    return value.astimezone(timezone.utc)


def calculate_lection_deadline(ended_at: datetime, deadline_hours: int) -> datetime:
    """Рассчитать deadline лекции в UTC от времени окончания."""
    return ensure_utc_datetime(ended_at) + timedelta(hours=deadline_hours)


def is_reflection_deadline_active(
    deadline: datetime,
    now: datetime | None = None,
) -> bool:
    """
    Проверить, что дедлайн отправки ещё активен.

    Даём студенту дополнительную минуту после указанного дедлайна:
    в указанную минуту отправка ещё допустима, а со следующей уже нет.
    """
    current_time = ensure_utc_datetime(now or datetime.now(timezone.utc))
    return current_time < ensure_utc_datetime(deadline) + timedelta(minutes=1)
