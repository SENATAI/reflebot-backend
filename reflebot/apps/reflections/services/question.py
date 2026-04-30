"""
Сервис для работы с вопросами к лекциям.
"""

import uuid
from typing import Protocol

from sqlalchemy import select

from reflebot.core.utils.exceptions import ModelNotFoundException
from ..repositories.question import QuestionRepositoryProtocol
from ..models import Question
from ..schemas import (
    QuestionReadSchema,
    QuestionCreateSchema,
    QuestionUpdateSchema,
)


class QuestionServiceProtocol(Protocol):
    """Протокол сервиса вопросов."""
    
    async def get_questions_by_lection(self, lection_id: uuid.UUID) -> list[QuestionReadSchema]:
        """Получить все вопросы для лекции."""
        ...

    async def get_question(self, question_id: uuid.UUID) -> QuestionReadSchema:
        """Получить вопрос по идентификатору."""
        ...
    
    async def create_question(
        self,
        lection_id: uuid.UUID,
        text: str,
        question_pool_index: int = 0,
        question_pool_questions_to_ask_count: int | None = None,
    ) -> QuestionReadSchema:
        """Создать вопрос для лекции."""
        ...
    
    async def update_question(self, question_id: uuid.UUID, text: str) -> QuestionReadSchema:
        """Обновить текст вопроса."""
        ...
    
    async def delete_question(self, question_id: uuid.UUID) -> None:
        """Удалить вопрос."""
        ...


class QuestionService(QuestionServiceProtocol):
    """Сервис для работы с вопросами к лекциям."""
    
    def __init__(self, question_repository: QuestionRepositoryProtocol):
        self.question_repository = question_repository
    
    async def get_questions_by_lection(self, lection_id: uuid.UUID) -> list[QuestionReadSchema]:
        """
        Получить все вопросы для лекции.
        
        Args:
            lection_id: ID лекции
        
        Returns:
            Список вопросов
        """
        async with self.question_repository.session as s:
            stmt = (
                select(Question)
                .where(Question.lection_session_id == lection_id)
                .order_by(Question.created_at)
            )
            result = await s.execute(stmt)
            questions = result.scalars().all()
            
            return [
                self._to_read_schema(question)
                for question in questions
            ]

    async def get_question(self, question_id: uuid.UUID) -> QuestionReadSchema:
        """Получить вопрос по идентификатору."""
        return await self.question_repository.get(question_id)
    
    async def create_question(
        self,
        lection_id: uuid.UUID,
        text: str,
        question_pool_index: int = 0,
        question_pool_questions_to_ask_count: int | None = None,
    ) -> QuestionReadSchema:
        """
        Создать вопрос для лекции.
        
        Args:
            lection_id: ID лекции
            text: Текст вопроса
        
        Returns:
            Созданный вопрос
        """
        create_data = QuestionCreateSchema(
            lection_session_id=lection_id,
            question_text=text,
            question_pool_index=question_pool_index,
            question_pool_questions_to_ask_count=question_pool_questions_to_ask_count,
        )
        return await self.question_repository.create(create_data)
    
    async def update_question(self, question_id: uuid.UUID, text: str) -> QuestionReadSchema:
        """
        Обновить текст вопроса.
        
        Args:
            question_id: ID вопроса
            text: Новый текст вопроса
        
        Returns:
            Обновленный вопрос
        """
        # Проверяем существование вопроса
        await self.get_question(question_id)
        
        # Обновляем текст
        update_data = QuestionUpdateSchema(
            id=question_id,
            question_text=text,
        )
        return await self.question_repository.update(update_data)
    
    async def delete_question(self, question_id: uuid.UUID) -> None:
        """
        Удалить вопрос.
        
        Args:
            question_id: ID вопроса
        """
        await self.question_repository.delete(question_id)

    @staticmethod
    def _to_read_schema(question: Question) -> QuestionReadSchema:
        """Преобразовать ORM-модель вопроса в read-schema с safe fallback для legacy моков."""
        pool_index = getattr(question, "question_pool_index", 0)
        if not isinstance(pool_index, int):
            pool_index = 0

        pool_questions_to_ask_count = getattr(
            question,
            "question_pool_questions_to_ask_count",
            None,
        )
        if not isinstance(pool_questions_to_ask_count, int):
            pool_questions_to_ask_count = None

        return QuestionReadSchema(
            id=question.id,
            lection_session_id=question.lection_session_id,
            question_text=question.question_text,
            question_pool_index=pool_index,
            question_pool_questions_to_ask_count=pool_questions_to_ask_count,
            created_at=question.created_at,
            updated_at=question.updated_at,
        )
