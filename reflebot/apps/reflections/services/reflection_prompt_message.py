"""
Сервис генерации сообщений запроса рефлексии.
"""

import uuid
from typing import Protocol

from ..repositories.lection import LectionSessionRepositoryProtocol
from ..schemas import ReflectionPromptMessageSchema
from ..telegram.buttons import TelegramButtons
from ..telegram.messages import TelegramMessages


class ReflectionPromptMessageServiceProtocol(Protocol):
    """Протокол сервиса генерации Reflection Prompt сообщения."""

    async def build_message(
        self,
        lection_session_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> ReflectionPromptMessageSchema:
        """Построить текст запроса рефлексии."""
        ...


class ReflectionPromptMessageService(ReflectionPromptMessageServiceProtocol):
    """Сервис генерации текста запроса рефлексии по лекции."""

    def __init__(self, lection_repository: LectionSessionRepositoryProtocol):
        self.lection_repository = lection_repository

    async def build_message(
        self,
        lection_session_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> ReflectionPromptMessageSchema:
        """Построить сообщение с темой лекции для запроса рефлексии."""
        del student_id
        lection = await self.lection_repository.get(lection_session_id)
        return ReflectionPromptMessageSchema(
            message_text=TelegramMessages.get_reflection_prompt_request(
                lection.topic,
                lection.deadline,
            ),
            parse_mode="HTML",
            buttons=[
                {
                    "text": button.text,
                    "action": button.action,
                }
                for button in TelegramButtons.get_reflection_prompt_buttons(str(lection.id))
            ],
        )
