"""
Property-based tests for StudentService bulk operations.

Feature: telegram-bot-full-workflow
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from hypothesis import given, strategies as st, settings

from reflebot.apps.reflections.services.student import StudentService
from reflebot.apps.reflections.schemas import (
    StudentReadSchema,
    StudentCreateSchema,
    StudentCourseCreateSchema,
    StudentLectionCreateSchema,
)


# Helper functions
def create_student_read_schema(
    student_id: uuid.UUID,
    full_name: str,
    telegram_username: str,
    telegram_id: int | None = None,
    is_active: bool = True,
) -> StudentReadSchema:
    """Helper to create StudentReadSchema."""
    now = datetime.now(timezone.utc)
    return StudentReadSchema(
        id=student_id,
        full_name=full_name,
        telegram_username=telegram_username,
        telegram_id=telegram_id,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


# Property 20: Bulk Student Attachment
# **Validates: Requirements 16.4, 16.5, 16.6**


@given(
    students_count=st.integers(min_value=1, max_value=50),
    existing_ratio=st.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_bulk_create_or_get_students(
    students_count,
    existing_ratio,
):
    """
    Property 20.1: Bulk Student Creation
    
    For any списка студентов из CSV файла, система должна создавать 
    Student записи для новых студентов с использованием bulk_create.
    
    **Validates: Requirements 16.4**
    """
    # Create mocks inside the test
    mock_student_repository = AsyncMock()
    mock_student_course_repository = AsyncMock()
    mock_student_lection_repository = AsyncMock()
    
    student_service = StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
    )
    
    # Arrange
    existing_count = int(students_count * existing_ratio)
    new_count = students_count - existing_count
    
    # Generate student data
    students_data = [
        {
            "full_name": f"Student {i}",
            "telegram_username": f"student{i}",
        }
        for i in range(students_count)
    ]
    
    # Mock existing students
    existing_students = [
        create_student_read_schema(
            student_id=uuid.uuid4(),
            full_name=students_data[i]["full_name"],
            telegram_username=students_data[i]["telegram_username"],
            telegram_id=100000 + i,
        )
        for i in range(existing_count)
    ]
    
    # Mock new students to be created
    new_students = [
        create_student_read_schema(
            student_id=uuid.uuid4(),
            full_name=students_data[existing_count + i]["full_name"],
            telegram_username=students_data[existing_count + i]["telegram_username"],
        )
        for i in range(new_count)
    ]
    
    # Setup mock responses
    get_by_username_responses = existing_students + [None] * new_count
    mock_student_repository.get_by_telegram_username.side_effect = get_by_username_responses
    mock_student_repository.bulk_create.return_value = new_students
    
    # Act
    result = await student_service.bulk_create_or_get(students_data)
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == students_count
    
    # Verify all students are returned
    for student in result:
        assert isinstance(student, StudentReadSchema)
        assert student.is_active is True
    
    # Verify get_by_telegram_username was called for each student
    assert mock_student_repository.get_by_telegram_username.call_count == students_count
    
    # Verify bulk_create was called only if there are new students
    if new_count > 0:
        mock_student_repository.bulk_create.assert_called_once()
        bulk_create_call_args = mock_student_repository.bulk_create.call_args[0][0]
        assert isinstance(bulk_create_call_args, list)
        assert len(bulk_create_call_args) == new_count
        
        # Verify each schema
        for schema in bulk_create_call_args:
            assert isinstance(schema, StudentCreateSchema)
            assert schema.is_active is True
    else:
        mock_student_repository.bulk_create.assert_not_called()


@given(
    student_count=st.integers(min_value=1, max_value=30),
    course_id=st.uuids(),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_bulk_attach_students_to_course(
    student_count,
    course_id,
):
    """
    Property 20.2: Bulk Student Course Attachment
    
    For any привязки студентов из CSV файла, система должна создавать 
    StudentCourse записи используя bulk_create операции.
    
    **Validates: Requirements 16.5**
    """
    # Create mocks inside the test
    mock_student_repository = AsyncMock()
    mock_student_course_repository = AsyncMock()
    mock_student_lection_repository = AsyncMock()
    
    student_service = StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
    )
    
    # Arrange
    student_ids = [uuid.uuid4() for _ in range(student_count)]
    
    # Mock bulk_create to return created records
    now = datetime.now(timezone.utc)
    mock_created_records = [
        Mock(
            id=uuid.uuid4(),
            student_id=student_id,
            course_session_id=course_id,
            created_at=now,
            updated_at=now,
        )
        for student_id in student_ids
    ]
    mock_student_course_repository.bulk_create.return_value = mock_created_records
    
    # Act
    await student_service.attach_to_course(student_ids, course_id)
    
    # Assert
    mock_student_course_repository.bulk_create.assert_called_once()
    
    # Verify bulk_create was called with correct schemas
    bulk_create_call_args = mock_student_course_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == student_count
    
    # Verify each schema
    for i, schema in enumerate(bulk_create_call_args):
        assert isinstance(schema, StudentCourseCreateSchema)
        assert schema.student_id == student_ids[i]
        assert schema.course_session_id == course_id


@given(
    student_count=st.integers(min_value=1, max_value=20),
    lection_count=st.integers(min_value=1, max_value=15),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_bulk_attach_students_to_lections(
    student_count,
    lection_count,
):
    """
    Property 20.3: Bulk Student Lection Attachment
    
    For any привязки студентов из CSV файла, система должна создавать 
    StudentLection записи для всех лекций курса с использованием bulk_create.
    
    **Validates: Requirements 16.6**
    """
    # Create mocks inside the test
    mock_student_repository = AsyncMock()
    mock_student_course_repository = AsyncMock()
    mock_student_lection_repository = AsyncMock()
    
    student_service = StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
    )
    
    # Arrange
    student_ids = [uuid.uuid4() for _ in range(student_count)]
    lection_ids = [uuid.uuid4() for _ in range(lection_count)]
    
    # Expected total combinations
    expected_count = student_count * lection_count
    
    # Mock bulk_create to return created records
    now = datetime.now(timezone.utc)
    mock_created_records = [
        Mock(
            id=uuid.uuid4(),
            student_id=student_id,
            lection_session_id=lection_id,
            created_at=now,
            updated_at=now,
        )
        for student_id in student_ids
        for lection_id in lection_ids
    ]
    mock_student_lection_repository.bulk_create.return_value = mock_created_records
    
    # Act
    await student_service.attach_to_lections(student_ids, lection_ids)
    
    # Assert
    mock_student_lection_repository.bulk_create.assert_called_once()
    
    # Verify bulk_create was called with correct schemas
    bulk_create_call_args = mock_student_lection_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == expected_count
    
    # Verify each schema and all combinations are present
    for schema in bulk_create_call_args:
        assert isinstance(schema, StudentLectionCreateSchema)
        assert schema.student_id in student_ids
        assert schema.lection_session_id in lection_ids
    
    # Verify all combinations exist
    created_combinations = {
        (schema.student_id, schema.lection_session_id)
        for schema in bulk_create_call_args
    }
    expected_combinations = {
        (student_id, lection_id)
        for student_id in student_ids
        for lection_id in lection_ids
    }
    assert created_combinations == expected_combinations


# Edge case: Empty lists
@pytest.mark.asyncio
async def test_attach_to_course_empty_students():
    """
    Property: Empty Student List Handling for Course
    
    For any пустого списка студентов, система должна корректно обрабатывать 
    ситуацию и вызывать bulk_create с пустым списком.
    """
    # Create mocks
    mock_student_repository = AsyncMock()
    mock_student_course_repository = AsyncMock()
    mock_student_lection_repository = AsyncMock()
    
    student_service = StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
    )
    
    # Arrange
    student_ids = []
    course_id = uuid.uuid4()
    
    mock_student_course_repository.bulk_create.return_value = []
    
    # Act
    await student_service.attach_to_course(student_ids, course_id)
    
    # Assert
    mock_student_course_repository.bulk_create.assert_called_once()
    bulk_create_call_args = mock_student_course_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == 0


@pytest.mark.asyncio
async def test_attach_to_lections_empty_students():
    """
    Property: Empty Student List Handling for Lections
    
    For any пустого списка студентов, система должна корректно обрабатывать 
    ситуацию и вызывать bulk_create с пустым списком.
    """
    # Create mocks
    mock_student_repository = AsyncMock()
    mock_student_course_repository = AsyncMock()
    mock_student_lection_repository = AsyncMock()
    
    student_service = StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
    )
    
    # Arrange
    student_ids = []
    lection_ids = [uuid.uuid4(), uuid.uuid4()]
    
    mock_student_lection_repository.bulk_create.return_value = []
    
    # Act
    await student_service.attach_to_lections(student_ids, lection_ids)
    
    # Assert
    mock_student_lection_repository.bulk_create.assert_called_once()
    bulk_create_call_args = mock_student_lection_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == 0


@pytest.mark.asyncio
async def test_attach_to_lections_empty_lections():
    """
    Property: Empty Lection List Handling
    
    For any пустого списка лекций, система должна корректно обрабатывать 
    ситуацию и вызывать bulk_create с пустым списком.
    """
    # Create mocks
    mock_student_repository = AsyncMock()
    mock_student_course_repository = AsyncMock()
    mock_student_lection_repository = AsyncMock()
    
    student_service = StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
    )
    
    # Arrange
    student_ids = [uuid.uuid4(), uuid.uuid4()]
    lection_ids = []
    
    mock_student_lection_repository.bulk_create.return_value = []
    
    # Act
    await student_service.attach_to_lections(student_ids, lection_ids)
    
    # Assert
    mock_student_lection_repository.bulk_create.assert_called_once()
    bulk_create_call_args = mock_student_lection_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == 0


# Additional property test: Single student, single lection
@pytest.mark.asyncio
async def test_attach_single_student_to_single_lection():
    """
    Property: Single Student Single Lection
    
    For any одного студента и одной лекции, система должна создавать 
    ровно одну запись StudentLection.
    """
    # Create mocks
    mock_student_repository = AsyncMock()
    mock_student_course_repository = AsyncMock()
    mock_student_lection_repository = AsyncMock()
    
    student_service = StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
    )
    
    # Arrange
    student_id = uuid.uuid4()
    lection_id = uuid.uuid4()
    
    now = datetime.now(timezone.utc)
    mock_created_record = Mock(
        id=uuid.uuid4(),
        student_id=student_id,
        lection_session_id=lection_id,
        created_at=now,
        updated_at=now,
    )
    mock_student_lection_repository.bulk_create.return_value = [mock_created_record]
    
    # Act
    await student_service.attach_to_lections([student_id], [lection_id])
    
    # Assert
    mock_student_lection_repository.bulk_create.assert_called_once()
    bulk_create_call_args = mock_student_lection_repository.bulk_create.call_args[0][0]
    assert len(bulk_create_call_args) == 1
    assert bulk_create_call_args[0].student_id == student_id
    assert bulk_create_call_args[0].lection_session_id == lection_id
