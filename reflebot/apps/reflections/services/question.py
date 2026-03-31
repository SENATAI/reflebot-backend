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
    
    async def create_question(self, lection_id: uuid.UUID, text: str) -> QuestionReadSchema:
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
                QuestionReadSchema.model_validate(question, from_attributes=True)
                for question in questions
            ]

    async def get_question(self, question_id: uuid.UUID) -> QuestionReadSchema:
        """Получить вопрос по идентификатору."""
        return await self.question_repository.get(question_id)
    
    async def create_question(self, lection_id: uuid.UUID, text: str) -> QuestionReadSchema:
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
