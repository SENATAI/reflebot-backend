"""
Property-based tests for CourseService.

Feature: telegram-bot-full-workflow
Task: 7.3 - Написать property tests для CourseService
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock
from hypothesis import given, strategies as st, settings

from reflebot.apps.reflections.services.course import CourseService
from reflebot.apps.reflections.schemas import (
    CourseSessionReadSchema,
    CourseSessionCreateSchema,
    LectionSessionCreateSchema,
    TeacherCourseReadSchema,
)
from reflebot.settings import settings as app_settings


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


# Custom strategy for generating lection data
@st.composite
def lection_data_strategy(draw):
    """Generate valid lection data with started_at < ended_at."""
    # Generate naive datetime first (hypothesis requirement)
    base_date_naive = draw(st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2025, 12, 31),
    ))
    
    # Add timezone to make it aware
    base_date = base_date_naive.replace(tzinfo=timezone.utc)
    
    # Duration between 30 minutes and 4 hours
    duration_minutes = draw(st.integers(min_value=30, max_value=240))
    
    started_at = base_date
    ended_at = base_date + timedelta(minutes=duration_minutes)
    
    topic = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
        min_codepoint=32,
        max_codepoint=126,
    )))
    
    return {
        'topic': topic,
        'started_at': started_at,
        'ended_at': ended_at,
    }


# Property 8: Course Date Calculation
# **Validates: Requirements 5.4, 5.5**


@given(
    lections=st.lists(
        lection_data_strategy(),
        min_size=1,
        max_size=20,
    ),
    course_name=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
        min_codepoint=32,
        max_codepoint=126,
    )),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_8_course_date_calculation(
    lections,
    course_name,
):
    """
    Property 8: Course Date Calculation
    
    For any созданного курса из Excel файла, дата начала курса должна 
    равняться минимальной дате лекций, а дата окончания - максимальной 
    дате лекций.
    
    **Validates: Requirements 5.4, 5.5**
    """
    # Create mocks inside the test
    mock_course_repository = AsyncMock()
    mock_course_repository.get_by_join_code_or_none.return_value = None
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Calculate expected dates
    all_dates = [lection['started_at'] for lection in lections] + \
                [lection['ended_at'] for lection in lections]
    expected_started_at = min(all_dates)
    expected_ended_at = max(all_dates)
    
    # Mock course creation
    course_id = uuid.uuid4()
    mock_created_course = create_course_read_schema(
        course_id=course_id,
        name=course_name,
        started_at=expected_started_at,
        ended_at=expected_ended_at,
    )
    mock_course_repository.create.return_value = mock_created_course
    
    # Mock lection bulk creation
    mock_lection_repository.bulk_create.return_value = []
    
    # Act
    result = await course_service.create_course_with_lections(
        course_name=course_name,
        lections_data=lections,
    )
    
    # Assert - Course dates match min/max of lection dates
    assert result.started_at == expected_started_at, \
        f"Course started_at should be {expected_started_at}, got {result.started_at}"
    assert result.ended_at == expected_ended_at, \
        f"Course ended_at should be {expected_ended_at}, got {result.ended_at}"
    
    # Verify course_repository.create was called with correct dates
    mock_course_repository.create.assert_called_once()
    create_call_args = mock_course_repository.create.call_args[0][0]
    assert isinstance(create_call_args, CourseSessionCreateSchema)
    assert create_call_args.name == course_name
    assert create_call_args.started_at == expected_started_at
    assert create_call_args.ended_at == expected_ended_at
    
    # Verify lection_repository.bulk_create was called
    mock_lection_repository.bulk_create.assert_called_once()
    bulk_create_call_args = mock_lection_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == len(lections)
    
    # Verify each lection schema
    for i, schema in enumerate(bulk_create_call_args):
        assert isinstance(schema, LectionSessionCreateSchema)
        assert schema.course_session_id == course_id
        assert schema.topic == lections[i]['topic']
        assert schema.started_at == lections[i]['started_at']
        assert schema.ended_at == lections[i]['ended_at']
        assert schema.deadline == lections[i]['ended_at'] + timedelta(hours=app_settings.default_deadline)


# Property 12: Cascade Delete on Course Cancellation
# **Validates: Requirements 7.1**


@given(
    course_id=st.uuids(),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_12_cascade_delete_on_course_cancellation(
    course_id,
):
    """
    Property 12: Cascade Delete on Course Cancellation
    
    For any отмененного парсинга курса, все связанные лекции должны 
    автоматически удаляться из БД через CASCADE DELETE.
    
    **Validates: Requirements 7.1**
    """
    # Create mocks inside the test
    mock_course_repository = AsyncMock()
    mock_course_repository.get_by_join_code_or_none.return_value = None
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Mock delete operation
    mock_course_repository.delete.return_value = None
    
    # Act
    await course_service.delete_course(course_id)
    
    # Assert - delete was called on course repository
    mock_course_repository.delete.assert_called_once_with(course_id)
    
    # Assert - lection repository was NOT called (CASCADE handled by DB)
    mock_lection_repository.delete.assert_not_called()
    mock_lection_repository.bulk_delete.assert_not_called()
    
    # Assert - teacher_course repository was NOT called (CASCADE handled by DB)
    mock_teacher_course_repository.delete.assert_not_called()


# Property 23: Role-Based Course Filtering
# **Validates: Requirements 19.2, 19.3**


@given(
    total_courses=st.integers(min_value=1, max_value=30),
    teacher_course_ratio=st.floats(min_value=0.0, max_value=1.0),
    page=st.integers(min_value=1, max_value=5),
    page_size=st.just(5),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_23_admin_sees_all_courses(
    total_courses,
    teacher_course_ratio,
    page,
    page_size,
):
    """
    Property 23.1: Admin Sees All Courses
    
    For any запроса списка курсов, администратор должен видеть все курсы 
    с пагинацией.
    
    **Validates: Requirements 19.2**
    """
    # Create mocks inside the test
    mock_course_repository = AsyncMock()
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Create all courses
    now = datetime.now(timezone.utc)
    all_courses = [
        create_course_read_schema(
            course_id=uuid.uuid4(),
            name=f"Course {i}",
            started_at=now,
            ended_at=now,
        )
        for i in range(total_courses)
    ]
    
    mock_course_repository.get_all.return_value = all_courses
    
    # Act
    result = await course_service.get_courses_for_admin(page=page, page_size=page_size)
    
    # Assert - Admin sees all courses (with pagination)
    assert result.total == total_courses, \
        f"Admin should see all {total_courses} courses, got {result.total}"
    
    # Calculate expected pagination
    expected_total_pages = (total_courses + page_size - 1) // page_size if total_courses > 0 else 1
    assert result.total_pages == expected_total_pages
    assert result.page == page
    assert result.page_size == page_size
    
    # Calculate expected items for this page
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_courses)
    expected_items_count = max(0, end_idx - start_idx) if page <= expected_total_pages else 0
    
    assert len(result.items) == expected_items_count, \
        f"Expected {expected_items_count} items on page {page}, got {len(result.items)}"
    
    # Verify get_all was called (admin gets all courses)
    mock_course_repository.get_all.assert_called_once()


@given(
    total_courses=st.integers(min_value=1, max_value=30),
    teacher_course_ratio=st.floats(min_value=0.0, max_value=1.0),
    page=st.integers(min_value=1, max_value=5),
    page_size=st.just(5),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_23_teacher_sees_only_assigned_courses(
    total_courses,
    teacher_course_ratio,
    page,
    page_size,
):
    """
    Property 23.2: Teacher Sees Only Assigned Courses
    
    For any запроса списка курсов, преподаватель должен видеть только курсы, 
    где он привязан через TeacherCourse.
    
    **Validates: Requirements 19.3**
    """
    # Create mocks inside the test
    mock_course_repository = AsyncMock()
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Create teacher and other teacher
    teacher_id = uuid.uuid4()
    other_teacher_id = uuid.uuid4()
    
    # Calculate how many courses belong to teacher
    teacher_courses_count = int(total_courses * teacher_course_ratio)
    other_courses_count = total_courses - teacher_courses_count
    
    # Create course IDs
    teacher_course_ids = [uuid.uuid4() for _ in range(teacher_courses_count)]
    other_course_ids = [uuid.uuid4() for _ in range(other_courses_count)]
    
    # Create teacher_course associations
    teacher_courses = [
        create_teacher_course_read_schema(teacher_id, course_id)
        for course_id in teacher_course_ids
    ] + [
        create_teacher_course_read_schema(other_teacher_id, course_id)
        for course_id in other_course_ids
    ]
    
    mock_teacher_course_repository.get_all.return_value = teacher_courses
    
    # Create courses for teacher
    now = datetime.now(timezone.utc)
    teacher_courses_list = [
        create_course_read_schema(
            course_id=course_id,
            name=f"Teacher Course {i}",
            started_at=now,
            ended_at=now,
        )
        for i, course_id in enumerate(teacher_course_ids)
    ]
    
    # Mock get_by_ids to return teacher's courses
    if teacher_courses_count > 0:
        mock_course_repository.get_by_ids.return_value = teacher_courses_list
    else:
        mock_course_repository.get_by_ids.return_value = []
    
    # Act
    result = await course_service.get_courses_for_teacher(
        teacher_id=teacher_id,
        page=page,
        page_size=page_size,
    )
    
    # Assert - Teacher sees only their courses
    assert result.total == teacher_courses_count, \
        f"Teacher should see {teacher_courses_count} courses, got {result.total}"
    
    # Calculate expected pagination
    if teacher_courses_count == 0:
        expected_total_pages = 1
    else:
        expected_total_pages = (teacher_courses_count + page_size - 1) // page_size
    
    assert result.total_pages == expected_total_pages
    assert result.page == page
    assert result.page_size == page_size
    
    # Calculate expected items for this page
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, teacher_courses_count)
    expected_items_count = max(0, end_idx - start_idx) if page <= expected_total_pages else 0
    
    assert len(result.items) == expected_items_count, \
        f"Expected {expected_items_count} items on page {page}, got {len(result.items)}"
    
    # Verify get_all was called on teacher_course_repository
    mock_teacher_course_repository.get_all.assert_called_once()
    
    # Verify get_by_ids was called with correct course IDs (if teacher has courses)
    if teacher_courses_count > 0:
        mock_course_repository.get_by_ids.assert_called_once()
        called_ids = mock_course_repository.get_by_ids.call_args[0][0]
        assert set(called_ids) == set(teacher_course_ids), \
            "get_by_ids should be called with teacher's course IDs only"
    
    # Verify get_all was NOT called (teacher doesn't get all courses)
    mock_course_repository.get_all.assert_not_called()


# Edge case: Teacher with no courses
@pytest.mark.asyncio
async def test_property_23_teacher_with_no_courses():
    """
    Property 23.3: Teacher With No Courses
    
    For any преподавателя без привязанных курсов, система должна возвращать 
    пустой список с корректной пагинацией.
    
    **Validates: Requirements 19.3**
    """
    # Create mocks
    mock_course_repository = AsyncMock()
    mock_course_repository.get_by_join_code_or_none.return_value = None
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Arrange
    teacher_id = uuid.uuid4()
    
    # Mock: no teacher_course associations
    mock_teacher_course_repository.get_all.return_value = []
    
    # Act
    result = await course_service.get_courses_for_teacher(
        teacher_id=teacher_id,
        page=1,
        page_size=5,
    )
    
    # Assert
    assert result.items == []
    assert result.total == 0
    assert result.page == 1
    assert result.page_size == 5
    assert result.total_pages == 1
    
    # Verify get_by_ids was NOT called
    mock_course_repository.get_by_ids.assert_not_called()


# Edge case: Single lection course
@pytest.mark.asyncio
async def test_property_8_single_lection_course():
    """
    Property 8 Edge Case: Single Lection Course
    
    For any курса с одной лекцией, даты начала и окончания курса должны 
    соответствовать датам этой лекции.
    
    **Validates: Requirements 5.4, 5.5**
    """
    # Create mocks
    mock_course_repository = AsyncMock()
    mock_course_repository.get_by_join_code_or_none.return_value = None
    mock_lection_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    
    course_service = CourseService(
        course_repository=mock_course_repository,
        lection_repository=mock_lection_repository,
        teacher_course_repository=mock_teacher_course_repository,
    )
    
    # Arrange - single lection
    now = datetime.now(timezone.utc)
    lection_start = now
    lection_end = now + timedelta(hours=2)
    
    lections_data = [
        {
            'topic': 'Single Lection',
            'started_at': lection_start,
            'ended_at': lection_end,
        }
    ]
    
    course_id = uuid.uuid4()
    mock_created_course = create_course_read_schema(
        course_id=course_id,
        name="Single Lection Course",
        started_at=lection_start,
        ended_at=lection_end,
    )
    mock_course_repository.create.return_value = mock_created_course
    mock_lection_repository.bulk_create.return_value = []
    
    # Act
    result = await course_service.create_course_with_lections(
        course_name="Single Lection Course",
        lections_data=lections_data,
    )
    
    # Assert
    assert result.started_at == lection_start
    assert result.ended_at == lection_end
