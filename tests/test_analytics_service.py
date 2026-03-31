"""
Unit tests for AnalyticsService.

Feature: telegram-bot-full-workflow
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock

from reflebot.apps.reflections.services.analytics import AnalyticsService
from reflebot.apps.reflections.schemas import (
    LectionStatisticsSchema,
    StudentStatisticsSchema,
    ReflectionDetailsSchema,
    LectionSessionReadSchema,
    StudentReadSchema,
    QuestionReadSchema,
    LectionReflectionReadSchema,
)
from reflebot.core.utils.exceptions import ModelNotFoundException


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


# Property 24: Lection Statistics Accuracy
# **Validates: Requirements 21.5, 21.6, 21.7**
@pytest.mark.asyncio
async def test_lection_statistics_accuracy():
    """
    Property 24: Lection Statistics Accuracy
    
    For any лекции, статистика должна корректно подсчитывать total_students 
    (через StudentLection), reflections_count (через LectionReflection) 
    и qa_count (через LectionQA).
    
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
    
    # Mock questions (3 questions)
    mock_questions = [
        create_mock_question(uuid.uuid4(), lection_id, f"Question {i}")
        for i in range(3)
    ]
    
    # Mock students (5 students with reflections)
    mock_students = [
        create_mock_student(uuid.uuid4(), f"Student {i}", f"student{i}")
        for i in range(5)
    ]
    
    # Setup execute to return different results for different queries
    mock_questions_result = Mock()
    mock_questions_result.scalars.return_value.all.return_value = mock_questions
    
    mock_total_students_result = Mock()
    mock_total_students_result.scalar_one.return_value = 10  # 10 total students
    
    mock_reflections_count_result = Mock()
    mock_reflections_count_result.scalar_one.return_value = 5  # 5 reflections
    
    mock_qa_count_result = Mock()
    mock_qa_count_result.scalar_one.return_value = 15  # 15 QA answers (5 students * 3 questions)
    
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
    assert result.lection.topic == "Test Lection"
    
    # Проверяем подсчет статистики
    assert result.total_students == 10
    assert result.reflections_count == 5
    assert result.qa_count == 15
    
    # Проверяем вопросы
    assert len(result.questions) == 3
    
    # Проверяем студентов с рефлексиями
    assert len(result.students_with_reflections) == 5


# Property 26: Student Statistics Accuracy
# **Validates: Requirements 23.3, 23.4, 23.5**
@pytest.mark.asyncio
async def test_student_statistics_accuracy():
    """
    Property 26: Student Statistics Accuracy
    
    For any студента в курсе, статистика должна корректно подсчитывать 
    total_lections (через StudentLection), reflections_count и qa_count 
    для данного курса.
    
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
        full_name="Test Student",
        telegram_username="teststudent",
    )
    mock_student_repository.get.return_value = mock_student
    
    # Mock session
    mock_session = AsyncMock()
    mock_student_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    # Mock lections with reflections (3 lections)
    mock_lections = [
        Mock(
            id=uuid.uuid4(),
            course_session_id=course_id,
            topic=f"Lection {i}",
            started_at=datetime.now(timezone.utc) + timedelta(days=i),
            ended_at=datetime.now(timezone.utc) + timedelta(days=i, hours=2),
            deadline=datetime.now(timezone.utc) + timedelta(days=i, hours=26),
            presentation_file_id=None,
            recording_file_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        for i in range(3)
    ]
    
    # Setup execute to return different results for different queries
    mock_total_lections_result = Mock()
    mock_total_lections_result.scalar_one.return_value = 8  # 8 total lections in course
    
    mock_reflections_count_result = Mock()
    mock_reflections_count_result.scalar_one.return_value = 3  # 3 reflections submitted
    
    mock_qa_count_result = Mock()
    mock_qa_count_result.scalar_one.return_value = 9  # 9 QA answers (3 lections * 3 questions)
    
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
    assert result.student.full_name == "Test Student"
    
    # Проверяем подсчет статистики
    assert result.total_lections == 8
    assert result.reflections_count == 3
    assert result.qa_count == 9
    
    # Проверяем лекции с рефлексиями
    assert len(result.lections_with_reflections) == 3


# Property 25: Reflection Details Completeness
# **Validates: Requirements 22.2, 22.3, 22.4, 22.5**
@pytest.mark.asyncio
async def test_reflection_details_completeness():
    """
    Property 25: Reflection Details Completeness
    
    For any запроса рефлексии студента, ответ должен содержать информацию 
    о рефлексии, список ReflectionVideo с Telegram file_id, список вопросов 
    с ответами и QAVideo с Telegram file_id.
    
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
    
    # Mock reflection
    mock_reflection = Mock()
    mock_reflection.id = reflection_id
    mock_reflection.student_id = student_id
    mock_reflection.lection_session_id = lection_id
    mock_reflection.submitted_at = datetime.now(timezone.utc)
    mock_reflection.ai_analysis_status = "PENDING"
    mock_reflection.created_at = datetime.now(timezone.utc)
    mock_reflection.updated_at = datetime.now(timezone.utc)
    
    # Mock reflection videos (2 videos)
    mock_reflection_video_1 = Mock()
    mock_reflection_video_1.id = uuid.uuid4()
    mock_reflection_video_1.reflection_id = reflection_id
    mock_reflection_video_1.file_id = "tg-reflection-video-1"
    mock_reflection_video_1.order_index = 0
    mock_reflection_video_1.created_at = datetime.now(timezone.utc)
    mock_reflection_video_1.updated_at = datetime.now(timezone.utc)
    
    mock_reflection_video_2 = Mock()
    mock_reflection_video_2.id = uuid.uuid4()
    mock_reflection_video_2.reflection_id = reflection_id
    mock_reflection_video_2.file_id = "tg-reflection-video-2"
    mock_reflection_video_2.order_index = 1
    mock_reflection_video_2.created_at = datetime.now(timezone.utc)
    mock_reflection_video_2.updated_at = datetime.now(timezone.utc)
    
    mock_reflection.reflection_videos = [mock_reflection_video_1, mock_reflection_video_2]
    
    # Mock question and QA
    mock_question = Mock()
    mock_question.id = uuid.uuid4()
    mock_question.lection_session_id = lection_id
    mock_question.question_text = "Test Question"
    mock_question.created_at = datetime.now(timezone.utc)
    mock_question.updated_at = datetime.now(timezone.utc)
    
    mock_lection_qa = Mock()
    mock_lection_qa.id = uuid.uuid4()
    mock_lection_qa.reflection_id = reflection_id
    mock_lection_qa.question_id = mock_question.id
    mock_lection_qa.answer_submitted_at = datetime.now(timezone.utc)
    mock_lection_qa.created_at = datetime.now(timezone.utc)
    mock_lection_qa.updated_at = datetime.now(timezone.utc)
    mock_lection_qa.question = mock_question
    
    # Mock QA video
    mock_qa_video = Mock()
    mock_qa_video.id = uuid.uuid4()
    mock_qa_video.lection_qa_id = mock_lection_qa.id
    mock_qa_video.file_id = "tg-qa-video-1"
    mock_qa_video.order_index = 1
    mock_qa_video.created_at = datetime.now(timezone.utc)
    mock_qa_video.updated_at = datetime.now(timezone.utc)
    
    mock_lection_qa.qa_videos = [mock_qa_video]
    mock_reflection.lection_qas = [mock_lection_qa]
    
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
    assert len(result.reflection_videos) == 2
    assert result.reflection_videos[0].file_id == "tg-reflection-video-1"
    assert result.reflection_videos[1].file_id == "tg-reflection-video-2"
    
    # Проверяем список вопросов и ответов
    assert len(result.qa_list) == 1
    assert result.qa_list[0].question.question_text == "Test Question"
    assert result.qa_list[0].lection_qa.id == mock_lection_qa.id
    
    # Проверяем видео ответов с Telegram file_id
    assert len(result.qa_list[0].qa_videos) == 1
    assert result.qa_list[0].qa_videos[0].file_id == "tg-qa-video-1"


# Test: Reflection not found
@pytest.mark.asyncio
async def test_reflection_details_not_found():
    """
    Test that get_reflection_details raises ModelNotFoundException 
    when reflection is not found.
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
    
    # Mock session
    mock_session = AsyncMock()
    mock_lection_repository.session = mock_session
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    # Act & Assert
    with pytest.raises(ModelNotFoundException):
        await analytics_service.get_reflection_details(student_id, lection_id)


# Test: Empty statistics
@pytest.mark.asyncio
async def test_lection_statistics_empty():
    """
    Test that get_lection_statistics works correctly when there are no 
    students, reflections, or QA answers.
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
