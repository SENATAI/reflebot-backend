"""
Сервис для работы с лекциями.
"""

import uuid
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select, func

from reflebot.settings import settings
from ..datetime_utils import calculate_lection_deadline
from ..repositories.course import CourseSessionRepositoryProtocol
from ..repositories.lection import LectionSessionRepositoryProtocol
from ..models import LectionSession, TeacherLection, Question
from ..schemas import (
    CourseSessionUpdateSchema,
    LectionDetailsSchema,
    LectionSessionReadSchema,
    LectionSessionUpdateSchema,
    PaginatedResponse,
    QuestionReadSchema,
)


class LectionServiceProtocol(Protocol):
    """Протокол сервиса лекций."""
    
    async def get_lections_by_course(
        self,
        course_id: uuid.UUID,
        page: int = 1,
        page_size: int = 5,
    ) -> PaginatedResponse:
        """Получить список лекций курса с пагинацией."""
        ...
    
    async def get_lection_details(self, lection_id: uuid.UUID) -> LectionDetailsSchema:
        """Получить детальную информацию о лекции."""
        ...

    async def get_by_id(self, lection_id: uuid.UUID) -> LectionSessionReadSchema:
        """Получить лекцию по идентификатору."""
        ...

    async def get_lection_ids_by_course(self, course_id: uuid.UUID) -> list[uuid.UUID]:
        """Получить идентификаторы всех лекций курса."""
        ...
    
    async def update_topic(self, lection_id: uuid.UUID, topic: str) -> LectionSessionReadSchema:
        """Обновить тему лекции."""
        ...
    
    async def update_datetime(
        self,
        lection_id: uuid.UUID,
        started_at: datetime,
        ended_at: datetime,
    ) -> LectionSessionReadSchema:
        """Обновить дату и время лекции."""
        ...
    
    async def get_nearest_lection_for_teacher(
        self,
        teacher_id: uuid.UUID,
    ) -> LectionSessionReadSchema | None:
        """Получить ближайшую лекцию для преподавателя."""
        ...

    async def get_nearest_lection(self) -> LectionSessionReadSchema | None:
        """Получить ближайшую лекцию среди всех лекций."""
        ...

    async def update_presentation_file(
        self,
        lection_id: uuid.UUID,
        file_id: str | None,
    ) -> LectionSessionReadSchema:
        """Обновить файл презентации лекции."""
        ...

    async def update_recording_file(
        self,
        lection_id: uuid.UUID,
        file_id: str | None,
    ) -> LectionSessionReadSchema:
        """Обновить файл записи лекции."""
        ...


class LectionService(LectionServiceProtocol):
    """Сервис для работы с лекциями."""
    
    def __init__(
        self,
        lection_repository: LectionSessionRepositoryProtocol,
        course_repository: CourseSessionRepositoryProtocol | None = None,
    ):
        self.lection_repository = lection_repository
        self.course_repository = course_repository
    
    async def get_lections_by_course(
        self,
        course_id: uuid.UUID,
        page: int = 1,
        page_size: int = 5,
    ) -> PaginatedResponse:
        """
        Получить список лекций курса с пагинацией.
        
        Args:
            course_id: ID курса
            page: Номер страницы (начиная с 1)
            page_size: Количество элементов на странице
        
        Returns:
            PaginatedResponse с лекциями
        """
        async with self.lection_repository.session as s:
            # Подсчитываем общее количество лекций
            count_stmt = select(func.count(LectionSession.id)).where(
                LectionSession.course_session_id == course_id
            )
            total = (await s.execute(count_stmt)).scalar_one()
            
            # Получаем лекции для текущей страницы
            offset = (page - 1) * page_size
            stmt = (
                select(LectionSession)
                .where(LectionSession.course_session_id == course_id)
                .order_by(LectionSession.started_at)
                .limit(page_size)
                .offset(offset)
            )
            result = await s.execute(stmt)
            lections = result.scalars().all()
            
            # Преобразуем в схемы
            lection_schemas = [
                LectionSessionReadSchema.model_validate(lection, from_attributes=True)
                for lection in lections
            ]
            
            return PaginatedResponse(
                items=lection_schemas,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size if total > 0 else 1,
            )
    
    async def get_lection_details(self, lection_id: uuid.UUID) -> LectionDetailsSchema:
        """
        Получить детальную информацию о лекции.
        
        Args:
            lection_id: ID лекции
        
        Returns:
            LectionDetailsSchema с детальной информацией
        """
        # Получаем лекцию
        lection = await self.lection_repository.get(lection_id)
        
        # Получаем вопросы к лекции
        async with self.lection_repository.session as s:
            stmt = select(Question).where(Question.lection_session_id == lection_id)
            result = await s.execute(stmt)
            questions = result.scalars().all()
            
            question_schemas = [
                QuestionReadSchema(
                    id=question.id,
                    lection_session_id=question.lection_session_id,
                    question_text=question.question_text,
                    created_at=question.created_at,
                    updated_at=(
                        question.updated_at
                        if isinstance(getattr(question, "updated_at", None), datetime)
                        else question.created_at
                    ),
                )
                for question in questions
            ]

        return LectionDetailsSchema(
            lection=lection,
            questions=question_schemas,
            has_presentation=lection.presentation_file_id is not None,
            has_recording=lection.recording_file_id is not None,
            presentation_filename=lection.presentation_file_id,
            recording_filename=lection.recording_file_id,
        )

    async def get_by_id(self, lection_id: uuid.UUID) -> LectionSessionReadSchema:
        """Получить лекцию по идентификатору."""
        return await self.lection_repository.get(lection_id)

    async def get_lection_ids_by_course(self, course_id: uuid.UUID) -> list[uuid.UUID]:
        """Получить идентификаторы всех лекций курса без пагинации."""
        async with self.lection_repository.session as s:
            stmt = (
                select(LectionSession.id)
                .where(LectionSession.course_session_id == course_id)
                .order_by(LectionSession.started_at)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())
    
    async def update_topic(self, lection_id: uuid.UUID, topic: str) -> LectionSessionReadSchema:
        """
        Обновить тему лекции.
        
        Args:
            lection_id: ID лекции
            topic: Новая тема лекции
        
        Returns:
            Обновленная лекция
        """
        # Получаем существующую лекцию
        existing_lection = await self.lection_repository.get(lection_id)
        
        # Обновляем тему
        update_data = LectionSessionUpdateSchema(
            id=lection_id,
            course_session_id=existing_lection.course_session_id,
            topic=topic,
            presentation_file_id=existing_lection.presentation_file_id,
            recording_file_id=existing_lection.recording_file_id,
            started_at=existing_lection.started_at,
            ended_at=existing_lection.ended_at,
            deadline=existing_lection.deadline,
        )
        return await self.lection_repository.update(update_data)
    
    async def update_datetime(
        self,
        lection_id: uuid.UUID,
        started_at: datetime,
        ended_at: datetime,
    ) -> LectionSessionReadSchema:
        """
        Обновить дату и время лекции.
        
        Args:
            lection_id: ID лекции
            started_at: Новая дата и время начала
            ended_at: Новая дата и время окончания
        
        Returns:
            Обновленная лекция
        """
        # Получаем существующую лекцию
        existing_lection = await self.lection_repository.get(lection_id)
        
        # Обновляем даты
        update_data = LectionSessionUpdateSchema(
            id=lection_id,
            course_session_id=existing_lection.course_session_id,
            topic=existing_lection.topic,
            presentation_file_id=existing_lection.presentation_file_id,
            recording_file_id=existing_lection.recording_file_id,
            started_at=started_at,
            ended_at=ended_at,
            deadline=calculate_lection_deadline(ended_at, settings.default_deadline),
        )
        updated_lection = await self.lection_repository.update(update_data)

        if self.course_repository is not None:
            course = await self.course_repository.get(existing_lection.course_session_id)
            new_course_started_at = min(course.started_at, started_at)
            new_course_ended_at = max(course.ended_at, ended_at)
            if (
                new_course_started_at != course.started_at
                or new_course_ended_at != course.ended_at
            ):
                await self.course_repository.update(
                    CourseSessionUpdateSchema(
                        id=course.id,
                        name=course.name,
                        started_at=new_course_started_at,
                        ended_at=new_course_ended_at,
                    )
                )

        return updated_lection
    
    async def get_nearest_lection_for_teacher(
        self,
        teacher_id: uuid.UUID,
    ) -> LectionSessionReadSchema | None:
        """
        Получить ближайшую лекцию для преподавателя.
        
        Возвращает лекцию с минимальным started_at >= текущее время,
        где преподаватель привязан через TeacherLection.
        
        Args:
            teacher_id: ID преподавателя
        
        Returns:
            Ближайшая лекция или None если не найдена
        """
        async with self.lection_repository.session as s:
            now = datetime.now(timezone.utc)
            
            stmt = (
                select(LectionSession)
                .join(TeacherLection, TeacherLection.lection_session_id == LectionSession.id)
                .where(
                    TeacherLection.teacher_id == teacher_id,
                    LectionSession.started_at >= now,
                )
                .order_by(LectionSession.started_at)
                .limit(1)
            )
            
            result = await s.execute(stmt)
            lection = result.scalar_one_or_none()
            
            if lection is None:
                return None
            
            return LectionSessionReadSchema.model_validate(lection, from_attributes=True)

    async def get_nearest_lection(self) -> LectionSessionReadSchema | None:
        """Получить ближайшую лекцию среди всех будущих лекций."""
        async with self.lection_repository.session as s:
            now = datetime.now(timezone.utc)

            stmt = (
                select(LectionSession)
                .where(LectionSession.started_at >= now)
                .order_by(LectionSession.started_at)
                .limit(1)
            )

            result = await s.execute(stmt)
            lection = result.scalar_one_or_none()

            if lection is None:
                return None

            return LectionSessionReadSchema.model_validate(lection, from_attributes=True)

    async def update_presentation_file(
        self,
        lection_id: uuid.UUID,
        file_id: str | None,
    ) -> LectionSessionReadSchema:
        """Обновить файл презентации лекции."""
        existing_lection = await self.lection_repository.get(lection_id)
        update_data = LectionSessionUpdateSchema(
            id=lection_id,
            course_session_id=existing_lection.course_session_id,
            topic=existing_lection.topic,
            presentation_file_id=file_id,
            recording_file_id=existing_lection.recording_file_id,
            started_at=existing_lection.started_at,
            ended_at=existing_lection.ended_at,
            deadline=existing_lection.deadline,
        )
        return await self.lection_repository.update(update_data)

    async def update_recording_file(
        self,
        lection_id: uuid.UUID,
        file_id: str | None,
    ) -> LectionSessionReadSchema:
        """Обновить файл записи лекции."""
        existing_lection = await self.lection_repository.get(lection_id)
        update_data = LectionSessionUpdateSchema(
            id=lection_id,
            course_session_id=existing_lection.course_session_id,
            topic=existing_lection.topic,
            presentation_file_id=existing_lection.presentation_file_id,
            recording_file_id=file_id,
            started_at=existing_lection.started_at,
            ended_at=existing_lection.ended_at,
            deadline=existing_lection.deadline,
        )
        return await self.lection_repository.update(update_data)
