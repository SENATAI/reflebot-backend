"""
Unit tests for AuthService.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
import uuid

import pytest

from reflebot.apps.reflections.schemas import AdminLoginSchema, AdminReadSchema, StudentReadSchema, TeacherReadSchema
from reflebot.apps.reflections.models import Admin
from reflebot.apps.reflections.services.auth import AuthService
from reflebot.core.utils.exceptions import ModelFieldNotFoundException


def create_admin() -> AdminReadSchema:
    now = datetime.now(timezone.utc)
    return AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Admin",
        telegram_username="user",
        telegram_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def create_student() -> StudentReadSchema:
    now = datetime.now(timezone.utc)
    return StudentReadSchema(
        id=uuid.uuid4(),
        full_name="Student",
        telegram_username="user",
        telegram_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def create_teacher() -> TeacherReadSchema:
    now = datetime.now(timezone.utc)
    return TeacherReadSchema(
        id=uuid.uuid4(),
        full_name="Teacher",
        telegram_username="user",
        telegram_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def build_auth_service(
    *,
    admin_repository: AsyncMock,
    student_repository: AsyncMock,
    teacher_repository: AsyncMock,
    course_repository: AsyncMock | None = None,
    context_service: AsyncMock | None = None,
    student_service: AsyncMock | None = None,
    lection_service: AsyncMock | None = None,
    course_invite_service: AsyncMock | None = None,
) -> AuthService:
    return AuthService(
        admin_repository=admin_repository,
        student_repository=student_repository,
        teacher_repository=teacher_repository,
        course_repository=course_repository or AsyncMock(),
        context_service=context_service or AsyncMock(),
        student_service=student_service or AsyncMock(),
        lection_service=lection_service or AsyncMock(),
        course_invite_service=course_invite_service or AsyncMock(),
    )


@pytest.mark.asyncio
async def test_auth_service_searches_all_tables_and_updates_telegram_id():
    admin_repository = AsyncMock()
    student_repository = AsyncMock()
    teacher_repository = AsyncMock()
    context_service = AsyncMock()
    admin = create_admin()
    student = create_student()
    teacher = create_teacher()

    admin_repository.get_by_telegram_username.return_value = admin
    admin_repository.update_telegram_id.return_value = admin.model_copy(update={"telegram_id": 99})
    student_repository.get_by_telegram_username.return_value = student
    student_repository.update_telegram_id.return_value = student.model_copy(update={"telegram_id": 99})
    teacher_repository.get_by_telegram_username.return_value = teacher
    teacher_repository.update_telegram_id.return_value = teacher.model_copy(update={"telegram_id": 99})

    service = build_auth_service(
        admin_repository=admin_repository,
        student_repository=student_repository,
        teacher_repository=teacher_repository,
        context_service=context_service,
    )

    response = await service.login_user("user", AdminLoginSchema(telegram_id=99))

    assert response.is_admin is True
    assert response.is_teacher is True
    assert response.is_student is True
    assert response.awaiting_input is False
    admin_repository.update_telegram_id.assert_called_once_with("user", 99)
    student_repository.update_telegram_id.assert_called_once_with("user", 99)
    teacher_repository.update_telegram_id.assert_called_once_with("user", 99)
    context_service.clear_context.assert_awaited_once_with(99)


@pytest.mark.asyncio
async def test_auth_service_gives_teacher_buttons_to_admin_without_teacher_role():
    admin_repository = AsyncMock()
    student_repository = AsyncMock()
    teacher_repository = AsyncMock()
    context_service = AsyncMock()
    admin = create_admin()

    admin_repository.get_by_telegram_username.return_value = admin
    admin_repository.update_telegram_id.return_value = admin.model_copy(update={"telegram_id": 99})
    student_repository.get_by_telegram_username.return_value = None
    teacher_repository.get_by_telegram_username.return_value = None

    service = build_auth_service(
        admin_repository=admin_repository,
        student_repository=student_repository,
        teacher_repository=teacher_repository,
        context_service=context_service,
    )

    response = await service.login_user("user", AdminLoginSchema(telegram_id=99))

    actions = {button.action for button in response.buttons}
    assert response.is_admin is True
    assert response.is_teacher is False
    assert "admin_view_courses" in actions
    assert "teacher_analytics" in actions
    assert "teacher_next_lection" in actions
    context_service.clear_context.assert_awaited_once_with(99)


@pytest.mark.asyncio
async def test_auth_service_existing_admin_or_teacher_never_falls_back_to_course_code_prompt():
    admin_repository = AsyncMock()
    student_repository = AsyncMock()
    teacher_repository = AsyncMock()
    context_service = AsyncMock()
    teacher = create_teacher()

    admin_repository.get_by_telegram_username.side_effect = ModelFieldNotFoundException(
        Admin,
        "telegram_username",
        "teacher_user",
    )
    student_repository.get_by_telegram_username.return_value = None
    teacher_repository.get_by_telegram_username.return_value = teacher
    teacher_repository.update_telegram_id.return_value = teacher.model_copy(update={"telegram_id": 99})

    service = build_auth_service(
        admin_repository=admin_repository,
        student_repository=student_repository,
        teacher_repository=teacher_repository,
        context_service=context_service,
    )

    response = await service.login_user("teacher_user", AdminLoginSchema(telegram_id=99))

    assert response.message != "Привет студент, введи код курса."
    assert response.is_teacher is True
    assert response.awaiting_input is False
    context_service.set_context.assert_not_awaited()
    context_service.clear_context.assert_awaited_once_with(99)


@pytest.mark.asyncio
async def test_auth_service_unknown_username_requests_course_code():
    admin_repository = AsyncMock()
    student_repository = AsyncMock()
    teacher_repository = AsyncMock()
    context_service = AsyncMock()
    student_repository.get_by_telegram_username.return_value = None
    teacher_repository.get_by_telegram_username.return_value = None
    admin_repository.get_by_telegram_username.side_effect = ModelFieldNotFoundException(
        Admin,
        "telegram_username",
        "new_student",
    )

    service = build_auth_service(
        admin_repository=admin_repository,
        student_repository=student_repository,
        teacher_repository=teacher_repository,
        context_service=context_service,
    )

    response = await service.login_user("new_student", AdminLoginSchema(telegram_id=99))

    assert response.message == "Привет студент, введи код курса."
    assert response.buttons == []
    assert response.awaiting_input is True
    context_service.set_context.assert_awaited_once_with(
        99,
        action="register_course_by_code",
        step="awaiting_course_code",
        data={
            "telegram_username": "new_student",
            "telegram_id": 99,
        },
    )
