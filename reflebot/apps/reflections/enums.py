"""
Перечисления для модуля рефлексий.
"""

import enum


class AIAnalysisStatus(str, enum.Enum):
    """Статус AI-анализа рефлексии."""
    
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class NotificationDeliveryType(str, enum.Enum):
    """Тип уведомления."""

    REFLECTION_PROMPT = "reflection_prompt"


class NotificationDeliveryStatus(str, enum.Enum):
    """Статус доставки уведомления."""

    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
