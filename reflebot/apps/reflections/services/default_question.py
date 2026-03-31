"""
Сервис для работы со стандартными вопросами.
"""

from __future__ import annotations

import random
from contextlib import suppress
from typing import Final, Protocol

from reflebot.core.utils.exceptions import ModelAlreadyExistsError, ValidationError
from ..repositories.default_question import DefaultQuestionRepositoryProtocol
from ..schemas import DefaultQuestionCreateSchema

DEFAULT_QUESTION_TEMPLATES: Final[list[str]] = [
    "Расскажи то же самое, только другими словами.",
    "Расскажи подробнее.",
    "Как бы ты объяснил это другу?",
    "Что здесь было самым важным?",
    "Приведи простой пример из жизни.",
    "Что показалось самым сложным и почему?",
]


class DefaultQuestionServiceProtocol(Protocol):
    """Протокол сервиса стандартных вопросов."""

    async def ensure_seeded(self) -> None:
        """Гарантировать наличие базового набора стандартных вопросов."""
        ...

    async def get_random_question_text(self) -> str:
        """Получить случайный стандартный вопрос."""
        ...


class DefaultQuestionService(DefaultQuestionServiceProtocol):
    """Сервис стандартных вопросов."""

    def __init__(self, repository: DefaultQuestionRepositoryProtocol):
        self.repository = repository

    async def ensure_seeded(self) -> None:
        """Добавить недостающие стандартные вопросы."""
        existing = set(await self.repository.get_all_question_texts())
        for question_text in DEFAULT_QUESTION_TEMPLATES:
            if question_text in existing:
                continue
            with suppress(ModelAlreadyExistsError):
                await self.repository.create(
                    DefaultQuestionCreateSchema(question_text=question_text),
                )

    async def get_random_question_text(self) -> str:
        """Получить случайный стандартный вопрос."""
        questions = await self.repository.get_all_question_texts()
        if not questions:
            raise ValidationError("default_question", "Стандартные вопросы ещё не инициализированы.")
        return random.choice(questions)
