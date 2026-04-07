"""
Сервис workflow рефлексии студента.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
import uuid

from reflebot.core.utils.exceptions import PermissionDeniedError, ValidationError
from ..datetime_utils import is_reflection_deadline_active
from ..repositories.reflection import ReflectionWorkflowRepositoryProtocol
from ..schemas import QuestionAnswerDraftSchema


class ReflectionWorkflowServiceProtocol(Protocol):
    """Протокол сервиса workflow рефлексии студента."""

    async def start_workflow(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Подготовить стартовый контекст workflow рефлексии."""
        ...

    def add_video_to_draft(
        self,
        context_data: dict[str, Any],
        telegram_file_id: str,
    ) -> dict[str, Any]:
        """Добавить новый кружок в текущий draft."""
        ...

    def remove_last_video_from_draft(
        self,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Удалить последний кружок из текущего draft."""
        ...

    async def submit_reflection(
        self,
        student_id: uuid.UUID,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Сохранить рефлексию и перейти к вопросам."""
        ...

    async def submit_question_answer(
        self,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Сохранить draft текущего ответа и перейти к следующему вопросу."""
        ...

    async def finalize_question_answers(
        self,
        context_data: dict[str, Any],
    ) -> None:
        """Сохранить все ответы на вопросы после завершения workflow."""
        ...

    def get_current_question(self, context_data: dict[str, Any]) -> dict[str, Any] | None:
        """Получить текущий вопрос из контекста."""
        ...

    def should_select_single_question(self, context_data: dict[str, Any]) -> bool:
        """Нужно ли студенту выбрать один вопрос из списка."""
        ...

    def select_single_question(
        self,
        context_data: dict[str, Any],
        question_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Оставить в контексте только выбранный студентом вопрос."""
        ...

    def get_current_video_count(self, context_data: dict[str, Any]) -> int:
        """Получить количество кружков в текущем draft."""
        ...

    async def get_reflection_status(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Получить текущее состояние рефлексии студента по лекции."""
        ...


class ReflectionWorkflowService(ReflectionWorkflowServiceProtocol):
    """Сервис workflow рефлексии студента."""

    def __init__(self, repository: ReflectionWorkflowRepositoryProtocol):
        self.repository = repository

    async def start_workflow(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Подготовить стартовый контекст workflow рефлексии."""
        lection = await self.repository.get_lection_for_student(student_id, lection_session_id)
        if lection is None:
            raise PermissionDeniedError("У студента нет доступа к этой лекции.")

        existing_reflection = await self.repository.get_reflection_for_student(
            student_id,
            lection_session_id,
        )
        if not is_reflection_deadline_active(lection.deadline):
            raise ValidationError(
                "deadline",
                "Нельзя отправить кружок/видео по данной лекции, дедлайн закончился.",
            )

        questions = (
            []
            if existing_reflection is not None
            else await self.repository.get_questions_for_lection(lection_session_id)
        )
        return {
            "lection_id": str(lection.id),
            "lection_topic": lection.topic,
            "lection_deadline": lection.deadline.isoformat(),
            "one_question_from_list": bool(lection.one_question_from_list),
            "stage": "reflection",
            "reflection_id": (
                str(existing_reflection.id)
                if existing_reflection is not None
                else None
            ),
            "reflection_videos": [],
            "questions": [
                {"id": str(question.id), "text": question.question_text}
                for question in questions
            ],
            "current_question_index": 0,
            "current_question_videos": [],
            "qa_answers": [],
        }

    def add_video_to_draft(
        self,
        context_data: dict[str, Any],
        telegram_file_id: str,
    ) -> dict[str, Any]:
        """Добавить новый кружок в текущий draft."""
        data = self._clone_context_data(context_data)
        key = self._draft_key(data)
        draft_videos = list(data.get(key, []))
        draft_videos.append(telegram_file_id)
        data[key] = draft_videos
        return data

    def remove_last_video_from_draft(
        self,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Удалить последний кружок из текущего draft."""
        data = self._clone_context_data(context_data)
        key = self._draft_key(data)
        draft_videos = list(data.get(key, []))
        if not draft_videos:
            raise ValidationError("reflection_video", "Сначала нужно загрузить кружок/видео.")
        draft_videos.pop()
        data[key] = draft_videos
        return data

    async def submit_reflection(
        self,
        student_id: uuid.UUID,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Сохранить рефлексию и перейти к вопросам."""
        data = self._clone_context_data(context_data)
        file_ids = list(data.get("reflection_videos", []))
        if not file_ids:
            raise ValidationError("reflection_video", "Сначала нужно загрузить хотя бы один кружок/видео.")

        submitted_at = datetime.now(timezone.utc)
        if data.get("reflection_id"):
            await self.repository.append_videos_to_reflection(
                reflection_id=uuid.UUID(str(data["reflection_id"])),
                file_ids=file_ids,
                submitted_at=submitted_at,
            )
        else:
            reflection = await self.repository.create_reflection_with_videos(
                student_id=student_id,
                lection_session_id=uuid.UUID(str(data["lection_id"])),
                file_ids=file_ids,
                submitted_at=submitted_at,
            )
            data["reflection_id"] = str(reflection.id)
        data["stage"] = "question"
        data["current_question_index"] = 0
        data["current_question_videos"] = []
        data["reflection_videos"] = []
        data["qa_answers"] = []
        return data

    async def submit_question_answer(
        self,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Сохранить draft текущего ответа и перейти к следующему вопросу."""
        data = self._clone_context_data(context_data)
        current_question = self.get_current_question(data)
        if current_question is None:
            raise ValidationError("question", "Для этой лекции больше нет вопросов.")

        file_ids = list(data.get("current_question_videos", []))
        if not file_ids:
            raise ValidationError("qa_video", "Сначала нужно записать хотя бы один кружок/видео.")

        qa_answers = list(data.get("qa_answers", []))
        qa_answers.append(
            {
                "question_id": current_question["id"],
                "file_ids": file_ids,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["qa_answers"] = qa_answers
        data["current_question_videos"] = []
        data["current_question_index"] = int(data.get("current_question_index", 0)) + 1
        return data

    async def finalize_question_answers(
        self,
        context_data: dict[str, Any],
    ) -> None:
        """Сохранить все ответы на вопросы после завершения workflow."""
        raw_answers = list(context_data.get("qa_answers", []))
        if not raw_answers:
            return

        answers = [
            QuestionAnswerDraftSchema(
                question_id=uuid.UUID(str(answer["question_id"])),
                file_ids=list(answer["file_ids"]),
                submitted_at=self._parse_datetime(answer["submitted_at"]),
            )
            for answer in raw_answers
        ]
        await self.repository.create_question_answers(
            reflection_id=uuid.UUID(str(context_data["reflection_id"])),
            answers=answers,
        )

    def get_current_question(self, context_data: dict[str, Any]) -> dict[str, Any] | None:
        """Получить текущий вопрос из контекста."""
        questions = list(context_data.get("questions", []))
        current_index = int(context_data.get("current_question_index", 0))
        if current_index < 0 or current_index >= len(questions):
            return None
        return questions[current_index]

    @staticmethod
    def should_select_single_question(context_data: dict[str, Any]) -> bool:
        """Нужно ли студенту сначала выбрать один вопрос из списка."""
        return bool(context_data.get("one_question_from_list")) and len(
            list(context_data.get("questions", []))
        ) > 1

    @staticmethod
    def select_single_question(
        context_data: dict[str, Any],
        question_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Оставить в контексте только выбранный студентом вопрос."""
        data = ReflectionWorkflowService._clone_context_data(context_data)
        selected_question = next(
            (
                question
                for question in data.get("questions", [])
                if str(question["id"]) == str(question_id)
            ),
            None,
        )
        if selected_question is None:
            raise ValidationError("question", "Выбранный вопрос не найден.")
        data["questions"] = [selected_question]
        data["current_question_index"] = 0
        data["current_question_videos"] = []
        return data

    def get_current_video_count(self, context_data: dict[str, Any]) -> int:
        """Получить количество кружков в текущем draft."""
        key = self._draft_key(context_data)
        return len(list(context_data.get(key, [])))

    async def get_reflection_status(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Получить текущее состояние рефлексии студента по лекции."""
        lection = await self.repository.get_lection_for_student(student_id, lection_session_id)
        if lection is None:
            raise PermissionDeniedError("У студента нет доступа к этой лекции.")

        reflection = await self.repository.get_reflection_for_student(student_id, lection_session_id)
        video_file_ids = await self.repository.get_reflection_video_file_ids(
            student_id,
            lection_session_id,
        )
        deadline = lection.deadline
        return {
            "lection_id": str(lection.id),
            "lection_topic": lection.topic,
            "lection_deadline": deadline.isoformat(),
            "reflection_id": str(reflection.id) if reflection is not None else None,
            "recorded_videos_count": len(video_file_ids),
            "deadline_active": is_reflection_deadline_active(deadline),
        }

    @staticmethod
    def _draft_key(context_data: dict[str, Any]) -> str:
        """Определить ключ draft-кружков для текущей стадии workflow."""
        if context_data.get("stage") == "question":
            return "current_question_videos"
        return "reflection_videos"

    @staticmethod
    def _clone_context_data(context_data: dict[str, Any]) -> dict[str, Any]:
        """Сделать безопасную копию контекста workflow."""
        return {
            **context_data,
            "reflection_videos": list(context_data.get("reflection_videos", [])),
            "questions": [dict(question) for question in context_data.get("questions", [])],
            "current_question_videos": list(context_data.get("current_question_videos", [])),
            "qa_answers": [dict(answer) for answer in context_data.get("qa_answers", [])],
        }

    @staticmethod
    def _parse_datetime(value: str | datetime) -> datetime:
        """Нормализовать datetime из JSON контекста."""
        if isinstance(value, datetime):
            return value
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
