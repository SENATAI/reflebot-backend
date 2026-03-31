"""
Use cases для работы с курсами.
"""

import uuid
from typing import Protocol, BinaryIO

from reflebot.core.use_cases import UseCaseProtocol
from ..services.course import CourseServiceProtocol
from ..services.teacher import TeacherServiceProtocol
from ..services.student import StudentServiceProtocol
from ..services.lection import LectionServiceProtocol
from ..services.question import QuestionServiceProtocol
from ..schemas import (
    CourseSessionReadSchema,
    AdminReadSchema,
    TeacherReadSchema,
)
from ..parsers.base import FileParserProtocol


class CreateCourseFromExcelUseCaseProtocol(UseCaseProtocol[CourseSessionReadSchema]):
    """Протокол use case создания курса из Excel."""
    
    async def __call__(
        self,
        course_name: str,
        excel_file: BinaryIO,
        current_admin: AdminReadSchema,
    ) -> CourseSessionReadSchema:
        ...


class CreateCourseFromExcelUseCase(CreateCourseFromExcelUseCaseProtocol):
    """Use case для создания курса из Excel файла."""
    
    def __init__(
        self,
        course_service: CourseServiceProtocol,
        lection_service: LectionServiceProtocol,
        question_service: QuestionServiceProtocol,
        parser: FileParserProtocol,
    ):
        self.course_service = course_service
        self.lection_service = lection_service
        self.question_service = question_service
        self.parser = parser
    
    async def __call__(
        self,
        course_name: str,
        excel_file: BinaryIO,
        current_admin: AdminReadSchema,
    ) -> CourseSessionReadSchema:
        """
        Создать курс из Excel файла.
        
        Доступ к use case должен контролироваться вызывающим workflow.
        
        Args:
            excel_file: Excel файл с данными курса
            current_admin: Текущий администратор
        
        Returns:
            Созданный курс
        """
        # Парсим Excel файл через инжектированный парсер
        parsed_lections_data = self.parser.parse(excel_file)
        lections_data = [
            {
                "topic": lection["topic"],
                "started_at": lection["started_at"],
                "ended_at": lection["ended_at"],
            }
            for lection in parsed_lections_data
        ]
        
        # Создаём курс с лекциями
        course = await self.course_service.create_course_with_lections(
            course_name=course_name,
            lections_data=lections_data,
        )

        lections_response = await self.lection_service.get_lections_by_course(
            course_id=course.id,
            page=1,
            page_size=max(len(parsed_lections_data), 1),
        )
        unmatched_lections = list(lections_response.items)
        for parsed_lection in parsed_lections_data:
            matched_lection = None
            for created_lection in unmatched_lections:
                if (
                    created_lection.topic == parsed_lection["topic"]
                    and created_lection.started_at == parsed_lection["started_at"]
                    and created_lection.ended_at == parsed_lection["ended_at"]
                ):
                    matched_lection = created_lection
                    break

            if matched_lection is None:
                continue

            unmatched_lections.remove(matched_lection)
            for question_text in parsed_lection.get("questions", []):
                await self.question_service.create_question(matched_lection.id, question_text)
        
        return course


class AttachTeachersToCourseUseCaseProtocol(UseCaseProtocol[TeacherReadSchema]):
    """Протокол use case привязки преподавателей к курсу."""
    
    async def __call__(
        self,
        course_id: uuid.UUID,
        full_name: str,
        telegram_username: str,
        current_admin: AdminReadSchema,
    ) -> TeacherReadSchema:
        ...


class AttachTeachersToCourseUseCase(AttachTeachersToCourseUseCaseProtocol):
    """Use case для привязки преподавателей к курсу."""
    
    def __init__(
        self,
        teacher_service: TeacherServiceProtocol,
        lection_service: LectionServiceProtocol,
    ):
        self.teacher_service = teacher_service
        self.lection_service = lection_service
    
    async def __call__(
        self,
        course_id: uuid.UUID,
        full_name: str,
        telegram_username: str,
        current_admin: AdminReadSchema,
    ) -> TeacherReadSchema:
        """
        Привязать преподавателя к курсу.
        
        Создаёт или получает преподавателя, привязывает его к курсу
        и ко всем лекциям курса с использованием bulk_create.
        
        Доступ к use case должен контролироваться вызывающим workflow.
        
        Args:
            course_id: ID курса
            full_name: ФИО преподавателя
            telegram_username: Telegram username (без @)
            current_admin: Текущий администратор
        
        Returns:
            Преподаватель
        """
        # Создаём или получаем преподавателя
        teacher = await self.teacher_service.create_or_get(
            full_name=full_name,
            telegram_username=telegram_username,
        )
        
        # Привязываем к курсу
        await self.teacher_service.attach_to_course(
            teacher_id=teacher.id,
            course_id=course_id,
        )
        
        # Получаем все лекции курса (используем большой page_size для получения всех)
        lections_response = await self.lection_service.get_lections_by_course(
            course_id=course_id,
            page=1,
            page_size=1000,  # Достаточно большое значение для получения всех лекций
        )
        lection_ids = [lection.id for lection in lections_response.items]
        
        # Привязываем ко всем лекциям курса (bulk_create)
        await self.teacher_service.attach_to_lections(
            teacher_id=teacher.id,
            lection_ids=lection_ids,
        )
        
        return teacher


class AttachStudentsToCourseUseCaseProtocol(UseCaseProtocol[int]):
    """Протокол use case привязки студентов к курсу."""
    
    async def __call__(
        self,
        course_id: uuid.UUID,
        csv_file: BinaryIO,
        current_admin: AdminReadSchema,
    ) -> int:
        ...


class AttachStudentsToCourseUseCase(AttachStudentsToCourseUseCaseProtocol):
    """Use case для привязки студентов к курсу из CSV файла."""
    
    def __init__(
        self,
        student_service: StudentServiceProtocol,
        lection_service: LectionServiceProtocol,
        parser: FileParserProtocol,
    ):
        self.student_service = student_service
        self.lection_service = lection_service
        self.parser = parser
    
    async def __call__(
        self,
        course_id: uuid.UUID,
        csv_file: BinaryIO,
        current_admin: AdminReadSchema,
    ) -> int:
        """
        Привязать студентов к курсу из CSV файла.
        
        Парсит CSV файл, создаёт или получает студентов, привязывает их к курсу
        и ко всем лекциям курса с использованием bulk_create.
        
        Доступ к use case должен контролироваться вызывающим workflow.
        
        Args:
            course_id: ID курса
            csv_file: CSV файл со списком студентов
            current_admin: Текущий администратор
        
        Returns:
            Количество добавленных студентов
        """
        # Парсим CSV файл через инжектированный парсер
        students_data = self.parser.parse(csv_file)
        
        # Создаём или получаем студентов (bulk_create для новых)
        students = await self.student_service.bulk_create_or_get(students_data)
        
        # Получаем ID студентов
        student_ids = [student.id for student in students]
        
        # Привязываем к курсу (bulk_create)
        await self.student_service.attach_to_course(
            student_ids=student_ids,
            course_id=course_id,
        )
        
        # Получаем все лекции курса (используем большой page_size для получения всех)
        lections_response = await self.lection_service.get_lections_by_course(
            course_id=course_id,
            page=1,
            page_size=1000,  # Достаточно большое значение для получения всех лекций
        )
        lection_ids = [lection.id for lection in lections_response.items]
        
        # Привязываем ко всем лекциям курса (bulk_create)
        await self.student_service.attach_to_lections(
            student_ids=student_ids,
            lection_ids=lection_ids,
        )
        
        return len(students)
