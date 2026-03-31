"""
Property-based tests for admin workflow and back navigation.

Feature: telegram-bot-full-workflow
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from hypothesis import given, settings, strategies as st

from reflebot.apps.reflections.handlers.button_handler import ButtonActionHandler
from reflebot.apps.reflections.handlers.text_handler import TextInputHandler
from reflebot.apps.reflections.models import Admin
from reflebot.apps.reflections.schemas import ActionResponseSchema, AdminReadSchema
from reflebot.apps.reflections.telegram.buttons import TelegramButtons
from reflebot.apps.reflections.telegram.messages import TelegramMessages
from reflebot.core.utils.exceptions import ModelFieldNotFoundException


def create_admin() -> AdminReadSchema:
    """Создать администратора для тестов."""
    now = datetime.now(timezone.utc)
    return AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Admin",
        telegram_username="admin",
        telegram_id=1,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def build_button_handler() -> ButtonActionHandler:
    """Собрать button handler с моками."""
    admin_service = AsyncMock()
    teacher_service = AsyncMock()
    student_service = AsyncMock()
    admin_service.get_by_telegram_id.return_value = create_admin()
    teacher_service.get_by_telegram_id.return_value = None
    student_service.get_by_telegram_id.return_value = None
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


def build_text_handler(
    *,
    context: dict,
    button_handler: ButtonActionHandler,
    create_admin_use_case: AsyncMock | None = None,
) -> tuple[TextInputHandler, AsyncMock, AsyncMock]:
    """Собрать text handler для тестового workflow."""
    context_service = AsyncMock()
    context_service.get_context.return_value = context
    create_admin_use_case = create_admin_use_case or AsyncMock()
    handler = TextInputHandler(
        context_service=context_service,
        admin_service=button_handler.admin_service,
        teacher_service=button_handler.teacher_service,
        student_service=button_handler.student_service,
        create_admin_use_case=create_admin_use_case,
        attach_teachers_to_course_use_case=AsyncMock(),
        update_lection_use_case=AsyncMock(),
        manage_questions_use_case=AsyncMock(),
        button_handler=button_handler,
    )
    return handler, context_service, create_admin_use_case


@given(
    fullname=st.text(
        alphabet=st.characters(whitelist_categories=("L", "Zs")),
        min_size=3,
        max_size=40,
    ).filter(lambda value: len(value.strip()) >= 3),
    username=st.text(
        alphabet=st.characters(whitelist_categories=("L", "Nd", "Pc")),
        min_size=1,
        max_size=32,
    ).filter(lambda value: value.strip() != ""),
    username_exists=st.booleans(),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_31_admin_creation_workflow(
    fullname: str,
    username: str,
    username_exists: bool,
):
    """
    Property 31: Admin Creation Workflow

    For any валидного многошагового диалога система должна запросить ФИО,
    затем username, проверить уникальность и либо создать администратора,
    либо запросить другой username.

    **Validates: Requirements 30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 30.7, 30.8**
    """
    button_handler = build_button_handler()

    start_response = await button_handler.handle(TelegramButtons.ADMIN_CREATE_ADMIN, 1)

    button_handler.context_service.push_navigation.assert_called_once_with(
        1,
        button_handler.CREATE_ADMIN_FULLNAME_SCREEN,
    )
    button_handler.context_service.set_context.assert_called_once_with(
        1,
        action="create_admin",
        step="awaiting_fullname",
    )
    assert start_response.awaiting_input is True
    assert start_response.message == TelegramMessages.get_create_admin_request_fullname()

    fullname_handler, fullname_context_service, _ = build_text_handler(
        context={"action": "create_admin", "step": "awaiting_fullname", "data": {}},
        button_handler=button_handler,
    )
    fullname_response = await fullname_handler.handle(fullname, 1)

    fullname_context_service.set_context.assert_called_once_with(
        1,
        action="create_admin",
        step="awaiting_username",
        data={"fullname": fullname.strip()},
    )
    fullname_context_service.push_navigation.assert_called_once_with(
        1,
        button_handler.CREATE_ADMIN_USERNAME_SCREEN,
    )
    assert fullname_response.awaiting_input is True
    assert fullname_response.message == TelegramMessages.get_create_admin_request_username()

    created_admin = create_admin()
    created_admin.full_name = fullname.strip()
    username_handler, username_context_service, create_admin_use_case = build_text_handler(
        context={
            "action": "create_admin",
            "step": "awaiting_username",
            "data": {"fullname": fullname.strip()},
        },
        button_handler=button_handler,
        create_admin_use_case=AsyncMock(return_value=created_admin),
    )

    if username_exists:
        button_handler.admin_service.get_by_telegram_username.side_effect = None
        button_handler.admin_service.get_by_telegram_username.return_value = created_admin
    else:
        button_handler.admin_service.get_by_telegram_username.side_effect = ModelFieldNotFoundException(
            Admin,
            "telegram_username",
            username.strip(),
        )

    response = await username_handler.handle(username, 1)

    if username_exists:
        create_admin_use_case.assert_not_called()
        username_context_service.clear_context.assert_not_called()
        assert response.awaiting_input is True
        assert response.message == TelegramMessages.get_username_already_exists()
    else:
        create_admin_use_case.assert_called_once()
        create_call = create_admin_use_case.call_args
        assert create_call.args[0].full_name == fullname.strip()
        assert create_call.args[0].telegram_username == username.strip()
        assert create_call.args[0].telegram_id is None
        assert create_call.args[0].is_active is True
        username_context_service.clear_context.assert_called_once_with(1)
        assert TelegramMessages.get_admin_created_message(fullname.strip()) in response.message
        assert any(button.action == TelegramButtons.ADMIN_CREATE_ADMIN for button in response.buttons)


@given(
    previous_screen=st.sampled_from(
        [
            "course_menu",
            "questions_menu",
            ButtonActionHandler.CREATE_ADMIN_FULLNAME_SCREEN,
        ]
    )
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_28_navigation_history(previous_screen: str):
    """
    Property 28: Navigation History

    For any кнопки "Назад" handler должен вернуть предыдущий экран
    согласно navigation_history.

    **Validates: Requirements 27.2, 27.3**
    """
    handler = build_button_handler()
    course_id = uuid.uuid4()
    lection_id = uuid.uuid4()
    handler.context_service.pop_navigation.return_value = previous_screen
    handler.context_service.get_context.return_value = {
        "data": {
            "course_id": str(course_id),
            "lection_id": str(lection_id),
        }
    }

    if previous_screen == "course_menu":
        expected = ActionResponseSchema(message="course", buttons=[], awaiting_input=False)
        handler.render_course_menu = AsyncMock(return_value=expected)
    elif previous_screen == "questions_menu":
        expected = ActionResponseSchema(message="questions", buttons=[], awaiting_input=False)
        handler.render_questions_menu = AsyncMock(return_value=expected)

    response = await handler.handle(TelegramButtons.BACK, 1)

    if previous_screen == "course_menu":
        handler.render_course_menu.assert_called_once_with(1, course_id)
        assert response.message == "course"
    elif previous_screen == "questions_menu":
        handler.render_questions_menu.assert_called_once_with(1, lection_id)
        assert response.message == "questions"
    else:
        handler.context_service.set_context.assert_called_once_with(
            1,
            action="create_admin",
            step="awaiting_fullname",
        )
        assert response.awaiting_input is True
        assert response.message == TelegramMessages.get_create_admin_request_fullname()


@pytest.mark.asyncio
async def test_back_to_main_menu_clears_context():
    """Возврат в главное меню должен очищать контекст пользователя."""
    handler = build_button_handler()
    handler.context_service.pop_navigation.return_value = None

    await handler.handle(TelegramButtons.BACK, 1)

    handler.context_service.clear_context.assert_called_once_with(1)
