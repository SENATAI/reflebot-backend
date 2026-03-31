"""
Репозиторий для workflow рефлексии студента.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
import uuid

import sqlalchemy as sa

from ..models import (
    LectionQA,
    LectionReflection,
    LectionSession,
    QAVideo,
    Question,
    ReflectionVideo,
    StudentLection,
)
from ..schemas import (
    LectionQAReadSchema,
    LectionReflectionReadSchema,
    LectionSessionReadSchema,
    QuestionAnswerDraftSchema,
    QuestionReadSchema,
)


class ReflectionWorkflowRepositoryProtocol(Protocol):
    """Протокол репозитория workflow рефлексии студента."""

    async def get_lection_for_student(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> LectionSessionReadSchema | None:
        """Получить лекцию, если студент к ней привязан."""
        ...

    async def get_questions_for_lection(
        self,
        lection_session_id: uuid.UUID,
    ) -> list[QuestionReadSchema]:
        """Получить вопросы лекции в порядке создания."""
        ...

    async def get_reflection_for_student(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> LectionReflectionReadSchema | None:
        """Получить уже отправленную рефлексию студента по лекции."""
        ...

    async def create_reflection_with_videos(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
        file_ids: list[str],
        submitted_at: datetime,
    ) -> LectionReflectionReadSchema:
        """Создать рефлексию и все её видео."""
        ...

    async def create_question_answers(
        self,
        reflection_id: uuid.UUID,
        answers: list[QuestionAnswerDraftSchema],
    ) -> list[LectionQAReadSchema]:
        """Создать ответы на вопросы и их кружки."""
        ...


class ReflectionWorkflowRepository(ReflectionWorkflowRepositoryProtocol):
    """Репозиторий workflow рефлексии студента."""

    def __init__(self, session):
        self.session = session

    async def get_lection_for_student(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> LectionSessionReadSchema | None:
        """Получить лекцию, если студент к ней привязан."""
        async with self.session as s:
            stmt = (
                sa.select(LectionSession)
                .join(
                    StudentLection,
                    StudentLection.lection_session_id == LectionSession.id,
                )
                .where(
                    StudentLection.student_id == student_id,
                    LectionSession.id == lection_session_id,
                )
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                return None
            return LectionSessionReadSchema.model_validate(model, from_attributes=True)

    async def get_questions_for_lection(
        self,
        lection_session_id: uuid.UUID,
    ) -> list[QuestionReadSchema]:
        """Получить вопросы лекции в порядке создания."""
        async with self.session as s:
            stmt = (
                sa.select(Question)
                .where(Question.lection_session_id == lection_session_id)
                .order_by(Question.created_at, Question.id)
            )
            models = (await s.execute(stmt)).scalars().all()
            return [
                QuestionReadSchema.model_validate(model, from_attributes=True)
                for model in models
            ]

    async def get_reflection_for_student(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
    ) -> LectionReflectionReadSchema | None:
        """Получить уже отправленную рефлексию студента по лекции."""
        async with self.session as s:
            stmt = sa.select(LectionReflection).where(
                LectionReflection.student_id == student_id,
                LectionReflection.lection_session_id == lection_session_id,
            )
            model = (await s.execute(stmt)).scalar_one_or_none()
            if model is None:
                return None
            return LectionReflectionReadSchema.model_validate(model, from_attributes=True)

    async def create_reflection_with_videos(
        self,
        student_id: uuid.UUID,
        lection_session_id: uuid.UUID,
        file_ids: list[str],
        submitted_at: datetime,
    ) -> LectionReflectionReadSchema:
        """Создать рефлексию и все её видео."""
        reflection_id = uuid.uuid4()
        async with self.session as s, s.begin():
            reflection = LectionReflection(
                id=reflection_id,
                student_id=student_id,
                lection_session_id=lection_session_id,
                submitted_at=submitted_at,
            )
            s.add(reflection)
            s.add_all(
                [
                    ReflectionVideo(
                        id=uuid.uuid4(),
                        reflection_id=reflection_id,
                        file_id=file_id,
                        order_index=index,
                    )
                    for index, file_id in enumerate(file_ids, start=1)
                ]
            )
        return LectionReflectionReadSchema.model_validate(reflection, from_attributes=True)

    async def create_question_answers(
        self,
        reflection_id: uuid.UUID,
        answers: list[QuestionAnswerDraftSchema],
    ) -> list[LectionQAReadSchema]:
        """Создать ответы на вопросы и все их кружки."""
        created: list[LectionQA] = []
        async with self.session as s, s.begin():
            for answer in answers:
                lection_qa = LectionQA(
                    id=uuid.uuid4(),
                    reflection_id=reflection_id,
                    question_id=answer.question_id,
                    answer_submitted_at=answer.submitted_at,
                )
                s.add(lection_qa)
                await s.flush()
                s.add_all(
                    [
                        QAVideo(
                            id=uuid.uuid4(),
                            lection_qa_id=lection_qa.id,
                            file_id=file_id,
                            order_index=index,
                        )
                        for index, file_id in enumerate(answer.file_ids, start=1)
                    ]
                )
                created.append(lection_qa)
        return [
            LectionQAReadSchema.model_validate(model, from_attributes=True)
            for model in created
        ]
