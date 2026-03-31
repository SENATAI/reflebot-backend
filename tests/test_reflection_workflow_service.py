"""
Unit tests for student reflection workflow service.
"""

from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import AsyncMock

import pytest

from reflebot.apps.reflections.schemas import (
    LectionReflectionReadSchema,
    LectionSessionReadSchema,
    QuestionAnswerDraftSchema,
    QuestionReadSchema,
)
from reflebot.apps.reflections.services.reflection import ReflectionWorkflowService
from reflebot.core.utils.exceptions import PermissionDeniedError, ValidationError


def create_lection(topic: str = "Лекция") -> LectionSessionReadSchema:
    now = datetime.now(timezone.utc)
    return LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic=topic,
        presentation_file_id=None,
        recording_file_id=None,
        started_at=now,
        ended_at=now,
        deadline=now + timedelta(hours=24),
        created_at=now,
        updated_at=now,
    )


def create_question(text: str = "Вопрос?") -> QuestionReadSchema:
    now = datetime.now(timezone.utc)
    return QuestionReadSchema(
        id=uuid.uuid4(),
        lection_session_id=uuid.uuid4(),
        question_text=text,
        created_at=now,
        updated_at=now,
    )


def create_reflection() -> LectionReflectionReadSchema:
    now = datetime.now(timezone.utc)
    return LectionReflectionReadSchema(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        lection_session_id=uuid.uuid4(),
        submitted_at=now,
        ai_analysis_status="pending",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_start_workflow_denies_student_without_lection_access():
    repository = AsyncMock()
    repository.get_lection_for_student.return_value = None
    service = ReflectionWorkflowService(repository)

    with pytest.raises(PermissionDeniedError):
        await service.start_workflow(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_start_workflow_rejects_already_submitted_reflection():
    repository = AsyncMock()
    repository.get_lection_for_student.return_value = create_lection()
    repository.get_reflection_for_student.return_value = create_reflection()
    service = ReflectionWorkflowService(repository)

    with pytest.raises(ValidationError):
        await service.start_workflow(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_start_workflow_rejects_expired_deadline():
    repository = AsyncMock()
    expired_lection = create_lection()
    expired_lection.deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
    repository.get_lection_for_student.return_value = expired_lection
    repository.get_reflection_for_student.return_value = None
    service = ReflectionWorkflowService(repository)

    with pytest.raises(ValidationError, match="дедлайн закончился"):
        await service.start_workflow(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_submit_reflection_switches_context_to_questions():
    repository = AsyncMock()
    repository.create_reflection_with_videos.return_value = create_reflection()
    service = ReflectionWorkflowService(repository)
    context_data = {
        "lection_id": str(uuid.uuid4()),
        "lection_topic": "Матан",
        "stage": "reflection",
        "reflection_videos": ["video-1"],
        "questions": [{"id": str(uuid.uuid4()), "text": "Что было полезно?"}],
        "current_question_index": 0,
        "current_question_videos": [],
        "qa_answers": [],
    }

    updated = await service.submit_reflection(uuid.uuid4(), context_data)

    repository.create_reflection_with_videos.assert_called_once()
    assert updated["stage"] == "question"
    assert updated["reflection_id"] is not None
    assert updated["current_question_index"] == 0


@pytest.mark.asyncio
async def test_submit_question_answer_appends_draft_and_moves_to_next_question():
    repository = AsyncMock()
    service = ReflectionWorkflowService(repository)
    first_question_id = uuid.uuid4()
    second_question_id = uuid.uuid4()
    context_data = {
        "stage": "question",
        "reflection_id": str(uuid.uuid4()),
        "questions": [
            {"id": str(first_question_id), "text": "Первый?"},
            {"id": str(second_question_id), "text": "Второй?"},
        ],
        "current_question_index": 0,
        "current_question_videos": ["video-qa-1"],
        "qa_answers": [],
    }

    updated = await service.submit_question_answer(context_data)

    assert updated["current_question_index"] == 1
    assert updated["current_question_videos"] == []
    assert updated["qa_answers"][0]["question_id"] == str(first_question_id)
    assert updated["qa_answers"][0]["file_ids"] == ["video-qa-1"]


@pytest.mark.asyncio
async def test_finalize_question_answers_converts_context_to_repository_payload():
    repository = AsyncMock()
    service = ReflectionWorkflowService(repository)
    question_id = uuid.uuid4()
    context_data = {
        "reflection_id": str(uuid.uuid4()),
        "qa_answers": [
            {
                "question_id": str(question_id),
                "file_ids": ["video-1", "video-2"],
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }

    await service.finalize_question_answers(context_data)

    repository.create_question_answers.assert_called_once()
    answers = repository.create_question_answers.call_args.kwargs["answers"]
    assert len(answers) == 1
    assert isinstance(answers[0], QuestionAnswerDraftSchema)
    assert answers[0].question_id == question_id
