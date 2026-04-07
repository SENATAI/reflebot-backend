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
    AttachStudentsToCourseUseCase,
    AttachTeachersToCourseUseCase,
    CreateCourseFromExcelUseCase,
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
            "one_question_from_list": True,
            "questions": ["Что это такое?"],
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
                "one_question_from_list": True,
            }
        ],
        join_code="AbCd",
    )
    question_service.create_question.assert_awaited_once_with(
        created_lection.id,
        "Что это такое?",
    )


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
