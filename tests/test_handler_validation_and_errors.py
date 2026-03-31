"""
Property-based tests for handler validation and error handling.

Feature: telegram-bot-full-workflow
"""

import io
import string
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import UploadFile
from hypothesis import given, settings, strategies as st

from reflebot.apps.reflections.exceptions import CSVParsingError
from reflebot.apps.reflections.handlers.button_handler import ButtonActionHandler
from reflebot.apps.reflections.handlers.file_handler import FileUploadHandler
from reflebot.apps.reflections.handlers.text_handler import TextInputHandler
from reflebot.apps.reflections.schemas import AdminReadSchema
from reflebot.apps.reflections.telegram.buttons import TelegramButtons
from reflebot.apps.reflections.telegram.messages import TelegramMessages
from reflebot.core.utils.exceptions import PermissionDeniedError

TECHNICAL_DETAIL_STRATEGY = st.text(
    alphabet=string.ascii_letters + string.digits,
    min_size=3,
    max_size=80,
)


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
    """Собрать handler кнопок с моками."""
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


def create_text_handler(
    *,
    context: dict,
    button_handler: ButtonActionHandler | None = None,
) -> tuple[TextInputHandler, AsyncMock]:
    """Собрать handler текста с заданным контекстом."""
    button_handler = button_handler or build_button_handler()
    context_service = AsyncMock()
    context_service.get_context.return_value = context
    handler = TextInputHandler(
        context_service=context_service,
        admin_service=button_handler.admin_service,
        teacher_service=button_handler.teacher_service,
        student_service=button_handler.student_service,
        create_admin_use_case=AsyncMock(),
        attach_teachers_to_course_use_case=AsyncMock(),
        update_lection_use_case=AsyncMock(),
        manage_questions_use_case=AsyncMock(),
        button_handler=button_handler,
    )
    return handler, context_service


@given(invalid_fullname=st.text(max_size=2))
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_29_invalid_fullname_validation(invalid_fullname: str):
    """
    Property 29: Input Validation

    For any невалидного ФИО короче 3 символов система должна вернуть
    понятную ошибку и запросить ввод повторно.

    **Validates: Requirements 28.1, 28.4**
    """
    handler, context_service = create_text_handler(
        context={"action": "create_admin", "step": "awaiting_fullname", "data": {}},
    )

    response = await handler.handle(invalid_fullname, 1)

    context_service.set_context.assert_called_once_with(
        1,
        action="create_admin",
        step="awaiting_fullname",
        data={"validation_attempts": 1},
    )
    assert response.awaiting_input is True
    assert response.message == TelegramMessages.get_validation_error_fullname()


@given(
    prefix=st.text(min_size=0, max_size=5),
    suffix=st.text(min_size=0, max_size=5),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_29_invalid_username_validation(prefix: str, suffix: str):
    """
    Property 29: Input Validation

    For any username с символом @ система должна вернуть ошибку
    и сохранить счетчик попыток.

    **Validates: Requirements 28.2, 28.4**
    """
    handler, context_service = create_text_handler(
        context={
            "action": "create_admin",
            "step": "awaiting_username",
            "data": {"fullname": "Иванов Иван"},
        },
    )

    response = await handler.handle(f"{prefix}@{suffix}", 1)

    context_service.set_context.assert_called_once()
    assert context_service.set_context.call_args.kwargs["data"]["validation_attempts"] == 1
    assert response.awaiting_input is True
    assert response.message == TelegramMessages.get_validation_error_username()


@given(
    invalid_datetime=st.sampled_from(
        [
            "not-a-date",
            "31.02.2024 10:00-11:00",
            "01.01.2024 12:00-10:00",
            "99.99.9999 10:00-11:00",
        ]
    )
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_29_datetime_validation(invalid_datetime: str):
    """
    Property 29: Input Validation

    For any невалидной даты лекции система должна вернуть ошибку
    и запросить ввод повторно.

    **Validates: Requirements 28.3, 28.4**
    """
    handler, context_service = create_text_handler(
        context={
            "action": "edit_lection_date",
            "step": "awaiting_datetime",
            "data": {"lection_id": str(uuid.uuid4())},
        },
    )

    response = await handler.handle(invalid_datetime, 1)

    context_service.set_context.assert_called_once()
    assert context_service.set_context.call_args.kwargs["data"]["validation_attempts"] == 1
    assert response.awaiting_input is True
    assert response.message in {
        TelegramMessages.get_invalid_date_format(),
        TelegramMessages.get_invalid_date_range(),
    }


@given(detail=st.text(min_size=1, max_size=80))
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_30_parser_error_message_clarity(detail: str):
    """
    Property 30: Error Message Clarity

    For any ошибки парсинга файла handler должен показать понятное
    сообщение пользователю и залогировать ошибку.

    **Validates: Requirements 29.1, 29.4**
    """
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "create_course",
        "data": {"course_name": "Тестовый курс"},
    }
    button_handler = build_button_handler()
    file_handler = FileUploadHandler(
        context_service=context_service,
        create_course_from_excel_use_case=AsyncMock(side_effect=CSVParsingError(detail)),
        attach_students_to_course_use_case=AsyncMock(),
        manage_files_use_case=AsyncMock(),
        reflection_workflow_service=AsyncMock(),
        button_handler=button_handler,
    )

    with patch("reflebot.apps.reflections.handlers.base.logger.exception") as logger_mock:
        response = await file_handler.handle(
            UploadFile(filename="students.csv", file=io.BytesIO(b"data")),
            1,
        )

    logger_mock.assert_called_once()
    assert response.awaiting_input is True
    assert "Ошибка обработки файла" in response.message
    assert detail in response.message


@given(detail=TECHNICAL_DETAIL_STRATEGY)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_30_permission_error_message_clarity(detail: str):
    """
    Property 30: Error Message Clarity

    For any ошибки прав доступа handler должен вернуть понятное сообщение
    без технических деталей и залогировать ошибку.

    **Validates: Requirements 29.3, 29.4**
    """
    handler = build_button_handler()
    handler.admin_service.get_by_telegram_id.side_effect = PermissionDeniedError(detail)

    with patch("reflebot.apps.reflections.handlers.base.logger.exception") as logger_mock:
        response = await handler.handle(TelegramButtons.ADMIN_CREATE_ADMIN, 1)

    logger_mock.assert_called_once()
    assert TelegramMessages.get_permission_denied() in response.message
    assert detail not in response.message


@given(detail=TECHNICAL_DETAIL_STRATEGY)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_30_critical_error_clears_context_and_hides_details(detail: str):
    """
    Property 30: Error Message Clarity

    For any критической ошибки система должна скрывать технические детали,
    очищать контекст и логировать исключение.

    **Validates: Requirements 29.2, 29.4, 29.5**
    """
    button_handler = build_button_handler()
    handler, context_service = create_text_handler(
        context={
            "action": "create_admin",
            "step": "awaiting_username",
            "data": {"fullname": "Иванов Иван"},
        },
        button_handler=button_handler,
    )
    handler.admin_service.get_by_telegram_username.side_effect = RuntimeError(detail)

    with patch("reflebot.apps.reflections.handlers.base.logger.exception") as logger_mock:
        response = await handler.handle("ivanov", 1)

    logger_mock.assert_called_once()
    context_service.clear_context.assert_called_once_with(1)
    assert response.message == TelegramMessages.get_generic_error()
    assert detail not in response.message
