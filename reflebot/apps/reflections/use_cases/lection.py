"""
Use cases для управления лекциями, вопросами и файлами.
"""

import uuid
from datetime import datetime
from typing import Protocol

from reflebot.core.utils.exceptions import FileNotFound
from ..schemas import (
    AdminReadSchema,
    LectionSessionReadSchema,
    QuestionReadSchema,
)
from ..services.lection import LectionServiceProtocol
from ..services.question import QuestionServiceProtocol


class UpdateLectionUseCaseProtocol(Protocol):
    """Протокол use case обновления лекции."""

    async def update_topic(
        self,
        lection_id: uuid.UUID,
        topic: str,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Обновить тему лекции."""
        ...

    async def update_datetime(
        self,
        lection_id: uuid.UUID,
        started_at: datetime,
        ended_at: datetime,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Обновить дату и время лекции."""
        ...


class UpdateLectionUseCase(UpdateLectionUseCaseProtocol):
    """Use case для обновления параметров лекции."""

    def __init__(self, lection_service: LectionServiceProtocol):
        self.lection_service = lection_service

    async def update_topic(
        self,
        lection_id: uuid.UUID,
        topic: str,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Обновить тему лекции после проверки прав администратора."""
        return await self.lection_service.update_topic(lection_id, topic)

    async def update_datetime(
        self,
        lection_id: uuid.UUID,
        started_at: datetime,
        ended_at: datetime,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Обновить дату и время лекции после проверки прав администратора."""
        return await self.lection_service.update_datetime(lection_id, started_at, ended_at)


class ManageQuestionsUseCaseProtocol(Protocol):
    """Протокол use case управления вопросами лекции."""

    async def get_questions(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Получить список вопросов лекции."""
        ...

    async def create_question(
        self,
        lection_id: uuid.UUID,
        text: str,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Добавить вопрос и вернуть обновлённый список."""
        ...

    async def update_question(
        self,
        question_id: uuid.UUID,
        text: str,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Обновить вопрос и вернуть обновлённый список."""
        ...

    async def delete_question(
        self,
        question_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Удалить вопрос и вернуть обновлённый список."""
        ...


class ManageQuestionsUseCase(ManageQuestionsUseCaseProtocol):
    """Use case для CRUD-управления вопросами лекции."""

    def __init__(self, question_service: QuestionServiceProtocol):
        self.question_service = question_service

    async def get_questions(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Получить все вопросы лекции."""
        return await self.question_service.get_questions_by_lection(lection_id)

    async def create_question(
        self,
        lection_id: uuid.UUID,
        text: str,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Добавить вопрос и вернуть обновлённый список."""
        await self.question_service.create_question(lection_id, text)
        return await self.get_questions(lection_id, current_admin)

    async def update_question(
        self,
        question_id: uuid.UUID,
        text: str,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Обновить существующий вопрос и вернуть обновлённый список."""
        question = await self.question_service.get_question(question_id)
        await self.question_service.update_question(question_id, text)
        return await self.get_questions(question.lection_session_id, current_admin)

    async def delete_question(
        self,
        question_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> list[QuestionReadSchema]:
        """Удалить вопрос и вернуть обновлённый список."""
        question = await self.question_service.get_question(question_id)
        await self.question_service.delete_question(question_id)
        return await self.get_questions(question.lection_session_id, current_admin)


class ManageFilesUseCaseProtocol(Protocol):
    """Протокол use case управления файлами лекции."""

    async def get_presentation_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str | None:
        """Получить Telegram file_id презентации."""
        ...

    async def upload_presentation(
        self,
        lection_id: uuid.UUID,
        telegram_file_id: str,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Загрузить или обновить презентацию."""
        ...

    async def get_presentation_telegram_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str:
        """Получить Telegram file_id презентации."""
        ...

    async def get_recording_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str | None:
        """Получить Telegram file_id записи."""
        ...

    async def upload_recording(
        self,
        lection_id: uuid.UUID,
        telegram_file_id: str,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Загрузить или обновить запись лекции."""
        ...

    async def get_recording_telegram_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str:
        """Получить Telegram file_id записи лекции."""
        ...


class ManageFilesUseCase(ManageFilesUseCaseProtocol):
    """Use case для управления презентациями и записями лекции."""

    def __init__(self, lection_service: LectionServiceProtocol):
        self.lection_service = lection_service

    async def get_presentation_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str | None:
        """Получить Telegram file_id презентации, если он привязан к лекции."""
        lection = await self.lection_service.get_by_id(lection_id)
        return lection.presentation_file_id

    async def upload_presentation(
        self,
        lection_id: uuid.UUID,
        telegram_file_id: str,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Сохранить Telegram file_id презентации в лекции."""
        return await self.lection_service.update_presentation_file(lection_id, telegram_file_id)

    async def get_presentation_telegram_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str:
        """Получить Telegram file_id презентации лекции."""
        lection = await self.lection_service.get_by_id(lection_id)
        if lection.presentation_file_id is None:
            raise FileNotFound(f"presentation for lection {lection_id}")
        return lection.presentation_file_id

    async def get_recording_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str | None:
        """Получить Telegram file_id записи, если он привязан к лекции."""
        lection = await self.lection_service.get_by_id(lection_id)
        return lection.recording_file_id

    async def upload_recording(
        self,
        lection_id: uuid.UUID,
        telegram_file_id: str,
        current_admin: AdminReadSchema,
    ) -> LectionSessionReadSchema:
        """Сохранить Telegram file_id записи лекции."""
        return await self.lection_service.update_recording_file(lection_id, telegram_file_id)

    async def get_recording_telegram_file_id(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema,
    ) -> str:
        """Получить Telegram file_id записи лекции."""
        lection = await self.lection_service.get_by_id(lection_id)
        if lection.recording_file_id is None:
            raise FileNotFound(f"recording for lection {lection_id}")
        return lection.recording_file_id
