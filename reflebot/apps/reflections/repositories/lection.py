"""
Репозиторий для работы с лекциями.
"""

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import LectionSession
from ..schemas import LectionSessionCreateSchema, LectionSessionReadSchema, LectionSessionUpdateSchema


class LectionSessionRepositoryProtocol(
    BaseRepositoryProtocol[LectionSession, LectionSessionReadSchema, LectionSessionCreateSchema, LectionSessionUpdateSchema]
):
    """Протокол репозитория лекций."""
    pass


class LectionSessionRepository(
    BaseRepositoryImpl[LectionSession, LectionSessionReadSchema, LectionSessionCreateSchema, LectionSessionUpdateSchema],
    LectionSessionRepositoryProtocol,
):
    """Репозиторий для работы с лекциями."""
    pass
