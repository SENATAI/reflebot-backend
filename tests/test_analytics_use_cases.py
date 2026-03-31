"""
Unit tests for analytics use cases.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from reflebot.apps.reflections.schemas import (
    AdminReadSchema,
    LectionSessionReadSchema,
    LectionStatisticsSchema,
    ReflectionDetailsSchema,
    StudentStatisticsSchema,
    TeacherCourseReadSchema,
    TeacherReadSchema,
)
from reflebot.apps.reflections.use_cases.analytics import (
    ViewLectionAnalyticsUseCase,
    ViewReflectionDetailsUseCase,
    ViewStudentAnalyticsUseCase,
)
from reflebot.core.utils.exceptions import PermissionDeniedError


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


def create_teacher() -> TeacherReadSchema:
    now = datetime.now(timezone.utc)
    return TeacherReadSchema(
        id=uuid.uuid4(),
        full_name="Teacher",
        telegram_username="teacher",
        telegram_id=2,
        is_active=True,
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


def create_teacher_course(teacher_id: uuid.UUID, course_id: uuid.UUID) -> TeacherCourseReadSchema:
    now = datetime.now(timezone.utc)
    return TeacherCourseReadSchema(
        id=uuid.uuid4(),
        teacher_id=teacher_id,
        course_session_id=course_id,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_view_lection_analytics_use_case_allows_admin():
    analytics_service = AsyncMock()
    lection_service = AsyncMock()
    teacher_course_repository = AsyncMock()
    course_id = uuid.uuid4()
    lection = create_lection(course_id)
    expected = AsyncMock(spec=LectionStatisticsSchema)
    lection_service.get_by_id.return_value = lection
    analytics_service.get_lection_statistics.return_value = expected
    use_case = ViewLectionAnalyticsUseCase(
        analytics_service=analytics_service,
        lection_service=lection_service,
        teacher_course_repository=teacher_course_repository,
    )

    result = await use_case(lection.id, current_admin=create_admin())

    assert result == expected
    analytics_service.get_lection_statistics.assert_called_once_with(lection.id)


@pytest.mark.asyncio
async def test_view_lection_analytics_use_case_denies_teacher_without_course_access():
    analytics_service = AsyncMock()
    lection_service = AsyncMock()
    teacher_course_repository = AsyncMock()
    course_id = uuid.uuid4()
    teacher = create_teacher()
    lection = create_lection(course_id)
    lection_service.get_by_id.return_value = lection
    teacher_course_repository.get_all.return_value = []
    use_case = ViewLectionAnalyticsUseCase(
        analytics_service=analytics_service,
        lection_service=lection_service,
        teacher_course_repository=teacher_course_repository,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(lection.id, current_teacher=teacher)


@pytest.mark.asyncio
async def test_view_student_analytics_use_case_allows_teacher_with_course_access():
    analytics_service = AsyncMock()
    lection_service = AsyncMock()
    teacher_course_repository = AsyncMock()
    teacher = create_teacher()
    course_id = uuid.uuid4()
    expected = AsyncMock(spec=StudentStatisticsSchema)
    teacher_course_repository.get_all.return_value = [create_teacher_course(teacher.id, course_id)]
    analytics_service.get_student_statistics.return_value = expected
    use_case = ViewStudentAnalyticsUseCase(
        analytics_service=analytics_service,
        lection_service=lection_service,
        teacher_course_repository=teacher_course_repository,
    )

    result = await use_case(uuid.uuid4(), course_id, current_teacher=teacher)

    assert result == expected
    analytics_service.get_student_statistics.assert_called_once()


@pytest.mark.asyncio
async def test_view_reflection_details_use_case_checks_access_and_returns_details():
    analytics_service = AsyncMock()
    lection_service = AsyncMock()
    teacher_course_repository = AsyncMock()
    course_id = uuid.uuid4()
    lection = create_lection(course_id)
    expected = AsyncMock(spec=ReflectionDetailsSchema)
    lection_service.get_by_id.return_value = lection
    analytics_service.get_reflection_details.return_value = expected
    use_case = ViewReflectionDetailsUseCase(
        analytics_service=analytics_service,
        lection_service=lection_service,
        teacher_course_repository=teacher_course_repository,
    )

    result = await use_case(uuid.uuid4(), lection.id, current_admin=create_admin())

    assert result == expected
    analytics_service.get_reflection_details.assert_called_once()
