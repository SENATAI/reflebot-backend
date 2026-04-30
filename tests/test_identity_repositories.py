"""
Unit tests for username-based identity repositories.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
import uuid

import pytest

from reflebot.apps.reflections.models import Admin, Student, Teacher
from reflebot.apps.reflections.repositories.admin import AdminRepository
from reflebot.apps.reflections.repositories.student import StudentRepository
from reflebot.apps.reflections.repositories.teacher import TeacherRepository


def configure_session(session: AsyncMock) -> AsyncMock:
    entered_session = AsyncMock()
    session.__aenter__.return_value = entered_session
    session.__aexit__.return_value = None
    begin_cm = AsyncMock()
    begin_cm.__aenter__.return_value = None
    begin_cm.__aexit__.return_value = None
    entered_session.begin = Mock(return_value=begin_cm)
    entered_session.execute = session.execute
    entered_session.flush = AsyncMock()
    return entered_session


def create_admin_model() -> Admin:
    now = datetime.now(timezone.utc)
    model = Admin(
        id=uuid.uuid4(),
        full_name="Admin",
        telegram_username="user",
        telegram_id=None,
        is_active=True,
    )
    model.created_at = now
    model.updated_at = now
    return model


def create_student_model() -> Student:
    now = datetime.now(timezone.utc)
    model = Student(
        id=uuid.uuid4(),
        full_name="Student",
        telegram_username="user",
        telegram_id=None,
        is_active=True,
    )
    model.created_at = now
    model.updated_at = now
    return model


def create_teacher_model() -> Teacher:
    now = datetime.now(timezone.utc)
    model = Teacher(
        id=uuid.uuid4(),
        full_name="Teacher",
        telegram_username="user",
        telegram_id=None,
        is_active=True,
    )
    model.created_at = now
    model.updated_at = now
    return model


@pytest.mark.asyncio
async def test_admin_repository_get_by_username_uses_preferred_row_lookup():
    session = AsyncMock()
    configure_session(session)
    repository = AdminRepository(session=session)
    execute_result = Mock()
    execute_result.scalar_one_or_none.side_effect = AssertionError(
        "Repository must not use scalar_one_or_none for telegram_username lookups."
    )
    execute_result.scalars.return_value.first.return_value = create_admin_model()
    session.execute.return_value = execute_result

    result = await repository.get_by_telegram_username("user")

    assert result.telegram_username == "user"


@pytest.mark.asyncio
async def test_student_repository_get_by_username_uses_preferred_row_lookup():
    session = AsyncMock()
    configure_session(session)
    repository = StudentRepository(session=session)
    execute_result = Mock()
    execute_result.scalar_one_or_none.side_effect = AssertionError(
        "Repository must not use scalar_one_or_none for telegram_username lookups."
    )
    execute_result.scalars.return_value.first.return_value = create_student_model()
    session.execute.return_value = execute_result

    result = await repository.get_by_telegram_username("user")

    assert result is not None
    assert result.telegram_username == "user"


@pytest.mark.asyncio
async def test_teacher_repository_get_by_username_uses_preferred_row_lookup():
    session = AsyncMock()
    configure_session(session)
    repository = TeacherRepository(session=session)
    execute_result = Mock()
    execute_result.scalar_one_or_none.side_effect = AssertionError(
        "Repository must not use scalar_one_or_none for telegram_username lookups."
    )
    execute_result.scalars.return_value.first.return_value = create_teacher_model()
    session.execute.return_value = execute_result

    result = await repository.get_by_telegram_username("user")

    assert result is not None
    assert result.telegram_username == "user"


@pytest.mark.asyncio
async def test_admin_repository_update_telegram_id_updates_only_preferred_row():
    session = AsyncMock()
    entered_session = configure_session(session)
    repository = AdminRepository(session=session)
    execute_result = Mock()
    execute_result.scalar_one_or_none.side_effect = AssertionError(
        "Repository must not bulk-update by telegram_username when duplicates exist."
    )
    model = create_admin_model()
    execute_result.scalars.return_value.first.return_value = model
    session.execute.return_value = execute_result

    result = await repository.update_telegram_id("user", 99)

    assert result.telegram_id == 99
    entered_session.flush.assert_awaited_once()
