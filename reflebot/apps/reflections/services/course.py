"""
Сервис для работы с курсами.
"""

import secrets
import uuid
from typing import Protocol
import sqlalchemy as sa
from sqlalchemy import select, func
from reflebot.core.utils.exceptions import ModelAlreadyExistsError
from reflebot.settings import settings
from ..datetime_utils import calculate_lection_deadline
from ..repositories.course import CourseSessionRepositoryProtocol
from ..repositories.lection import LectionSessionRepositoryProtocol
from ..repositories.teacher_course import TeacherCourseRepositoryProtocol
from ..schemas import (
    CourseSessionCreateSchema,
    CourseSessionReadSchema,
    CourseSessionUpdateSchema,
    LectionSessionCreateSchema,
    LectionSessionReadSchema,
    PaginatedResponse,
)
from ..models import CourseSession, TeacherCourse

COURSE_JOIN_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class CourseServiceProtocol(Protocol):
    """Протокол сервиса курсов."""
    
    async def create_course_with_lections(
        self,
        course_name: str,
        lections_data: list[dict],
        join_code: str | None = None,
    ) -> CourseSessionReadSchema:
        """Создать курс с лекциями."""
        ...
    
    async def delete_course(self, course_id: uuid.UUID) -> None:
        """Удалить курс (CASCADE DELETE обрабатывается БД)."""
        ...

    async def append_lections_to_course(
        self,
        course_id: uuid.UUID,
        lections_data: list[dict],
    ) -> list[LectionSessionReadSchema]:
        """Добавить новые лекции в существующий курс."""
        ...

    async def get_by_id(self, course_id: uuid.UUID) -> CourseSessionReadSchema:
        """Получить курс по идентификатору."""
        ...

    async def get_by_join_code(self, join_code: str) -> CourseSessionReadSchema:
        """Получить курс по коду."""
        ...

    async def delete_lections_from_course(
        self,
        course_id: uuid.UUID,
        lection_ids: list[uuid.UUID],
    ) -> int:
        """Удалить выбранные лекции курса и пересчитать границы курса."""
        ...
    
    async def get_courses_for_admin(
        self, 
        page: int = 1, 
        page_size: int = 5
    ) -> PaginatedResponse:
        """Получить все курсы с пагинацией для администратора."""
        ...
    
    async def get_courses_for_teacher(
        self,
        teacher_id: uuid.UUID,
        page: int = 1,
        page_size: int = 5
    ) -> PaginatedResponse:
        """Получить курсы преподавателя с пагинацией."""
        ...


class CourseService(CourseServiceProtocol):
    """Сервис для работы с курсами."""
    
    def __init__(
        self,
        course_repository: CourseSessionRepositoryProtocol,
        lection_repository: LectionSessionRepositoryProtocol,
        teacher_course_repository: TeacherCourseRepositoryProtocol,
    ):
        self.course_repository = course_repository
        self.lection_repository = lection_repository
        self.teacher_course_repository = teacher_course_repository
    
    async def create_course_with_lections(
        self,
        course_name: str,
        lections_data: list[dict],
        join_code: str | None = None,
    ) -> CourseSessionReadSchema:
        """
        Создать курс с лекциями.
        
        Args:
            course_name: Название курса
            lections_data: Список данных лекций с полями:
                - topic: тема лекции
                - started_at: дата и время начала
                - ended_at: дата и время окончания
                - deadline: дата и время дедлайна (опционально)
            join_code: Код курса, если уже задан извне
        
        Returns:
            Созданный курс
        """
        # Определяем даты курса (первая и последняя лекция)
        all_dates = [lection['started_at'] for lection in lections_data] + \
                    [lection['ended_at'] for lection in lections_data]
        
        course_started_at = min(all_dates)
        course_ended_at = max(all_dates)
        
        # Создаём курс
        course_data = CourseSessionCreateSchema(
            name=course_name,
            join_code=join_code or await self._generate_unique_join_code(),
            started_at=course_started_at,
            ended_at=course_ended_at,
        )
        if join_code:
            existing_course = await self.course_repository.get_by_join_code_or_none(join_code)
            if existing_course is not None:
                raise ModelAlreadyExistsError(
                    CourseSession,
                    "join_code",
                    "duplicate key for field: join_code",
                )
        course = await self.course_repository.create(course_data)
        
        # Создаём лекции с использованием bulk_create
        lection_schemas = [
            LectionSessionCreateSchema(
                course_session_id=course.id,
                topic=lection_data['topic'],
                started_at=lection_data['started_at'],
                ended_at=lection_data['ended_at'],
                deadline=lection_data.get("deadline")
                or calculate_lection_deadline(
                    lection_data['ended_at'],
                    settings.default_deadline,
                ),
                one_question_from_list=lection_data.get("one_question_from_list", False),
                questions_to_ask_count=lection_data.get("questions_to_ask_count"),
            )
            for lection_data in lections_data
        ]
        await self.lection_repository.bulk_create(lection_schemas)
        
        return course
    
    async def delete_course(self, course_id: uuid.UUID) -> None:
        """
        Удалить курс.
        
        CASCADE DELETE автоматически удаляет связанные записи:
        - lection_sessions (через ondelete="CASCADE")
        - student_courses (через ondelete="CASCADE")
        - teacher_courses (через ondelete="CASCADE")
        
        Args:
            course_id: ID курса для удаления
        """
        await self.course_repository.delete(course_id)

    async def append_lections_to_course(
        self,
        course_id: uuid.UUID,
        lections_data: list[dict],
    ) -> list[LectionSessionReadSchema]:
        """Добавить новые лекции в курс и обновить границы курса при необходимости."""
        if not lections_data:
            return []

        course = await self.course_repository.get(course_id)
        all_dates = [lection["started_at"] for lection in lections_data] + [
            lection["ended_at"] for lection in lections_data
        ]
        new_started_at = min([course.started_at, *all_dates])
        new_ended_at = max([course.ended_at, *all_dates])
        if new_started_at != course.started_at or new_ended_at != course.ended_at:
            await self.course_repository.update(
                CourseSessionUpdateSchema(
                    id=course.id,
                    name=course.name,
                    join_code=course.join_code,
                    started_at=new_started_at,
                    ended_at=new_ended_at,
                )
            )

        lection_schemas = [
            LectionSessionCreateSchema(
                course_session_id=course_id,
                topic=lection_data["topic"],
                started_at=lection_data["started_at"],
                ended_at=lection_data["ended_at"],
                deadline=lection_data.get("deadline")
                or calculate_lection_deadline(
                    lection_data["ended_at"],
                    settings.default_deadline,
                ),
                one_question_from_list=lection_data.get("one_question_from_list", False),
                questions_to_ask_count=lection_data.get("questions_to_ask_count"),
            )
            for lection_data in lections_data
        ]
        return await self.lection_repository.bulk_create(lection_schemas)

    async def get_by_id(self, course_id: uuid.UUID) -> CourseSessionReadSchema:
        """Получить курс по идентификатору."""
        return await self.course_repository.get(course_id)

    async def get_by_join_code(self, join_code: str) -> CourseSessionReadSchema:
        """Получить курс по коду."""
        return await self.course_repository.get_by_join_code(join_code)

    async def delete_lections_from_course(
        self,
        course_id: uuid.UUID,
        lection_ids: list[uuid.UUID],
    ) -> int:
        """Удалить выбранные лекции курса и пересчитать границы курса."""
        if not lection_ids:
            return 0

        async with self.lection_repository.session as s, s.begin():
            delete_stmt = sa.delete(LectionSession).where(
                LectionSession.course_session_id == course_id,
                LectionSession.id.in_(lection_ids),
            )
            delete_result = await s.execute(delete_stmt)
            deleted_count = int(delete_result.rowcount or 0)

        course = await self.course_repository.get(course_id)
        async with self.lection_repository.session as s:
            bounds_stmt = select(
                func.min(LectionSession.started_at),
                func.max(LectionSession.ended_at),
            ).where(
                LectionSession.course_session_id == course_id,
            )
            min_started_at, max_ended_at = (await s.execute(bounds_stmt)).one()

        if min_started_at is not None and max_ended_at is not None:
            await self.course_repository.update(
                CourseSessionUpdateSchema(
                    id=course.id,
                    name=course.name,
                    join_code=course.join_code,
                    started_at=min_started_at,
                    ended_at=max_ended_at,
                )
            )

        return deleted_count
    
    async def get_courses_for_admin(
        self, 
        page: int = 1, 
        page_size: int = 5
    ) -> PaginatedResponse:
        """
        Получить все курсы с пагинацией для администратора.
        
        Args:
            page: Номер страницы (начиная с 1)
            page_size: Количество элементов на странице
        
        Returns:
            PaginatedResponse с курсами
        """
        # Получаем все курсы
        all_courses = await self.course_repository.get_all()
        
        # Вычисляем пагинацию
        total = len(all_courses)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        # Вычисляем индексы для среза
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # Получаем элементы для текущей страницы
        items = all_courses[start_idx:end_idx]
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def _generate_unique_join_code(self) -> str:
        """Сгенерировать уникальный четырёхсимвольный код курса."""
        for _ in range(100):
            code = "".join(secrets.choice(COURSE_JOIN_CODE_CHARS) for _ in range(4))
            existing_course = await self.course_repository.get_by_join_code_or_none(code)
            if existing_course is None:
                return code
        raise RuntimeError("Unable to generate unique course join code.")
    
    async def get_courses_for_teacher(
        self,
        teacher_id: uuid.UUID,
        page: int = 1,
        page_size: int = 5
    ) -> PaginatedResponse:
        """
        Получить курсы преподавателя с пагинацией.
        
        Фильтрует курсы по привязке через TeacherCourse.
        
        Args:
            teacher_id: ID преподавателя
            page: Номер страницы (начиная с 1)
            page_size: Количество элементов на странице
        
        Returns:
            PaginatedResponse с курсами преподавателя
        """
        # Получаем все привязки преподавателя к курсам
        teacher_courses = await self.teacher_course_repository.get_all()
        
        # Фильтруем по teacher_id
        teacher_course_ids = [
            tc.course_session_id 
            for tc in teacher_courses 
            if tc.teacher_id == teacher_id
        ]
        
        # Получаем курсы по ID
        if not teacher_course_ids:
            return PaginatedResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=1,
            )
        
        courses = await self.course_repository.get_by_ids(teacher_course_ids)
        
        # Вычисляем пагинацию
        total = len(courses)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        # Вычисляем индексы для среза
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # Получаем элементы для текущей страницы
        items = courses[start_idx:end_idx]
        
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
