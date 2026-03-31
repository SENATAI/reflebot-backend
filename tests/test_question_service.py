"""
Unit тесты для QuestionService.

**Validates: Requirements 12.3, 12.4, 12.6**
"""

import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from hypothesis import given, strategies as st, settings

from reflebot.apps.reflections.services.question import QuestionService
from reflebot.apps.reflections.schemas import QuestionReadSchema
from reflebot.core.utils.exceptions import ModelNotFoundException


def create_question_read_schema(
    question_id: uuid.UUID,
    lection_id: uuid.UUID,
    text: str,
) -> QuestionReadSchema:
    """Helper to create QuestionReadSchema."""
    now = datetime.now(timezone.utc)
    return QuestionReadSchema(
        id=question_id,
        lection_session_id=lection_id,
        question_text=text,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_question_repository():
    """Create a mock question repository."""
    return AsyncMock()


@pytest.fixture
def question_service(mock_question_repository):
    """Create a QuestionService instance with mocked repository."""
    return QuestionService(question_repository=mock_question_repository)


class TestCreateQuestion:
    """Test create_question method."""
    
    @pytest.mark.asyncio
    async def test_create_question_success(
        self, question_service, mock_question_repository
    ):
        """Тест успешного создания вопроса."""
        # Arrange
        lection_id = uuid.uuid4()
        question_text = "Что такое Clean Architecture?"
        question_id = uuid.uuid4()
        
        expected_question = create_question_read_schema(
            question_id=question_id,
            lection_id=lection_id,
            text=question_text,
        )
        mock_question_repository.create.return_value = expected_question
        
        # Act
        result = await question_service.create_question(lection_id, question_text)
        
        # Assert
        assert result.id == question_id
        assert result.lection_session_id == lection_id
        assert result.question_text == question_text
        mock_question_repository.create.assert_called_once()


class TestGetQuestionsByLection:
    """Test get_questions_by_lection method."""
    
    @pytest.mark.asyncio
    async def test_get_questions_empty_list(
        self, question_service, mock_question_repository
    ):
        """Тест получения пустого списка вопросов."""
        # Arrange
        lection_id = uuid.uuid4()
        
        # Mock session context manager and query
        mock_session = AsyncMock()
        mock_question_repository.session = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await question_service.get_questions_by_lection(lection_id)
        
        # Assert
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_questions_multiple(
        self, question_service, mock_question_repository
    ):
        """Тест получения нескольких вопросов."""
        # Arrange
        lection_id = uuid.uuid4()
        
        # Create mock questions
        mock_q1 = Mock()
        mock_q1.id = uuid.uuid4()
        mock_q1.lection_session_id = lection_id
        mock_q1.question_text = "Вопрос 1"
        mock_q1.created_at = datetime.now(timezone.utc)
        mock_q1.updated_at = datetime.now(timezone.utc)
        
        mock_q2 = Mock()
        mock_q2.id = uuid.uuid4()
        mock_q2.lection_session_id = lection_id
        mock_q2.question_text = "Вопрос 2"
        mock_q2.created_at = datetime.now(timezone.utc)
        mock_q2.updated_at = datetime.now(timezone.utc)
        
        # Mock session context manager and query
        mock_session = AsyncMock()
        mock_question_repository.session = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_q1, mock_q2]
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await question_service.get_questions_by_lection(lection_id)
        
        # Assert
        assert len(result) == 2
        assert result[0].question_text == "Вопрос 1"
        assert result[1].question_text == "Вопрос 2"


class TestUpdateQuestion:
    """Test update_question method."""
    
    @pytest.mark.asyncio
    async def test_update_question_success(
        self, question_service, mock_question_repository
    ):
        """Тест успешного обновления вопроса."""
        # Arrange
        question_id = uuid.uuid4()
        lection_id = uuid.uuid4()
        old_text = "Старый текст"
        new_text = "Новый текст"
        
        # Mock get to verify question exists
        existing_question = create_question_read_schema(
            question_id=question_id,
            lection_id=lection_id,
            text=old_text,
        )
        mock_question_repository.get.return_value = existing_question
        
        # Mock update
        updated_question = create_question_read_schema(
            question_id=question_id,
            lection_id=lection_id,
            text=new_text,
        )
        mock_question_repository.update.return_value = updated_question
        
        # Act
        result = await question_service.update_question(question_id, new_text)
        
        # Assert
        assert result.id == question_id
        assert result.question_text == new_text
        mock_question_repository.get.assert_called_once_with(question_id)
        mock_question_repository.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_question(
        self, question_service, mock_question_repository
    ):
        """Тест обновления несуществующего вопроса."""
        # Arrange
        question_id = uuid.uuid4()
        from reflebot.apps.reflections.models import Question
        mock_question_repository.get.side_effect = ModelNotFoundException(
            model=Question,
            model_id=question_id,
        )
        
        # Act & Assert
        with pytest.raises(ModelNotFoundException):
            await question_service.update_question(question_id, "Новый текст")


class TestDeleteQuestion:
    """Test delete_question method."""
    
    @pytest.mark.asyncio
    async def test_delete_question_success(
        self, question_service, mock_question_repository
    ):
        """Тест успешного удаления вопроса."""
        # Arrange
        question_id = uuid.uuid4()
        mock_question_repository.delete.return_value = None
        
        # Act
        await question_service.delete_question(question_id)
        
        # Assert
        mock_question_repository.delete.assert_called_once_with(question_id)
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_question(
        self, question_service, mock_question_repository
    ):
        """Тест удаления несуществующего вопроса."""
        # Arrange
        question_id = uuid.uuid4()
        from reflebot.apps.reflections.models import Question
        mock_question_repository.delete.side_effect = ModelNotFoundException(
            model=Question,
            model_id=question_id,
        )
        
        # Act & Assert
        with pytest.raises(ModelNotFoundException):
            await question_service.delete_question(question_id)



# ============================================================================
# Property-Based Tests
# ============================================================================

class TestQuestionCRUDOperationsProperty:
    """
    Property-based tests for Question CRUD operations.
    
    **Validates: Property 17 - Question CRUD Operations**
    **Validates: Requirements 12.3, 12.4, 12.6**
    """
    
    @given(
        question_texts=st.lists(
            st.text(min_size=1, max_size=200, alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
                whitelist_characters='?!.,;:-'
            )),
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_property_question_crud_maintains_order(self, question_texts):
        """
        **Validates: Property 17: Question CRUD Operations**
        
        For any лекции, система должна поддерживать добавление, изменение и 
        удаление вопросов с сохранением порядка.
        
        This property test verifies that:
        1. Questions can be created (Create)
        2. Questions can be retrieved in order (Read)
        3. Questions can be updated (Update)
        4. Questions can be deleted (Delete)
        5. Order is maintained throughout all operations
        """
        # Arrange
        lection_id = uuid.uuid4()
        mock_repository = AsyncMock()
        service = QuestionService(question_repository=mock_repository)
        
        # Track created questions with their creation order
        created_questions = []
        creation_times = []
        
        # Phase 1: CREATE - Add all questions
        for idx, text in enumerate(question_texts):
            question_id = uuid.uuid4()
            created_at = datetime.now(timezone.utc)
            creation_times.append(created_at)
            
            question = QuestionReadSchema(
                id=question_id,
                lection_session_id=lection_id,
                question_text=text,
                created_at=created_at,
                updated_at=created_at,
            )
            created_questions.append(question)
            mock_repository.create.return_value = question
            
            result = await service.create_question(lection_id, text)
            
            # Verify creation
            assert result.id == question_id
            assert result.question_text == text
            assert result.lection_session_id == lection_id
        
        # Phase 2: READ - Retrieve all questions and verify order
        mock_session = AsyncMock()
        mock_repository.session = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        
        # Create mock Question objects with proper attributes
        mock_questions = []
        for q in created_questions:
            mock_q = Mock()
            mock_q.id = q.id
            mock_q.lection_session_id = q.lection_session_id
            mock_q.question_text = q.question_text
            mock_q.created_at = q.created_at
            mock_q.updated_at = q.updated_at
            mock_questions.append(mock_q)
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_questions
        mock_session.execute.return_value = mock_result
        
        retrieved_questions = await service.get_questions_by_lection(lection_id)
        
        # Verify order is maintained (by created_at)
        assert len(retrieved_questions) == len(created_questions)
        for i, retrieved in enumerate(retrieved_questions):
            assert retrieved.question_text == question_texts[i]
            assert retrieved.created_at == creation_times[i]
        
        # Phase 3: UPDATE - Modify some questions
        if len(created_questions) > 0:
            # Update first question
            first_question = created_questions[0]
            updated_text = f"UPDATED: {first_question.question_text}"
            
            mock_repository.get.return_value = first_question
            
            updated_question = QuestionReadSchema(
                id=first_question.id,
                lection_session_id=lection_id,
                question_text=updated_text,
                created_at=first_question.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            mock_repository.update.return_value = updated_question
            
            result = await service.update_question(first_question.id, updated_text)
            
            # Verify update
            assert result.id == first_question.id
            assert result.question_text == updated_text
            assert result.created_at == first_question.created_at  # created_at unchanged
            assert result.updated_at > first_question.updated_at  # updated_at changed
        
        # Phase 4: DELETE - Remove some questions
        if len(created_questions) > 1:
            # Delete last question
            last_question = created_questions[-1]
            mock_repository.delete.return_value = None
            
            await service.delete_question(last_question.id)
            
            # Verify delete was called
            mock_repository.delete.assert_called_with(last_question.id)
            
            # Simulate retrieval after deletion
            remaining_questions = mock_questions[:-1]
            mock_result.scalars.return_value.all.return_value = remaining_questions
            
            retrieved_after_delete = await service.get_questions_by_lection(lection_id)
            
            # Verify order is still maintained after deletion
            assert len(retrieved_after_delete) == len(created_questions) - 1
            for i, retrieved in enumerate(retrieved_after_delete):
                assert retrieved.question_text == question_texts[i]
    
    @given(
        initial_questions=st.lists(
            st.text(min_size=1, max_size=100),
            min_size=2,
            max_size=5,
            unique=True
        ),
        delete_indices=st.data()
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_property_delete_maintains_order_of_remaining(
        self, initial_questions, delete_indices
    ):
        """
        **Validates: Property 17: Question CRUD Operations**
        
        For any набора вопросов, после удаления некоторых вопросов, 
        порядок оставшихся вопросов должен сохраняться.
        """
        # Arrange
        lection_id = uuid.uuid4()
        mock_repository = AsyncMock()
        service = QuestionService(question_repository=mock_repository)
        
        # Create questions
        created_questions = []
        for idx, text in enumerate(initial_questions):
            question_id = uuid.uuid4()
            created_at = datetime.now(timezone.utc)
            
            question = QuestionReadSchema(
                id=question_id,
                lection_session_id=lection_id,
                question_text=text,
                created_at=created_at,
                updated_at=created_at,
            )
            created_questions.append(question)
        
        # Select random indices to delete (at least keep one question)
        num_to_delete = delete_indices.draw(
            st.integers(min_value=1, max_value=len(initial_questions) - 1)
        )
        indices_to_delete = delete_indices.draw(
            st.lists(
                st.integers(min_value=0, max_value=len(initial_questions) - 1),
                min_size=num_to_delete,
                max_size=num_to_delete,
                unique=True
            )
        )
        
        # Delete selected questions
        for idx in sorted(indices_to_delete, reverse=True):
            question_to_delete = created_questions[idx]
            mock_repository.delete.return_value = None
            await service.delete_question(question_to_delete.id)
        
        # Get remaining questions
        remaining_questions = [
            q for i, q in enumerate(created_questions) 
            if i not in indices_to_delete
        ]
        
        # Mock retrieval of remaining questions
        mock_session = AsyncMock()
        mock_repository.session = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        
        mock_questions = []
        for q in remaining_questions:
            mock_q = Mock()
            mock_q.id = q.id
            mock_q.lection_session_id = q.lection_session_id
            mock_q.question_text = q.question_text
            mock_q.created_at = q.created_at
            mock_q.updated_at = q.updated_at
            mock_questions.append(mock_q)
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_questions
        mock_session.execute.return_value = mock_result
        
        retrieved = await service.get_questions_by_lection(lection_id)
        
        # Verify order is maintained
        assert len(retrieved) == len(remaining_questions)
        for i, (retrieved_q, expected_q) in enumerate(zip(retrieved, remaining_questions)):
            assert retrieved_q.id == expected_q.id
            assert retrieved_q.question_text == expected_q.question_text
            assert retrieved_q.created_at == expected_q.created_at
    
    @given(
        questions=st.lists(
            st.text(min_size=1, max_size=100),
            min_size=1,
            max_size=5,
            unique=True
        ),
        update_data=st.data()
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_property_update_preserves_creation_order(
        self, questions, update_data
    ):
        """
        **Validates: Property 17: Question CRUD Operations**
        
        For any набора вопросов, обновление текста вопроса не должно 
        изменять порядок вопросов (порядок определяется created_at).
        """
        # Arrange
        lection_id = uuid.uuid4()
        mock_repository = AsyncMock()
        service = QuestionService(question_repository=mock_repository)
        
        # Create questions with incrementing timestamps
        created_questions = []
        base_time = datetime.now(timezone.utc)
        
        for idx, text in enumerate(questions):
            question_id = uuid.uuid4()
            created_at = base_time.replace(microsecond=idx * 1000)
            
            question = QuestionReadSchema(
                id=question_id,
                lection_session_id=lection_id,
                question_text=text,
                created_at=created_at,
                updated_at=created_at,
            )
            created_questions.append(question)
        
        # Select random question to update
        question_to_update_idx = update_data.draw(
            st.integers(min_value=0, max_value=len(questions) - 1)
        )
        question_to_update = created_questions[question_to_update_idx]
        new_text = f"UPDATED: {question_to_update.question_text}"
        
        # Mock get and update
        mock_repository.get.return_value = question_to_update
        
        updated_question = QuestionReadSchema(
            id=question_to_update.id,
            lection_session_id=lection_id,
            question_text=new_text,
            created_at=question_to_update.created_at,  # created_at unchanged
            updated_at=datetime.now(timezone.utc),  # updated_at changed
        )
        mock_repository.update.return_value = updated_question
        
        # Update the question
        result = await service.update_question(question_to_update.id, new_text)
        
        # Verify update
        assert result.id == question_to_update.id
        assert result.question_text == new_text
        assert result.created_at == question_to_update.created_at
        
        # Update the question in our list
        created_questions[question_to_update_idx] = updated_question
        
        # Mock retrieval after update
        mock_session = AsyncMock()
        mock_repository.session = mock_session
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        
        mock_questions = []
        for q in created_questions:
            mock_q = Mock()
            mock_q.id = q.id
            mock_q.lection_session_id = q.lection_session_id
            mock_q.question_text = q.question_text
            mock_q.created_at = q.created_at
            mock_q.updated_at = q.updated_at
            mock_questions.append(mock_q)
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_questions
        mock_session.execute.return_value = mock_result
        
        retrieved = await service.get_questions_by_lection(lection_id)
        
        # Verify order is still based on created_at (unchanged)
        assert len(retrieved) == len(created_questions)
        for i, retrieved_q in enumerate(retrieved):
            assert retrieved_q.created_at == created_questions[i].created_at
            # The updated question should be in the same position
            if i == question_to_update_idx:
                assert retrieved_q.question_text == new_text
            else:
                assert retrieved_q.question_text == questions[i]
