"""
Сервис для работы со студентами.
"""

import uuid
from typing import Protocol

from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..repositories.admin import AdminRepositoryProtocol
from ..repositories.student import StudentRepositoryProtocol
from ..repositories.student_course import StudentCourseRepositoryProtocol
from ..repositories.student_lection import StudentLectionRepositoryProtocol
from ..repositories.teacher import TeacherRepositoryProtocol
from ..schemas import (
    StudentReadSchema,
    StudentCreateSchema,
    StudentCourseCreateSchema,
    StudentLectionCreateSchema,
)


class StudentServiceProtocol(Protocol):
    """Протокол сервиса студентов."""
    
    async def bulk_create_or_get(self, students_data: list[dict]) -> list[StudentReadSchema]:
        """Массово создать или получить студентов."""
        ...

    async def get_by_telegram_id(self, telegram_id: int) -> StudentReadSchema | None:
        """Получить студента по telegram_id."""
        ...

    async def get_by_telegram_username(self, telegram_username: str) -> StudentReadSchema | None:
        """Получить студента по telegram_username."""
        ...

    async def update_telegram_id(
        self,
        telegram_username: str,
        telegram_id: int,
    ) -> StudentReadSchema:
        """Обновить telegram_id студента."""
        ...

    async def create_student(
        self,
        full_name: str,
        telegram_username: str,
        telegram_id: int,
    ) -> StudentReadSchema:
        """Создать нового студента."""
        ...

    async def get_by_id(self, student_id: uuid.UUID) -> StudentReadSchema:
        """Получить студента по идентификатору."""
        ...
    
    async def attach_to_course(
        self,
        student_ids: list[uuid.UUID],
        course_id: uuid.UUID,
    ) -> None:
        """Привязать студентов к курсу."""
        ...

    async def is_attached_to_course(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить, записан ли студент на курс."""
        ...
    
    async def attach_to_lections(
        self,
        student_ids: list[uuid.UUID],
        lection_ids: list[uuid.UUID],
    ) -> None:
        """Привязать студентов к лекциям с использованием bulk_create."""
        ...
    
    async def get_students_by_course(
        self,
        course_id: uuid.UUID,
        page: int = 1,
        page_size: int = 5,
    ) -> dict:
        """Получить студентов курса с пагинацией."""
        ...


class StudentService(StudentServiceProtocol):
    """Сервис для работы со студентами."""
    
    def __init__(
        self,
        student_repository: StudentRepositoryProtocol,
        student_course_repository: StudentCourseRepositoryProtocol,
        student_lection_repository: StudentLectionRepositoryProtocol,
        admin_repository: AdminRepositoryProtocol | None = None,
        teacher_repository: TeacherRepositoryProtocol | None = None,
    ):
        self.student_repository = student_repository
        self.student_course_repository = student_course_repository
        self.student_lection_repository = student_lection_repository
        self.admin_repository = admin_repository
        self.teacher_repository = teacher_repository

    async def _get_admin_by_username(self, telegram_username: str):
        """Безопасно получить администратора по username."""
        if self.admin_repository is None:
            return None

        try:
            return await self.admin_repository.get_by_telegram_username(telegram_username)
        except ModelFieldNotFoundException:
            return None

    async def _get_related_telegram_id(self, telegram_username: str) -> int | None:
        """Получить telegram_id из соседних таблиц по username."""
        admin = await self._get_admin_by_username(telegram_username)
        if admin and admin.telegram_id is not None:
            return admin.telegram_id

        if self.teacher_repository is not None:
            teacher = await self.teacher_repository.get_by_telegram_username(telegram_username)
            if teacher and teacher.telegram_id is not None:
                return teacher.telegram_id

        return None
    
    async def bulk_create_or_get(self, students_data: list[dict]) -> list[StudentReadSchema]:
        """
        Массово создать или получить студентов.
        
        Для каждого студента проверяет существование по telegram_username.
        Если студент существует, возвращает его, иначе создаёт нового.
        Использует bulk_create для оптимизации создания новых студентов.
        
        Args:
            students_data: Список словарей с данными студентов
                          [{"full_name": "...", "telegram_username": "..."}, ...]
        
        Returns:
            Список студентов (существующих и созданных)
        """
        result_students = []
        students_to_create = []
        
        # Проверяем каждого студента на существование
        for student_data in students_data:
            telegram_username = student_data["telegram_username"]
            existing_student = await self.student_repository.get_by_telegram_username(
                telegram_username
            )
            
            if existing_student:
                result_students.append(existing_student)
            else:
                students_to_create.append(student_data)
        
        # Массово создаём новых студентов
        if students_to_create:
            student_schemas = [
                StudentCreateSchema(
                    full_name=data["full_name"],
                    telegram_username=data["telegram_username"],
                    telegram_id=await self._get_related_telegram_id(data["telegram_username"]),
                    is_active=True,
                )
                for data in students_to_create
            ]
            
            created_students = await self.student_repository.bulk_create(student_schemas)
            result_students.extend(created_students)
        
        return result_students

    async def get_by_telegram_id(self, telegram_id: int) -> StudentReadSchema | None:
        """Получить студента по telegram_id."""
        return await self.student_repository.get_by_telegram_id(telegram_id)

    async def get_by_telegram_username(self, telegram_username: str) -> StudentReadSchema | None:
        """Получить студента по telegram_username."""
        return await self.student_repository.get_by_telegram_username(telegram_username)

    async def update_telegram_id(
        self,
        telegram_username: str,
        telegram_id: int,
    ) -> StudentReadSchema:
        """Обновить telegram_id существующего студента."""
        return await self.student_repository.update_telegram_id(telegram_username, telegram_id)

    async def create_student(
        self,
        full_name: str,
        telegram_username: str,
        telegram_id: int,
    ) -> StudentReadSchema:
        """Создать нового студента с telegram_id текущего пользователя."""
        return await self.student_repository.create(
            StudentCreateSchema(
                full_name=full_name,
                telegram_username=telegram_username,
                telegram_id=telegram_id,
                is_active=True,
            )
        )

    async def get_by_id(self, student_id: uuid.UUID) -> StudentReadSchema:
        """Получить студента по идентификатору."""
        return await self.student_repository.get(student_id)
    
    async def attach_to_course(
        self,
        student_ids: list[uuid.UUID],
        course_id: uuid.UUID,
    ) -> None:
        """
        Привязать студентов к курсу.
        
        Создаёт записи StudentCourse для всех студентов одним запросом
        для оптимизации производительности.
        
        Args:
            student_ids: Список ID студентов
            course_id: ID курса
        """
        # Создаём схемы для всех привязок
        student_course_schemas = [
            StudentCourseCreateSchema(
                student_id=student_id,
                course_session_id=course_id,
            )
            for student_id in student_ids
        ]
        
        # Используем bulk_create для оптимизации
        await self.student_course_repository.bulk_create(student_course_schemas)

    async def is_attached_to_course(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить, записан ли студент на курс."""
        return await self.student_course_repository.exists_by_student_and_course(
            student_id,
            course_id,
        )
    
    async def attach_to_lections(
        self,
        student_ids: list[uuid.UUID],
        lection_ids: list[uuid.UUID],
    ) -> None:
        """
        Привязать студентов к лекциям с использованием bulk_create.
        
        Создаёт записи StudentLection для всех комбинаций студентов и лекций
        одним запросом для оптимизации производительности.
        
        Args:
            student_ids: Список ID студентов
            lection_ids: Список ID лекций
        """
        # Создаём схемы для всех комбинаций студент-лекция
        student_lection_schemas = [
            StudentLectionCreateSchema(
                student_id=student_id,
                lection_session_id=lection_id,
            )
            for student_id in student_ids
            for lection_id in lection_ids
        ]
        
        # Используем bulk_create для оптимизации
        await self.student_lection_repository.bulk_create(student_lection_schemas)
    
    async def get_students_by_course(
        self,
        course_id: uuid.UUID,
        page: int = 1,
        page_size: int = 5,
    ) -> dict:
        """
        Получить студентов курса с пагинацией.
        
        Возвращает студентов, привязанных к курсу через StudentCourse,
        с поддержкой пагинации.
        
        Args:
            course_id: ID курса
            page: Номер страницы (начиная с 1)
            page_size: Количество элементов на странице
        
        Returns:
            Словарь с полями:
            - items: список студентов
            - total: общее количество студентов
            - page: текущая страница
            - page_size: размер страницы
            - total_pages: общее количество страниц
        """
        student_courses = await self.student_course_repository.get_all()
        student_ids = [
            student_course.student_id
            for student_course in student_courses
            if student_course.course_session_id == course_id
        ]
        students = await self.student_repository.get_by_ids(student_ids) if student_ids else []
        students = sorted(
            students,
            key=lambda student: (student.full_name.casefold(), str(student.id)),
        )

        total = len(students)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        normalized_page = max(1, min(page, total_pages))
        start_idx = (normalized_page - 1) * page_size
        end_idx = start_idx + page_size

        return {
            "items": students[start_idx:end_idx],
            "total": total,
            "page": normalized_page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
