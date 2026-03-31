"""
Сервис для работы с аналитикой.
"""

import uuid
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from ..models import (
    LectionSession,
    StudentLection,
    LectionReflection,
    ReflectionVideo,
    LectionQA,
    QAVideo,
    Question,
    Student,
)
from ..schemas import (
    LectionStatisticsSchema,
    StudentStatisticsSchema,
    ReflectionDetailsSchema,
    LectionSessionReadSchema,
    StudentReadSchema,
    QuestionReadSchema,
    LectionReflectionReadSchema,
    ReflectionVideoReadSchema,
    LectionQAReadSchema,
    QAVideoReadSchema,
    QADetailsSchema,
)
from ..repositories.lection import LectionSessionRepositoryProtocol
from ..repositories.student import StudentRepositoryProtocol


class AnalyticsServiceProtocol(Protocol):
    """Протокол сервиса аналитики."""
    
    async def get_lection_statistics(self, lection_id: uuid.UUID) -> LectionStatisticsSchema:
        """Получить статистику по лекции."""
        ...
    
    async def get_student_statistics(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> StudentStatisticsSchema:
        """Получить статистику студента по курсу."""
        ...
    
    async def get_reflection_details(
        self,
        student_id: uuid.UUID,
        lection_id: uuid.UUID,
    ) -> ReflectionDetailsSchema:
        """Получить детальную информацию о рефлексии студента."""
        ...


class AnalyticsService(AnalyticsServiceProtocol):
    """Сервис для работы с аналитикой."""
    
    def __init__(
        self,
        lection_repository: LectionSessionRepositoryProtocol,
        student_repository: StudentRepositoryProtocol,
    ):
        self.lection_repository = lection_repository
        self.student_repository = student_repository
    
    async def get_lection_statistics(self, lection_id: uuid.UUID) -> LectionStatisticsSchema:
        """
        Получить статистику по лекции.
        
        Подсчитывает:
        - Общее количество студентов (через StudentLection)
        - Количество рефлексий (через LectionReflection)
        - Количество ответов на вопросы (через LectionQA)
        - Список студентов, отправивших рефлексии
        
        Args:
            lection_id: ID лекции
        
        Returns:
            LectionStatisticsSchema со статистикой
        
        Validates: Requirements 21.5, 21.6, 21.7
        """
        async with self.lection_repository.session as s:
            # Получаем лекцию
            lection = await self.lection_repository.get(lection_id)
            
            # Получаем вопросы к лекции
            questions_stmt = select(Question).where(Question.lection_session_id == lection_id)
            questions_result = await s.execute(questions_stmt)
            questions = questions_result.scalars().all()
            questions_schemas = [
                QuestionReadSchema.model_validate(q, from_attributes=True)
                for q in questions
            ]
            
            # Подсчитываем общее количество студентов через StudentLection
            total_students_stmt = select(func.count(StudentLection.id)).where(
                StudentLection.lection_session_id == lection_id
            )
            total_students = (await s.execute(total_students_stmt)).scalar_one()
            
            # Подсчитываем количество рефлексий
            reflections_count_stmt = select(func.count(LectionReflection.id)).where(
                LectionReflection.lection_session_id == lection_id
            )
            reflections_count = (await s.execute(reflections_count_stmt)).scalar_one()
            
            # Подсчитываем количество ответов на вопросы
            # Нужно посчитать LectionQA для рефлексий этой лекции
            qa_count_stmt = (
                select(func.count(LectionQA.id))
                .join(LectionReflection, LectionReflection.id == LectionQA.reflection_id)
                .where(LectionReflection.lection_session_id == lection_id)
            )
            qa_count = (await s.execute(qa_count_stmt)).scalar_one()
            
            # Получаем студентов, отправивших рефлексии
            students_stmt = (
                select(Student)
                .join(LectionReflection, LectionReflection.student_id == Student.id)
                .where(LectionReflection.lection_session_id == lection_id)
                .distinct()
            )
            students_result = await s.execute(students_stmt)
            students = students_result.scalars().all()
            students_schemas = [
                StudentReadSchema.model_validate(student, from_attributes=True)
                for student in students
            ]
            
            return LectionStatisticsSchema(
                lection=lection,
                questions=questions_schemas,
                total_students=total_students,
                reflections_count=reflections_count,
                qa_count=qa_count,
                students_with_reflections=students_schemas,
            )
    
    async def get_student_statistics(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> StudentStatisticsSchema:
        """
        Получить статистику студента по курсу.
        
        Подсчитывает:
        - Общее количество лекций в курсе (через StudentLection)
        - Количество отправленных рефлексий
        - Количество ответов на вопросы
        - Список лекций, на которые студент отправил рефлексии
        
        Args:
            student_id: ID студента
            course_id: ID курса
        
        Returns:
            StudentStatisticsSchema со статистикой
        
        Validates: Requirements 23.3, 23.4, 23.5
        """
        async with self.student_repository.session as s:
            # Получаем студента
            student = await self.student_repository.get(student_id)
            
            # Подсчитываем общее количество лекций в курсе для этого студента
            total_lections_stmt = (
                select(func.count(StudentLection.id))
                .join(LectionSession, LectionSession.id == StudentLection.lection_session_id)
                .where(
                    StudentLection.student_id == student_id,
                    LectionSession.course_session_id == course_id,
                )
            )
            total_lections = (await s.execute(total_lections_stmt)).scalar_one()
            
            # Подсчитываем количество рефлексий для данного курса
            reflections_count_stmt = (
                select(func.count(LectionReflection.id))
                .join(LectionSession, LectionSession.id == LectionReflection.lection_session_id)
                .where(
                    LectionReflection.student_id == student_id,
                    LectionSession.course_session_id == course_id,
                )
            )
            reflections_count = (await s.execute(reflections_count_stmt)).scalar_one()
            
            # Подсчитываем количество ответов на вопросы для данного курса
            qa_count_stmt = (
                select(func.count(LectionQA.id))
                .join(LectionReflection, LectionReflection.id == LectionQA.reflection_id)
                .join(LectionSession, LectionSession.id == LectionReflection.lection_session_id)
                .where(
                    LectionReflection.student_id == student_id,
                    LectionSession.course_session_id == course_id,
                )
            )
            qa_count = (await s.execute(qa_count_stmt)).scalar_one()
            
            # Получаем лекции, на которые студент отправил рефлексии
            lections_stmt = (
                select(LectionSession)
                .join(LectionReflection, LectionReflection.lection_session_id == LectionSession.id)
                .where(
                    LectionReflection.student_id == student_id,
                    LectionSession.course_session_id == course_id,
                )
                .distinct()
                .order_by(LectionSession.started_at)
            )
            lections_result = await s.execute(lections_stmt)
            lections = lections_result.scalars().all()
            lections_schemas = [
                LectionSessionReadSchema.model_validate(lection, from_attributes=True)
                for lection in lections
            ]
            
            return StudentStatisticsSchema(
                student=student,
                total_lections=total_lections,
                reflections_count=reflections_count,
                qa_count=qa_count,
                lections_with_reflections=lections_schemas,
            )
    
    async def get_reflection_details(
        self,
        student_id: uuid.UUID,
        lection_id: uuid.UUID,
    ) -> ReflectionDetailsSchema:
        """
        Получить детальную информацию о рефлексии студента.
        
        Возвращает:
        - Информацию о рефлексии
        - Список видео рефлексий с Telegram file_id
        - Список вопросов и ответов с Telegram file_id
        
        Args:
            student_id: ID студента
            lection_id: ID лекции
        
        Returns:
            ReflectionDetailsSchema с детальной информацией
        
        Validates: Requirements 22.2, 22.3, 22.4, 22.5
        """
        async with self.lection_repository.session as s:
            # Получаем рефлексию с eager loading связанных данных
            reflection_stmt = (
                select(LectionReflection)
                .options(
                    selectinload(LectionReflection.reflection_videos),
                    selectinload(LectionReflection.lection_qas).selectinload(LectionQA.qa_videos),
                    selectinload(LectionReflection.lection_qas).selectinload(LectionQA.question),
                )
                .where(
                    LectionReflection.student_id == student_id,
                    LectionReflection.lection_session_id == lection_id,
                )
            )
            reflection_result = await s.execute(reflection_stmt)
            reflection = reflection_result.scalar_one_or_none()
            
            if not reflection:
                # Если рефлексия не найдена, возвращаем пустую структуру
                # или можно выбросить исключение
                from reflebot.core.utils.exceptions import ModelNotFoundException
                raise ModelNotFoundException(LectionReflection, f"student_id={student_id}, lection_id={lection_id}")
            
            # Преобразуем рефлексию в схему
            reflection_schema = LectionReflectionReadSchema.model_validate(
                reflection, from_attributes=True
            )
            
            # Обрабатываем видео рефлексий
            reflection_videos = []
            for video in sorted(reflection.reflection_videos, key=lambda item: item.order_index):
                video_schema = ReflectionVideoReadSchema.model_validate(video, from_attributes=True)
                reflection_videos.append(video_schema)
            
            # Обрабатываем ответы на вопросы
            qa_details_list = []
            sorted_qas = sorted(
                reflection.lection_qas,
                key=lambda item: (
                    item.question.created_at,
                    item.question.id,
                ),
            )
            for lection_qa in sorted_qas:
                # Преобразуем вопрос
                question_schema = QuestionReadSchema.model_validate(
                    lection_qa.question, from_attributes=True
                )
                
                # Преобразуем ответ
                lection_qa_schema = LectionQAReadSchema.model_validate(
                    lection_qa, from_attributes=True
                )
                
                # Обрабатываем видео ответов
                qa_videos = []
                for qa_video in sorted(
                    lection_qa.qa_videos,
                    key=lambda item: item.order_index,
                ):
                    qa_video_schema = QAVideoReadSchema.model_validate(qa_video, from_attributes=True)
                    qa_videos.append(qa_video_schema)
                
                qa_details_list.append(
                    QADetailsSchema(
                        question=question_schema,
                        lection_qa=lection_qa_schema,
                        qa_videos=qa_videos,
                    )
                )
            
            return ReflectionDetailsSchema(
                reflection=reflection_schema,
                reflection_videos=reflection_videos,
                qa_list=qa_details_list,
            )
