"""
Property-based tests for TeacherService.

Feature: telegram-bot-full-workflow
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from hypothesis import given, strategies as st, settings

from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from reflebot.apps.reflections.models import Admin
from reflebot.apps.reflections.services.teacher import TeacherService
from reflebot.apps.reflections.schemas import (
    AdminReadSchema,
    StudentReadSchema,
    TeacherReadSchema,
    TeacherCreateSchema,
    TeacherCourseCreateSchema,
    TeacherLectionCreateSchema,
)


# Helper functions
def create_teacher_read_schema(
    teacher_id: uuid.UUID,
    full_name: str,
    telegram_username: str,
    is_active: bool = True,
) -> TeacherReadSchema:
    """Helper to create TeacherReadSchema."""
    now = datetime.now(timezone.utc)
    return TeacherReadSchema(
        id=teacher_id,
        full_name=full_name,
        telegram_username=telegram_username,
        telegram_id=None,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


# Property 19: Bulk Teacher Attachment
# **Validates: Requirements 15.5, 15.6, 15.7**
@given(
    full_name=st.text(min_size=3, max_size=255),
    telegram_username=st.text(
        min_size=3, max_size=100, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"))
    ),
    teacher_exists=st.booleans(),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_create_or_get_teacher(
    full_name,
    telegram_username,
    teacher_exists,
):
    """
    Property: Create or Get Teacher
    
    For any ФИО и username, система должна создавать нового преподавателя 
    если не существует, или возвращать существующего.
    
    **Validates: Requirements 15.5**
    """
    # Create mocks inside the test
    mock_teacher_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    mock_teacher_lection_repository = AsyncMock()
    
    teacher_service = TeacherService(
        teacher_repository=mock_teacher_repository,
        teacher_course_repository=mock_teacher_course_repository,
        teacher_lection_repository=mock_teacher_lection_repository,
    )
    
    # Arrange
    teacher_id = uuid.uuid4()
    
    if teacher_exists:
        # Mock existing teacher
        existing_teacher = create_teacher_read_schema(
            teacher_id=teacher_id,
            full_name=full_name,
            telegram_username=telegram_username,
        )
        mock_teacher_repository.get_by_telegram_username.return_value = existing_teacher
    else:
        # Mock no existing teacher
        mock_teacher_repository.get_by_telegram_username.return_value = None
        
        # Mock created teacher
        created_teacher = create_teacher_read_schema(
            teacher_id=teacher_id,
            full_name=full_name,
            telegram_username=telegram_username,
        )
        mock_teacher_repository.create.return_value = created_teacher
    
    # Act
    result = await teacher_service.create_or_get(full_name, telegram_username)
    
    # Assert
    assert isinstance(result, TeacherReadSchema)
    assert result.full_name == full_name
    assert result.telegram_username == telegram_username
    assert result.is_active is True
    
    # Verify correct repository method was called
    mock_teacher_repository.get_by_telegram_username.assert_called_once_with(telegram_username)
    
    if teacher_exists:
        # Should not create new teacher
        mock_teacher_repository.create.assert_not_called()
    else:
        # Should create new teacher
        mock_teacher_repository.create.assert_called_once()
        create_call_args = mock_teacher_repository.create.call_args[0][0]
        assert isinstance(create_call_args, TeacherCreateSchema)
        assert create_call_args.full_name == full_name
        assert create_call_args.telegram_username == telegram_username
        assert create_call_args.is_active is True


@pytest.mark.asyncio
async def test_create_or_get_teacher_copies_telegram_id_from_admin():
    """Новый преподаватель наследует telegram_id из администраторов."""
    mock_teacher_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    mock_teacher_lection_repository = AsyncMock()
    mock_admin_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    teacher_service = TeacherService(
        teacher_repository=mock_teacher_repository,
        teacher_course_repository=mock_teacher_course_repository,
        teacher_lection_repository=mock_teacher_lection_repository,
        admin_repository=mock_admin_repository,
        student_repository=mock_student_repository,
    )
    mock_teacher_repository.get_by_telegram_username.return_value = None
    mock_admin_repository.get_by_telegram_username.return_value = AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=123456,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_teacher_repository.create.return_value = create_teacher_read_schema(
        teacher_id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
    )

    await teacher_service.create_or_get("Иванов Иван", "ivanov")

    create_call = mock_teacher_repository.create.call_args[0][0]
    assert create_call.telegram_id == 123456
    mock_student_repository.get_by_telegram_username.assert_not_called()


@pytest.mark.asyncio
async def test_create_or_get_teacher_copies_telegram_id_from_student_when_admin_missing():
    """Новый преподаватель наследует telegram_id из студентов."""
    mock_teacher_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    mock_teacher_lection_repository = AsyncMock()
    mock_admin_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    teacher_service = TeacherService(
        teacher_repository=mock_teacher_repository,
        teacher_course_repository=mock_teacher_course_repository,
        teacher_lection_repository=mock_teacher_lection_repository,
        admin_repository=mock_admin_repository,
        student_repository=mock_student_repository,
    )
    mock_teacher_repository.get_by_telegram_username.return_value = None
    mock_admin_repository.get_by_telegram_username.side_effect = ModelFieldNotFoundException(
        Admin,
        "telegram_username",
        "ivanov",
    )
    mock_student_repository.get_by_telegram_username.return_value = StudentReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=654321,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_teacher_repository.create.return_value = create_teacher_read_schema(
        teacher_id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
    )

    await teacher_service.create_or_get("Иванов Иван", "ivanov")

    create_call = mock_teacher_repository.create.call_args[0][0]
    assert create_call.telegram_id == 654321
    mock_student_repository.get_by_telegram_username.assert_called_once_with("ivanov")


# Property: Attach Teacher to Course
# **Validates: Requirements 15.6**
@given(
    teacher_id=st.uuids(),
    course_id=st.uuids(),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_attach_teacher_to_course(
    teacher_id,
    course_id,
):
    """
    Property: Attach Teacher to Course
    
    For any привязки преподавателя к курсу, система должна создавать 
    запись TeacherCourse.
    
    **Validates: Requirements 15.6**
    """
    # Create mocks inside the test
    mock_teacher_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    mock_teacher_lection_repository = AsyncMock()
    
    teacher_service = TeacherService(
        teacher_repository=mock_teacher_repository,
        teacher_course_repository=mock_teacher_course_repository,
        teacher_lection_repository=mock_teacher_lection_repository,
    )
    
    # Arrange
    now = datetime.now(timezone.utc)
    teacher_course_id = uuid.uuid4()
    
    mock_teacher_course = Mock()
    mock_teacher_course.id = teacher_course_id
    mock_teacher_course.teacher_id = teacher_id
    mock_teacher_course.course_session_id = course_id
    mock_teacher_course.created_at = now
    mock_teacher_course.updated_at = now
    
    mock_teacher_course_repository.create.return_value = Mock(
        id=teacher_course_id,
        teacher_id=teacher_id,
        course_session_id=course_id,
        created_at=now,
        updated_at=now,
    )
    
    # Act
    await teacher_service.attach_to_course(teacher_id, course_id)
    
    # Assert
    mock_teacher_course_repository.create.assert_called_once()
    create_call_args = mock_teacher_course_repository.create.call_args[0][0]
    assert isinstance(create_call_args, TeacherCourseCreateSchema)
    assert create_call_args.teacher_id == teacher_id
    assert create_call_args.course_session_id == course_id


# Property: Bulk Attach Teacher to Lections
# **Validates: Requirements 15.7**
@given(
    teacher_id=st.uuids(),
    lection_count=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_bulk_attach_teacher_to_lections(
    teacher_id,
    lection_count,
):
    """
    Property 19: Bulk Teacher Attachment
    
    For any привязки преподавателя к курсу, система должна создавать 
    TeacherCourse и TeacherLection записи для всех лекций курса одним 
    bulk_create запросом.
    
    **Validates: Requirements 15.7**
    """
    # Create mocks inside the test
    mock_teacher_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    mock_teacher_lection_repository = AsyncMock()
    
    teacher_service = TeacherService(
        teacher_repository=mock_teacher_repository,
        teacher_course_repository=mock_teacher_course_repository,
        teacher_lection_repository=mock_teacher_lection_repository,
    )
    
    # Arrange
    lection_ids = [uuid.uuid4() for _ in range(lection_count)]
    
    # Mock bulk_create to return created records
    now = datetime.now(timezone.utc)
    mock_created_records = [
        Mock(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            lection_session_id=lection_id,
            created_at=now,
            updated_at=now,
        )
        for lection_id in lection_ids
    ]
    mock_teacher_lection_repository.bulk_create.return_value = mock_created_records
    
    # Act
    await teacher_service.attach_to_lections(teacher_id, lection_ids)
    
    # Assert
    mock_teacher_lection_repository.bulk_create.assert_called_once()
    
    # Verify bulk_create was called with correct schemas
    bulk_create_call_args = mock_teacher_lection_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == lection_count
    
    # Verify each schema
    for i, schema in enumerate(bulk_create_call_args):
        assert isinstance(schema, TeacherLectionCreateSchema)
        assert schema.teacher_id == teacher_id
        assert schema.lection_session_id == lection_ids[i]


# Additional property test: Empty lection list
@pytest.mark.asyncio
async def test_attach_to_lections_empty_list():
    """
    Property: Empty Lection List Handling
    
    For any пустого списка лекций, система должна корректно обрабатывать 
    ситуацию и вызывать bulk_create с пустым списком.
    """
    # Create mocks
    mock_teacher_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    mock_teacher_lection_repository = AsyncMock()
    
    teacher_service = TeacherService(
        teacher_repository=mock_teacher_repository,
        teacher_course_repository=mock_teacher_course_repository,
        teacher_lection_repository=mock_teacher_lection_repository,
    )
    
    # Arrange
    teacher_id = uuid.uuid4()
    lection_ids = []
    
    mock_teacher_lection_repository.bulk_create.return_value = []
    
    # Act
    await teacher_service.attach_to_lections(teacher_id, lection_ids)
    
    # Assert
    mock_teacher_lection_repository.bulk_create.assert_called_once()
    bulk_create_call_args = mock_teacher_lection_repository.bulk_create.call_args[0][0]
    assert isinstance(bulk_create_call_args, list)
    assert len(bulk_create_call_args) == 0


# Additional property test: Username normalization
@given(
    full_name=st.text(min_size=3, max_size=255),
    username_with_at=st.text(
        min_size=3, max_size=100, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"))
    ).map(lambda x: f"@{x}"),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_create_teacher_username_without_at(
    full_name,
    username_with_at,
):
    """
    Property: Username Normalization
    
    For any username с символом @, система должна принимать его как есть 
    (валидация на уровне API).
    
    **Validates: Requirements 15.4**
    """
    # Create mocks
    mock_teacher_repository = AsyncMock()
    mock_teacher_course_repository = AsyncMock()
    mock_teacher_lection_repository = AsyncMock()
    
    teacher_service = TeacherService(
        teacher_repository=mock_teacher_repository,
        teacher_course_repository=mock_teacher_course_repository,
        teacher_lection_repository=mock_teacher_lection_repository,
    )
    
    # Arrange
    teacher_id = uuid.uuid4()
    
    # Mock no existing teacher
    mock_teacher_repository.get_by_telegram_username.return_value = None
    
    # Mock created teacher
    created_teacher = create_teacher_read_schema(
        teacher_id=teacher_id,
        full_name=full_name,
        telegram_username=username_with_at,
    )
    mock_teacher_repository.create.return_value = created_teacher
    
    # Act
    result = await teacher_service.create_or_get(full_name, username_with_at)
    
    # Assert
    assert result.telegram_username == username_with_at
    
    # Verify create was called with username as-is
    mock_teacher_repository.create.assert_called_once()
    create_call_args = mock_teacher_repository.create.call_args[0][0]
    assert create_call_args.telegram_username == username_with_at
