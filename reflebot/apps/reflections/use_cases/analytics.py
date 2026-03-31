"""
Use cases для аналитики по лекциям и студентам.
"""

import uuid
from typing import Protocol

from reflebot.core.utils.exceptions import PermissionDeniedError
from ..schemas import (
    AdminReadSchema,
    LectionStatisticsSchema,
    ReflectionDetailsSchema,
    StudentStatisticsSchema,
    TeacherReadSchema,
)
from ..services.analytics import AnalyticsServiceProtocol
from ..services.lection import LectionServiceProtocol
from ..repositories.teacher_course import TeacherCourseRepositoryProtocol


class ViewLectionAnalyticsUseCaseProtocol(Protocol):
    """Протокол use case просмотра аналитики по лекции."""

    async def __call__(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema | None = None,
        current_teacher: TeacherReadSchema | None = None,
    ) -> LectionStatisticsSchema:
        """Получить статистику по лекции с проверкой прав доступа."""
        ...


class ViewStudentAnalyticsUseCaseProtocol(Protocol):
    """Протокол use case просмотра статистики студента."""

    async def __call__(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
        current_admin: AdminReadSchema | None = None,
        current_teacher: TeacherReadSchema | None = None,
    ) -> StudentStatisticsSchema:
        """Получить статистику студента по курсу с проверкой прав доступа."""
        ...


class ViewReflectionDetailsUseCaseProtocol(Protocol):
    """Протокол use case просмотра деталей рефлексии."""

    async def __call__(
        self,
        student_id: uuid.UUID,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema | None = None,
        current_teacher: TeacherReadSchema | None = None,
    ) -> ReflectionDetailsSchema:
        """Получить детали рефлексии с проверкой прав доступа."""
        ...


class _AnalyticsAccessMixin:
    """Общая логика проверки доступа к аналитике."""

    teacher_course_repository: TeacherCourseRepositoryProtocol
    lection_service: LectionServiceProtocol

    async def _ensure_course_access(
        self,
        course_id: uuid.UUID,
        current_admin: AdminReadSchema | None,
        current_teacher: TeacherReadSchema | None,
    ) -> None:
        if current_admin is not None:
            return

        if current_teacher is None:
            raise PermissionDeniedError("Недостаточно прав для просмотра аналитики")

        teacher_courses = await self.teacher_course_repository.get_all()
        has_access = any(
            teacher_course.teacher_id == current_teacher.id
            and teacher_course.course_session_id == course_id
            for teacher_course in teacher_courses
        )
        if not has_access:
            raise PermissionDeniedError("Недостаточно прав для просмотра аналитики курса")

    async def _ensure_lection_access(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema | None,
        current_teacher: TeacherReadSchema | None,
    ) -> uuid.UUID:
        lection = await self.lection_service.get_by_id(lection_id)
        await self._ensure_course_access(
            lection.course_session_id,
            current_admin=current_admin,
            current_teacher=current_teacher,
        )
        return lection.course_session_id


class ViewLectionAnalyticsUseCase(_AnalyticsAccessMixin, ViewLectionAnalyticsUseCaseProtocol):
    """Use case просмотра статистики по лекции."""

    def __init__(
        self,
        analytics_service: AnalyticsServiceProtocol,
        lection_service: LectionServiceProtocol,
        teacher_course_repository: TeacherCourseRepositoryProtocol,
    ):
        self.analytics_service = analytics_service
        self.lection_service = lection_service
        self.teacher_course_repository = teacher_course_repository

    async def __call__(
        self,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema | None = None,
        current_teacher: TeacherReadSchema | None = None,
    ) -> LectionStatisticsSchema:
        await self._ensure_lection_access(lection_id, current_admin, current_teacher)
        return await self.analytics_service.get_lection_statistics(lection_id)


class ViewStudentAnalyticsUseCase(_AnalyticsAccessMixin, ViewStudentAnalyticsUseCaseProtocol):
    """Use case просмотра статистики студента по курсу."""

    def __init__(
        self,
        analytics_service: AnalyticsServiceProtocol,
        lection_service: LectionServiceProtocol,
        teacher_course_repository: TeacherCourseRepositoryProtocol,
    ):
        self.analytics_service = analytics_service
        self.lection_service = lection_service
        self.teacher_course_repository = teacher_course_repository

    async def __call__(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
        current_admin: AdminReadSchema | None = None,
        current_teacher: TeacherReadSchema | None = None,
    ) -> StudentStatisticsSchema:
        await self._ensure_course_access(course_id, current_admin, current_teacher)
        return await self.analytics_service.get_student_statistics(student_id, course_id)


class ViewReflectionDetailsUseCase(_AnalyticsAccessMixin, ViewReflectionDetailsUseCaseProtocol):
    """Use case просмотра деталей рефлексии."""

    def __init__(
        self,
        analytics_service: AnalyticsServiceProtocol,
        lection_service: LectionServiceProtocol,
        teacher_course_repository: TeacherCourseRepositoryProtocol,
    ):
        self.analytics_service = analytics_service
        self.lection_service = lection_service
        self.teacher_course_repository = teacher_course_repository

    async def __call__(
        self,
        student_id: uuid.UUID,
        lection_id: uuid.UUID,
        current_admin: AdminReadSchema | None = None,
        current_teacher: TeacherReadSchema | None = None,
    ) -> ReflectionDetailsSchema:
        await self._ensure_lection_access(lection_id, current_admin, current_teacher)
        return await self.analytics_service.get_reflection_details(student_id, lection_id)
