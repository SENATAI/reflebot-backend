"""
Unit tests for CourseService.

Feature: telegram-bot-full-workflow
Task: 7.2 - Добавить методы delete_course, get_courses_for_admin, get_courses_for_teacher
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from reflebot.apps.reflections.services.course import CourseService
from reflebot.apps.reflections.schemas import (
    CourseSessionReadSchema,
    TeacherCourseReadSchema,
)


# Helper functions
def create_course_read_schema(
    course_id: uuid.UUID,
    name: str,
    started_at: datetime,
    ended_at: datetime,
) -> CourseSessionReadSchema:
    """Helper to create CourseSessionReadSchema."""
    now = datetime.now(timezone.utc)
    return CourseSessionReadSchema(
        id=course_id,
        name=name,
        join_code="ABCD",
        started_at=started_at,
        ended_at=ended_at,
        created_at=now,
        updated_at=now,
    )


def create_teacher_course_read_schema(
    teacher_id: uuid.UUID,
    course_id: uuid.UUID,
) -> TeacherCourseReadSchema:
    """Helper to create TeacherCourseReadSchema."""
    now = datetime.now(timezone.utc)
    return TeacherCourseReadSchema(
        id=uuid.uuid4(),
        teacher_id=teacher_id,
        course_session_id=course_id,
        created_at=now,
        updated_at=now,
    )


# Test delete_course
@pytest.mark.asyncio
async def test_delete_course_success():
    """
    Test: delete_course успешно удаляет курс.
    
    Validates: Requirements 7.1 - CASCADE DELETE обрабатывается БД.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_course_repository.get_by_join_code_or_none.return_value = None
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    course_id = uuid.uuid4()
    mock_course_repository.delete.return_value = None
    
    # Act
    await course_service.delete_course(course_id)
    
    # Assert
    mock_course_repository.delete.assert_called_once_with(course_id)


# Test get_courses_for_admin
@pytest.mark.asyncio
async def test_get_courses_for_admin_empty_list():
    """
    Test: get_courses_for_admin возвращает пустой список когда нет курсов.
    
    Validates: Requirements 19.2 - Администратор видит все курсы.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_course_repository.get_by_join_code_or_none.return_value = None
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    mock_course_repository.get_all.return_value = []
    
    # Act
    result = await course_service.get_courses_for_admin(page=1, page_size=5)
    
    # Assert
    assert result.items == []
    assert result.total == 0
    assert result.page == 1
    assert result.page_size == 5
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test_get_courses_for_admin_single_page():
    """
    Test: get_courses_for_admin возвращает все курсы на одной странице.
    
    Validates: Requirements 19.2 - Администратор видит все курсы с пагинацией.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_course_repository.get_by_join_code_or_none.return_value = None
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Create 3 courses
    now = datetime.now(timezone.utc)
    courses = [
        create_course_read_schema(
            course_id=uuid.uuid4(),
            name=f"Course {i}",
            started_at=now,
            ended_at=now,
        )
        for i in range(3)
    ]
    
    mock_course_repository.get_all.return_value = courses
    
    # Act
    result = await course_service.get_courses_for_admin(page=1, page_size=5)
    
    # Assert
    assert len(result.items) == 3
    assert result.total == 3
    assert result.page == 1
    assert result.page_size == 5
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test_get_courses_for_admin_multiple_pages():
    """
    Test: get_courses_for_admin корректно обрабатывает пагинацию.
    
    Validates: Requirements 19.2 - Пагинация по 5 записей.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Create 12 courses
    now = datetime.now(timezone.utc)
    courses = [
        create_course_read_schema(
            course_id=uuid.uuid4(),
            name=f"Course {i}",
            started_at=now,
            ended_at=now,
        )
        for i in range(12)
    ]
    
    mock_course_repository.get_all.return_value = courses
    
    # Act - Page 1
    result_page1 = await course_service.get_courses_for_admin(page=1, page_size=5)
    
    # Assert - Page 1
    assert len(result_page1.items) == 5
    assert result_page1.total == 12
    assert result_page1.page == 1
    assert result_page1.page_size == 5
    assert result_page1.total_pages == 3
    assert result_page1.items[0].name == "Course 0"
    assert result_page1.items[4].name == "Course 4"
    
    # Act - Page 2
    result_page2 = await course_service.get_courses_for_admin(page=2, page_size=5)
    
    # Assert - Page 2
    assert len(result_page2.items) == 5
    assert result_page2.total == 12
    assert result_page2.page == 2
    assert result_page2.items[0].name == "Course 5"
    assert result_page2.items[4].name == "Course 9"
    
    # Act - Page 3
    result_page3 = await course_service.get_courses_for_admin(page=3, page_size=5)
    
    # Assert - Page 3
    assert len(result_page3.items) == 2
    assert result_page3.total == 12
    assert result_page3.page == 3
    assert result_page3.items[0].name == "Course 10"
    assert result_page3.items[1].name == "Course 11"


# Test get_courses_for_teacher
@pytest.mark.asyncio
async def test_get_courses_for_teacher_no_courses():
    """
    Test: get_courses_for_teacher возвращает пустой список когда преподаватель не привязан к курсам.
    
    Validates: Requirements 19.3 - Преподаватель видит только свои курсы.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    teacher_id = uuid.uuid4()
    mock_teacher_course_repository.get_all.return_value = []
    
    # Act
    result = await course_service.get_courses_for_teacher(teacher_id, page=1, page_size=5)
    
    # Assert
    assert result.items == []
    assert result.total == 0
    assert result.page == 1
    assert result.page_size == 5
    assert result.total_pages == 1


@pytest.mark.asyncio
async def test_get_courses_for_teacher_filters_by_teacher_id():
    """
    Test: get_courses_for_teacher фильтрует курсы по teacher_id.
    
    Validates: Requirements 19.3 - Фильтрация по TeacherCourse.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    teacher_id = uuid.uuid4()
    other_teacher_id = uuid.uuid4()
    
    course1_id = uuid.uuid4()
    course2_id = uuid.uuid4()
    course3_id = uuid.uuid4()
    
    # Mock teacher_courses: teacher привязан к course1 и course2, другой преподаватель к course3
    teacher_courses = [
        create_teacher_course_read_schema(teacher_id, course1_id),
        create_teacher_course_read_schema(teacher_id, course2_id),
        create_teacher_course_read_schema(other_teacher_id, course3_id),
    ]
    
    mock_teacher_course_repository.get_all.return_value = teacher_courses
    
    # Mock courses
    now = datetime.now(timezone.utc)
    courses = [
        create_course_read_schema(course1_id, "Course 1", now, now),
        create_course_read_schema(course2_id, "Course 2", now, now),
    ]
    
    mock_course_repository.get_by_ids.return_value = courses
    
    # Act
    result = await course_service.get_courses_for_teacher(teacher_id, page=1, page_size=5)
    
    # Assert
    assert len(result.items) == 2
    assert result.total == 2
    assert result.page == 1
    assert result.page_size == 5
    assert result.total_pages == 1
    
    # Verify get_by_ids was called with correct course IDs
    mock_course_repository.get_by_ids.assert_called_once()
    called_ids = mock_course_repository.get_by_ids.call_args[0][0]
    assert set(called_ids) == {course1_id, course2_id}


@pytest.mark.asyncio
async def test_get_courses_for_teacher_pagination():
    """
    Test: get_courses_for_teacher корректно обрабатывает пагинацию.
    
    Validates: Requirements 19.3 - Пагинация по 5 записей.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    teacher_id = uuid.uuid4()
    
    # Create 7 courses for teacher
    course_ids = [uuid.uuid4() for _ in range(7)]
    teacher_courses = [
        create_teacher_course_read_schema(teacher_id, course_id)
        for course_id in course_ids
    ]
    
    mock_teacher_course_repository.get_all.return_value = teacher_courses
    
    # Mock courses
    now = datetime.now(timezone.utc)
    courses = [
        create_course_read_schema(course_id, f"Course {i}", now, now)
        for i, course_id in enumerate(course_ids)
    ]
    
    mock_course_repository.get_by_ids.return_value = courses
    
    # Act - Page 1
    result_page1 = await course_service.get_courses_for_teacher(teacher_id, page=1, page_size=5)
    
    # Assert - Page 1
    assert len(result_page1.items) == 5
    assert result_page1.total == 7
    assert result_page1.page == 1
    assert result_page1.page_size == 5
    assert result_page1.total_pages == 2
    
    # Act - Page 2
    result_page2 = await course_service.get_courses_for_teacher(teacher_id, page=2, page_size=5)
    
    # Assert - Page 2
    assert len(result_page2.items) == 2
    assert result_page2.total == 7
    assert result_page2.page == 2
    assert result_page2.total_pages == 2


@pytest.mark.asyncio
async def test_get_courses_for_teacher_default_page_size():
    """
    Test: get_courses_for_teacher использует page_size=5 по умолчанию.
    
    Validates: Context requirement - Use page_size=5 by default.
    """
    # Arrange
    mock_course_repository = AsyncMock()
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    teacher_id = uuid.uuid4()
    mock_teacher_course_repository.get_all.return_value = []
    
    # Act - не передаём page_size
    result = await course_service.get_courses_for_teacher(teacher_id, page=1)
    
    # Assert
    assert result.page_size == 5
