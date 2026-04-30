"""
Сервис для работы с преподавателями.
"""

import uuid
from typing import Protocol

from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..repositories.admin import AdminRepositoryProtocol
from ..repositories.student import StudentRepositoryProtocol
from ..repositories.teacher import TeacherRepositoryProtocol
from ..repositories.teacher_course import TeacherCourseRepositoryProtocol
from ..repositories.teacher_lection import TeacherLectionRepositoryProtocol
from ..schemas import (
    TeacherReadSchema,
    TeacherCreateSchema,
    TeacherCourseCreateSchema,
    TeacherLectionCreateSchema,
)


class TeacherServiceProtocol(Protocol):
    """Протокол сервиса преподавателей."""
    
    async def create_or_get(self, full_name: str, telegram_username: str) -> TeacherReadSchema:
        """Создать или получить преподавателя."""
        ...

    async def get_by_telegram_id(self, telegram_id: int) -> TeacherReadSchema | None:
        """Получить преподавателя по telegram_id."""
        ...

    async def get_by_telegram_username(self, telegram_username: str) -> TeacherReadSchema | None:
        """Получить преподавателя по telegram_username."""
        ...
    
    async def attach_to_course(
        self,
        teacher_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> None:
        """Привязать преподавателя к курсу."""
        ...
    
    async def attach_to_lections(
        self,
        teacher_id: uuid.UUID,
        lection_ids: list[uuid.UUID],
    ) -> None:
        """Привязать преподавателя к лекциям с использованием bulk_create."""
        ...

    async def is_attached_to_course(
        self,
        teacher_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить, привязан ли преподаватель к курсу."""
        ...

    async def get_teacher_ids_by_course(self, course_id: uuid.UUID) -> list[uuid.UUID]:
        """Получить идентификаторы преподавателей курса."""
        ...


class TeacherService(TeacherServiceProtocol):
    """Сервис для работы с преподавателями."""
    
    def __init__(
        self,
        teacher_repository: TeacherRepositoryProtocol,
        teacher_course_repository: TeacherCourseRepositoryProtocol,
        teacher_lection_repository: TeacherLectionRepositoryProtocol,
        admin_repository: AdminRepositoryProtocol | None = None,
        student_repository: StudentRepositoryProtocol | None = None,
    ):
        self.teacher_repository = teacher_repository
        self.teacher_course_repository = teacher_course_repository
        self.teacher_lection_repository = teacher_lection_repository
        self.admin_repository = admin_repository
        self.student_repository = student_repository

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

        if self.student_repository is not None:
            student = await self.student_repository.get_by_telegram_username(telegram_username)
            if student and student.telegram_id is not None:
                return student.telegram_id

        return None
    
    async def create_or_get(self, full_name: str, telegram_username: str) -> TeacherReadSchema:
        """
        Создать или получить преподавателя.
        
        Если преподаватель с таким telegram_username существует, возвращает его.
        Иначе создаёт нового преподавателя.
        
        Args:
            full_name: ФИО преподавателя
            telegram_username: Никнейм в Telegram (без @)
        
        Returns:
            Преподаватель
        """
        # Пытаемся найти существующего преподавателя по username
        existing_teacher = await self.teacher_repository.get_by_telegram_username(telegram_username)
        
        if existing_teacher:
            return existing_teacher
        
        # Создаём нового преподавателя
        teacher_data = TeacherCreateSchema(
            full_name=full_name,
            telegram_username=telegram_username,
            telegram_id=await self._get_related_telegram_id(telegram_username),
            is_active=True,
        )
        
        return await self.teacher_repository.create(teacher_data)

    async def get_by_telegram_id(self, telegram_id: int) -> TeacherReadSchema | None:
        """Получить преподавателя по telegram_id."""
        return await self.teacher_repository.get_by_telegram_id(telegram_id)

    async def get_by_telegram_username(self, telegram_username: str) -> TeacherReadSchema | None:
        """Получить преподавателя по telegram_username."""
        return await self.teacher_repository.get_by_telegram_username(telegram_username)
    
    async def attach_to_course(
        self,
        teacher_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> None:
        """
        Привязать преподавателя к курсу.
        
        Создаёт запись TeacherCourse для привязки преподавателя к курсу.
        
        Args:
            teacher_id: ID преподавателя
            course_id: ID курса
        """
        teacher_course_data = TeacherCourseCreateSchema(
            teacher_id=teacher_id,
            course_session_id=course_id,
        )
        
        await self.teacher_course_repository.create(teacher_course_data)

    async def is_attached_to_course(
        self,
        teacher_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> bool:
        """Проверить, привязан ли преподаватель к курсу."""
        return await self.teacher_course_repository.exists_by_teacher_and_course(
            teacher_id,
            course_id,
        )
    
    async def attach_to_lections(
        self,
        teacher_id: uuid.UUID,
        lection_ids: list[uuid.UUID],
    ) -> None:
        """
        Привязать преподавателя к лекциям с использованием bulk_create.
        
        Создаёт записи TeacherLection для всех лекций одним запросом
        для оптимизации производительности.
        
        Args:
            teacher_id: ID преподавателя
            lection_ids: Список ID лекций
        """
        # Создаём схемы для всех привязок
        teacher_lection_schemas = [
            TeacherLectionCreateSchema(
                teacher_id=teacher_id,
                lection_session_id=lection_id,
            )
            for lection_id in lection_ids
        ]
        
        # Используем bulk_create для оптимизации
        await self.teacher_lection_repository.bulk_create(teacher_lection_schemas)

    async def get_teacher_ids_by_course(self, course_id: uuid.UUID) -> list[uuid.UUID]:
        """Получить идентификаторы преподавателей, привязанных к курсу."""
        return await self.teacher_course_repository.get_teacher_ids_by_course(course_id)
