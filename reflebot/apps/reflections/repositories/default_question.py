"""
Репозиторий для стандартных вопросов.
"""

from typing import Protocol

import sqlalchemy as sa

from reflebot.core.repositories.base_repository import BaseRepositoryImpl, BaseRepositoryProtocol
from ..models import DefaultQuestion
from ..schemas import DefaultQuestionCreateSchema, DefaultQuestionReadSchema, DefaultQuestionUpdateSchema


class DefaultQuestionRepositoryProtocol(
    BaseRepositoryProtocol[
        DefaultQuestion,
        DefaultQuestionReadSchema,
        DefaultQuestionCreateSchema,
        DefaultQuestionUpdateSchema,
    ],
    Protocol,
):
    """Протокол репозитория стандартных вопросов."""

    async def get_all_question_texts(self) -> list[str]:
        """Получить все тексты стандартных вопросов."""
        ...


class DefaultQuestionRepository(
    BaseRepositoryImpl[
        DefaultQuestion,
        DefaultQuestionReadSchema,
        DefaultQuestionCreateSchema,
        DefaultQuestionUpdateSchema,
    ],
    DefaultQuestionRepositoryProtocol,
):
    """Репозиторий стандартных вопросов."""

    async def get_all_question_texts(self) -> list[str]:
        async with self.session as s:
            stmt = sa.select(DefaultQuestion.question_text).order_by(DefaultQuestion.created_at, DefaultQuestion.id)
            return list((await s.execute(stmt)).scalars().all())
