"""
Unit тесты для StudentService.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from reflebot.apps.reflections.models import Admin
from reflebot.apps.reflections.services.student import StudentService
from reflebot.apps.reflections.schemas import (
    AdminReadSchema,
    StudentReadSchema,
    StudentCourseReadSchema,
    StudentLectionReadSchema,
    TeacherReadSchema,
)


@pytest.fixture
def mock_student_repository():
    """Мок репозитория студентов."""
    return AsyncMock()


@pytest.fixture
def mock_student_course_repository():
    """Мок репозитория привязок студентов к курсам."""
    return AsyncMock()


@pytest.fixture
def mock_student_lection_repository():
    """Мок репозитория привязок студентов к лекциям."""
    return AsyncMock()


@pytest.fixture
def mock_admin_repository():
    """Мок репозитория администраторов."""
    return AsyncMock()


@pytest.fixture
def mock_teacher_repository():
    """Мок репозитория преподавателей."""
    return AsyncMock()


@pytest.fixture
def student_service(
    mock_student_repository,
    mock_student_course_repository,
    mock_student_lection_repository,
    mock_admin_repository,
    mock_teacher_repository,
):
    """Сервис студентов с моками."""
    return StudentService(
        student_repository=mock_student_repository,
        student_course_repository=mock_student_course_repository,
        student_lection_repository=mock_student_lection_repository,
        admin_repository=mock_admin_repository,
        teacher_repository=mock_teacher_repository,
    )


@pytest.mark.asyncio
async def test_bulk_create_or_get_all_new_students(
    student_service,
    mock_student_repository,
):
    """Тест создания всех новых студентов."""
    # Arrange
    students_data = [
        {"full_name": "Иванов Иван", "telegram_username": "ivanov"},
        {"full_name": "Петров Петр", "telegram_username": "petrov"},
    ]
    
    # Все студенты новые (не найдены)
    mock_student_repository.get_by_telegram_username.return_value = None
    
    # Мокируем bulk_create
    created_students = [
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Иванов Иван",
            telegram_username="ivanov",
            telegram_id=None,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Петров Петр",
            telegram_username="petrov",
            telegram_id=None,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
    ]
    mock_student_repository.bulk_create.return_value = created_students
    
    # Act
    result = await student_service.bulk_create_or_get(students_data)
    
    # Assert
    assert len(result) == 2
    assert result[0].full_name == "Иванов Иван"
    assert result[1].full_name == "Петров Петр"
    mock_student_repository.bulk_create.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_create_or_get_all_existing_students(
    student_service,
    mock_student_repository,
):
    """Тест получения всех существующих студентов."""
    # Arrange
    students_data = [
        {"full_name": "Иванов Иван", "telegram_username": "ivanov"},
        {"full_name": "Петров Петр", "telegram_username": "petrov"},
    ]
    
    existing_students = [
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Иванов Иван",
            telegram_username="ivanov",
            telegram_id=123456,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Петров Петр",
            telegram_username="petrov",
            telegram_id=789012,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
    ]
    
    # Все студенты существуют
    mock_student_repository.get_by_telegram_username.side_effect = existing_students
    
    # Act
    result = await student_service.bulk_create_or_get(students_data)
    
    # Assert
    assert len(result) == 2
    assert result[0].telegram_id == 123456
    assert result[1].telegram_id == 789012
    mock_student_repository.bulk_create.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_create_or_get_mixed_students(
    student_service,
    mock_student_repository,
):
    """Тест создания и получения смешанных студентов."""
    # Arrange
    students_data = [
        {"full_name": "Иванов Иван", "telegram_username": "ivanov"},
        {"full_name": "Петров Петр", "telegram_username": "petrov"},
        {"full_name": "Сидоров Сидор", "telegram_username": "sidorov"},
    ]
    
    existing_student = StudentReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=123456,
        is_active=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )
    
    # Первый студент существует, остальные новые
    mock_student_repository.get_by_telegram_username.side_effect = [
        existing_student,
        None,
        None,
    ]
    
    created_students = [
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Петров Петр",
            telegram_username="petrov",
            telegram_id=None,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Сидоров Сидор",
            telegram_username="sidorov",
            telegram_id=None,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
    ]
    mock_student_repository.bulk_create.return_value = created_students
    
    # Act
    result = await student_service.bulk_create_or_get(students_data)
    
    # Assert
    assert len(result) == 3
    assert result[0].telegram_username == "ivanov"
    assert result[1].telegram_username == "petrov"
    assert result[2].telegram_username == "sidorov"
    mock_student_repository.bulk_create.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_create_or_get_copies_telegram_id_from_admin(
    student_service,
    mock_student_repository,
    mock_admin_repository,
    mock_teacher_repository,
):
    """Новый студент наследует telegram_id из таблицы администраторов."""
    students_data = [{"full_name": "Иванов Иван", "telegram_username": "ivanov"}]
    mock_student_repository.get_by_telegram_username.return_value = None
    mock_admin_repository.get_by_telegram_username.return_value = AdminReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=123456,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )
    mock_teacher_repository.get_by_telegram_username.return_value = None
    mock_student_repository.bulk_create.return_value = [
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Иванов Иван",
            telegram_username="ivanov",
            telegram_id=123456,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    ]

    result = await student_service.bulk_create_or_get(students_data)

    assert result[0].telegram_id == 123456
    create_schema = mock_student_repository.bulk_create.call_args[0][0][0]
    assert create_schema.telegram_id == 123456
    mock_admin_repository.get_by_telegram_username.assert_called_once_with("ivanov")
    mock_teacher_repository.get_by_telegram_username.assert_not_called()


@pytest.mark.asyncio
async def test_bulk_create_or_get_copies_telegram_id_from_teacher_when_admin_missing(
    student_service,
    mock_student_repository,
    mock_admin_repository,
    mock_teacher_repository,
):
    """Новый студент наследует telegram_id из таблицы преподавателей."""
    students_data = [{"full_name": "Иванов Иван", "telegram_username": "ivanov"}]
    mock_student_repository.get_by_telegram_username.return_value = None
    mock_admin_repository.get_by_telegram_username.side_effect = ModelFieldNotFoundException(
        Admin,
        "telegram_username",
        "ivanov",
    )
    mock_teacher_repository.get_by_telegram_username.return_value = TeacherReadSchema(
        id=uuid.uuid4(),
        full_name="Иванов Иван",
        telegram_username="ivanov",
        telegram_id=654321,
        is_active=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )
    mock_student_repository.bulk_create.return_value = [
        StudentReadSchema(
            id=uuid.uuid4(),
            full_name="Иванов Иван",
            telegram_username="ivanov",
            telegram_id=654321,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        )
    ]

    result = await student_service.bulk_create_or_get(students_data)

    assert result[0].telegram_id == 654321
    create_schema = mock_student_repository.bulk_create.call_args[0][0][0]
    assert create_schema.telegram_id == 654321
    mock_teacher_repository.get_by_telegram_username.assert_called_once_with("ivanov")


@pytest.mark.asyncio
async def test_attach_to_course(
    student_service,
    mock_student_course_repository,
):
    """Тест привязки студентов к курсу."""
    # Arrange
    student_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    course_id = uuid.uuid4()
    
    # Act
    await student_service.attach_to_course(student_ids, course_id)
    
    # Assert
    mock_student_course_repository.bulk_create.assert_called_once()
    call_args = mock_student_course_repository.bulk_create.call_args[0][0]
    assert len(call_args) == 3
    assert all(sc.course_session_id == course_id for sc in call_args)
    assert all(sc.student_id in student_ids for sc in call_args)


@pytest.mark.asyncio
async def test_attach_to_lections(
    student_service,
    mock_student_lection_repository,
):
    """Тест привязки студентов к лекциям."""
    # Arrange
    student_ids = [uuid.uuid4(), uuid.uuid4()]
    lection_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    
    # Act
    await student_service.attach_to_lections(student_ids, lection_ids)
    
    # Assert
    mock_student_lection_repository.bulk_create.assert_called_once()
    call_args = mock_student_lection_repository.bulk_create.call_args[0][0]
    # Должно быть 2 студента * 3 лекции = 6 привязок
    assert len(call_args) == 6
    
    # Проверяем, что все комбинации созданы
    for student_id in student_ids:
        for lection_id in lection_ids:
            assert any(
                sl.student_id == student_id and sl.lection_session_id == lection_id
                for sl in call_args
            )


@pytest.mark.asyncio
async def test_get_students_by_course(
    student_service,
    mock_student_course_repository,
    mock_student_repository,
):
    """Тест получения студентов курса с пагинацией."""
    # Arrange
    course_id = uuid.uuid4()
    student_id_1 = uuid.uuid4()
    student_id_2 = uuid.uuid4()
    
    # Мокируем привязки студентов к курсу
    mock_student_course_repository.get_all.return_value = [
        StudentCourseReadSchema(
            id=uuid.uuid4(),
            student_id=student_id_1,
            course_session_id=course_id,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
        StudentCourseReadSchema(
            id=uuid.uuid4(),
            student_id=student_id_2,
            course_session_id=course_id,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
    ]
    
    # Мокируем get_by_ids
    students = [
        StudentReadSchema(
            id=student_id_2,
            full_name="Петров Петр",
            telegram_username="petrov",
            telegram_id=789012,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
        StudentReadSchema(
            id=student_id_1,
            full_name="Иванов Иван",
            telegram_username="ivanov",
            telegram_id=123456,
            is_active=True,
            created_at=MagicMock(),
            updated_at=MagicMock(),
        ),
    ]
    mock_student_repository.get_by_ids.return_value = students
    
    # Act
    result = await student_service.get_students_by_course(course_id, page=1, page_size=5)
    
    # Assert
    assert len(result["items"]) == 2
    assert [student.full_name for student in result["items"]] == [
        "Иванов Иван",
        "Петров Петр",
    ]
    assert result["total"] == 2
    assert result["page"] == 1
    assert result["page_size"] == 5
    assert result["total_pages"] == 1
    mock_student_course_repository.get_all.assert_called_once()
    mock_student_repository.get_by_ids.assert_called_once_with([student_id_1, student_id_2])


@pytest.mark.asyncio
async def test_attach_to_course_empty_list(
    student_service,
    mock_student_course_repository,
):
    """Тест привязки пустого списка студентов к курсу."""
    # Arrange
    student_ids = []
    course_id = uuid.uuid4()
    
    # Act
    await student_service.attach_to_course(student_ids, course_id)
    
    # Assert
    mock_student_course_repository.bulk_create.assert_called_once()
    call_args = mock_student_course_repository.bulk_create.call_args[0][0]
    assert len(call_args) == 0


@pytest.mark.asyncio
async def test_attach_to_lections_empty_students(
    student_service,
    mock_student_lection_repository,
):
    """Тест привязки пустого списка студентов к лекциям."""
    # Arrange
    student_ids = []
    lection_ids = [uuid.uuid4(), uuid.uuid4()]
    
    # Act
    await student_service.attach_to_lections(student_ids, lection_ids)
    
    # Assert
    mock_student_lection_repository.bulk_create.assert_called_once()
    call_args = mock_student_lection_repository.bulk_create.call_args[0][0]
    assert len(call_args) == 0


@pytest.mark.asyncio
async def test_attach_to_lections_empty_lections(
    student_service,
    mock_student_lection_repository,
):
    """Тест привязки студентов к пустому списку лекций."""
    # Arrange
    student_ids = [uuid.uuid4(), uuid.uuid4()]
    lection_ids = []
    
    # Act
    await student_service.attach_to_lections(student_ids, lection_ids)
    
    # Assert
    mock_student_lection_repository.bulk_create.assert_called_once()
    call_args = mock_student_lection_repository.bulk_create.call_args[0][0]
    assert len(call_args) == 0
