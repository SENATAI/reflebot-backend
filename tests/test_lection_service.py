"""
Property-based tests for LectionService.

Feature: telegram-bot-full-workflow
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock
from hypothesis import given, strategies as st, settings, assume

from reflebot.apps.reflections.services.lection import (
    LectionService,
    LectionDetailsSchema,
    PaginatedResponse,
)
from reflebot.apps.reflections.schemas import CourseSessionReadSchema, LectionSessionReadSchema
from reflebot.apps.reflections.models import LectionSession, Question
from reflebot.core.utils.exceptions import ModelNotFoundException


# Helper functions
def create_lection_read_schema(
    lection_id: uuid.UUID,
    course_id: uuid.UUID,
    topic: str,
    started_at: datetime,
    ended_at: datetime,
    presentation_file_id: str | None = None,
    recording_file_id: str | None = None,
) -> LectionSessionReadSchema:
    """Helper to create LectionSessionReadSchema."""
    now = datetime.now(timezone.utc)
    return LectionSessionReadSchema(
        id=lection_id,
        course_session_id=course_id,
        topic=topic,
        started_at=started_at,
        ended_at=ended_at,
        deadline=ended_at + timedelta(hours=24),
        presentation_file_id=presentation_file_id,
        recording_file_id=recording_file_id,
        created_at=now,
        updated_at=now,
    )


def create_course_read_schema(
    course_id: uuid.UUID,
    started_at: datetime,
    ended_at: datetime,
) -> CourseSessionReadSchema:
    """Helper to create CourseSessionReadSchema."""
    now = datetime.now(timezone.utc)
    return CourseSessionReadSchema(
        id=course_id,
        name="Course",
        join_code="ABCD",
        started_at=started_at,
        ended_at=ended_at,
        created_at=now,
        updated_at=now,
    )


def create_mock_question(question_id: uuid.UUID, lection_id: uuid.UUID, text: str):
    """Helper to create mock Question."""
    mock_q = Mock()
    mock_q.id = question_id
    mock_q.lection_session_id = lection_id
    mock_q.question_text = text
    mock_q.created_at = datetime.now(timezone.utc)
    return mock_q


# Property 14: Lection Details Completeness
# **Validates: Requirements 9.1, 9.2, 9.3, 9.4**
@given(
    topic=st.text(min_size=1, max_size=500),
    has_presentation=st.booleans(),
    has_recording=st.booleans(),
    question_count=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_lection_details_completeness(
    topic,
    has_presentation,
    has_recording,
    question_count,
):
    """
    Property 14: Lection Details Completeness
    
    For any запроса детальной информации о лекции, ответ должен содержать 
    тему, дату, время, список вопросов, информацию о презентации и записи.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    lection_service = LectionService(lection_repository=mock_lection_repository)
    
    # Arrange
    lection_id = uuid.uuid4()
    course_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    ended_at = started_at + timedelta(hours=2)
    
    presentation_file_id = "tg-presentation-id" if has_presentation else None
    recording_file_id = "tg-recording-id" if has_recording else None
    
    # Mock lection
    mock_lection = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic=topic,
        started_at=started_at,
        ended_at=ended_at,
        presentation_file_id=presentation_file_id,
        recording_file_id=recording_file_id,
    )
    mock_lection_repository.get.return_value = mock_lection
    
    # Mock questions
    mock_questions = [
        create_mock_question(uuid.uuid4(), lection_id, f"Question {i}")
        for i in range(question_count)
    ]
    
    # Mock session context manager
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    mock_result = Mock()
    mock_result.scalars.return_value.all.return_value = mock_questions
    mock_session.execute.return_value = mock_result
    
    # Act
    result = await lection_service.get_lection_details(lection_id)
    
    # Assert - проверяем полноту информации
    assert isinstance(result, LectionDetailsSchema)
    
    # Проверяем тему
    assert result.lection.topic == topic
    
    # Проверяем дату и время
    assert result.lection.started_at == started_at
    assert result.lection.ended_at == ended_at
    
    # Проверяем список вопросов
    assert isinstance(result.questions, list)
    assert len(result.questions) == question_count
    
    # Проверяем информацию о презентации
    assert result.has_presentation == has_presentation
    if has_presentation:
        assert result.lection.presentation_file_id == presentation_file_id
    else:
        assert result.lection.presentation_file_id is None
    
    # Проверяем информацию о записи
    assert result.has_recording == has_recording
    if has_recording:
        assert result.lection.recording_file_id == recording_file_id
    else:
        assert result.lection.recording_file_id is None


# Property 15: Topic Update Persistence
# **Validates: Requirements 10.3, 10.4**
@given(
    old_topic=st.text(min_size=1, max_size=500),
    new_topic=st.text(min_size=1, max_size=500),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_topic_update_persistence(
    old_topic,
    new_topic,
):
    """
    Property 15: Topic Update Persistence
    
    For any обновления темы лекции, новая тема должна сохраняться в БД 
    и возвращаться при последующих запросах.
    
    **Validates: Requirements 10.3, 10.4**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    lection_service = LectionService(lection_repository=mock_lection_repository)
    
    # Arrange
    lection_id = uuid.uuid4()
    course_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    ended_at = started_at + timedelta(hours=2)
    
    # Mock existing lection
    existing_lection = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic=old_topic,
        started_at=started_at,
        ended_at=ended_at,
    )
    mock_lection_repository.get.return_value = existing_lection
    
    # Mock updated lection
    updated_lection = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic=new_topic,
        started_at=started_at,
        ended_at=ended_at,
    )
    mock_lection_repository.update.return_value = updated_lection
    
    # Act
    result = await lection_service.update_topic(lection_id, new_topic)
    
    # Assert - новая тема должна сохраниться и вернуться
    assert result.topic == new_topic
    assert result.id == lection_id
    
    # Проверяем, что update был вызван с правильными данными
    mock_lection_repository.update.assert_called_once()
    update_call_args = mock_lection_repository.update.call_args[0][0]
    assert update_call_args.id == lection_id
    assert update_call_args.topic == new_topic


# Property 16: DateTime Update Validation
# **Validates: Requirements 11.3, 11.4**
@given(
    hours_offset=st.integers(min_value=1, max_value=100),
    duration_hours=st.integers(min_value=1, max_value=8),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_datetime_update_validation(
    hours_offset,
    duration_hours,
):
    """
    Property 16: DateTime Update Validation
    
    For any обновления даты и времени лекции, система должна валидировать 
    формат DD.MM.YYYY HH:MM-HH:MM и обновлять поля started_at и ended_at.
    
    **Validates: Requirements 11.3, 11.4**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    lection_service = LectionService(lection_repository=mock_lection_repository)
    
    # Arrange
    lection_id = uuid.uuid4()
    course_id = uuid.uuid4()
    
    # Старые даты
    old_started_at = datetime.now(timezone.utc)
    old_ended_at = old_started_at + timedelta(hours=2)
    
    # Новые даты
    new_started_at = datetime.now(timezone.utc) + timedelta(hours=hours_offset)
    new_ended_at = new_started_at + timedelta(hours=duration_hours)
    
    # Mock existing lection
    existing_lection = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic="Test Topic",
        started_at=old_started_at,
        ended_at=old_ended_at,
    )
    mock_lection_repository.get.return_value = existing_lection
    
    # Mock updated lection
    updated_lection = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic="Test Topic",
        started_at=new_started_at,
        ended_at=new_ended_at,
    )
    mock_lection_repository.update.return_value = updated_lection
    
    # Act
    result = await lection_service.update_datetime(
        lection_id, new_started_at, new_ended_at
    )
    
    # Assert - поля started_at и ended_at должны обновиться
    assert result.started_at == new_started_at
    assert result.ended_at == new_ended_at
    assert result.id == lection_id
    
    # Проверяем, что update был вызван с правильными данными
    mock_lection_repository.update.assert_called_once()
    update_call_args = mock_lection_repository.update.call_args[0][0]
    assert update_call_args.id == lection_id
    assert update_call_args.started_at == new_started_at
    assert update_call_args.ended_at == new_ended_at


@pytest.mark.asyncio
async def test_update_datetime_expands_course_bounds_when_lection_moves_outside_course():
    mock_lection_repository = AsyncMock()
    mock_course_repository = AsyncMock()
    lection_service = LectionService(
        lection_repository=mock_lection_repository,
        course_repository=mock_course_repository,
    )

    lection_id = uuid.uuid4()
    course_id = uuid.uuid4()
    course_started_at = datetime(2026, 3, 10, 7, 0, tzinfo=timezone.utc)
    course_ended_at = datetime(2026, 3, 20, 15, 0, tzinfo=timezone.utc)
    new_started_at = course_started_at - timedelta(days=2)
    new_ended_at = course_ended_at + timedelta(days=3)

    mock_lection_repository.get.return_value = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic="Moved lecture",
        started_at=course_started_at,
        ended_at=course_started_at + timedelta(hours=2),
    )
    mock_lection_repository.update.return_value = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic="Moved lecture",
        started_at=new_started_at,
        ended_at=new_ended_at,
    )
    mock_course_repository.get.return_value = create_course_read_schema(
        course_id=course_id,
        started_at=course_started_at,
        ended_at=course_ended_at,
    )

    await lection_service.update_datetime(lection_id, new_started_at, new_ended_at)

    mock_course_repository.update.assert_awaited_once()
    course_update = mock_course_repository.update.call_args.args[0]
    assert course_update.id == course_id
    assert course_update.started_at == new_started_at
    assert course_update.ended_at == new_ended_at


# Additional property test: Pagination consistency
@given(
    total_lections=st.integers(min_value=1, max_value=50),
    page_size=st.integers(min_value=1, max_value=10),
    page=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_pagination_consistency(
    total_lections,
    page_size,
    page,
):
    """
    Property: Pagination Consistency
    
    For any запроса списка лекций с пагинацией, система должна возвращать 
    корректное количество элементов и метаданные пагинации.
    
    **Validates: Requirements 8.1, 26.1, 26.2, 26.3**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    lection_service = LectionService(lection_repository=mock_lection_repository)
    
    # Skip invalid page numbers
    total_pages = (total_lections + page_size - 1) // page_size
    assume(page <= total_pages)
    
    # Arrange
    course_id = uuid.uuid4()
    
    # Calculate expected items for this page
    offset = (page - 1) * page_size
    expected_count = min(page_size, total_lections - offset)
    
    # Mock count query
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    # Mock count result
    mock_count_result = Mock()
    mock_count_result.scalar_one.return_value = total_lections
    
    # Mock lections result
    mock_lections = [
        Mock(
            id=uuid.uuid4(),
            course_session_id=course_id,
            topic=f"Lection {i}",
            started_at=datetime.now(timezone.utc) + timedelta(days=i),
            ended_at=datetime.now(timezone.utc) + timedelta(days=i, hours=2),
            deadline=datetime.now(timezone.utc) + timedelta(days=i, hours=26),
            one_question_from_list=False,
            presentation_file_id=None,
            recording_file_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        for i in range(offset, min(offset + page_size, total_lections))
    ]
    
    mock_lections_result = Mock()
    mock_lections_result.scalars.return_value.all.return_value = mock_lections
    
    # Setup execute to return different results for count and select queries
    mock_session.execute.side_effect = [mock_count_result, mock_lections_result]
    
    # Act
    result = await lection_service.get_lections_by_course(
        course_id, page=page, page_size=page_size
    )
    
    # Assert
    assert isinstance(result, PaginatedResponse)
    assert result.total == total_lections
    assert result.page == page
    assert result.page_size == page_size
    assert len(result.items) == expected_count
    assert result.total_pages == total_pages


# Additional property test: Nearest lection query
@given(
    future_lections_count=st.integers(min_value=0, max_value=10),
    past_lections_count=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_nearest_lection_for_teacher(
    future_lections_count,
    past_lections_count,
):
    """
    Property 22: Nearest Lection Query
    
    For any преподавателя, запрос ближайшей лекции должен возвращать лекцию 
    с минимальным started_at >= текущее время.
    
    **Validates: Requirements 18.2, 18.3**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    lection_service = LectionService(lection_repository=mock_lection_repository)
    
    # Arrange
    teacher_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    
    # Mock session
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    # Create nearest future lection if any
    if future_lections_count > 0:
        nearest_lection = Mock(
            id=uuid.uuid4(),
            course_session_id=uuid.uuid4(),
            topic="Nearest Lection",
            started_at=now + timedelta(hours=1),
            ended_at=now + timedelta(hours=3),
            deadline=now + timedelta(hours=27),
            one_question_from_list=False,
            presentation_file_id=None,
            recording_file_id=None,
            created_at=now,
            updated_at=now,
        )
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = nearest_lection
    else:
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
    
    mock_session.execute.return_value = mock_result
    
    # Act
    result = await lection_service.get_nearest_lection_for_teacher(teacher_id)
    
    # Assert
    if future_lections_count > 0:
        assert result is not None
        assert isinstance(result, LectionSessionReadSchema)
        # Ближайшая лекция должна быть в будущем
        assert result.started_at >= now
    else:
        assert result is None


@pytest.mark.asyncio
async def test_get_nearest_lection_returns_upcoming_lection_for_admin_scope():
    mock_lection_repository = AsyncMock()
    lection_service = LectionService(lection_repository=mock_lection_repository)
    now = datetime.now(timezone.utc)

    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    nearest_lection = Mock(
        id=uuid.uuid4(),
        course_session_id=uuid.uuid4(),
        topic="Global Nearest Lection",
        started_at=now + timedelta(hours=1),
        ended_at=now + timedelta(hours=3),
        deadline=now + timedelta(hours=27),
        one_question_from_list=False,
        presentation_file_id=None,
        recording_file_id=None,
        created_at=now,
        updated_at=now,
    )
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = nearest_lection
    mock_session.execute.return_value = mock_result

    result = await lection_service.get_nearest_lection()

    assert result is not None
    assert result.topic == "Global Nearest Lection"
    assert result.started_at >= now
