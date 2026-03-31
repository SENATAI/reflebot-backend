"""
Property-based tests for nearest lection button workflow.

Feature: telegram-bot-full-workflow
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from hypothesis import given, settings, strategies as st

from reflebot.apps.reflections.datetime_utils import REFLECTIONS_LOCAL_TIMEZONE
from reflebot.apps.reflections.handlers.button_handler import ButtonActionHandler
from reflebot.apps.reflections.schemas import AdminReadSchema, LectionSessionReadSchema, TeacherReadSchema
from reflebot.apps.reflections.telegram.buttons import TelegramButtons
from reflebot.apps.reflections.telegram.messages import TelegramMessages


def create_admin() -> AdminReadSchema:
    """Создать администратора для тестов."""
    now = datetime.now(timezone.utc)
    return AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Admin",
        telegram_username="admin",
        telegram_id=100,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def create_teacher() -> TeacherReadSchema:
    """Создать преподавателя для тестов."""
    now = datetime.now(timezone.utc)
    return TeacherReadSchema(
        id=uuid.uuid4(),
        full_name="Teacher",
        telegram_username="teacher",
        telegram_id=200,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def build_button_handler(*, teacher: TeacherReadSchema | None) -> ButtonActionHandler:
    """Собрать handler кнопок для тестов ближайшей лекции."""
    admin_service = AsyncMock()
    teacher_service = AsyncMock()
    student_service = AsyncMock()
    admin_service.get_by_telegram_id.side_effect = Exception("not admin")
    teacher_service.get_by_telegram_id.return_value = teacher
    student_service.get_by_telegram_id.side_effect = Exception("not student")
    context_service = AsyncMock()
    context_service.get_context.return_value = None
    return ButtonActionHandler(
        context_service=context_service,
        admin_service=admin_service,
        teacher_service=teacher_service,
        student_service=student_service,
        course_service=AsyncMock(),
        course_invite_service=AsyncMock(
            build_course_invite_link=Mock(return_value="https://t.me/reflebot?start=test"),
            generate_course_join_code=Mock(return_value="COURSE-CODE"),
            parse_course_join_code=Mock(return_value=uuid.uuid4()),
        ),
        default_question_service=AsyncMock(),
        lection_service=AsyncMock(),
        question_service=AsyncMock(),
        pagination_service=AsyncMock(),
        manage_files_use_case=AsyncMock(),
        reflection_workflow_service=AsyncMock(),
        view_lection_analytics_use_case=AsyncMock(),
        view_student_analytics_use_case=AsyncMock(),
        view_reflection_details_use_case=AsyncMock(),
    )


@given(
    topic=st.text(min_size=1, max_size=80),
    hours_until_start=st.integers(min_value=1, max_value=240),
    duration_hours=st.integers(min_value=1, max_value=8),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_22_nearest_lection_button_returns_upcoming_lection(
    topic: str,
    hours_until_start: int,
    duration_hours: int,
):
    """
    Property 22: Nearest Lection Query

    For any преподавателя кнопка "Ближайшая лекция" должна возвращать
    ближайшую будущую лекцию и сохранять экран в контексте.

    **Validates: Requirements 18.2, 18.3**
    """
    teacher = create_teacher()
    handler = build_button_handler(teacher=teacher)
    started_at = datetime.now(timezone.utc) + timedelta(hours=hours_until_start)
    ended_at = started_at + timedelta(hours=duration_hours)
    lection = LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic=topic,
        presentation_file_id=None,
        recording_file_id=None,
        started_at=started_at,
        ended_at=ended_at,
        deadline=ended_at + timedelta(hours=24),
        created_at=started_at,
        updated_at=started_at,
    )
    handler.lection_service.get_nearest_lection_for_teacher.return_value = lection

    response = await handler.handle(TelegramButtons.TEACHER_NEXT_LECTION, teacher.telegram_id)

    handler.lection_service.get_nearest_lection_for_teacher.assert_called_once_with(teacher.id)
    handler.context_service.push_navigation.assert_called_once_with(
        teacher.telegram_id,
        handler.TEACHER_NEAREST_LECTION_SCREEN,
    )
    handler.context_service.set_context.assert_called_once_with(
        teacher.telegram_id,
        action="teacher_nearest_lection",
        step="view",
        data={
            "lection_id": str(lection.id),
            "course_id": str(lection.course_session_id),
        },
    )
    assert topic in response.message
    assert started_at.astimezone(REFLECTIONS_LOCAL_TIMEZONE).strftime("%d.%m.%Y") in response.message
    assert any(button.action == TelegramButtons.BACK for button in response.buttons)


@pytest.mark.asyncio
async def test_nearest_lection_button_returns_empty_state_when_nothing_found():
    """Если ближайшей лекции нет, handler должен вернуть понятное сообщение."""
    teacher = create_teacher()
    handler = build_button_handler(teacher=teacher)
    handler.lection_service.get_nearest_lection_for_teacher.return_value = None

    response = await handler.handle(TelegramButtons.TEACHER_NEXT_LECTION, teacher.telegram_id)

    handler.context_service.push_navigation.assert_not_called()
    handler.context_service.set_context.assert_not_called()
    assert response.message == TelegramMessages.get_no_upcoming_lections()


@pytest.mark.asyncio
async def test_admin_can_open_nearest_lection_without_teacher_role():
    admin = create_admin()
    handler = build_button_handler(teacher=None)
    handler.admin_service.get_by_telegram_id.side_effect = None
    handler.admin_service.get_by_telegram_id.return_value = admin
    started_at = datetime.now(timezone.utc) + timedelta(hours=2)
    ended_at = started_at + timedelta(hours=2)
    lection = LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic="Admin Lecture",
        presentation_file_id=None,
        recording_file_id=None,
        started_at=started_at,
        ended_at=ended_at,
        deadline=ended_at + timedelta(hours=24),
        created_at=started_at,
        updated_at=started_at,
    )
    handler.lection_service.get_nearest_lection.return_value = lection

    response = await handler.handle(TelegramButtons.TEACHER_NEXT_LECTION, admin.telegram_id)

    handler.lection_service.get_nearest_lection.assert_called_once_with()
    handler.lection_service.get_nearest_lection_for_teacher.assert_not_called()
    assert "Admin Lecture" in response.message


@pytest.mark.asyncio
async def test_nearest_lection_back_to_main_menu():
    """Возврат с экрана ближайшей лекции должен приводить в главное меню."""
    teacher = create_teacher()
    handler = build_button_handler(teacher=teacher)
    handler.context_service.pop_navigation.return_value = None

    response = await handler.handle(TelegramButtons.BACK, teacher.telegram_id)

    handler.context_service.clear_context.assert_called_once_with(teacher.telegram_id)
    assert any(button.action == TelegramButtons.TEACHER_NEXT_LECTION for button in response.buttons)
