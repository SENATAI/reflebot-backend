"""
Unit tests for lection management use cases.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from reflebot.apps.reflections.schemas import (
    AdminReadSchema,
    LectionSessionReadSchema,
    QuestionReadSchema,
)
from reflebot.apps.reflections.use_cases.lection import (
    ManageFilesUseCase,
    ManageQuestionsUseCase,
    UpdateLectionUseCase,
)
from reflebot.core.utils.exceptions import FileNotFound


def create_admin() -> AdminReadSchema:
    now = datetime.now(timezone.utc)
    return AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Admin User",
        telegram_username="admin",
        telegram_id=1,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def create_lection(
    presentation_file_id: str | None = None,
    recording_file_id: str | None = None,
) -> LectionSessionReadSchema:
    now = datetime.now(timezone.utc)
    return LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic="Topic",
        presentation_file_id=presentation_file_id,
        recording_file_id=recording_file_id,
        started_at=now,
        ended_at=now,
        deadline=now,
        created_at=now,
        updated_at=now,
    )


def create_question(lection_id: uuid.UUID, text: str = "Question") -> QuestionReadSchema:
    now = datetime.now(timezone.utc)
    return QuestionReadSchema(
        id=uuid.uuid4(),
        lection_session_id=lection_id,
        question_text=text,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_lection_use_case_delegates_topic_and_datetime_updates():
    lection_service = AsyncMock()
    use_case = UpdateLectionUseCase(lection_service=lection_service)
    admin = create_admin()
    lection = create_lection()
    lection_service.update_topic.return_value = lection
    lection_service.update_datetime.return_value = lection

    topic_result = await use_case.update_topic(lection.id, "New Topic", admin)
    datetime_result = await use_case.update_datetime(
        lection.id,
        lection.started_at,
        lection.ended_at,
        admin,
    )

    assert topic_result == lection
    assert datetime_result == lection
    lection_service.update_topic.assert_called_once_with(lection.id, "New Topic")
    lection_service.update_datetime.assert_called_once_with(
        lection.id,
        lection.started_at,
        lection.ended_at,
    )


@pytest.mark.asyncio
async def test_manage_questions_use_case_returns_updated_question_lists():
    question_service = AsyncMock()
    admin = create_admin()
    lection = create_lection()
    question = create_question(lection.id)
    updated_questions = [question]
    question_service.get_questions_by_lection.return_value = updated_questions
    question_service.get_question.return_value = question
    use_case = ManageQuestionsUseCase(question_service=question_service)

    created = await use_case.create_question(lection.id, "New Question", admin)
    updated = await use_case.update_question(question.id, "Updated", admin)
    deleted = await use_case.delete_question(question.id, admin)

    assert created == updated_questions
    assert updated == updated_questions
    assert deleted == updated_questions
    question_service.create_question.assert_called_once_with(lection.id, "New Question")
    question_service.update_question.assert_called_once_with(question.id, "Updated")
    question_service.delete_question.assert_called_once_with(question.id)


@pytest.mark.asyncio
async def test_manage_files_use_case_uploads_updates_and_reads_presentation():
    lection_service = AsyncMock()
    existing_file_id = "tg-existing-presentation"
    uploaded_file_id = "tg-uploaded-presentation"
    lection = create_lection(presentation_file_id=existing_file_id)
    updated_lection = create_lection(presentation_file_id=uploaded_file_id)
    updated_lection.id = lection.id
    lection_service.get_by_id.return_value = updated_lection
    lection_service.update_presentation_file.return_value = updated_lection
    use_case = ManageFilesUseCase(lection_service=lection_service)
    admin = create_admin()

    upload_result = await use_case.upload_presentation(lection.id, uploaded_file_id, admin)
    file_id = await use_case.get_presentation_file_id(lection.id, admin)
    telegram_file_id = await use_case.get_presentation_telegram_file_id(lection.id, admin)

    assert upload_result == updated_lection
    assert file_id == uploaded_file_id
    assert telegram_file_id == uploaded_file_id
    lection_service.update_presentation_file.assert_called_once_with(lection.id, uploaded_file_id)


@pytest.mark.asyncio
async def test_manage_files_use_case_raises_when_presentation_missing():
    lection_service = AsyncMock()
    lection = create_lection(presentation_file_id=None)
    lection_service.get_by_id.return_value = lection
    use_case = ManageFilesUseCase(lection_service=lection_service)

    with pytest.raises(FileNotFound):
        await use_case.get_presentation_telegram_file_id(lection.id, create_admin())
