"""
Unit tests for course-related use cases.
"""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from reflebot.apps.reflections.schemas import (
    AdminReadSchema,
    CourseSessionReadSchema,
    LectionSessionReadSchema,
    StudentReadSchema,
    TeacherReadSchema,
)
from reflebot.apps.reflections.use_cases.course import (
    AppendCourseFromExcelUseCase,
    AttachStudentsToCourseUseCase,
    AttachTeachersToCourseUseCase,
    CreateCourseFromExcelUseCase,
    SendCourseReflectionAlertUseCase,
    SendCourseBroadcastMessageUseCase,
)


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


def create_course(course_id: uuid.UUID | None = None) -> CourseSessionReadSchema:
    now = datetime.now(timezone.utc)
    return CourseSessionReadSchema(
        id=course_id or uuid.uuid4(),
        name="Python Backend",
        join_code="ABCD",
        started_at=now,
        ended_at=now,
        created_at=now,
        updated_at=now,
    )


def create_lection(course_id: uuid.UUID) -> LectionSessionReadSchema:
    now = datetime.now(timezone.utc)
    return LectionSessionReadSchema(
        id=uuid.uuid4(),
        course_session_id=course_id,
        topic="Topic",
        presentation_file_id=None,
        recording_file_id=None,
        started_at=now,
        ended_at=now,
        deadline=now,
        created_at=now,
        updated_at=now,
    )


def create_teacher() -> TeacherReadSchema:
    now = datetime.now(timezone.utc)
    return TeacherReadSchema(
        id=uuid.uuid4(),
        full_name="Teacher",
        telegram_username="teacher",
        telegram_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def create_student(name: str) -> StudentReadSchema:
    now = datetime.now(timezone.utc)
    return StudentReadSchema(
        id=uuid.uuid4(),
        full_name=name,
        telegram_username=name.lower(),
        telegram_id=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def create_student_with_telegram(name: str, telegram_id: int | None) -> StudentReadSchema:
    now = datetime.now(timezone.utc)
    return StudentReadSchema(
        id=uuid.uuid4(),
        full_name=name,
        telegram_username=name.lower(),
        telegram_id=telegram_id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_course_from_excel_use_case_parses_and_creates_course():
    deadline = datetime.now(timezone.utc)
    parser = Mock()
    parser.parse.return_value = [
        {
            "topic": "Intro",
            "started_at": datetime.now(),
            "ended_at": datetime.now(),
            "deadline": deadline,
            "join_code": "AbCd",
            "questions_to_ask_count": 1,
            "questions": ["Что это такое?"],
            "question_pools": [
                {
                    "pool_index": 0,
                    "questions_to_ask_count": 1,
                    "questions": ["Что это такое?"],
                }
            ],
        }
    ]
    course_service = AsyncMock()
    lection_service = AsyncMock()
    question_service = AsyncMock()
    created_course = create_course()
    created_lection = create_lection(created_course.id)
    created_lection = created_lection.model_copy(
        update={
            "topic": "Intro",
            "started_at": parser.parse.return_value[0]["started_at"],
            "ended_at": parser.parse.return_value[0]["ended_at"],
        }
    )
    course_service.create_course_with_lections.return_value = created_course
    lection_service.get_lections_by_course.return_value = type(
        "Paginated",
        (),
        {"items": [created_lection]},
    )()
    use_case = CreateCourseFromExcelUseCase(
        course_service=course_service,
        lection_service=lection_service,
        question_service=question_service,
        parser=parser,
    )

    result = await use_case("Python Backend", io.BytesIO(b"excel"), create_admin())

    assert result == created_course
    parser.parse.assert_called_once()
    course_service.create_course_with_lections.assert_called_once_with(
        course_name="Python Backend",
        lections_data=[
            {
                "topic": "Intro",
                "started_at": parser.parse.return_value[0]["started_at"],
                "ended_at": parser.parse.return_value[0]["ended_at"],
                "deadline": deadline,
                "questions_to_ask_count": 1,
            }
        ],
        join_code="AbCd",
    )
    question_service.create_question.assert_awaited_once_with(
        created_lection.id,
        "Что это такое?",
        question_pool_index=0,
        question_pool_questions_to_ask_count=1,
    )


@pytest.mark.asyncio
async def test_append_course_from_excel_use_case_returns_created_lections_without_student_attach():
    deadline = datetime.now(timezone.utc)
    course_id = uuid.uuid4()
    parser = Mock()
    parser.parse.return_value = [
        {
            "topic": "Intro",
            "started_at": datetime.now(timezone.utc),
            "ended_at": datetime.now(timezone.utc),
            "deadline": deadline,
            "questions_to_ask_count": 1,
            "question_pools": [
                {
                    "pool_index": 0,
                    "questions_to_ask_count": 1,
                    "questions": ["Что это такое?"],
                }
            ],
        }
    ]
    created_lection = create_lection(course_id)
    created_lection = created_lection.model_copy(
        update={
            "topic": "Intro",
            "started_at": parser.parse.return_value[0]["started_at"],
            "ended_at": parser.parse.return_value[0]["ended_at"],
        }
    )
    course_service = AsyncMock()
    course_service.append_lections_to_course.return_value = [created_lection]
    question_service = AsyncMock()
    student_service = AsyncMock()
    use_case = AppendCourseFromExcelUseCase(
        course_service=course_service,
        question_service=question_service,
        student_service=student_service,
        parser=parser,
    )

    result = await use_case(course_id, io.BytesIO(b"excel"), create_admin())

    assert result == [created_lection]
    course_service.append_lections_to_course.assert_awaited_once()
    question_service.create_question.assert_awaited_once_with(
        created_lection.id,
        "Что это такое?",
        question_pool_index=0,
        question_pool_questions_to_ask_count=1,
    )
    student_service.get_students_by_course.assert_not_called()
    student_service.attach_to_lections.assert_not_called()


@pytest.mark.asyncio
async def test_attach_teachers_to_course_use_case_attaches_teacher_and_all_lections():
    teacher_service = AsyncMock()
    lection_service = AsyncMock()
    course_id = uuid.uuid4()
    teacher = create_teacher()
    teacher_service.create_or_get.return_value = teacher
    lection_service.get_lections_by_course.return_value = type(
        "Paginated",
        (),
        {"items": [create_lection(course_id), create_lection(course_id)]},
    )()
    use_case = AttachTeachersToCourseUseCase(
        teacher_service=teacher_service,
        lection_service=lection_service,
    )

    result = await use_case(
        course_id=course_id,
        full_name="Teacher",
        telegram_username="teacher",
        current_admin=create_admin(),
    )

    assert result == teacher
    teacher_service.create_or_get.assert_called_once_with(
        full_name="Teacher",
        telegram_username="teacher",
    )
    teacher_service.attach_to_course.assert_called_once_with(
        teacher_id=teacher.id,
        course_id=course_id,
    )
    teacher_service.attach_to_lections.assert_called_once()
    attached_ids = teacher_service.attach_to_lections.call_args.kwargs["lection_ids"]
    assert len(attached_ids) == 2


@pytest.mark.asyncio
async def test_attach_students_to_course_use_case_parses_csv_and_attaches_students():
    student_service = AsyncMock()
    lection_service = AsyncMock()
    parser = Mock()
    course_id = uuid.uuid4()
    parser.parse.return_value = [
        {"full_name": "Alice", "telegram_username": "alice"},
        {"full_name": "Bob", "telegram_username": "bob"},
    ]
    students = [create_student("Alice"), create_student("Bob")]
    student_service.bulk_create_or_get.return_value = students
    lection_service.get_lections_by_course.return_value = type(
        "Paginated",
        (),
        {"items": [create_lection(course_id), create_lection(course_id)]},
    )()
    use_case = AttachStudentsToCourseUseCase(
        student_service=student_service,
        lection_service=lection_service,
        parser=parser,
    )

    result = await use_case(
        course_id=course_id,
        csv_file=io.BytesIO(b"csv"),
        current_admin=create_admin(),
    )

    assert result == 2
    parser.parse.assert_called_once()
    student_service.bulk_create_or_get.assert_called_once_with(parser.parse.return_value)
    student_service.attach_to_course.assert_called_once()
    student_service.attach_to_lections.assert_called_once()


@pytest.mark.asyncio
async def test_send_course_broadcast_message_use_case_publishes_only_students_with_telegram():
    student_service = AsyncMock()
    publisher = AsyncMock()
    course_id = uuid.uuid4()
    students = [
        create_student_with_telegram("Alice", 111),
        create_student_with_telegram("Bob", None),
        create_student_with_telegram("Charlie", 333),
    ]
    student_service.get_students_by_course.return_value = {"items": students}
    use_case = SendCourseBroadcastMessageUseCase(
        student_service=student_service,
        publisher=publisher,
    )

    result = await use_case(
        course_id=course_id,
        message_text="Hello students",
        current_admin=create_admin(),
    )

    assert result == 2
    assert publisher.publish_course_message.await_count == 2
    first_payload = publisher.publish_course_message.await_args_list[0].args[0]
    second_payload = publisher.publish_course_message.await_args_list[1].args[0]
    assert first_payload.course_id == course_id
    assert first_payload.telegram_id == 111
    assert first_payload.message_text == "Hello students"
    assert second_payload.telegram_id == 333


@pytest.mark.asyncio
async def test_send_course_reflection_alert_use_case_publishes_prompt_for_selected_student():
    lection_service = AsyncMock()
    student_service = AsyncMock()
    message_service = AsyncMock()
    publisher = AsyncMock()
    course_id = uuid.uuid4()
    lection = create_lection(course_id)
    student = create_student_with_telegram("Alice", 111)
    lection_service.get_by_id.return_value = lection
    student_service.get_by_id.return_value = student
    message_service.build_message.return_value = Mock(
        message_text="Reflection prompt",
        parse_mode="HTML",
        buttons=[],
    )
    use_case = SendCourseReflectionAlertUseCase(
        lection_service=lection_service,
        student_service=student_service,
        message_service=message_service,
        publisher=publisher,
    )

    await use_case(
        course_id=course_id,
        lection_id=lection.id,
        student_id=student.id,
        current_admin=create_admin(),
    )

    message_service.build_message.assert_awaited_once_with(
        lection_session_id=lection.id,
        student_id=student.id,
    )
    publisher.publish_course_message.assert_awaited_once()
    payload = publisher.publish_course_message.await_args.args[0]
    assert payload.course_id == course_id
    assert payload.student_id == student.id
    assert payload.telegram_id == 111
    assert payload.message_text == "Reflection prompt"
