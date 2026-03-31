"""
Property-based tests for AnalyticsService.

Feature: telegram-bot-full-workflow
Task: 8.3 - Написать property tests для аналитики
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock
from hypothesis import given, strategies as st, settings

from reflebot.apps.reflections.services.analytics import AnalyticsService
from reflebot.apps.reflections.schemas import (
    LectionStatisticsSchema,
    StudentStatisticsSchema,
    ReflectionDetailsSchema,
    LectionSessionReadSchema,
    StudentReadSchema,
    QuestionReadSchema,
)


# Helper functions
def create_lection_read_schema(
    lection_id: uuid.UUID,
    course_id: uuid.UUID,
    topic: str,
    started_at: datetime,
    ended_at: datetime,
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
        presentation_file_id=None,
        recording_file_id=None,
        created_at=now,
        updated_at=now,
    )


def create_student_read_schema(
    student_id: uuid.UUID,
    full_name: str,
    telegram_username: str,
) -> StudentReadSchema:
    """Helper to create StudentReadSchema."""
    now = datetime.now(timezone.utc)
    return StudentReadSchema(
        id=student_id,
        full_name=full_name,
        telegram_username=telegram_username,
        telegram_id=None,
        is_active=True,
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
    mock_q.updated_at = datetime.now(timezone.utc)
    return mock_q


def create_mock_student(student_id: uuid.UUID, full_name: str, telegram_username: str):
    """Helper to create mock Student."""
    mock_s = Mock()
    mock_s.id = student_id
    mock_s.full_name = full_name
    mock_s.telegram_username = telegram_username
    mock_s.telegram_id = None
    mock_s.is_active = True
    mock_s.created_at = datetime.now(timezone.utc)
    mock_s.updated_at = datetime.now(timezone.utc)
    return mock_s


def create_mock_lection(lection_id: uuid.UUID, course_id: uuid.UUID, topic: str):
    """Helper to create mock LectionSession."""
    now = datetime.now(timezone.utc)
    mock_l = Mock()
    mock_l.id = lection_id
    mock_l.course_session_id = course_id
    mock_l.topic = topic
    mock_l.started_at = now
    mock_l.ended_at = now + timedelta(hours=2)
    mock_l.deadline = now + timedelta(hours=26)
    mock_l.presentation_file_id = None
    mock_l.recording_file_id = None
    mock_l.created_at = now
    mock_l.updated_at = now
    return mock_l


# Property 24: Lection Statistics Accuracy
# **Validates: Requirements 21.5, 21.6, 21.7**


@given(
    total_students=st.integers(min_value=0, max_value=100),
    reflections_count=st.integers(min_value=0, max_value=100),
    questions_count=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_24_lection_statistics_accuracy(
    total_students,
    reflections_count,
    questions_count,
):
    """
    Property 24: Lection Statistics Accuracy
    
    For any лекции, статистика должна корректно подсчитывать total_students 
    (через StudentLection), reflections_count (через LectionReflection) 
    и qa_count (через LectionQA).
    
    **Validates: Requirements 21.5, 21.6, 21.7**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    analytics_service = AnalyticsService(
        lection_repository=mock_lection_repository,
        student_repository=mock_student_repository,
    )
    
    # Arrange
    lection_id = uuid.uuid4()
    course_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    ended_at = started_at + timedelta(hours=2)
    
    # Mock lection
    mock_lection = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic="Test Lection",
        started_at=started_at,
        ended_at=ended_at,
    )
    mock_lection_repository.get.return_value = mock_lection
    
    # Mock session
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    # Mock questions
    mock_questions = [
        create_mock_question(uuid.uuid4(), lection_id, f"Question {i}")
        for i in range(questions_count)
    ]
    
    # Mock students with reflections (limited by reflections_count)
    students_with_reflections_count = min(reflections_count, total_students)
    mock_students = [
        create_mock_student(uuid.uuid4(), f"Student {i}", f"student{i}")
        for i in range(students_with_reflections_count)
    ]
    
    # Calculate QA count (each reflection can have answers to all questions)
    qa_count = reflections_count * questions_count
    
    # Setup execute to return different results for different queries
    mock_questions_result = Mock()
    mock_questions_result.scalars.return_value.all.return_value = mock_questions
    
    mock_total_students_result = Mock()
    mock_total_students_result.scalar_one.return_value = total_students
    
    mock_reflections_count_result = Mock()
    mock_reflections_count_result.scalar_one.return_value = reflections_count
    
    mock_qa_count_result = Mock()
    mock_qa_count_result.scalar_one.return_value = qa_count
    
    mock_students_result = Mock()
    mock_students_result.scalars.return_value.all.return_value = mock_students
    
    mock_session.execute.side_effect = [
        mock_questions_result,
        mock_total_students_result,
        mock_reflections_count_result,
        mock_qa_count_result,
        mock_students_result,
    ]
    
    # Act
    result = await analytics_service.get_lection_statistics(lection_id)
    
    # Assert
    assert isinstance(result, LectionStatisticsSchema)
    assert result.lection.id == lection_id
    
    # Проверяем подсчет статистики
    assert result.total_students == total_students, \
        f"Expected total_students={total_students}, got {result.total_students}"
    assert result.reflections_count == reflections_count, \
        f"Expected reflections_count={reflections_count}, got {result.reflections_count}"
    assert result.qa_count == qa_count, \
        f"Expected qa_count={qa_count}, got {result.qa_count}"
    
    # Проверяем вопросы
    assert len(result.questions) == questions_count, \
        f"Expected {questions_count} questions, got {len(result.questions)}"
    
    # Проверяем студентов с рефлексиями
    assert len(result.students_with_reflections) == students_with_reflections_count, \
        f"Expected {students_with_reflections_count} students, got {len(result.students_with_reflections)}"


# Property 26: Student Statistics Accuracy
# **Validates: Requirements 23.3, 23.4, 23.5**


@given(
    total_lections=st.integers(min_value=0, max_value=50),
    reflections_count=st.integers(min_value=0, max_value=50),
    questions_per_lection=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_26_student_statistics_accuracy(
    total_lections,
    reflections_count,
    questions_per_lection,
):
    """
    Property 26: Student Statistics Accuracy
    
    For any студента в курсе, статистика должна корректно подсчитывать 
    total_lections (через StudentLection), reflections_count и qa_count 
    для данного курса.
    
    **Validates: Requirements 23.3, 23.4, 23.5**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    analytics_service = AnalyticsService(
        lection_repository=mock_lection_repository,
        student_repository=mock_student_repository,
    )
    
    # Arrange
    student_id = uuid.uuid4()
    course_id = uuid.uuid4()
    
    # Mock student
    mock_student = create_student_read_schema(
        student_id=student_id,
        full_name="Test Student",
        telegram_username="teststudent",
    )
    mock_student_repository.get.return_value = mock_student
    
    # Mock session
    mock_session = AsyncMock()
    mock_student_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    # Mock lections with reflections (limited by reflections_count)
    lections_with_reflections_count = min(reflections_count, total_lections)
    mock_lections = [
        create_mock_lection(uuid.uuid4(), course_id, f"Lection {i}")
        for i in range(lections_with_reflections_count)
    ]
    
    # Calculate QA count (each reflection can have answers to all questions)
    qa_count = reflections_count * questions_per_lection
    
    # Setup execute to return different results for different queries
    mock_total_lections_result = Mock()
    mock_total_lections_result.scalar_one.return_value = total_lections
    
    mock_reflections_count_result = Mock()
    mock_reflections_count_result.scalar_one.return_value = reflections_count
    
    mock_qa_count_result = Mock()
    mock_qa_count_result.scalar_one.return_value = qa_count
    
    mock_lections_result = Mock()
    mock_lections_result.scalars.return_value.all.return_value = mock_lections
    
    mock_session.execute.side_effect = [
        mock_total_lections_result,
        mock_reflections_count_result,
        mock_qa_count_result,
        mock_lections_result,
    ]
    
    # Act
    result = await analytics_service.get_student_statistics(student_id, course_id)
    
    # Assert
    assert isinstance(result, StudentStatisticsSchema)
    assert result.student.id == student_id
    
    # Проверяем подсчет статистики
    assert result.total_lections == total_lections, \
        f"Expected total_lections={total_lections}, got {result.total_lections}"
    assert result.reflections_count == reflections_count, \
        f"Expected reflections_count={reflections_count}, got {result.reflections_count}"
    assert result.qa_count == qa_count, \
        f"Expected qa_count={qa_count}, got {result.qa_count}"
    
    # Проверяем лекции с рефлексиями
    assert len(result.lections_with_reflections) == lections_with_reflections_count, \
        f"Expected {lections_with_reflections_count} lections, got {len(result.lections_with_reflections)}"


# Property 25: Reflection Details Completeness
# **Validates: Requirements 22.2, 22.3, 22.4, 22.5**


@given(
    reflection_videos_count=st.integers(min_value=0, max_value=10),
    questions_count=st.integers(min_value=0, max_value=15),
    qa_videos_per_question=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_25_reflection_details_completeness(
    reflection_videos_count,
    questions_count,
    qa_videos_per_question,
):
    """
    Property 25: Reflection Details Completeness
    
    For any запроса рефлексии студента, ответ должен содержать информацию 
    о рефлексии, список ReflectionVideo с Telegram file_id, список вопросов 
    с ответами и QAVideo с Telegram file_id.
    
    **Validates: Requirements 22.2, 22.3, 22.4, 22.5**
    """
    # Create mocks inside the test
    mock_lection_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    analytics_service = AnalyticsService(
        lection_repository=mock_lection_repository,
        student_repository=mock_student_repository,
    )
    
    # Arrange
    student_id = uuid.uuid4()
    lection_id = uuid.uuid4()
    reflection_id = uuid.uuid4()
    
    # Mock reflection
    mock_reflection = Mock()
    mock_reflection.id = reflection_id
    mock_reflection.student_id = student_id
    mock_reflection.lection_session_id = lection_id
    mock_reflection.submitted_at = datetime.now(timezone.utc)
    mock_reflection.ai_analysis_status = "PENDING"
    mock_reflection.created_at = datetime.now(timezone.utc)
    mock_reflection.updated_at = datetime.now(timezone.utc)
    
    # Mock reflection videos
    mock_reflection_videos = []
    for i in range(reflection_videos_count):
        mock_video = Mock()
        mock_video.id = uuid.uuid4()
        mock_video.reflection_id = reflection_id
        mock_video.file_id = f"tg-reflection-video-{i}"
        mock_video.order_index = i
        mock_video.created_at = datetime.now(timezone.utc)
        mock_video.updated_at = datetime.now(timezone.utc)
        mock_reflection_videos.append(mock_video)
    
    mock_reflection.reflection_videos = mock_reflection_videos
    
    # Mock questions and QAs
    mock_lection_qas = []
    total_qa_videos = 0
    
    for i in range(questions_count):
        # Mock question
        mock_question = Mock()
        mock_question.id = uuid.uuid4()
        mock_question.lection_session_id = lection_id
        mock_question.question_text = f"Question {i}"
        mock_question.created_at = datetime.now(timezone.utc)
        mock_question.updated_at = datetime.now(timezone.utc)
        
        # Mock lection QA
        mock_lection_qa = Mock()
        mock_lection_qa.id = uuid.uuid4()
        mock_lection_qa.reflection_id = reflection_id
        mock_lection_qa.question_id = mock_question.id
        mock_lection_qa.answer_submitted_at = datetime.now(timezone.utc)
        mock_lection_qa.created_at = datetime.now(timezone.utc)
        mock_lection_qa.updated_at = datetime.now(timezone.utc)
        mock_lection_qa.question = mock_question
        
        # Mock QA videos
        mock_qa_videos = []
        for j in range(qa_videos_per_question):
            mock_qa_video = Mock()
            mock_qa_video.id = uuid.uuid4()
            mock_qa_video.lection_qa_id = mock_lection_qa.id
            mock_qa_video.file_id = f"tg-qa-video-{i}-{j}"
            mock_qa_video.order_index = j + 1
            mock_qa_video.created_at = datetime.now(timezone.utc)
            mock_qa_video.updated_at = datetime.now(timezone.utc)
            mock_qa_videos.append(mock_qa_video)
            total_qa_videos += 1
        
        mock_lection_qa.qa_videos = mock_qa_videos
        mock_lection_qas.append(mock_lection_qa)
    
    mock_reflection.lection_qas = mock_lection_qas
    
    # Mock session
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_reflection
    mock_session.execute.return_value = mock_result
    
    # Act
    result = await analytics_service.get_reflection_details(student_id, lection_id)
    
    # Assert
    assert isinstance(result, ReflectionDetailsSchema)
    
    # Проверяем информацию о рефлексии
    assert result.reflection.id == reflection_id
    assert result.reflection.student_id == student_id
    assert result.reflection.lection_session_id == lection_id
    
    # Проверяем видео рефлексий с Telegram file_id
    assert len(result.reflection_videos) == reflection_videos_count, \
        f"Expected {reflection_videos_count} reflection videos, got {len(result.reflection_videos)}"
    
    for video in result.reflection_videos:
        assert video.file_id.startswith("tg-reflection-video-"), \
            f"Expected Telegram file_id, got {video.file_id}"
    
    # Проверяем список вопросов и ответов
    assert len(result.qa_list) == questions_count, \
        f"Expected {questions_count} QA items, got {len(result.qa_list)}"
    
    # Проверяем видео ответов с Telegram file_id
    for qa_item in result.qa_list:
        assert len(qa_item.qa_videos) == qa_videos_per_question, \
            f"Expected {qa_videos_per_question} QA videos per question, got {len(qa_item.qa_videos)}"
        
        for qa_video in qa_item.qa_videos:
            assert qa_video.file_id.startswith("tg-qa-video-"), \
                f"Expected Telegram file_id, got {qa_video.file_id}"


# Edge case: Empty statistics
@pytest.mark.asyncio
async def test_property_24_empty_lection_statistics():
    """
    Property 24 Edge Case: Empty Lection Statistics
    
    For any лекции без студентов, рефлексий и вопросов, статистика должна 
    корректно возвращать нулевые значения.
    
    **Validates: Requirements 21.5, 21.6, 21.7**
    """
    # Create mocks
    mock_lection_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    analytics_service = AnalyticsService(
        lection_repository=mock_lection_repository,
        student_repository=mock_student_repository,
    )
    
    # Arrange
    lection_id = uuid.uuid4()
    course_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    ended_at = started_at + timedelta(hours=2)
    
    # Mock lection
    mock_lection = create_lection_read_schema(
        lection_id=lection_id,
        course_id=course_id,
        topic="Empty Lection",
        started_at=started_at,
        ended_at=ended_at,
    )
    mock_lection_repository.get.return_value = mock_lection
    
    # Mock session
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    # Mock empty results
    mock_questions_result = Mock()
    mock_questions_result.scalars.return_value.all.return_value = []
    
    mock_total_students_result = Mock()
    mock_total_students_result.scalar_one.return_value = 0
    
    mock_reflections_count_result = Mock()
    mock_reflections_count_result.scalar_one.return_value = 0
    
    mock_qa_count_result = Mock()
    mock_qa_count_result.scalar_one.return_value = 0
    
    mock_students_result = Mock()
    mock_students_result.scalars.return_value.all.return_value = []
    
    mock_session.execute.side_effect = [
        mock_questions_result,
        mock_total_students_result,
        mock_reflections_count_result,
        mock_qa_count_result,
        mock_students_result,
    ]
    
    # Act
    result = await analytics_service.get_lection_statistics(lection_id)
    
    # Assert
    assert isinstance(result, LectionStatisticsSchema)
    assert result.total_students == 0
    assert result.reflections_count == 0
    assert result.qa_count == 0
    assert len(result.questions) == 0
    assert len(result.students_with_reflections) == 0


@pytest.mark.asyncio
async def test_property_26_empty_student_statistics():
    """
    Property 26 Edge Case: Empty Student Statistics
    
    For any студента без лекций и рефлексий, статистика должна корректно 
    возвращать нулевые значения.
    
    **Validates: Requirements 23.3, 23.4, 23.5**
    """
    # Create mocks
    mock_lection_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    analytics_service = AnalyticsService(
        lection_repository=mock_lection_repository,
        student_repository=mock_student_repository,
    )
    
    # Arrange
    student_id = uuid.uuid4()
    course_id = uuid.uuid4()
    
    # Mock student
    mock_student = create_student_read_schema(
        student_id=student_id,
        full_name="Empty Student",
        telegram_username="emptystudent",
    )
    mock_student_repository.get.return_value = mock_student
    
    # Mock session
    mock_session = AsyncMock()
    mock_student_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    # Mock empty results
    mock_total_lections_result = Mock()
    mock_total_lections_result.scalar_one.return_value = 0
    
    mock_reflections_count_result = Mock()
    mock_reflections_count_result.scalar_one.return_value = 0
    
    mock_qa_count_result = Mock()
    mock_qa_count_result.scalar_one.return_value = 0
    
    mock_lections_result = Mock()
    mock_lections_result.scalars.return_value.all.return_value = []
    
    mock_session.execute.side_effect = [
        mock_total_lections_result,
        mock_reflections_count_result,
        mock_qa_count_result,
        mock_lections_result,
    ]
    
    # Act
    result = await analytics_service.get_student_statistics(student_id, course_id)
    
    # Assert
    assert isinstance(result, StudentStatisticsSchema)
    assert result.total_lections == 0
    assert result.reflections_count == 0
    assert result.qa_count == 0
    assert len(result.lections_with_reflections) == 0


@pytest.mark.asyncio
async def test_property_25_empty_reflection_details():
    """
    Property 25 Edge Case: Empty Reflection Details
    
    For any рефлексии без видео, вопросов и ответов, детали должны корректно 
    возвращать пустые списки.
    
    **Validates: Requirements 22.2, 22.3, 22.4, 22.5**
    """
    # Create mocks
    mock_lection_repository = AsyncMock()
    mock_student_repository = AsyncMock()
    analytics_service = AnalyticsService(
        lection_repository=mock_lection_repository,
        student_repository=mock_student_repository,
    )
    
    # Arrange
    student_id = uuid.uuid4()
    lection_id = uuid.uuid4()
    reflection_id = uuid.uuid4()
    
    # Mock reflection with empty lists
    mock_reflection = Mock()
    mock_reflection.id = reflection_id
    mock_reflection.student_id = student_id
    mock_reflection.lection_session_id = lection_id
    mock_reflection.submitted_at = datetime.now(timezone.utc)
    mock_reflection.ai_analysis_status = "PENDING"
    mock_reflection.created_at = datetime.now(timezone.utc)
    mock_reflection.updated_at = datetime.now(timezone.utc)
    mock_reflection.reflection_videos = []
    mock_reflection.lection_qas = []
    
    # Mock session
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_reflection
    mock_session.execute.return_value = mock_result
    
    # Act
    result = await analytics_service.get_reflection_details(student_id, lection_id)
    
    # Assert
    assert isinstance(result, ReflectionDetailsSchema)
    assert result.reflection.id == reflection_id
    assert len(result.reflection_videos) == 0
    assert len(result.qa_list) == 0
    
