"""
Tests for button, text and file handlers.
"""

import io
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, AsyncMock, Mock

import pytest
from fastapi import UploadFile

from reflebot.apps.reflections.handlers.button_handler import ButtonActionHandler
from reflebot.apps.reflections.handlers.file_handler import FileUploadHandler
from reflebot.apps.reflections.handlers.text_handler import TextInputHandler
from reflebot.apps.reflections.schemas import (
    ActionResponseSchema,
    AdminReadSchema,
    CourseSessionReadSchema,
    LectionQAReadSchema,
    LectionReflectionReadSchema,
    LectionSessionReadSchema,
    QADetailsSchema,
    QAVideoReadSchema,
    QuestionReadSchema,
    ReflectionDetailsSchema,
    ReflectionVideoReadSchema,
    StudentReadSchema,
)
from reflebot.apps.reflections.services.default_question import DEFAULT_QUESTION_TEMPLATES
from reflebot.apps.reflections.telegram.buttons import TelegramButtons
from reflebot.apps.reflections.telegram.messages import TelegramMessages
from reflebot.apps.reflections.exceptions import CSVFileMissingColumnError
from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from reflebot.apps.reflections.models import Admin, CourseSession


def create_admin() -> AdminReadSchema:
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


def create_course() -> CourseSessionReadSchema:
    now = datetime.now(timezone.utc)
    return CourseSessionReadSchema(
        id=uuid.uuid4(),
        name="Course",
        join_code="ABCD",
        started_at=now,
        ended_at=now,
        created_at=now,
        updated_at=now,
    )


def create_lection(topic: str = "Lecture") -> LectionSessionReadSchema:
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


def create_question(lection_id: uuid.UUID, text: str = "Question?") -> QuestionReadSchema:
    now = datetime.now(timezone.utc)
    return QuestionReadSchema(
        id=uuid.uuid4(),
        lection_session_id=lection_id,
        question_text=text,
        created_at=now,
        updated_at=now,
    )


def create_student() -> StudentReadSchema:
    now = datetime.now(timezone.utc)
    return StudentReadSchema(
        id=uuid.uuid4(),
        full_name="Student",
        telegram_username="student",
        telegram_id=2,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def build_button_handler() -> ButtonActionHandler:
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
        default_question_service=AsyncMock(get_random_question_text=AsyncMock(return_value=DEFAULT_QUESTION_TEMPLATES[0])),
        lection_service=AsyncMock(),
        question_service=AsyncMock(get_questions_by_lection=AsyncMock(return_value=[])),
        pagination_service=AsyncMock(),
        manage_files_use_case=AsyncMock(),
        reflection_workflow_service=AsyncMock(),
        student_history_log_service=AsyncMock(),
        view_lection_analytics_use_case=AsyncMock(),
        view_student_analytics_use_case=AsyncMock(),
        view_reflection_details_use_case=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_button_handler_persists_context_on_create_admin_click():
    handler = build_button_handler()

    response = await handler.handle(TelegramButtons.ADMIN_CREATE_ADMIN, 1)

    handler.context_service.set_context.assert_called_once_with(
        1,
        action="create_admin",
        step="awaiting_fullname",
    )
    assert response.awaiting_input is True


@pytest.mark.asyncio
async def test_text_handler_processes_context_based_fullname_step():
    button_handler = build_button_handler()
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "create_admin",
        "step": "awaiting_fullname",
        "data": {},
    }
    text_handler = TextInputHandler(
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

    response = await text_handler.handle("Иванов Иван", 1)

    context_service.set_context.assert_called_once()
    assert response.awaiting_input is True


@pytest.mark.asyncio
async def test_text_handler_cleans_up_context_on_admin_creation_completion():
    button_handler = build_button_handler()
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "create_admin",
        "step": "awaiting_username",
        "data": {"fullname": "Иванов Иван"},
    }
    button_handler.admin_service.get_by_telegram_username.side_effect = ModelFieldNotFoundException(
        Admin,
        "telegram_username",
        "ivanov",
    )
    created_admin = create_admin()
    created_admin.full_name = "Иванов Иван"
    button_handler.admin_service.create_admin.return_value = created_admin
    text_handler = TextInputHandler(
        context_service=context_service,
        admin_service=button_handler.admin_service,
        teacher_service=button_handler.teacher_service,
        student_service=button_handler.student_service,
        create_admin_use_case=AsyncMock(return_value=created_admin),
        attach_teachers_to_course_use_case=AsyncMock(),
        update_lection_use_case=AsyncMock(),
        manage_questions_use_case=AsyncMock(),
        button_handler=button_handler,
    )

    response = await text_handler.handle("ivanov", 1)

    context_service.clear_context.assert_called_once_with(1)
    assert "успешно создан" in response.message


@pytest.mark.asyncio
async def test_text_handler_course_code_prompts_new_student_for_fullname():
    button_handler = build_button_handler()
    context_service = AsyncMock()
    course = create_course()
    context_service.get_context.return_value = {
        "action": "register_course_by_code",
        "step": "awaiting_course_code",
        "data": {
            "telegram_username": "student",
            "telegram_id": 2,
        },
    }
    button_handler.student_service.get_by_telegram_username.return_value = None
    button_handler.course_service.get_by_id.return_value = course
    button_handler.course_service.get_by_join_code.return_value = course
    text_handler = TextInputHandler(
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

    response = await text_handler.handle(course.join_code, 2)

    context_service.set_context.assert_awaited_once_with(
        2,
        action="register_course_by_code",
        step="awaiting_fullname",
        data={
            "course_id": str(course.id),
            "course_name": course.name,
            "telegram_username": "student",
            "telegram_id": 2,
        },
    )
    assert response.message == TelegramMessages.get_student_course_fullname_request(course.name)
    assert response.awaiting_input is True


@pytest.mark.asyncio
async def test_text_handler_registers_new_student_after_fullname():
    button_handler = build_button_handler()
    context_service = AsyncMock()
    course = create_course()
    student = create_student()
    lection_ids = [uuid.uuid4(), uuid.uuid4()]
    context_service.get_context.return_value = {
        "action": "register_course_by_code",
        "step": "awaiting_fullname",
        "data": {
            "course_id": str(course.id),
            "course_name": course.name,
            "telegram_username": "student",
            "telegram_id": 2,
        },
    }
    button_handler.student_service.get_by_telegram_username.return_value = None
    button_handler.student_service.create_student.return_value = student
    button_handler.lection_service.get_lection_ids_by_course.return_value = lection_ids
    text_handler = TextInputHandler(
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

    response = await text_handler.handle("Иванов Иван", 2)

    button_handler.student_service.create_student.assert_awaited_once_with(
        full_name="Иванов Иван",
        telegram_username="student",
        telegram_id=2,
    )
    button_handler.student_service.attach_to_course.assert_awaited_once_with([student.id], course.id)
    button_handler.student_service.attach_to_lections.assert_awaited_once_with([student.id], lection_ids)
    context_service.clear_context.assert_awaited_once_with(2)
    assert response.message == TelegramMessages.get_student_course_registered(course.name)


@pytest.mark.asyncio
async def test_text_handler_join_course_prompts_existing_student_for_code():
    button_handler = build_button_handler()
    student = create_student()
    button_handler.student_service.get_by_telegram_id.return_value = student
    context_service = AsyncMock()
    context_service.get_context.return_value = None
    text_handler = TextInputHandler(
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

    response = await text_handler.handle("/join_course", student.telegram_id)

    context_service.set_context.assert_awaited_once_with(
        student.telegram_id,
        action="join_course",
        step="awaiting_course_code",
        data={
            "student_id": str(student.id),
            "telegram_username": student.telegram_username,
            "telegram_id": student.telegram_id,
        },
    )
    assert response.message == TelegramMessages.get_join_course_code_request()
    assert response.awaiting_input is True


@pytest.mark.asyncio
async def test_text_handler_join_course_attaches_existing_student_by_code():
    button_handler = build_button_handler()
    student = create_student()
    course = create_course()
    lection_ids = [uuid.uuid4(), uuid.uuid4()]
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "join_course",
        "step": "awaiting_course_code",
        "data": {
            "student_id": str(student.id),
            "telegram_username": student.telegram_username,
            "telegram_id": student.telegram_id,
        },
    }
    button_handler.student_service.get_by_id.return_value = student
    button_handler.course_service.get_by_id.return_value = course
    button_handler.course_service.get_by_join_code.return_value = course
    button_handler.lection_service.get_lection_ids_by_course.return_value = lection_ids
    text_handler = TextInputHandler(
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

    response = await text_handler.handle(course.join_code, student.telegram_id)

    button_handler.student_service.attach_to_course.assert_awaited_once_with([student.id], course.id)
    button_handler.student_service.attach_to_lections.assert_awaited_once_with([student.id], lection_ids)
    context_service.clear_context.assert_awaited_once_with(student.telegram_id)
    assert response.message == TelegramMessages.get_student_course_registered(course.name)


@pytest.mark.asyncio
async def test_text_handler_join_course_returns_validation_message_when_code_not_found():
    button_handler = build_button_handler()
    student = create_student()
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "join_course",
        "step": "awaiting_course_code",
        "data": {
            "student_id": str(student.id),
            "telegram_username": student.telegram_username,
            "telegram_id": student.telegram_id,
        },
    }
    button_handler.course_service.get_by_join_code.side_effect = ModelFieldNotFoundException(
        CourseSession,
        "join_code",
        "ZZZZ",
    )
    text_handler = TextInputHandler(
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

    response = await text_handler.handle("ZZZZ", student.telegram_id)

    assert response.message == TelegramMessages.get_course_code_not_found()
    assert response.awaiting_input is True
    context_service.clear_context.assert_not_awaited()


@pytest.mark.asyncio
async def test_text_handler_join_course_prompts_admin_without_student_role_for_code():
    button_handler = build_button_handler()
    admin = create_admin()
    button_handler.admin_service.get_by_telegram_id.return_value = admin
    button_handler.teacher_service.get_by_telegram_id.return_value = None
    button_handler.student_service.get_by_telegram_id.return_value = None
    context_service = AsyncMock()
    context_service.get_context.return_value = None
    text_handler = TextInputHandler(
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

    response = await text_handler.handle("/join_course", 777)

    context_service.set_context.assert_awaited_once_with(
        777,
        action="join_course",
        step="awaiting_course_code",
        data={
            "full_name": admin.full_name,
            "telegram_username": admin.telegram_username,
            "telegram_id": 777,
        },
    )
    assert response.message == TelegramMessages.get_join_course_code_request()
    assert response.awaiting_input is True


@pytest.mark.asyncio
async def test_text_handler_join_course_creates_student_for_admin_without_student_role():
    button_handler = build_button_handler()
    course = create_course()
    lection_ids = [uuid.uuid4(), uuid.uuid4()]
    created_student = create_student()
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "join_course",
        "step": "awaiting_course_code",
        "data": {
            "full_name": "Admin User",
            "telegram_username": "admin_user",
            "telegram_id": 777,
        },
    }
    button_handler.student_service.get_by_telegram_username.return_value = None
    button_handler.student_service.create_student.return_value = created_student
    button_handler.course_service.get_by_join_code.return_value = course
    button_handler.lection_service.get_lection_ids_by_course.return_value = lection_ids
    text_handler = TextInputHandler(
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

    response = await text_handler.handle(course.join_code, 777)

    button_handler.student_service.create_student.assert_awaited_once_with(
        full_name="Admin User",
        telegram_username="admin_user",
        telegram_id=777,
    )
    button_handler.student_service.attach_to_course.assert_awaited_once_with(
        [created_student.id],
        course.id,
    )
    button_handler.student_service.attach_to_lections.assert_awaited_once_with(
        [created_student.id],
        lection_ids,
    )
    context_service.clear_context.assert_awaited_once_with(777)
    assert response.message == TelegramMessages.get_student_course_registered(course.name)


@pytest.mark.asyncio
async def test_text_handler_teacher_attach_completion_shows_finish_creation_button():
    button_handler = build_button_handler()
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "attach_teacher",
        "step": "awaiting_username",
        "data": {"course_id": str(uuid.uuid4()), "fullname": "Иванов Иван"},
    }
    teacher = Mock(full_name="Иванов Иван")
    attach_teachers_use_case = AsyncMock(return_value=teacher)
    text_handler = TextInputHandler(
        context_service=context_service,
        admin_service=button_handler.admin_service,
        teacher_service=button_handler.teacher_service,
        student_service=button_handler.student_service,
        create_admin_use_case=AsyncMock(),
        attach_teachers_to_course_use_case=attach_teachers_use_case,
        update_lection_use_case=AsyncMock(),
        manage_questions_use_case=AsyncMock(),
        button_handler=button_handler,
    )

    response = await text_handler.handle("teacher_username", 1)

    context_service.set_context.assert_awaited_once()
    assert response.message == TelegramMessages.get_teacher_attached(teacher.full_name)
    assert [button.action for button in response.buttons] == [
        TelegramButtons.TEACHER_ADD_ANOTHER,
        TelegramButtons.COURSE_ATTACH_STUDENTS,
        TelegramButtons.TEACHER_FINISH_COURSE_CREATION,
    ]


@pytest.mark.asyncio
async def test_button_handler_starts_course_creation_with_name_request():
    button_handler = build_button_handler()

    response = await button_handler.handle(TelegramButtons.ADMIN_CREATE_COURSE, 1)

    button_handler.context_service.set_context.assert_awaited_once_with(
        1,
        action="create_course",
        step="awaiting_course_name",
        data={},
    )
    assert response.message == TelegramMessages.get_create_course_request_name()
    assert response.awaiting_input is True


@pytest.mark.asyncio
async def test_text_handler_create_course_requests_file_after_course_name():
    button_handler = build_button_handler()
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "create_course",
        "step": "awaiting_course_name",
        "data": {},
    }
    text_handler = TextInputHandler(
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

    response = await text_handler.handle("Новый курс", 1)

    context_service.set_context.assert_awaited_once_with(
        1,
        action="create_course",
        step="awaiting_file",
        data={"course_name": "Новый курс"},
    )
    assert response.message == TelegramMessages.get_create_course_request_file()
    assert response.awaiting_input is True


@pytest.mark.asyncio
async def test_render_course_menu_shows_default_questions_button_only_for_lections_without_questions():
    button_handler = build_button_handler()
    course = create_course()
    button_handler.course_service.get_by_id.return_value = course
    lection_with_question = uuid.uuid4()
    lection_without_question = uuid.uuid4()
    button_handler.lection_service.get_lection_ids_by_course.return_value = [
        lection_with_question,
        lection_without_question,
    ]
    button_handler.question_service.get_questions_by_lection.side_effect = [
        [create_question(lection_with_question)],
        [],
    ]

    response = await button_handler.render_course_menu(1, course.id)

    assert course.join_code in response.message
    assert any(button.action == TelegramButtons.COURSE_ADD_DEFAULT_QUESTIONS for button in response.buttons)
    assert all(button.action != TelegramButtons.COURSE_ATTACH_STUDENTS for button in response.buttons[:1])


@pytest.mark.asyncio
async def test_render_course_menu_hides_default_questions_button_when_all_lections_have_questions():
    button_handler = build_button_handler()
    course = create_course()
    lection_ids = [uuid.uuid4(), uuid.uuid4()]
    button_handler.course_service.get_by_id.return_value = course
    button_handler.lection_service.get_lection_ids_by_course.return_value = lection_ids
    button_handler.question_service.get_questions_by_lection.side_effect = [
        [create_question(lection_ids[0])],
        [create_question(lection_ids[1])],
    ]

    response = await button_handler.render_course_menu(1, course.id)

    assert all(button.action != TelegramButtons.COURSE_ADD_DEFAULT_QUESTIONS for button in response.buttons)


@pytest.mark.asyncio
async def test_render_admin_courses_returns_paginated_course_buttons():
    button_handler = build_button_handler()
    course = create_course()
    button_handler.course_service.get_courses_for_admin.return_value = Mock(
        items=[course],
        total_pages=1,
    )

    response = await button_handler.render_admin_courses(1, page=1)

    assert response.message == TelegramMessages.get_select_course_for_admin()
    assert response.buttons[0].action == f"{TelegramButtons.ADMIN_VIEW_COURSE}:{course.id}"
    assert response.buttons[-1].action == TelegramButtons.BACK


@pytest.mark.asyncio
async def test_render_admin_course_details_shows_course_code_and_back_button():
    button_handler = build_button_handler()
    course = create_course()
    button_handler.course_service.get_by_id.return_value = course
    response = await button_handler.render_admin_course_details(1, course.id, page=2)

    assert course.name in response.message
    assert course.join_code in response.message
    assert [button.action for button in response.buttons] == [TelegramButtons.BACK]


@pytest.mark.asyncio
async def test_handle_admin_view_course_uses_page_from_admin_courses_context():
    button_handler = build_button_handler()
    course = create_course()
    button_handler.context_service.get_context.return_value = {
        "action": "admin_courses",
        "step": "view",
        "data": {"page": 3},
    }
    button_handler.render_admin_course_details = AsyncMock(
        return_value=ActionResponseSchema(message="ok"),
    )

    response = await button_handler.handle(f"{TelegramButtons.ADMIN_VIEW_COURSE}:{course.id}", 1)

    button_handler.render_admin_course_details.assert_awaited_once_with(
        1,
        course.id,
        page=3,
        push_navigation=True,
    )
    assert response.message == "ok"


@pytest.mark.asyncio
async def test_button_handler_adds_default_questions_to_course():
    button_handler = build_button_handler()
    course = create_course()
    lection_ids = [uuid.uuid4(), uuid.uuid4()]
    button_handler.context_service.get_context.return_value = {
        "action": "course_menu",
        "step": "view",
        "data": {"course_id": str(course.id)},
    }
    button_handler.lection_service.get_lection_ids_by_course.return_value = lection_ids
    button_handler.question_service.get_questions_by_lection.side_effect = [
        [],
        [create_question(lection_ids[1])],
    ]

    response = await button_handler.handle(TelegramButtons.COURSE_ADD_DEFAULT_QUESTIONS, 1)

    button_handler.lection_service.get_lection_ids_by_course.assert_called_once_with(course.id)
    button_handler.default_question_service.get_random_question_text.assert_awaited_once()
    button_handler.question_service.create_question.assert_awaited_once_with(
        lection_ids[0],
        DEFAULT_QUESTION_TEMPLATES[0],
    )
    button_handler.context_service.set_context.assert_called_with(
        1,
        action="course_menu",
        step="view",
        data={"course_id": str(course.id), "page": 1},
    )
    assert response.message == TelegramMessages.get_default_questions_added()
    assert all(button.action != TelegramButtons.COURSE_ADD_DEFAULT_QUESTIONS for button in response.buttons)
    assert any(button.action == TelegramButtons.COURSE_ATTACH_TEACHERS for button in response.buttons)


@pytest.mark.asyncio
async def test_button_handler_finishes_course_creation_from_teacher_attached_screen():
    button_handler = build_button_handler()
    course = create_course()
    button_handler.course_service.get_by_id.return_value = course
    button_handler.context_service.get_context.return_value = {
        "action": "teacher_attached",
        "step": "view",
        "data": {"course_id": str(course.id)},
    }
    expected = ActionResponseSchema(message="done", buttons=[])
    button_handler.build_main_menu_response = AsyncMock(return_value=expected)

    response = await button_handler.handle(TelegramButtons.TEACHER_FINISH_COURSE_CREATION, 1)

    button_handler.context_service.clear_context.assert_awaited_once_with(1)
    button_handler.build_main_menu_response.assert_awaited_once_with(
        1,
        TelegramMessages.get_course_created_success(
            course.name,
            course.started_at,
            course.ended_at,
            course.join_code,
        ),
    )
    assert response is expected


@pytest.mark.asyncio
async def test_text_handler_converts_lection_datetime_input_from_moscow_to_utc():
    button_handler = build_button_handler()
    button_handler.render_lection_details = AsyncMock(
        return_value=ActionResponseSchema(message="ok", awaiting_input=False),
    )
    context_service = AsyncMock()
    lection_id = uuid.uuid4()
    course_id = uuid.uuid4()
    context_service.get_context.return_value = {
        "action": "edit_lection_date",
        "step": "awaiting_datetime",
        "data": {"lection_id": str(lection_id), "course_id": str(course_id)},
    }
    update_lection_use_case = AsyncMock()
    text_handler = TextInputHandler(
        context_service=context_service,
        admin_service=button_handler.admin_service,
        teacher_service=button_handler.teacher_service,
        student_service=button_handler.student_service,
        create_admin_use_case=AsyncMock(),
        attach_teachers_to_course_use_case=AsyncMock(),
        update_lection_use_case=update_lection_use_case,
        manage_questions_use_case=AsyncMock(),
        button_handler=button_handler,
    )

    await text_handler.handle("01.01.2026 10:00-12:30", 1)

    update_call = update_lection_use_case.update_datetime.call_args.kwargs
    assert update_call["started_at"] == datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc)
    assert update_call["ended_at"] == datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_telegram_messages_render_lection_details_in_moscow_time():
    started_at = datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc)
    ended_at = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)

    message = TelegramMessages.get_lection_details(
        topic="Lecture",
        started_at=started_at,
        ended_at=ended_at,
        questions_count=2,
        has_presentation=False,
        has_recording=False,
    )

    assert "01.01.2026" in message
    assert "10:00–12:30" in message


@pytest.mark.asyncio
async def test_telegram_messages_render_nearest_lection_in_moscow_time():
    started_at = datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)
    ended_at = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)

    message = TelegramMessages.get_nearest_lection_info(
        topic="Lecture",
        started_at=started_at,
        ended_at=ended_at,
    )

    assert "01.01.2026" in message
    assert "18:00–19:30" in message


@pytest.mark.asyncio
async def test_text_handler_removes_prompt_screen_after_question_creation():
    button_handler = build_button_handler()
    button_handler.render_questions_menu = AsyncMock(return_value=Mock(message="ok"))
    context_service = AsyncMock()
    lection_id = uuid.uuid4()
    context_service.get_context.return_value = {
        "action": "add_question",
        "step": "awaiting_question_text",
        "data": {"lection_id": str(lection_id)},
    }
    manage_questions_use_case = AsyncMock()
    text_handler = TextInputHandler(
        context_service=context_service,
        admin_service=button_handler.admin_service,
        teacher_service=button_handler.teacher_service,
        student_service=button_handler.student_service,
        create_admin_use_case=AsyncMock(),
        attach_teachers_to_course_use_case=AsyncMock(),
        update_lection_use_case=AsyncMock(),
        manage_questions_use_case=manage_questions_use_case,
        button_handler=button_handler,
    )

    await text_handler.handle("Новый вопрос", 1)

    context_service.pop_navigation.assert_called_once_with(1)
    manage_questions_use_case.create_question.assert_called_once()
    button_handler.render_questions_menu.assert_called_once_with(1, lection_id)


@pytest.mark.asyncio
async def test_file_handler_removes_upload_prompt_after_presentation_upload():
    context_service = AsyncMock()
    lection_id = uuid.uuid4()
    context_service.get_context.return_value = {
        "action": "edit_lection_presentation",
        "data": {"lection_id": str(lection_id)},
    }
    button_handler = Mock()
    button_handler._require_admin = AsyncMock(return_value=create_admin())
    button_handler.build_main_menu_response = AsyncMock(return_value=Mock())
    button_handler.build_error_response = AsyncMock(return_value=Mock())
    button_handler.render_course_menu = AsyncMock(return_value=Mock())
    button_handler.render_presentation_menu = AsyncMock(return_value=Mock())
    button_handler.render_recording_menu = AsyncMock(return_value=Mock())
    manage_files_use_case = AsyncMock()
    file_handler = FileUploadHandler(
        context_service=context_service,
        create_course_from_excel_use_case=AsyncMock(return_value=create_course()),
        attach_students_to_course_use_case=AsyncMock(return_value=2),
        manage_files_use_case=manage_files_use_case,
        reflection_workflow_service=AsyncMock(),
        button_handler=button_handler,
    )

    await file_handler.handle(
        UploadFile(filename="presentation.bin", file=io.BytesIO(b"data")),
        1,
        telegram_file_id="tg-presentation-1",
    )

    context_service.pop_navigation.assert_called_once_with(1)
    manage_files_use_case.upload_presentation.assert_called_once_with(
        lection_id=lection_id,
        telegram_file_id="tg-presentation-1",
        current_admin=button_handler._require_admin.return_value,
    )
    button_handler.render_presentation_menu.assert_called_once_with(1, lection_id)


@pytest.mark.asyncio
async def test_file_handler_returns_friendly_message_for_missing_csv_column():
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "attach_students",
        "data": {"course_id": str(uuid.uuid4())},
    }
    button_handler = build_button_handler()
    file_handler = FileUploadHandler(
        context_service=context_service,
        create_course_from_excel_use_case=AsyncMock(),
        attach_students_to_course_use_case=AsyncMock(
            side_effect=CSVFileMissingColumnError("username")
        ),
        manage_files_use_case=AsyncMock(),
        reflection_workflow_service=AsyncMock(),
        button_handler=button_handler,
    )

    response = await file_handler.handle(
        UploadFile(filename="students.csv", file=io.BytesIO(b"bad,data")),
        1,
    )

    assert response.awaiting_input is True
    assert "Ошибка обработки файла" in response.message
    assert "username" in response.message
    assert response.message != TelegramMessages.get_generic_error()


@pytest.mark.asyncio
@pytest.mark.parametrize("action_name", ["create_course", "attach_students", "edit_lection_presentation", "edit_lection_recording"])
async def test_file_handler_routes_by_context_action(action_name: str):
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": action_name,
        "data": {
            "course_id": str(uuid.uuid4()),
            "lection_id": str(uuid.uuid4()),
            "course_name": "Тестовый курс",
        },
    }
    button_handler = Mock()
    button_handler._require_admin = AsyncMock(return_value=create_admin())
    button_handler.build_main_menu_response = AsyncMock(return_value=Mock())
    button_handler.render_course_menu = AsyncMock(return_value=Mock())
    button_handler.render_presentation_menu = AsyncMock(return_value=Mock())
    button_handler.render_recording_menu = AsyncMock(return_value=Mock())
    create_course_use_case = AsyncMock(return_value=create_course())
    attach_students_use_case = AsyncMock(return_value=2)
    manage_files_use_case = AsyncMock()
    file_handler = FileUploadHandler(
        context_service=context_service,
        create_course_from_excel_use_case=create_course_use_case,
        attach_students_to_course_use_case=attach_students_use_case,
        manage_files_use_case=manage_files_use_case,
        reflection_workflow_service=AsyncMock(),
        button_handler=button_handler,
    )

    telegram_file_id = "tg-file-1" if action_name.startswith("edit_lection_") else None
    await file_handler.handle(
        UploadFile(filename="file.bin", file=io.BytesIO(b"data")),
        1,
        telegram_file_id=telegram_file_id,
    )

    if action_name == "create_course":
        create_course_use_case.assert_called_once_with(
            "Тестовый курс",
            ANY,
            button_handler._require_admin.return_value,
        )
    elif action_name == "attach_students":
        attach_students_use_case.assert_called_once()
    elif action_name == "edit_lection_presentation":
        manage_files_use_case.upload_presentation.assert_called_once()
    elif action_name == "edit_lection_recording":
        manage_files_use_case.upload_recording.assert_called_once()


@pytest.mark.asyncio
async def test_button_handler_starts_student_reflection_workflow():
    handler = build_button_handler()
    student = create_student()
    lection_id = uuid.uuid4()
    handler.student_service.get_by_telegram_id.return_value = student
    handler.reflection_workflow_service.start_workflow.return_value = {
        "lection_id": str(lection_id),
        "lection_topic": "Линейная алгебра",
        "lection_deadline": datetime.now(timezone.utc).isoformat(),
        "stage": "reflection",
        "reflection_videos": [],
        "questions": [],
        "current_question_index": 0,
        "current_question_videos": [],
        "qa_answers": [],
    }

    response = await handler.handle(
        f"{TelegramButtons.STUDENT_START_REFLECTION}:{lection_id}",
        student.telegram_id,
    )

    handler.context_service.set_context.assert_called_once_with(
        student.telegram_id,
        action="student_reflection_workflow",
        step="awaiting_reflection_video",
        data=handler.reflection_workflow_service.start_workflow.return_value,
    )
    handler.student_history_log_service.log_action.assert_awaited_once_with(
        student.id,
        f"{TelegramButtons.STUDENT_START_REFLECTION}:{lection_id}",
    )
    assert response.message == TelegramMessages.get_reflection_recording_request()
    assert response.awaiting_input is True
    assert response.buttons == []


@pytest.mark.asyncio
async def test_button_handler_renders_student_question_prompt_without_upload_button():
    handler = build_button_handler()
    question_id = uuid.uuid4()
    context_data = {
        "stage": "question",
        "questions": [
            {
                "id": str(question_id),
                "text": "Что было самым полезным?",
            }
        ],
        "current_question_index": 0,
        "current_question_videos": [],
        "reflection_videos": ["video-note-1"],
        "qa_answers": [],
    }
    handler.reflection_workflow_service.get_current_question = Mock(return_value={
        "id": str(question_id),
        "text": "Что было самым полезным?",
    })

    response = await handler.render_student_question_prompt(context_data)

    assert response.message == TelegramMessages.get_question_reflection_prompt(
        "Что было самым полезным?",
        1,
        1,
    )
    assert response.awaiting_input is True
    assert response.buttons == []


@pytest.mark.asyncio
async def test_button_handler_logs_generic_back_action_for_student_role():
    handler = build_button_handler()
    student = create_student()
    handler.admin_service.get_by_telegram_id.return_value = None
    handler.student_service.get_by_telegram_id.return_value = student
    handler.context_service.get_context.return_value = {"action": "course_menu", "data": {}}
    handler.context_service.pop_navigation.return_value = None

    await handler.handle(TelegramButtons.BACK, student.telegram_id)

    handler.student_history_log_service.log_action.assert_awaited_once_with(
        student.id,
        TelegramButtons.BACK,
    )


@pytest.mark.asyncio
async def test_file_handler_saves_student_video_to_draft_and_returns_review_actions():
    context_service = AsyncMock()
    context_service.get_context.return_value = {
        "action": "student_reflection_workflow",
        "step": "awaiting_reflection_video",
        "data": {
            "lection_id": str(uuid.uuid4()),
            "lection_topic": "Теория вероятностей",
            "stage": "reflection",
            "reflection_videos": [],
            "questions": [],
            "current_question_index": 0,
            "current_question_videos": [],
            "qa_answers": [],
        },
    }
    student = create_student()
    button_handler = build_button_handler()
    button_handler.student_service.get_by_telegram_id.return_value = student
    button_handler.render_student_video_review = AsyncMock(
        return_value=ActionResponseSchema(
            message=TelegramMessages.get_reflection_video_saved(),
            buttons=[],
        )
    )
    reflection_workflow_service = Mock()
    reflection_workflow_service.add_video_to_draft.return_value = {
        **context_service.get_context.return_value["data"],
        "reflection_videos": ["video-note-1"],
    }
    student_history_log_service = AsyncMock()
    file_handler = FileUploadHandler(
        context_service=context_service,
        create_course_from_excel_use_case=AsyncMock(),
        attach_students_to_course_use_case=AsyncMock(),
        manage_files_use_case=AsyncMock(),
        reflection_workflow_service=reflection_workflow_service,
        button_handler=button_handler,
        student_history_log_service=student_history_log_service,
    )

    response = await file_handler.handle(None, student.telegram_id, telegram_file_id="video-note-1")

    reflection_workflow_service.add_video_to_draft.assert_called_once()
    context_service.set_context.assert_called_once_with(
        student.telegram_id,
        action="student_reflection_workflow",
        step="review_reflection_videos",
        data=reflection_workflow_service.add_video_to_draft.return_value,
    )
    student_history_log_service.log_action.assert_awaited_once_with(
        student.id,
        "student_upload_reflection_video",
    )
    assert response.message == TelegramMessages.get_reflection_video_saved()


@pytest.mark.asyncio
async def test_button_handler_submits_student_reflection_without_questions():
    handler = build_button_handler()
    student = create_student()
    handler.student_service.get_by_telegram_id.return_value = student
    handler.context_service.get_context.return_value = {
        "action": "student_reflection_workflow",
        "step": "review_reflection_videos",
        "data": {
            "lection_id": str(uuid.uuid4()),
            "lection_topic": "Матан",
            "stage": "reflection",
            "reflection_videos": ["video-1"],
            "questions": [],
            "current_question_index": 0,
            "current_question_videos": [],
            "qa_answers": [],
        },
    }
    handler.reflection_workflow_service.submit_reflection.return_value = {
        **handler.context_service.get_context.return_value["data"],
        "stage": "question",
        "reflection_id": str(uuid.uuid4()),
    }

    response = await handler.handle(TelegramButtons.STUDENT_SUBMIT_REFLECTION, student.telegram_id)

    handler.context_service.clear_context.assert_called_once_with(student.telegram_id)
    assert response.message == TelegramMessages.get_reflection_submission_completed()


@pytest.mark.asyncio
async def test_button_handler_submits_last_question_and_finishes_workflow():
    handler = build_button_handler()
    student = create_student()
    question_id = uuid.uuid4()
    handler.student_service.get_by_telegram_id.return_value = student
    handler.context_service.get_context.return_value = {
        "action": "student_reflection_workflow",
        "step": "review_question_videos",
        "data": {
            "lection_id": str(uuid.uuid4()),
            "lection_topic": "Алгоритмы",
            "stage": "question",
            "reflection_id": str(uuid.uuid4()),
            "reflection_videos": ["video-1"],
            "questions": [{"id": str(question_id), "text": "Что было полезным?"}],
            "current_question_index": 0,
            "current_question_videos": ["video-qa-1"],
            "qa_answers": [],
        },
    }
    handler.reflection_workflow_service.submit_question_answer.return_value = {
        **handler.context_service.get_context.return_value["data"],
        "current_question_index": 1,
        "current_question_videos": [],
        "qa_answers": [
            {
                "question_id": str(question_id),
                "file_ids": ["video-qa-1"],
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    handler.reflection_workflow_service.get_current_question = Mock(return_value=None)

    response = await handler.handle(TelegramButtons.STUDENT_SUBMIT_QA, student.telegram_id)

    handler.reflection_workflow_service.finalize_question_answers.assert_called_once()
    handler.context_service.clear_context.assert_called_once_with(student.telegram_id)
    assert response.message == TelegramMessages.get_questions_completed_message()


@pytest.mark.asyncio
async def test_render_reflection_details_returns_dialog_messages_in_order():
    handler = build_button_handler()
    student = create_student()
    lection = create_lection("Архитектура ПО")
    submitted_at = datetime.now(timezone.utc)
    question_1 = QuestionReadSchema(
        id=uuid.uuid4(),
        lection_session_id=lection.id,
        question_text="Что было самым полезным?",
        created_at=submitted_at,
        updated_at=submitted_at,
    )
    question_2 = QuestionReadSchema(
        id=uuid.uuid4(),
        lection_session_id=lection.id,
        question_text="Что осталось непонятным?",
        created_at=submitted_at + timedelta(seconds=1),
        updated_at=submitted_at + timedelta(seconds=1),
    )
    handler.student_service.get_by_id.return_value = student
    handler.lection_service.get_by_id.return_value = lection
    handler.view_reflection_details_use_case.return_value = ReflectionDetailsSchema(
        reflection=LectionReflectionReadSchema(
            id=uuid.uuid4(),
            student_id=student.id,
            lection_session_id=lection.id,
            submitted_at=submitted_at,
            ai_analysis_status="pending",
            created_at=submitted_at,
            updated_at=submitted_at,
        ),
        reflection_videos=[
            ReflectionVideoReadSchema(
                id=uuid.uuid4(),
                reflection_id=uuid.uuid4(),
                file_id="reflection-video-1",
                order_index=1,
                created_at=submitted_at,
                updated_at=submitted_at,
            ),
            ReflectionVideoReadSchema(
                id=uuid.uuid4(),
                reflection_id=uuid.uuid4(),
                file_id="reflection-video-2",
                order_index=2,
                created_at=submitted_at,
                updated_at=submitted_at,
            ),
        ],
        qa_list=[
            QADetailsSchema(
                question=question_1,
                lection_qa=LectionQAReadSchema(
                    id=uuid.uuid4(),
                    reflection_id=uuid.uuid4(),
                    question_id=question_1.id,
                    answer_submitted_at=submitted_at,
                    created_at=submitted_at,
                    updated_at=submitted_at,
                ),
                qa_videos=[
                    QAVideoReadSchema(
                        id=uuid.uuid4(),
                        lection_qa_id=uuid.uuid4(),
                        file_id="qa1-video-1",
                        order_index=1,
                        created_at=submitted_at,
                        updated_at=submitted_at,
                    ),
                    QAVideoReadSchema(
                        id=uuid.uuid4(),
                        lection_qa_id=uuid.uuid4(),
                        file_id="qa1-video-2",
                        order_index=2,
                        created_at=submitted_at,
                        updated_at=submitted_at,
                    ),
                ],
            ),
            QADetailsSchema(
                question=question_2,
                lection_qa=LectionQAReadSchema(
                    id=uuid.uuid4(),
                    reflection_id=uuid.uuid4(),
                    question_id=question_2.id,
                    answer_submitted_at=submitted_at,
                    created_at=submitted_at,
                    updated_at=submitted_at,
                ),
                qa_videos=[
                    QAVideoReadSchema(
                        id=uuid.uuid4(),
                        lection_qa_id=uuid.uuid4(),
                        file_id="qa2-video-1",
                        order_index=1,
                        created_at=submitted_at,
                        updated_at=submitted_at,
                    ),
                ],
            ),
        ],
    )

    response = await handler.render_reflection_details(1, student.id, lection.id)

    assert "Архитектура ПО" in response.message
    assert [item.files[0].telegram_file_id for item in response.dialog_messages if item.files] == [
        "reflection-video-1",
        "reflection-video-2",
        "qa1-video-1",
        "qa1-video-2",
        "qa2-video-1",
    ]
    question_messages = [item.message for item in response.dialog_messages if item.message]
    assert question_messages == [
        "❓ <b>Вопрос</b>\n\nЧто было самым полезным?",
        "❓ <b>Вопрос</b>\n\nЧто осталось непонятным?",
        TelegramMessages.get_next_actions_prompt(),
    ]
    assert response.dialog_messages[-1].buttons
    assert [button.action for button in response.dialog_messages[-1].buttons] == [
        TelegramButtons.ADMIN_CREATE_ADMIN,
        TelegramButtons.ADMIN_CREATE_COURSE,
        TelegramButtons.ADMIN_VIEW_COURSES,
        TelegramButtons.TEACHER_ANALYTICS,
        TelegramButtons.TEACHER_NEXT_LECTION,
        None,
    ]
    assert response.dialog_messages[-1].buttons[-1].url == TelegramButtons.TECH_SUPPORT_URL


@pytest.mark.asyncio
async def test_render_student_statistics_uses_short_reflection_actions():
    handler = build_button_handler()
    student = create_student()
    course = create_course()
    lection = create_lection("Архитектура ПО")
    handler.view_student_analytics_use_case.return_value = Mock(
        student=student,
        total_lections=3,
        reflections_count=1,
        qa_count=1,
        lections_with_reflections=[lection],
    )

    response = await handler.render_student_statistics(1, course.id, student.id)

    assert response.buttons[0].action == f"{TelegramButtons.ANALYTICS_VIEW_REFLECTION}:{lection.id}"


@pytest.mark.asyncio
async def test_render_analytics_lection_statistics_uses_short_reflection_actions():
    handler = build_button_handler()
    student = create_student()
    lection = create_lection("Архитектура ПО")
    handler.pagination_service.paginate = Mock(return_value={
        "items": [student],
        "total_pages": 1,
    })
    handler.view_lection_analytics_use_case.return_value = Mock(
        lection=lection,
        total_students=10,
        reflections_count=1,
        qa_count=1,
        students_with_reflections=[student],
    )

    response = await handler.render_analytics_lection_statistics(1, lection.id, 1)

    assert response.buttons[0].action == f"{TelegramButtons.ANALYTICS_VIEW_REFLECTION}:{student.id}"


@pytest.mark.asyncio
async def test_handle_reflection_details_from_student_statistics_context():
    handler = build_button_handler()
    student = create_student()
    lection = create_lection("Архитектура ПО")
    handler.context_service.get_context.return_value = {
        "action": "student_statistics",
        "step": "view",
        "data": {
            "course_id": str(lection.course_session_id),
            "student_id": str(student.id),
        },
    }
    handler.render_reflection_details = AsyncMock(return_value=ActionResponseSchema(message="ok"))

    response = await handler.handle(
        f"{TelegramButtons.ANALYTICS_VIEW_REFLECTION}:{lection.id}",
        1,
    )

    handler.render_reflection_details.assert_awaited_once_with(
        1,
        student.id,
        lection.id,
        push_navigation=True,
    )
    assert response.message == "ok"


@pytest.mark.asyncio
async def test_handle_reflection_details_from_lection_statistics_context():
    handler = build_button_handler()
    student = create_student()
    lection = create_lection("Архитектура ПО")
    handler.context_service.get_context.return_value = {
        "action": "analytics_lection_statistics",
        "step": "view",
        "data": {
            "course_id": str(lection.course_session_id),
            "lection_id": str(lection.id),
            "page": 1,
        },
    }
    handler.render_reflection_details = AsyncMock(return_value=ActionResponseSchema(message="ok"))

    response = await handler.handle(
        f"{TelegramButtons.ANALYTICS_VIEW_REFLECTION}:{student.id}",
        1,
    )

    handler.render_reflection_details.assert_awaited_once_with(
        1,
        student.id,
        lection.id,
        push_navigation=True,
    )
    assert response.message == "ok"
