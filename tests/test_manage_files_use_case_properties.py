"""
Property-based tests for ManageFilesUseCase.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings, strategies as st

from reflebot.apps.reflections.schemas import AdminReadSchema, LectionSessionReadSchema
from reflebot.apps.reflections.use_cases.lection import ManageFilesUseCase


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


def create_lection(file_id: str | None, recording: bool = False) -> LectionSessionReadSchema:
    now = datetime.now(timezone.utc)
    return LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic="Topic",
        presentation_file_id=None if recording else file_id,
        recording_file_id=file_id if recording else None,
        started_at=now,
        ended_at=now,
        deadline=now,
        created_at=now,
        updated_at=now,
    )


@given(has_previous_file=st.booleans(), is_recording=st.booleans())
@settings(max_examples=40)
@pytest.mark.asyncio
async def test_property_18_file_upload_and_retrieval(has_previous_file: bool, is_recording: bool):
    """
    Property 18: File Upload and Retrieval.

    Для любой лекции загрузка файла должна сохранять новый file_id,
    а получение URL должно использовать именно его.
    """
    previous_file_id = "tg-old-file" if has_previous_file else None
    new_file_id = "tg-new-file"
    lection_service = AsyncMock()
    updated_lection = create_lection(new_file_id, recording=is_recording)
    lection_service.get_by_id.return_value = updated_lection
    if is_recording:
        lection_service.update_recording_file.return_value = updated_lection
    else:
        lection_service.update_presentation_file.return_value = updated_lection

    use_case = ManageFilesUseCase(lection_service=lection_service)
    admin = create_admin()

    if is_recording:
        result = await use_case.upload_recording(updated_lection.id, new_file_id, admin)
        stored_file_id = await use_case.get_recording_telegram_file_id(updated_lection.id, admin)
        lection_service.update_recording_file.assert_called_once_with(updated_lection.id, new_file_id)
    else:
        result = await use_case.upload_presentation(updated_lection.id, new_file_id, admin)
        stored_file_id = await use_case.get_presentation_telegram_file_id(updated_lection.id, admin)
        lection_service.update_presentation_file.assert_called_once_with(updated_lection.id, new_file_id)

    assert result.id == updated_lection.id
    assert stored_file_id == new_file_id
