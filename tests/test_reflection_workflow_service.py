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
        one_question_from_list=False,
        questions_to_ask_count=None,
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
async def test_start_workflow_allows_existing_reflection_for_dozapis():
    repository = AsyncMock()
    repository.get_lection_for_student.return_value = create_lection()
    repository.get_reflection_for_student.return_value = create_reflection()
    service = ReflectionWorkflowService(repository)

    result = await service.start_workflow(uuid.uuid4(), uuid.uuid4())

    assert result["reflection_id"] is not None
    assert result["questions"] == []
    assert result["reflection_videos"] == []


@pytest.mark.asyncio
async def test_start_workflow_selects_only_requested_number_of_questions():
    repository = AsyncMock()
    lection = create_lection()
    lection.questions_to_ask_count = 1
    repository.get_lection_for_student.return_value = lection
    repository.get_reflection_for_student.return_value = None
    repository.get_questions_for_lection.return_value = [
        create_question("Первый?"),
        create_question("Второй?"),
    ]
    service = ReflectionWorkflowService(repository)

    result = await service.start_workflow(uuid.uuid4(), uuid.uuid4())

    assert result["one_question_from_list"] is False
    assert result["questions_to_ask_count"] == 1
    assert len(result["questions"]) == 1


@pytest.mark.asyncio
async def test_start_workflow_rejects_expired_deadline():
    repository = AsyncMock()
    expired_lection = create_lection()
    expired_lection.deadline = datetime.now(timezone.utc) - timedelta(minutes=1, seconds=1)
    repository.get_lection_for_student.return_value = expired_lection
    repository.get_reflection_for_student.return_value = None
    service = ReflectionWorkflowService(repository)

    with pytest.raises(ValidationError, match="дедлайн закончился"):
        await service.start_workflow(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_start_workflow_allows_deadline_during_extra_minute():
    repository = AsyncMock()
    lection = create_lection()
    lection.deadline = datetime.now(timezone.utc)
    repository.get_lection_for_student.return_value = lection
    repository.get_reflection_for_student.return_value = None
    repository.get_questions_for_lection.return_value = []
    service = ReflectionWorkflowService(repository)

    result = await service.start_workflow(uuid.uuid4(), uuid.uuid4())

    assert result["lection_id"] == str(lection.id)


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
    assert updated["reflection_videos"] == []


@pytest.mark.asyncio
async def test_submit_reflection_appends_videos_to_existing_reflection():
    repository = AsyncMock()
    service = ReflectionWorkflowService(repository)
    reflection_id = uuid.uuid4()
    context_data = {
        "lection_id": str(uuid.uuid4()),
        "lection_topic": "Матан",
        "stage": "reflection",
        "reflection_id": str(reflection_id),
        "reflection_videos": ["video-1"],
        "questions": [],
        "current_question_index": 0,
        "current_question_videos": [],
        "qa_answers": [],
    }

    updated = await service.submit_reflection(uuid.uuid4(), context_data)

    repository.append_videos_to_reflection.assert_called_once()
    repository.create_reflection_with_videos.assert_not_called()
    assert updated["reflection_id"] == str(reflection_id)
    assert updated["reflection_videos"] == []


def test_should_select_single_question_returns_true_only_for_legacy_contexts():
    repository = AsyncMock()
    service = ReflectionWorkflowService(repository)

    assert service.should_select_single_question(
        {
            "one_question_from_list": True,
            "questions": [{"id": "1"}, {"id": "2"}],
        }
    ) is True
    assert service.should_select_single_question(
        {
            "one_question_from_list": False,
            "questions": [{"id": "1"}, {"id": "2"}],
        }
    ) is False
    assert service.should_select_single_question(
        {
            "one_question_from_list": True,
            "questions": [{"id": "1"}],
        }
    ) is False


def test_select_single_question_keeps_only_chosen_question():
    repository = AsyncMock()
    service = ReflectionWorkflowService(repository)
    first_question_id = uuid.uuid4()
    second_question_id = uuid.uuid4()

    updated = service.select_single_question(
        {
            "questions": [
                {"id": str(first_question_id), "text": "Первый?"},
                {"id": str(second_question_id), "text": "Второй?"},
            ],
            "current_question_index": 1,
            "current_question_videos": ["video-old"],
        },
        second_question_id,
    )

    assert updated["questions"] == [{"id": str(second_question_id), "text": "Второй?"}]
    assert updated["current_question_index"] == 0
    assert updated["current_question_videos"] == []


@pytest.mark.asyncio
async def test_get_reflection_status_returns_deadline_and_total_saved_count():
    repository = AsyncMock()
    lection = create_lection("Теория игр")
    reflection = create_reflection()
    repository.get_lection_for_student.return_value = lection
    repository.get_reflection_for_student.return_value = reflection
    repository.get_reflection_video_file_ids.return_value = [
        "reflection-video-1",
        "qa-video-1",
        "qa-video-2",
    ]
    service = ReflectionWorkflowService(repository)

    status = await service.get_reflection_status(uuid.uuid4(), lection.id)

    assert status["lection_id"] == str(lection.id)
    assert status["lection_topic"] == "Теория игр"
    assert status["reflection_id"] == str(reflection.id)
    assert status["recorded_videos_count"] == 3
    assert status["deadline_active"] is True


@pytest.mark.asyncio
async def test_get_reflection_status_marks_deadline_inactive_after_extra_minute():
    repository = AsyncMock()
    lection = create_lection("Теория игр")
    lection.deadline = datetime.now(timezone.utc) - timedelta(minutes=1, seconds=1)
    repository.get_lection_for_student.return_value = lection
    repository.get_reflection_for_student.return_value = None
    repository.get_reflection_video_file_ids.return_value = []
    service = ReflectionWorkflowService(repository)

    status = await service.get_reflection_status(uuid.uuid4(), lection.id)

    assert status["deadline_active"] is False


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
