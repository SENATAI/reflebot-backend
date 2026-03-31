"""
Репозиторий для работы с вопросами к лекциям.
"""

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import Question
from ..schemas import QuestionCreateSchema, QuestionReadSchema, QuestionUpdateSchema


class QuestionRepositoryProtocol(
    BaseRepositoryProtocol[Question, QuestionReadSchema, QuestionCreateSchema, QuestionUpdateSchema]
):
    """Протокол репозитория вопросов."""
    pass


class QuestionRepository(
    BaseRepositoryImpl[Question, QuestionReadSchema, QuestionCreateSchema, QuestionUpdateSchema],
    QuestionRepositoryProtocol,
):
    """Репозиторий для работы с вопросами к лекциям."""
    pass
