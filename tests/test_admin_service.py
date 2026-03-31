"""
Unit тесты для AdminService.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from reflebot.apps.reflections.services.admin import AdminService
from reflebot.apps.reflections.schemas import (
    AdminCreateSchema,
    AdminReadSchema,
    StudentReadSchema,
    TeacherReadSchema,
)


@pytest.fixture
def mock_admin_repository():
    """Мок репозитория администраторов."""
    return AsyncMock()


@pytest.fixture
def mock_student_repository():
    """Мок репозитория студентов."""
    return AsyncMock()


@pytest.fixture
def mock_teacher_repository():
    """Мок репозитория преподавателей."""
    return AsyncMock()


@pytest.fixture
def admin_service(
    mock_admin_repository,
    mock_student_repository,
    mock_teacher_repository,
):
    """Сервис администраторов с моками."""
    return AdminService(
        repository=mock_admin_repository,
        student_repository=mock_student_repository,
        teacher_repository=mock_teacher_repository,
    )


@pytest.mark.asyncio
async def test_create_admin_copies_telegram_id_from_teacher(
    admin_service,
    mock_admin_repository,
    mock_student_repository,
    mock_teacher_repository,
):
    """Новый администратор наследует telegram_id из преподавателей."""
    create_data = AdminCreateSchema(
        full_name="Иванов Иван",
        telegram_username="ivanov",
    )
    mock_teacher_repository.get_by_telegram_username.return_value = TeacherReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=111222,
        is_active=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )
    mock_admin_repository.create.return_value = AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=111222,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    result = await admin_service.create_admin(create_data)

    assert result.telegram_id == 111222
    create_call = mock_admin_repository.create.call_args[0][0]
    assert create_call.telegram_id == 111222
    mock_student_repository.get_by_telegram_username.assert_not_called()


@pytest.mark.asyncio
async def test_create_admin_copies_telegram_id_from_student_when_teacher_missing(
    admin_service,
    mock_admin_repository,
    mock_student_repository,
    mock_teacher_repository,
):
    """Новый администратор наследует telegram_id из студентов."""
    create_data = AdminCreateSchema(
        full_name="Иванов Иван",
        telegram_username="ivanov",
    )
    mock_teacher_repository.get_by_telegram_username.return_value = None
    mock_student_repository.get_by_telegram_username.return_value = StudentReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=333444,
        is_active=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )
    mock_admin_repository.create.return_value = AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=333444,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    result = await admin_service.create_admin(create_data)

    assert result.telegram_id == 333444
    create_call = mock_admin_repository.create.call_args[0][0]
    assert create_call.telegram_id == 333444
    mock_student_repository.get_by_telegram_username.assert_called_once_with("ivanov")


@pytest.mark.asyncio
async def test_create_admin_keeps_explicit_telegram_id(
    admin_service,
    mock_admin_repository,
    mock_student_repository,
    mock_teacher_repository,
):
    """Явно переданный telegram_id не переопределяется."""
    create_data = AdminCreateSchema(
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=999888,
    )
    mock_admin_repository.create.return_value = AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=999888,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    result = await admin_service.create_admin(create_data)

    assert result.telegram_id == 999888
    create_call = mock_admin_repository.create.call_args[0][0]
    assert create_call.telegram_id == 999888
    mock_teacher_repository.get_by_telegram_username.assert_not_called()
    mock_student_repository.get_by_telegram_username.assert_not_called()
