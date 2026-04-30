"""
Сервис для работы с аутентификацией.
"""

from typing import Protocol
from reflebot.core.utils.exceptions import ModelFieldNotFoundException

from ..repositories.course import CourseSessionRepositoryProtocol
from ..repositories.admin import AdminRepositoryProtocol
from ..repositories.student import StudentRepositoryProtocol
from ..repositories.teacher import TeacherRepositoryProtocol
from ..services.context import ContextServiceProtocol
from ..services.course_invite import CourseInviteServiceProtocol
from ..services.lection import LectionServiceProtocol
from ..services.student import StudentServiceProtocol
from ..telegram.messages import TelegramMessages
from ..telegram.buttons import TelegramButtons
from ..schemas import (
    AdminLoginSchema,
    UserLoginResponseSchema,
    AdminReadSchema,
    StudentReadSchema,
    TeacherReadSchema,
    TelegramButtonSchema,
)


class AuthServiceProtocol(Protocol):
    """Протокол сервиса аутентификации."""
    
    async def login_user(
        self, telegram_username: str, login_data: AdminLoginSchema
    ) -> UserLoginResponseSchema:
        """Вход пользователя (проверка во всех таблицах)."""
        ...


class AuthService(AuthServiceProtocol):
    """Сервис для работы с аутентификацией."""
    
    def __init__(
        self,
        admin_repository: AdminRepositoryProtocol,
        student_repository: StudentRepositoryProtocol,
        teacher_repository: TeacherRepositoryProtocol,
        course_repository: CourseSessionRepositoryProtocol,
        context_service: ContextServiceProtocol,
        student_service: StudentServiceProtocol,
        lection_service: LectionServiceProtocol,
        course_invite_service: CourseInviteServiceProtocol,
    ):
        self.admin_repository = admin_repository
        self.student_repository = student_repository
        self.teacher_repository = teacher_repository
        self.course_repository = course_repository
        self.context_service = context_service
        self.student_service = student_service
        self.lection_service = lection_service
        self.course_invite_service = course_invite_service

    async def _get_admin_by_telegram_id(self, telegram_id: int) -> AdminReadSchema | None:
        """Безопасно получить администратора по telegram_id."""
        try:
            admin = await self.admin_repository.get_by_telegram_id(telegram_id)
        except ModelFieldNotFoundException:
            return None
        return admin if isinstance(admin, AdminReadSchema) else None

    async def _get_teacher_by_telegram_id(self, telegram_id: int) -> TeacherReadSchema | None:
        """Безопасно получить преподавателя по telegram_id."""
        try:
            teacher = await self.teacher_repository.get_by_telegram_id(telegram_id)
        except ModelFieldNotFoundException:
            return None
        return teacher if isinstance(teacher, TeacherReadSchema) else None

    async def _get_student_by_telegram_id(self, telegram_id: int) -> StudentReadSchema | None:
        """Безопасно получить студента по telegram_id."""
        student = await self.student_repository.get_by_telegram_id(telegram_id)
        return student if isinstance(student, StudentReadSchema) else None
    
    async def login_user(
        self, telegram_username: str, login_data: AdminLoginSchema
    ) -> UserLoginResponseSchema:
        """
        Вход пользователя.
        
        Проверяет наличие пользователя в таблицах Admin, Student, Teacher
        и обновляет telegram_id во всех найденных записях.
        """
        telegram_id = login_data.telegram_id
        # Проверяем и обновляем во всех таблицах
        admin: AdminReadSchema | None = None
        student: StudentReadSchema | None = None
        teacher: TeacherReadSchema | None = None
        
        # Проверяем админа
        try:
            admin_found = await self.admin_repository.get_by_telegram_username(telegram_username)
            if admin_found:
                admin = await self.admin_repository.update_telegram_id(
                    telegram_username, telegram_id
                )
        except ModelFieldNotFoundException:
            admin = await self._get_admin_by_telegram_id(telegram_id)
        
        # Проверяем студента
        student_found = await self.student_repository.get_by_telegram_username(telegram_username)
        if student_found:
            student = await self.student_repository.update_telegram_id(
                telegram_username, telegram_id
            )
        else:
            student = await self._get_student_by_telegram_id(telegram_id)
        
        # Проверяем преподавателя
        teacher_found = await self.teacher_repository.get_by_telegram_username(telegram_username)
        if teacher_found:
            teacher = await self.teacher_repository.update_telegram_id(
                telegram_username, telegram_id
            )
        else:
            teacher = await self._get_teacher_by_telegram_id(telegram_id)
        
        # Если не найден ни в одной таблице
        if not admin and not student and not teacher:
            await self.context_service.set_context(
                telegram_id,
                action="register_course_by_code",
                step="awaiting_course_code",
                data={
                    "telegram_username": telegram_username,
                    "telegram_id": telegram_id,
                },
            )
            return UserLoginResponseSchema(
                full_name=telegram_username,
                telegram_username=telegram_username,
                telegram_id=telegram_id,
                is_active=True,
                is_admin=False,
                is_teacher=False,
                is_student=False,
                message=TelegramMessages.get_student_course_code_request(),
                parse_mode="HTML",
                buttons=[],
                awaiting_input=True,
            )
        
        # Берём данные из первой найденной записи
        user_data = admin or student or teacher
        
        # Определяем роли
        is_admin = admin is not None
        is_teacher = teacher is not None
        is_student = student is not None

        current_context = await self.context_service.get_context(telegram_id)
        if (
            is_student
            and isinstance(current_context, dict)
            and current_context.get("action") == "student_reflection_workflow"
            and current_context.get("step") in {
                "awaiting_reflection_video",
                "awaiting_question_video",
                "question_prompt",
            }
        ):
            return UserLoginResponseSchema(
                full_name=user_data.full_name,
                telegram_username=user_data.telegram_username,
                telegram_id=telegram_id,
                is_active=user_data.is_active,
                is_admin=is_admin,
                is_teacher=is_teacher,
                is_student=is_student,
                message=TelegramMessages.get_reflection_video_required(
                    (current_context.get("data") or {}).get("lection_topic")
                ),
                parse_mode="HTML",
                buttons=[],
                awaiting_input=True,
            )

        # Если пользователь уже найден хотя бы в одной из ролей, сбрасываем
        # незавершённый student-flow по коду курса и возвращаем обычное меню.
        await self.context_service.clear_context(telegram_id)
        
        # Генерируем сообщение и кнопки
        message = TelegramMessages.get_login_message(
            full_name=user_data.full_name,
            is_admin=is_admin,
            is_teacher=is_teacher,
            is_student=is_student,
        )
        
        buttons_data = TelegramButtons.get_login_buttons(
            is_admin=is_admin,
            is_teacher=is_teacher,
            is_student=is_student,
        )
        
        # Конвертируем кнопки в схемы
        buttons = [
            TelegramButtonSchema(text=btn.text, action=btn.action, url=btn.url)
            for btn in buttons_data
        ]
        
        return UserLoginResponseSchema(
            full_name=user_data.full_name,
            telegram_username=user_data.telegram_username,
            telegram_id=telegram_id,
            is_active=user_data.is_active,
            is_admin=is_admin,
            is_teacher=is_teacher,
            is_student=is_student,
            message=message,
            parse_mode="HTML",
            buttons=buttons,
            awaiting_input=False,
        )
