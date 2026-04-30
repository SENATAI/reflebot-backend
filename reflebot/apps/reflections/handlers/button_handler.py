"""
Handler для нажатий кнопок Telegram.
"""

from datetime import datetime
from typing import Protocol
import uuid

from reflebot.core.utils.exceptions import PermissionDeniedError
from ..schemas import (
    ActionResponseSchema,
    AdminReadSchema,
    TelegramButtonSchema,
    TelegramDialogMessageSchema,
    TelegramFileReferenceSchema,
    TelegramMessageTrackingSchema,
)
from ..services.admin import AdminServiceProtocol
from ..services.context import ContextServiceProtocol
from ..services.course import CourseServiceProtocol
from ..services.course_invite import CourseInviteServiceProtocol
from ..services.default_question import DefaultQuestionServiceProtocol
from ..services.lection import LectionServiceProtocol
from ..services.pagination import PaginationServiceProtocol
from ..services.question import QuestionServiceProtocol
from ..services.reflection import ReflectionWorkflowServiceProtocol
from ..services.student import StudentServiceProtocol
from ..services.student_history_log import StudentHistoryLogServiceProtocol
from ..services.telegram_tracked_message import TelegramTrackedMessageServiceProtocol
from ..services.teacher import TeacherServiceProtocol
from ..telegram.buttons import TelegramButtons
from ..telegram.messages import TelegramMessages
from ..use_cases.analytics import (
    ViewLectionAnalyticsUseCaseProtocol,
    ViewReflectionDetailsUseCaseProtocol,
    ViewStudentAnalyticsUseCaseProtocol,
)
from ..use_cases.course import SendCourseReflectionAlertUseCaseProtocol
from ..use_cases.lection import ManageFilesUseCaseProtocol
from .base import BaseHandler, ResolvedRoles


class ButtonActionHandlerProtocol(Protocol):
    """Протокол обработчика кнопок."""

    async def handle(self, action: str, telegram_id: int) -> ActionResponseSchema:
        """Обработать действие кнопки."""
        ...


class ButtonActionHandler(BaseHandler, ButtonActionHandlerProtocol):
    """Обработчик нажатий кнопок в backend-driven Telegram bot."""

    CREATE_ADMIN_FULLNAME_SCREEN = "create_admin_fullname"
    CREATE_ADMIN_USERNAME_SCREEN = "create_admin_username"
    ATTACH_TEACHER_FULLNAME_SCREEN = "attach_teacher_fullname"
    ATTACH_TEACHER_USERNAME_SCREEN = "attach_teacher_username"
    EDIT_LECTION_TOPIC_SCREEN = "edit_lection_topic_prompt"
    EDIT_LECTION_DATE_SCREEN = "edit_lection_date_prompt"
    ADD_QUESTION_SCREEN = "add_question_prompt"
    EDIT_QUESTION_SCREEN = "edit_question_prompt"
    PRESENTATION_UPLOAD_SCREEN = "presentation_upload_prompt"
    RECORDING_UPLOAD_SCREEN = "recording_upload_prompt"
    TEACHER_NEAREST_LECTION_SCREEN = "teacher_nearest_lection"

    def __init__(
        self,
        context_service: ContextServiceProtocol,
        admin_service: AdminServiceProtocol,
        teacher_service: TeacherServiceProtocol,
        student_service: StudentServiceProtocol,
        course_service: CourseServiceProtocol,
        course_invite_service: CourseInviteServiceProtocol,
        default_question_service: DefaultQuestionServiceProtocol,
        lection_service: LectionServiceProtocol,
        question_service: QuestionServiceProtocol,
        pagination_service: PaginationServiceProtocol,
        manage_files_use_case: ManageFilesUseCaseProtocol,
        reflection_workflow_service: ReflectionWorkflowServiceProtocol,
        view_lection_analytics_use_case: ViewLectionAnalyticsUseCaseProtocol,
        view_student_analytics_use_case: ViewStudentAnalyticsUseCaseProtocol,
        view_reflection_details_use_case: ViewReflectionDetailsUseCaseProtocol,
        send_course_reflection_alert_use_case: SendCourseReflectionAlertUseCaseProtocol | None = None,
        student_history_log_service: StudentHistoryLogServiceProtocol | None = None,
        telegram_tracked_message_service: TelegramTrackedMessageServiceProtocol | None = None,
    ):
        super().__init__(
            admin_service,
            teacher_service,
            student_service,
            context_service=context_service,
        )
        self.context_service = context_service
        self.course_service = course_service
        self.course_invite_service = course_invite_service
        self.default_question_service = default_question_service
        self.lection_service = lection_service
        self.question_service = question_service
        self.pagination_service = pagination_service
        self.manage_files_use_case = manage_files_use_case
        self.reflection_workflow_service = reflection_workflow_service
        self.student_history_log_service = student_history_log_service
        self.telegram_tracked_message_service = telegram_tracked_message_service
        self.view_lection_analytics_use_case = view_lection_analytics_use_case
        self.view_student_analytics_use_case = view_student_analytics_use_case
        self.view_reflection_details_use_case = view_reflection_details_use_case
        self.send_course_reflection_alert_use_case = send_course_reflection_alert_use_case

    async def handle(self, action: str, telegram_id: int) -> ActionResponseSchema:
        """Обработать нажатие кнопки."""
        try:
            base_action, *parts = action.split(":")
            context = await self.context_service.get_context(telegram_id) or {}
            context_data = context.get("data", {})
            roles = await self.resolve_roles(telegram_id)
            await self._log_student_button_action(roles, action)
            if (
                context.get("action") == "student_reflection_workflow"
                and context.get("step") in {
                    "awaiting_reflection_video",
                    "awaiting_question_video",
                    "question_prompt",
                }
            ):
                return ActionResponseSchema(
                    message=TelegramMessages.get_reflection_video_required(
                        context_data.get("lection_topic")
                    ),
                    awaiting_input=True,
                )

            if base_action == TelegramButtons.STUDENT_START_REFLECTION and parts:
                return await self._start_student_reflection(
                    telegram_id,
                    roles,
                    uuid.UUID(parts[0]),
                )
            if base_action == TelegramButtons.STUDENT_JOIN_COURSE:
                return await self._start_join_course(telegram_id, roles)
            if base_action == TelegramButtons.STUDENT_RECORD_REFLECTION_VIDEO:
                return await self._request_student_reflection_video(
                    telegram_id,
                    roles,
                    context_data,
                )
            if base_action == TelegramButtons.STUDENT_SUBMIT_REFLECTION:
                return await self._submit_student_reflection(telegram_id, roles, context_data)
            if base_action == TelegramButtons.STUDENT_DELETE_REFLECTION_VIDEO:
                return await self._delete_student_reflection_video(
                    telegram_id,
                    roles,
                    context_data,
                )
            if base_action in {
                TelegramButtons.STUDENT_ADD_REFLECTION_VIDEO,
                TelegramButtons.STUDENT_APPEND_REFLECTION,
            }:
                if parts:
                    return await self._resume_student_reflection_upload(
                        telegram_id,
                        roles,
                        uuid.UUID(parts[0]),
                    )
                return await self._request_student_reflection_video(
                    telegram_id,
                    roles,
                    context_data,
                )
            if base_action == TelegramButtons.STUDENT_RECORD_QA_VIDEO:
                return await self._request_student_question_video(
                    telegram_id,
                    roles,
                    context_data,
                )
            if base_action == TelegramButtons.STUDENT_SELECT_QUESTION and parts:
                return await self._select_student_question(
                    telegram_id,
                    roles,
                    context_data,
                    uuid.UUID(parts[0]),
                )
            if base_action == TelegramButtons.STUDENT_SUBMIT_QA:
                return await self._submit_student_question(telegram_id, roles, context_data)
            if base_action == TelegramButtons.STUDENT_DELETE_QA_VIDEO:
                return await self._delete_student_question_video(
                    telegram_id,
                    roles,
                    context_data,
                )
            if base_action == TelegramButtons.STUDENT_ADD_QA_VIDEO:
                return await self._request_student_question_video(
                    telegram_id,
                    roles,
                    context_data,
                )
            if base_action == TelegramButtons.ADMIN_CREATE_ADMIN:
                return await self._start_create_admin(telegram_id, roles)
            if base_action == TelegramButtons.ADMIN_CREATE_COURSE:
                return await self._start_create_course(telegram_id, roles)
            if base_action == TelegramButtons.ADMIN_VIEW_COURSES:
                return await self.render_admin_courses(
                    telegram_id,
                    page=1,
                    push_navigation=True,
                )
            if base_action == TelegramButtons.ADMIN_VIEW_COURSE and parts:
                page = (
                    int(context_data.get("page", 1))
                    if context.get("action") == "admin_courses"
                    else 1
                )
                return await self.render_admin_course_details(
                    telegram_id,
                    uuid.UUID(parts[0]),
                    page=page,
                    push_navigation=True,
                )
            if base_action == TelegramButtons.COURSE_APPEND_LECTIONS:
                return await self._start_append_course_lections(telegram_id, roles, context_data)
            if base_action == TelegramButtons.COURSE_CONFIRM_APPEND:
                return await self._confirm_appended_course_lections(
                    telegram_id,
                    roles,
                    context_data,
                )
            if base_action == TelegramButtons.COURSE_SEND_ALERT:
                return await self.render_course_alert_lections(
                    telegram_id,
                    uuid.UUID(str(context_data["course_id"])),
                    page=1,
                    push_navigation=True,
                )
            if base_action == TelegramButtons.COURSE_ALERT_LECTION and parts:
                lection_id = uuid.UUID(parts[0])
                lection = await self.lection_service.get_by_id(lection_id)
                return await self.render_course_alert_students(
                    telegram_id,
                    course_id=lection.course_session_id,
                    lection_id=lection_id,
                    page=1,
                    push_navigation=True,
                )
            if base_action == TelegramButtons.COURSE_ALERT_STUDENT and parts:
                return await self._send_course_reflection_alert(
                    telegram_id,
                    roles,
                    context_data,
                    uuid.UUID(parts[0]),
                )
            if base_action == TelegramButtons.COURSE_SEND_MESSAGE:
                return await self._start_course_broadcast_message(telegram_id, roles, context_data)
            if base_action == TelegramButtons.COURSE_VIEW_PARSED_LECTIONS:
                return await self.render_parsed_lections(
                    telegram_id,
                    uuid.UUID(str(context_data["course_id"])),
                    page=1,
                    push_navigation=True,
                    extra_data={
                        key: value
                        for key, value in context_data.items()
                        if key not in {"course_id", "page"}
                    },
                )
            if base_action == TelegramButtons.COURSE_ADD_DEFAULT_QUESTIONS:
                return await self._add_default_questions_to_course(telegram_id, roles, context_data)
            if base_action == TelegramButtons.COURSE_ATTACH_TEACHERS:
                return await self._start_attach_teacher(telegram_id, roles, context_data)
            if base_action == TelegramButtons.COURSE_ATTACH_STUDENTS:
                return await self._start_attach_students(telegram_id, roles, context_data)
            if base_action == TelegramButtons.COURSE_CANCEL_PARSING:
                return await self._cancel_course(telegram_id, roles, context_data)
            if base_action == TelegramButtons.LECTION_INFO and parts:
                lection_id = uuid.UUID(parts[0])
                if context.get("action") == "analytics_lection_list":
                    return await self.render_analytics_lection_statistics(
                        telegram_id,
                        lection_id,
                        page=1,
                        push_navigation=True,
                    )
                return await self.render_lection_details(
                    telegram_id,
                    lection_id,
                    context_data.get("course_id"),
                    push_navigation=True,
                )
            if base_action == TelegramButtons.LECTION_EDIT_TOPIC:
                return await self._request_lection_topic_edit(telegram_id, roles, context_data)
            if base_action == TelegramButtons.LECTION_EDIT_DATE:
                return await self._request_lection_date_edit(telegram_id, roles, context_data)
            if base_action == TelegramButtons.LECTION_MANAGE_QUESTIONS:
                return await self.render_questions_menu(
                    telegram_id,
                    uuid.UUID(str(context_data["lection_id"])),
                    push_navigation=True,
                )
            if base_action == TelegramButtons.QUESTIONS_ADD:
                return await self._request_add_question(telegram_id, roles, context_data)
            if base_action == TelegramButtons.QUESTIONS_EDIT:
                return await self._request_edit_question(telegram_id, roles, context_data)
            if base_action == TelegramButtons.QUESTIONS_DELETE:
                return await self.render_question_delete_menu(
                    telegram_id,
                    uuid.UUID(str(context_data["lection_id"])),
                )
            if base_action == TelegramButtons.QUESTION_DELETE_SPECIFIC and parts:
                return await self._delete_question(telegram_id, roles, uuid.UUID(parts[0]))
            if base_action == TelegramButtons.LECTION_MANAGE_PRESENTATION:
                return await self.render_presentation_menu(
                    telegram_id,
                    uuid.UUID(str(context_data["lection_id"])),
                    push_navigation=True,
                )
            if base_action == TelegramButtons.PRESENTATION_UPLOAD:
                return await self._request_presentation_upload(telegram_id, roles, context_data)
            if base_action == TelegramButtons.PRESENTATION_DOWNLOAD:
                return await self._download_presentation(telegram_id, roles, context_data)
            if base_action == TelegramButtons.LECTION_MANAGE_RECORDING:
                return await self.render_recording_menu(
                    telegram_id,
                    uuid.UUID(str(context_data["lection_id"])),
                    push_navigation=True,
                )
            if base_action == TelegramButtons.RECORDING_UPLOAD:
                return await self._request_recording_upload(telegram_id, roles, context_data)
            if base_action == TelegramButtons.RECORDING_DOWNLOAD:
                return await self._download_recording(telegram_id, roles, context_data)
            if base_action == TelegramButtons.TEACHER_ADD_ANOTHER:
                return await self._start_attach_teacher(telegram_id, roles, context_data)
            if base_action == TelegramButtons.TEACHER_FINISH_COURSE_CREATION:
                return await self._finish_course_creation(telegram_id, roles, context_data)
            if base_action == TelegramButtons.TEACHER_ANALYTICS:
                return await self.render_analytics_courses(
                    telegram_id,
                    page=1,
                    push_navigation=True,
                )
            if base_action == TelegramButtons.TEACHER_NEXT_LECTION:
                return await self._show_nearest_lection(telegram_id, roles)
            if base_action == TelegramButtons.ANALYTICS_SELECT_COURSE and parts:
                return await self.render_analytics_course_menu(
                    telegram_id,
                    uuid.UUID(parts[0]),
                    push_navigation=True,
                )
            if base_action == TelegramButtons.ANALYTICS_LECTION_STATS:
                return await self.render_analytics_lection_list(
                    telegram_id,
                    uuid.UUID(str(context_data["course_id"])),
                    page=1,
                    push_navigation=True,
                )
            if base_action == TelegramButtons.ANALYTICS_FIND_STUDENT and not parts:
                return await self.render_analytics_student_list(
                    telegram_id,
                    uuid.UUID(str(context_data["course_id"])),
                    page=1,
                    push_navigation=True,
                )
            if base_action == TelegramButtons.ANALYTICS_FIND_STUDENT and parts:
                return await self.render_student_statistics(
                    telegram_id,
                    uuid.UUID(str(context_data["course_id"])),
                    uuid.UUID(parts[0]),
                    push_navigation=True,
                )
            if base_action == TelegramButtons.ANALYTICS_VIEW_REFLECTION and len(parts) == 1:
                return await self._render_reflection_details_from_context(
                    telegram_id,
                    context,
                    uuid.UUID(parts[0]),
                )
            if base_action == TelegramButtons.NEXT_PAGE:
                return await self._paginate(telegram_id, roles, context, 1)
            if base_action == TelegramButtons.PREV_PAGE:
                return await self._paginate(telegram_id, roles, context, -1)
            if base_action == TelegramButtons.BACK:
                return await self._go_back(telegram_id)

            return ActionResponseSchema(message=TelegramMessages.get_unknown_action(action))
        except Exception as exc:
            return await self.build_error_response(telegram_id, exc)

    async def render_course_menu(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать меню курса после парсинга или при возврате."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "course_menu")
        course = await self.course_service.get_by_id(course_id)
        await self.context_service.set_context(
            telegram_id,
            action="course_menu",
            step="view",
            data={"course_id": str(course_id), "page": 1},
        )
        has_lections_without_questions = await self._course_has_lections_without_questions(course_id)
        return ActionResponseSchema(
            message=TelegramMessages.get_course_created_success(
                course.name,
                course.started_at,
                course.ended_at,
                course.join_code,
            ),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_course_menu_buttons(
                    show_add_default_questions=has_lections_without_questions
                )
            ],
        )

    async def render_parsed_lections(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        page: int,
        push_navigation: bool = False,
        extra_data: dict | None = None,
    ) -> ActionResponseSchema:
        """Показать список спаршенных лекций с пагинацией."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "parsed_lections")
        course = await self.course_service.get_by_id(course_id)
        response = await self.lection_service.get_lections_by_course(course_id=course_id, page=page, page_size=5)
        context_data = {"course_id": str(course_id), "page": page}
        if extra_data:
            context_data.update(extra_data)
        await self.context_service.set_context(
            telegram_id,
            action="parsed_lections",
            step="view",
            data=context_data,
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for lection in response.items
            for button in [TelegramButtons.create_lection_button(lection.topic, str(lection.id))]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, response.total_pages)
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_parsed_lections_title(course.name),
            buttons=buttons,
        )

    async def render_append_course_menu(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        page: int,
        appended_lection_ids: list[str],
        message_prefix: str | None = None,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать экран подтверждения догруженных лекций."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "append_course_menu")
        course = await self.course_service.get_by_id(course_id)
        await self.context_service.set_context(
            telegram_id,
            action="append_course_menu",
            step="view",
            data={
                "course_id": str(course_id),
                "page": page,
                "appended_lection_ids": appended_lection_ids,
            },
        )
        show_add_default_questions = await self._lections_have_missing_questions(
            [uuid.UUID(lection_id) for lection_id in appended_lection_ids]
        )
        message = TelegramMessages.get_append_course_preview(
            course.name,
            course.started_at,
            course.ended_at,
        )
        if message_prefix:
            separator = "" if message_prefix.endswith("\n\n") else "\n\n"
            message = f"{message_prefix}{separator}{message}"
        return ActionResponseSchema(
            message=message,
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_append_course_menu_buttons(
                    show_add_default_questions=show_add_default_questions,
                )
            ],
        )

    async def render_lection_details(
        self,
        telegram_id: int,
        lection_id: uuid.UUID,
        course_id: str | None = None,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать детальную информацию о лекции."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "lection_details")
        details = await self.lection_service.get_lection_details(lection_id)
        await self.context_service.set_context(
            telegram_id,
            action="lection_details",
            step="view",
            data={
                "course_id": course_id or str(details.lection.course_session_id),
                "lection_id": str(lection_id),
            },
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_lection_details(
                topic=details.lection.topic,
                started_at=details.lection.started_at,
                ended_at=details.lection.ended_at,
                questions_count=len(details.questions),
                has_presentation=details.has_presentation,
                has_recording=details.has_recording,
            ),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_lection_details_buttons()
            ],
        )

    async def render_questions_menu(
        self,
        telegram_id: int,
        lection_id: uuid.UUID,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать меню вопросов лекции."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "questions_menu")
        questions = await self.question_service.get_questions_by_lection(lection_id)
        await self.context_service.set_context(
            telegram_id,
            action="questions_menu",
            step="view",
            data={"lection_id": str(lection_id)},
        )
        question_rows = [(index, question.question_text) for index, question in enumerate(questions, start=1)]
        return ActionResponseSchema(
            message=TelegramMessages.get_questions_list(question_rows),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_questions_menu_buttons()
            ],
        )

    async def render_question_delete_menu(
        self,
        telegram_id: int,
        lection_id: uuid.UUID,
    ) -> ActionResponseSchema:
        """Показать список вопросов для удаления."""
        questions = await self.question_service.get_questions_by_lection(lection_id)
        await self.context_service.set_context(
            telegram_id,
            action="delete_question",
            step="choose_question",
            data={"lection_id": str(lection_id)},
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for question in questions
            for button in [TelegramButtons.create_question_delete_button(question.question_text, str(question.id))]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_back_button()
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_delete_question_prompt(),
            buttons=buttons,
        )

    async def render_presentation_menu(
        self,
        telegram_id: int,
        lection_id: uuid.UUID,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать меню презентации лекции."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "presentation_menu")
        file_id = await self.manage_files_use_case.get_presentation_file_id(
            lection_id,
            current_admin=await self._require_admin(telegram_id),
        )
        await self.context_service.set_context(
            telegram_id,
            action="presentation_menu",
            step="view",
            data={"lection_id": str(lection_id)},
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_presentation_info(file_id),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_presentation_menu_buttons(file_id is not None)
            ],
        )

    async def render_recording_menu(
        self,
        telegram_id: int,
        lection_id: uuid.UUID,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать меню записи лекции."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "recording_menu")
        file_id = await self.manage_files_use_case.get_recording_file_id(
            lection_id,
            current_admin=await self._require_admin(telegram_id),
        )
        await self.context_service.set_context(
            telegram_id,
            action="recording_menu",
            step="view",
            data={"lection_id": str(lection_id)},
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_recording_info(file_id),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_recording_menu_buttons(file_id is not None)
            ],
        )

    async def render_analytics_courses(
        self,
        telegram_id: int,
        page: int,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать список курсов для аналитики."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "analytics_courses")
        roles = await self.resolve_roles(telegram_id)
        if roles.is_admin:
            courses = await self.course_service.get_courses_for_admin(page=page, page_size=5)
        elif roles.teacher is not None:
            courses = await self.course_service.get_courses_for_teacher(
                teacher_id=roles.teacher.id,
                page=page,
                page_size=5,
            )
        else:
            return ActionResponseSchema(message=TelegramMessages.get_permission_denied())
        await self.context_service.set_context(
            telegram_id,
            action="analytics_courses",
            step="view",
            data={"page": page},
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for course in courses.items
            for button in [TelegramButtons.create_course_button(course.name, str(course.id))]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, courses.total_pages)
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_select_course_for_analytics(),
            buttons=buttons,
        )

    async def render_admin_courses(
        self,
        telegram_id: int,
        page: int,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать список курсов для администратора."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "admin_courses")
        roles = await self.resolve_roles(telegram_id)
        self._require_roles_admin(roles)
        courses = await self.course_service.get_courses_for_admin(page=page, page_size=5)
        await self.context_service.set_context(
            telegram_id,
            action="admin_courses",
            step="view",
            data={"page": page},
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for course in courses.items
            for button in [TelegramButtons.create_admin_course_button(course.name, str(course.id))]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, courses.total_pages)
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_select_course_for_admin(),
            buttons=buttons,
        )

    async def render_admin_course_details(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        page: int,
        push_navigation: bool = False,
        message_prefix: str = "",
    ) -> ActionResponseSchema:
        """Показать карточку курса для администратора."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "admin_course_details")
        roles = await self.resolve_roles(telegram_id)
        self._require_roles_admin(roles)
        course = await self.course_service.get_by_id(course_id)
        await self.context_service.set_context(
            telegram_id,
            action="admin_course_details",
            step="view",
            data={
                "course_id": str(course_id),
                "page": page,
                "course_flow": "existing_course",
            },
        )
        return ActionResponseSchema(
            message=message_prefix + TelegramMessages.get_admin_course_info(
                course.name,
                course.join_code,
            ),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_admin_course_details_buttons()
            ],
        )

    async def render_course_alert_lections(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        page: int,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать список лекций курса для ручной повторной отправки alert."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "course_alert_lections")
        self._require_roles_admin(await self.resolve_roles(telegram_id))
        response = await self.lection_service.get_lections_by_course(
            course_id=course_id,
            page=page,
            page_size=5,
        )
        await self.context_service.set_context(
            telegram_id,
            action="course_alert_lections",
            step="view",
            data={"course_id": str(course_id), "page": page},
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for lection in response.items
            for button in [
                TelegramButtons.create_course_alert_lection_button(lection.topic, str(lection.id))
            ]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, response.total_pages)
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_course_alert_select_lection(),
            buttons=buttons,
        )

    async def render_course_alert_students(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        lection_id: uuid.UUID,
        page: int,
        push_navigation: bool = False,
        message_prefix: str = "",
    ) -> ActionResponseSchema:
        """Показать список студентов для ручной повторной отправки alert."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "course_alert_students")
        self._require_roles_admin(await self.resolve_roles(telegram_id))
        lection = await self.lection_service.get_by_id(lection_id)
        response = await self.student_service.get_students_by_course(
            course_id=course_id,
            page=page,
            page_size=5,
        )
        await self.context_service.set_context(
            telegram_id,
            action="course_alert_students",
            step="view",
            data={
                "course_id": str(course_id),
                "lection_id": str(lection_id),
                "page": page,
            },
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for student in response["items"]
            for button in [
                TelegramButtons.create_course_alert_student_button(
                    student.full_name,
                    str(student.id),
                    student.telegram_username,
                )
            ]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, response["total_pages"])
        )
        return ActionResponseSchema(
            message=message_prefix + TelegramMessages.get_course_alert_select_student(lection.topic),
            buttons=buttons,
        )

    async def render_analytics_course_menu(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать меню аналитики выбранного курса."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "analytics_course_menu")
        course = await self.course_service.get_by_id(course_id)
        await self.context_service.set_context(
            telegram_id,
            action="analytics_course_menu",
            step="view",
            data={"course_id": str(course_id), "page": 1},
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_course_analytics_menu(course.name),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_analytics_course_menu_buttons()
            ],
        )

    async def render_analytics_lection_list(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        page: int,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать список лекций курса для аналитики."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "analytics_lection_list")
        response = await self.lection_service.get_lections_by_course(course_id=course_id, page=page, page_size=5)
        await self.context_service.set_context(
            telegram_id,
            action="analytics_lection_list",
            step="view",
            data={"course_id": str(course_id), "page": page},
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for lection in response.items
            for button in [TelegramButtons.create_lection_button(lection.topic, str(lection.id))]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, response.total_pages)
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_select_lection_for_analytics(),
            buttons=buttons,
        )

    async def render_analytics_lection_statistics(
        self,
        telegram_id: int,
        lection_id: uuid.UUID,
        page: int,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать статистику по лекции и список студентов с рефлексиями."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "analytics_lection_statistics")
        roles = await self.resolve_roles(telegram_id)
        statistics = await self.view_lection_analytics_use_case(
            lection_id=lection_id,
            current_admin=roles.admin,
            current_teacher=roles.teacher,
        )
        sorted_students = sorted(
            statistics.students_with_reflections,
            key=lambda student: (student.full_name.casefold(), str(student.id)),
        )
        pagination = self.pagination_service.paginate(sorted_students, page, 5)
        await self.context_service.set_context(
            telegram_id,
            action="analytics_lection_statistics",
            step="view",
            data={
                "course_id": str(statistics.lection.course_session_id),
                "lection_id": str(lection_id),
                "page": page,
            },
        )
        buttons = [
            TelegramButtonSchema(
                text=TelegramButtons.create_student_button(
                    student.full_name,
                    str(student.id),
                    student.telegram_username,
                ).text,
                action=f"{TelegramButtons.ANALYTICS_VIEW_REFLECTION}:{student.id}",
            )
            for student in pagination["items"]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, pagination["total_pages"])
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_lection_statistics(
                topic=statistics.lection.topic,
                started_at=statistics.lection.started_at,
                total_students=statistics.total_students,
                reflections_count=statistics.reflections_count,
                qa_count=statistics.qa_count,
            ),
            buttons=buttons,
        )

    async def render_analytics_student_list(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        page: int,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать список студентов курса."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "analytics_student_list")
        response = await self.student_service.get_students_by_course(course_id=course_id, page=page, page_size=5)
        await self.context_service.set_context(
            telegram_id,
            action="analytics_student_list",
            step="view",
            data={"course_id": str(course_id), "page": page},
        )
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for student in response["items"]
            for button in [
                TelegramButtons.create_student_button(
                    student.full_name,
                    str(student.id),
                    student.telegram_username,
                )
            ]
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_pagination_buttons(page, response["total_pages"])
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_select_student_for_analytics(),
            buttons=buttons,
        )

    async def render_student_statistics(
        self,
        telegram_id: int,
        course_id: uuid.UUID,
        student_id: uuid.UUID,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать статистику студента по курсу."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "student_statistics")
        roles = await self.resolve_roles(telegram_id)
        statistics = await self.view_student_analytics_use_case(
            student_id=student_id,
            course_id=course_id,
            current_admin=roles.admin,
            current_teacher=roles.teacher,
        )
        await self.context_service.set_context(
            telegram_id,
            action="student_statistics",
            step="view",
            data={"course_id": str(course_id), "student_id": str(student_id)},
        )
        buttons = [
            TelegramButtonSchema(
                text=f"📝 {lection.topic}",
                action=f"{TelegramButtons.ANALYTICS_VIEW_REFLECTION}:{lection.id}",
            )
            for lection in statistics.lections_with_reflections
        ]
        buttons.extend(
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_back_button()
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_student_statistics(
                student_name=statistics.student.full_name,
                telegram_username=statistics.student.telegram_username,
                total_lections=statistics.total_lections,
                reflections_count=statistics.reflections_count,
                qa_count=statistics.qa_count,
            ),
            buttons=buttons,
        )

    async def render_reflection_details(
        self,
        telegram_id: int,
        student_id: uuid.UUID,
        lection_id: uuid.UUID,
        push_navigation: bool = False,
    ) -> ActionResponseSchema:
        """Показать детали рефлексии студента."""
        if push_navigation:
            await self.context_service.push_navigation(telegram_id, "reflection_details")
        roles = await self.resolve_roles(telegram_id)
        details = await self.view_reflection_details_use_case(
            student_id=student_id,
            lection_id=lection_id,
            current_admin=roles.admin,
            current_teacher=roles.teacher,
        )
        student = await self.student_service.get_by_id(student_id)
        lection = await self.lection_service.get_by_id(lection_id)
        message = TelegramMessages.get_reflection_details(
            student_name=student.full_name,
            telegram_username=student.telegram_username,
            lection_topic=lection.topic,
            created_at=details.reflection.submitted_at,
        )
        dialog_messages = [
            TelegramDialogMessageSchema(
                files=[
                    TelegramFileReferenceSchema(
                        telegram_file_id=video.file_id,
                        kind="reflection_video",
                    )
                ],
            )
            for video in details.reflection_videos
        ]
        for qa in details.qa_list:
            dialog_messages.append(
                TelegramDialogMessageSchema(
                    message=f"❓ <b>Вопрос</b>\n\n{qa.question.question_text}",
                )
            )
            dialog_messages.extend(
                TelegramDialogMessageSchema(
                    files=[
                        TelegramFileReferenceSchema(
                            telegram_file_id=video.file_id,
                            kind="qa_video",
                        )
                    ],
                )
                for video in qa.qa_videos
            )
        dialog_messages.append(
            TelegramDialogMessageSchema(
                message=TelegramMessages.get_next_actions_prompt(),
                buttons=[
                    TelegramButtonSchema(text=button.text, action=button.action, url=button.url)
                    for button in TelegramButtons.get_login_buttons(
                        is_admin=roles.admin is not None,
                        is_teacher=roles.teacher is not None,
                        is_student=roles.student is not None,
                    )
                ],
            )
        )
        await self.context_service.set_context(
            telegram_id,
            action="reflection_details",
            step="view",
            data={"student_id": str(student_id), "lection_id": str(lection_id), "course_id": str(lection.course_session_id)},
        )
        return ActionResponseSchema(
            message=message,
            dialog_messages=dialog_messages,
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
        )

    async def render_student_reflection_prompt(
        self,
        context_data: dict,
    ) -> ActionResponseSchema:
        """Показать студенту стартовый prompt рефлексии по лекции."""
        deadline_raw = context_data.get("lection_deadline")
        deadline = (
            datetime.fromisoformat(deadline_raw)
            if isinstance(deadline_raw, str)
            else deadline_raw
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_reflection_prompt_request(
                context_data["lection_topic"],
                deadline,
            ),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_reflection_prompt_buttons(
                    str(context_data["lection_id"])
                )
            ],
        )

    async def render_student_reflection_status(
        self,
        status_data: dict,
    ) -> ActionResponseSchema:
        """Показать студенту текущий статус записи рефлексии по лекции."""
        deadline_raw = status_data.get("lection_deadline")
        deadline = (
            datetime.fromisoformat(deadline_raw)
            if isinstance(deadline_raw, str)
            else deadline_raw
        )
        recorded_videos_count = int(status_data.get("recorded_videos_count", 0))
        deadline_active = bool(status_data.get("deadline_active"))

        if deadline_active:
            message = TelegramMessages.get_reflection_status_active(
                str(status_data["lection_topic"]),
                deadline,
                recorded_videos_count,
            )
        elif recorded_videos_count > 0:
            message = TelegramMessages.get_reflection_status_expired(
                str(status_data["lection_topic"]),
                deadline,
                recorded_videos_count,
            )
        else:
            message = TelegramMessages.get_reflection_status_expired_without_videos(
                str(status_data["lection_topic"]),
                deadline,
            )

        message_tracking = None
        if deadline_active and self.telegram_tracked_message_service is not None:
            message_tracking = TelegramMessageTrackingSchema(
                tracking_key=self.telegram_tracked_message_service.build_reflection_status_tracking_key(
                    str(status_data["lection_id"])
                )
            )

        return ActionResponseSchema(
            message=message,
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action, url=button.url)
                for button in TelegramButtons.get_reflection_status_buttons(
                    str(status_data["lection_id"]),
                    deadline_active=deadline_active,
                )
            ],
            message_tracking=message_tracking,
        )

    async def render_student_question_prompt(
        self,
        context_data: dict,
    ) -> ActionResponseSchema:
        """Показать студенту вопрос и сразу ожидать загрузку кружка/видео."""
        question = self.reflection_workflow_service.get_current_question(context_data)
        if question is None:
            return ActionResponseSchema(
                message=TelegramMessages.get_questions_completed_message(),
            )
        current_index = int(context_data.get("current_question_index", 0)) + 1
        total = len(list(context_data.get("questions", [])))
        return ActionResponseSchema(
            message=TelegramMessages.get_question_reflection_prompt(
                question["text"],
                current_index,
                total,
            ),
            awaiting_input=True,
        )

    async def render_student_question_selection(
        self,
        context_data: dict,
    ) -> ActionResponseSchema:
        """Показать студенту список вопросов для выбора одного ответа."""
        questions = context_data.get("questions", [])
        return ActionResponseSchema(
            message=TelegramMessages.get_question_selection_prompt(questions),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in [
                    TelegramButtons.create_question_selection_button(
                        str(question["id"]),
                        str(question["text"]),
                        index,
                    )
                    for index, question in enumerate(questions, start=1)
                ]
            ],
        )

    async def render_student_video_review(
        self,
        context_data: dict,
        message: str,
    ) -> ActionResponseSchema:
        """Показать студенту действия после записи/удаления кружка."""
        buttons_factory = (
            TelegramButtons.get_question_review_buttons
            if context_data.get("stage") == "question"
            else TelegramButtons.get_reflection_review_buttons
        )
        return ActionResponseSchema(
            message=message,
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in buttons_factory()
            ],
        )

    async def _start_create_admin(self, telegram_id: int, roles: ResolvedRoles) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.CREATE_ADMIN_FULLNAME_SCREEN)
        await self.context_service.set_context(telegram_id, action="create_admin", step="awaiting_fullname")
        return ActionResponseSchema(
            message=TelegramMessages.get_create_admin_request_fullname(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _start_student_reflection(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        lection_id: uuid.UUID,
    ) -> ActionResponseSchema:
        student = self._require_roles_student(roles)
        status = await self.reflection_workflow_service.get_reflection_status(
            student.id,
            lection_id,
        )
        if (not status.get("deadline_active")) or status.get("recorded_videos_count", 0) > 0:
            return await self.render_student_reflection_status(status)

        data = await self.reflection_workflow_service.start_workflow(student.id, lection_id)
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="awaiting_reflection_video",
            data=data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_reflection_recording_request(),
            awaiting_input=True,
        )

    async def _resume_student_reflection_upload(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        lection_id: uuid.UUID,
    ) -> ActionResponseSchema:
        """Разрешить студенту дозаписать кружок/видео в уже существующую рефлексию."""
        student = self._require_roles_student(roles)
        status = await self.reflection_workflow_service.get_reflection_status(
            student.id,
            lection_id,
        )
        if not status.get("deadline_active"):
            return await self.render_student_reflection_status(status)
        data = await self.reflection_workflow_service.start_workflow(student.id, lection_id)
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="awaiting_reflection_video",
            data=data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_reflection_recording_request(),
            awaiting_input=True,
        )

    async def _start_join_course(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
    ) -> ActionResponseSchema:
        """Запустить сценарий записи студента на курс по коду."""
        student = self._require_roles_student(roles)
        await self.context_service.set_context(
            telegram_id,
            action="join_course",
            step="awaiting_course_code",
            data={
                "student_id": str(student.id),
                "telegram_username": student.telegram_username,
                "telegram_id": telegram_id,
            },
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_join_course_code_request(),
            awaiting_input=True,
        )

    async def _request_student_reflection_video(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        student = self._require_roles_student(roles)
        status = await self.reflection_workflow_service.get_reflection_status(
            student.id,
            uuid.UUID(str(context_data["lection_id"])),
        )
        if not status.get("deadline_active"):
            return await self.render_student_reflection_status(status)
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="awaiting_reflection_video",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_reflection_recording_request(),
            awaiting_input=True,
        )

    async def _submit_student_reflection(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        student = self._require_roles_student(roles)
        updated_data = await self.reflection_workflow_service.submit_reflection(
            student.id,
            context_data,
        )
        if not updated_data.get("questions"):
            await self.context_service.clear_context(telegram_id)
            return await self.render_student_reflection_status(
                await self.reflection_workflow_service.get_reflection_status(
                    student.id,
                    uuid.UUID(str(updated_data["lection_id"])),
                )
            )
        if self.reflection_workflow_service.should_select_single_question(updated_data):
            await self.context_service.set_context(
                telegram_id,
                action="student_reflection_workflow",
                step="question_select",
                data=updated_data,
            )
            return await self.render_student_question_selection(updated_data)
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="question_prompt",
            data=updated_data,
        )
        return await self.render_student_question_prompt(updated_data)

    async def _select_student_question(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
        question_id: uuid.UUID,
    ) -> ActionResponseSchema:
        """Сохранить выбранный вопрос и перевести студента к записи ответа."""
        student = self._require_roles_student(roles)
        status = await self.reflection_workflow_service.get_reflection_status(
            student.id,
            uuid.UUID(str(context_data["lection_id"])),
        )
        if not status.get("deadline_active"):
            await self.context_service.clear_context(telegram_id)
            return await self.render_student_reflection_status(status)
        updated_data = self.reflection_workflow_service.select_single_question(
            context_data,
            question_id,
        )
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="question_prompt",
            data=updated_data,
        )
        return await self.render_student_question_prompt(updated_data)

    async def _delete_student_reflection_video(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        self._require_roles_student(roles)
        updated_data = self.reflection_workflow_service.remove_last_video_from_draft(context_data)
        if self.reflection_workflow_service.get_current_video_count(updated_data) == 0:
            await self.context_service.set_context(
                telegram_id,
                action="student_reflection_workflow",
                step="reflection_prompt",
                data=updated_data,
            )
            return await self.render_student_reflection_prompt(updated_data)
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="review_reflection_videos",
            data=updated_data,
        )
        return await self.render_student_video_review(
            updated_data,
            TelegramMessages.get_reflection_video_deleted(),
        )

    async def _request_student_question_video(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        student = self._require_roles_student(roles)
        status = await self.reflection_workflow_service.get_reflection_status(
            student.id,
            uuid.UUID(str(context_data["lection_id"])),
        )
        if not status.get("deadline_active"):
            await self.context_service.clear_context(telegram_id)
            return await self.render_student_reflection_status(status)
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="awaiting_question_video",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_reflection_recording_request(),
            awaiting_input=True,
        )

    async def _submit_student_question(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        student = self._require_roles_student(roles)
        if self.reflection_workflow_service.get_current_question(context_data) is None:
            await self.context_service.clear_context(telegram_id)
            return await self.render_student_reflection_status(
                await self.reflection_workflow_service.get_reflection_status(
                    student.id,
                    uuid.UUID(str(context_data["lection_id"])),
                )
            )
        updated_data = await self.reflection_workflow_service.submit_question_answer(context_data)
        if self.reflection_workflow_service.get_current_question(updated_data) is None:
            await self.reflection_workflow_service.finalize_question_answers(updated_data)
            await self.context_service.clear_context(telegram_id)
            return await self.render_student_reflection_status(
                await self.reflection_workflow_service.get_reflection_status(
                    student.id,
                    uuid.UUID(str(updated_data["lection_id"])),
                )
            )
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="question_prompt",
            data=updated_data,
        )
        return await self.render_student_question_prompt(updated_data)

    async def _delete_student_question_video(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        self._require_roles_student(roles)
        updated_data = self.reflection_workflow_service.remove_last_video_from_draft(context_data)
        if self.reflection_workflow_service.get_current_video_count(updated_data) == 0:
            await self.context_service.set_context(
                telegram_id,
                action="student_reflection_workflow",
                step="question_prompt",
                data=updated_data,
            )
            return await self.render_student_question_prompt(updated_data)
        await self.context_service.set_context(
            telegram_id,
            action="student_reflection_workflow",
            step="review_question_videos",
            data=updated_data,
        )
        return await self.render_student_video_review(
            updated_data,
            TelegramMessages.get_reflection_video_deleted(),
        )

    async def _start_create_course(self, telegram_id: int, roles: ResolvedRoles) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.set_context(
            telegram_id,
            action="create_course",
            step="awaiting_course_name",
            data={},
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_create_course_request_name(),
            awaiting_input=True,
        )

    async def _start_append_course_lections(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        """Запустить сценарий догрузки лекций в существующий курс."""
        self._require_roles_admin(roles)
        await self.context_service.set_context(
            telegram_id,
            action="append_course_lections",
            step="awaiting_course_file",
            data={
                "course_id": str(context_data["course_id"]),
                "page": int(context_data.get("page", 1)),
            },
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_append_course_request_file(),
            awaiting_input=True,
        )

    async def _confirm_appended_course_lections(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        """Подтвердить догрузку новых лекций и привязать их к участникам курса."""
        self._require_roles_admin(roles)
        course_id = uuid.UUID(str(context_data["course_id"]))
        appended_lection_ids = [
            uuid.UUID(str(lection_id))
            for lection_id in context_data.get("appended_lection_ids", [])
        ]
        if not appended_lection_ids:
            return await self.render_admin_course_details(
                telegram_id,
                course_id,
                page=int(context_data.get("page", 1)),
            )

        students_response = await self.student_service.get_students_by_course(
            course_id=course_id,
            page=1,
            page_size=10_000,
        )
        await self.student_service.attach_to_lections(
            student_ids=[student.id for student in students_response["items"]],
            lection_ids=appended_lection_ids,
        )
        teacher_ids = await self.teacher_service.get_teacher_ids_by_course(course_id)
        for teacher_id in teacher_ids:
            await self.teacher_service.attach_to_lections(
                teacher_id=teacher_id,
                lection_ids=appended_lection_ids,
            )

        await self.context_service.clear_context(telegram_id)
        return await self.render_admin_course_details(
            telegram_id,
            course_id,
            page=int(context_data.get("page", 1)),
            message_prefix=TelegramMessages.get_course_appended_success(len(appended_lection_ids)),
        )

    async def _start_course_broadcast_message(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        """Запустить сценарий ввода текста сообщения для студентов курса."""
        self._require_roles_admin(roles)
        await self.context_service.set_context(
            telegram_id,
            action="course_broadcast_message",
            step="awaiting_message_text",
            data={
                "course_id": str(context_data["course_id"]),
                "page": int(context_data.get("page", 1)),
            },
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_course_broadcast_request_text(),
            awaiting_input=True,
        )

    async def _send_course_reflection_alert(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
        student_id: uuid.UUID,
    ) -> ActionResponseSchema:
        """Повторно отправить студенту alert по выбранной лекции."""
        current_admin = self._require_roles_admin(roles)
        if self.send_course_reflection_alert_use_case is None:
            raise PermissionDeniedError("Сценарий повторной отправки alert сейчас недоступен.")

        course_id = uuid.UUID(str(context_data["course_id"]))
        lection_id = uuid.UUID(str(context_data["lection_id"]))
        page = int(context_data.get("page", 1))
        student = await self.student_service.get_by_id(student_id)
        lection = await self.lection_service.get_by_id(lection_id)

        await self.send_course_reflection_alert_use_case(
            course_id=course_id,
            lection_id=lection_id,
            student_id=student_id,
            current_admin=current_admin,
        )
        return await self.render_course_alert_students(
            telegram_id,
            course_id=course_id,
            lection_id=lection_id,
            page=page,
            message_prefix=TelegramMessages.get_course_alert_sent(
                student.full_name,
                lection.topic,
            ),
        )

    async def _start_attach_teacher(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.ATTACH_TEACHER_FULLNAME_SCREEN)
        next_context_data = dict(context_data)
        next_context_data.pop("fullname", None)
        await self.context_service.set_context(
            telegram_id,
            action="attach_teacher",
            step="awaiting_fullname",
            data=next_context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_attach_teacher_request_fullname(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _start_attach_students(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.set_context(
            telegram_id,
            action="attach_students",
            step="awaiting_file",
            data={"course_id": context_data["course_id"]},
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_attach_students_request_file(),
            awaiting_input=True,
        )

    async def _add_default_questions_to_course(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        course_id = uuid.UUID(str(context_data["course_id"]))
        appended_lection_ids = [
            uuid.UUID(str(lection_id))
            for lection_id in context_data.get("appended_lection_ids", [])
        ]
        lection_ids = appended_lection_ids or await self.lection_service.get_lection_ids_by_course(course_id)
        for lection_id in lection_ids:
            existing_questions = await self.question_service.get_questions_by_lection(lection_id)
            if existing_questions:
                continue
            question_text = await self.default_question_service.get_random_question_text()
            await self.question_service.create_question(lection_id, question_text)
        if appended_lection_ids:
            return await self.render_append_course_menu(
                telegram_id,
                course_id,
                page=int(context_data.get("page", 1)),
                appended_lection_ids=[str(lection_id) for lection_id in appended_lection_ids],
                message_prefix=TelegramMessages.get_default_questions_added(),
            )
        await self.context_service.set_context(
            telegram_id,
            action="course_menu",
            step="view",
            data={"course_id": str(course_id), "page": 1},
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_default_questions_added(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_course_menu_buttons(
                    show_add_default_questions=False
                )
            ],
        )

    async def _finish_course_creation(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context_data: dict,
    ) -> ActionResponseSchema:
        """Завершить создание курса и вернуть главное меню по ролям."""
        self._require_roles_admin(roles)
        course_id = uuid.UUID(str(context_data["course_id"]))
        course = await self.course_service.get_by_id(course_id)
        await self.context_service.clear_context(telegram_id)
        return await self.build_main_menu_response(
            telegram_id,
            TelegramMessages.get_course_created_success(
                course.name,
                course.started_at,
                course.ended_at,
                course.join_code,
            ),
        )

    async def _course_has_lections_without_questions(self, course_id: uuid.UUID) -> bool:
        """Проверить, есть ли у курса лекции без вопросов."""
        lection_ids = await self.lection_service.get_lection_ids_by_course(course_id)
        return await self._lections_have_missing_questions(lection_ids)

    async def _lections_have_missing_questions(self, lection_ids: list[uuid.UUID]) -> bool:
        """Проверить, есть ли среди переданных лекций лекции без вопросов."""
        for lection_id in lection_ids:
            questions = await self.question_service.get_questions_by_lection(lection_id)
            if not questions:
                return True
        return False

    async def _cancel_course(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        appended_lection_ids = [
            uuid.UUID(str(lection_id))
            for lection_id in context_data.get("appended_lection_ids", [])
        ]
        if appended_lection_ids:
            deleted_count = await self.course_service.delete_lections_from_course(
                uuid.UUID(str(context_data["course_id"])),
                appended_lection_ids,
            )
            await self.context_service.clear_context(telegram_id)
            return await self.render_admin_course_details(
                telegram_id,
                uuid.UUID(str(context_data["course_id"])),
                page=int(context_data.get("page", 1)),
                message_prefix=TelegramMessages.get_course_append_cancelled(deleted_count),
            )
        await self.course_service.delete_course(uuid.UUID(str(context_data["course_id"])))
        await self.context_service.clear_context(telegram_id)
        return await self.build_main_menu_response(
            telegram_id,
            message=TelegramMessages.get_course_cancelled(),
        )

    async def _request_lection_topic_edit(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.EDIT_LECTION_TOPIC_SCREEN)
        await self.context_service.set_context(
            telegram_id,
            action="edit_lection_topic",
            step="awaiting_topic",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_edit_lection_topic_request(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _request_lection_date_edit(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.EDIT_LECTION_DATE_SCREEN)
        await self.context_service.set_context(
            telegram_id,
            action="edit_lection_date",
            step="awaiting_datetime",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_edit_lection_date_request(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _request_add_question(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.ADD_QUESTION_SCREEN)
        await self.context_service.set_context(
            telegram_id,
            action="add_question",
            step="awaiting_question_text",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_add_question_request(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _request_edit_question(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.EDIT_QUESTION_SCREEN)
        await self.context_service.set_context(
            telegram_id,
            action="edit_question",
            step="awaiting_question_update",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_edit_question_request(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _delete_question(self, telegram_id: int, roles: ResolvedRoles, question_id: uuid.UUID) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        question = await self.question_service.get_question(question_id)
        await self.question_service.delete_question(question_id)
        return await self.render_questions_menu(telegram_id, question.lection_session_id)

    async def _request_presentation_upload(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.PRESENTATION_UPLOAD_SCREEN)
        await self.context_service.set_context(
            telegram_id,
            action="edit_lection_presentation",
            step="awaiting_file",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_upload_presentation_request(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _download_presentation(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        current_admin = self._require_roles_admin(roles)
        lection_id = uuid.UUID(str(context_data["lection_id"]))
        telegram_file_id = await self.manage_files_use_case.get_presentation_telegram_file_id(
            lection_id,
            current_admin=current_admin,
        )
        menu = await self.render_presentation_menu(telegram_id, lection_id)
        menu.message = f"{menu.message}\n\n📤 Файл готов к отправке ботом."
        menu.files = [
            TelegramFileReferenceSchema(
                telegram_file_id=telegram_file_id,
                kind="presentation",
            )
        ]
        return menu

    async def _request_recording_upload(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        self._require_roles_admin(roles)
        await self.context_service.push_navigation(telegram_id, self.RECORDING_UPLOAD_SCREEN)
        await self.context_service.set_context(
            telegram_id,
            action="edit_lection_recording",
            step="awaiting_file",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_upload_recording_request(),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _download_recording(self, telegram_id: int, roles: ResolvedRoles, context_data: dict) -> ActionResponseSchema:
        current_admin = self._require_roles_admin(roles)
        lection_id = uuid.UUID(str(context_data["lection_id"]))
        telegram_file_id = await self.manage_files_use_case.get_recording_telegram_file_id(
            lection_id,
            current_admin=current_admin,
        )
        menu = await self.render_recording_menu(telegram_id, lection_id)
        menu.message = f"{menu.message}\n\n📤 Файл готов к отправке ботом."
        menu.files = [
            TelegramFileReferenceSchema(
                telegram_file_id=telegram_file_id,
                kind="recording",
            )
        ]
        return menu

    async def _show_nearest_lection(self, telegram_id: int, roles: ResolvedRoles) -> ActionResponseSchema:
        if roles.is_admin:
            lection = await self.lection_service.get_nearest_lection()
        elif roles.teacher is not None:
            lection = await self.lection_service.get_nearest_lection_for_teacher(roles.teacher.id)
        else:
            return ActionResponseSchema(message=TelegramMessages.get_permission_denied())
        if lection is None:
            return ActionResponseSchema(message=TelegramMessages.get_no_upcoming_lections())
        await self.context_service.push_navigation(telegram_id, self.TEACHER_NEAREST_LECTION_SCREEN)
        await self.context_service.set_context(
            telegram_id,
            action="teacher_nearest_lection",
            step="view",
            data={
                "lection_id": str(lection.id),
                "course_id": str(lection.course_session_id),
            },
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_nearest_lection_info(
                lection.topic,
                lection.started_at,
                lection.ended_at,
            ),
            buttons=[
                TelegramButtonSchema(text=button.text, action=button.action)
                for button in TelegramButtons.get_back_button()
            ],
        )

    async def _paginate(
        self,
        telegram_id: int,
        roles: ResolvedRoles,
        context: dict,
        delta: int,
    ) -> ActionResponseSchema:
        data = context.get("data", {})
        page = max(1, int(data.get("page", 1)) + delta)
        action = context.get("action")
        if action == "parsed_lections":
            return await self.render_parsed_lections(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                page,
                extra_data={
                    key: value
                    for key, value in data.items()
                    if key not in {"course_id", "page"}
                },
            )
        if action == "course_alert_lections":
            return await self.render_course_alert_lections(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                page,
            )
        if action == "course_alert_students":
            return await self.render_course_alert_students(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                uuid.UUID(str(data["lection_id"])),
                page,
            )
        if action == "admin_courses":
            return await self.render_admin_courses(telegram_id, page)
        if action == "analytics_courses":
            return await self.render_analytics_courses(telegram_id, page)
        if action == "analytics_lection_list":
            return await self.render_analytics_lection_list(telegram_id, uuid.UUID(str(data["course_id"])), page)
        if action == "analytics_student_list":
            return await self.render_analytics_student_list(telegram_id, uuid.UUID(str(data["course_id"])), page)
        if action == "analytics_lection_statistics":
            return await self.render_analytics_lection_statistics(telegram_id, uuid.UUID(str(data["lection_id"])), page)
        support_button = TelegramButtons.create_support_button()
        return ActionResponseSchema(
            message=TelegramMessages.get_unknown_context_action(),
            buttons=[
                TelegramButtonSchema(
                    text=support_button.text,
                    action=support_button.action,
                    url=support_button.url,
                )
            ],
        )

    async def _render_reflection_details_from_context(
        self,
        telegram_id: int,
        context: dict,
        selected_entity_id: uuid.UUID,
    ) -> ActionResponseSchema:
        """Показать детали рефлексии, восстанавливая недостающий идентификатор из контекста."""
        context_data = context.get("data", {})
        context_action = context.get("action")

        if context_action == "student_statistics":
            return await self.render_reflection_details(
                telegram_id,
                uuid.UUID(str(context_data["student_id"])),
                selected_entity_id,
                push_navigation=True,
            )

        if context_action == "analytics_lection_statistics":
            return await self.render_reflection_details(
                telegram_id,
                selected_entity_id,
                uuid.UUID(str(context_data["lection_id"])),
                push_navigation=True,
            )

        return ActionResponseSchema(
            message=TelegramMessages.get_unknown_action(
                f"{TelegramButtons.ANALYTICS_VIEW_REFLECTION}:{selected_entity_id}"
            )
        )

    async def _go_back(self, telegram_id: int) -> ActionResponseSchema:
        previous_screen = await self.context_service.pop_navigation(telegram_id)
        if previous_screen is None:
            await self.context_service.clear_context(telegram_id)
            return await self.build_main_menu_response(telegram_id)

        context = await self.context_service.get_context(telegram_id) or {}
        data = context.get("data", {})
        if previous_screen == "course_menu":
            return await self.render_course_menu(telegram_id, uuid.UUID(str(data["course_id"])))
        if previous_screen == "append_course_menu":
            return await self.render_append_course_menu(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                int(data.get("page", 1)),
                list(data.get("appended_lection_ids", [])),
            )
        if previous_screen == "parsed_lections":
            return await self.render_parsed_lections(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                int(data.get("page", 1)),
                extra_data={
                    key: value
                    for key, value in data.items()
                    if key not in {"course_id", "page"}
                },
            )
        if previous_screen == "course_alert_lections":
            return await self.render_course_alert_lections(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                int(data.get("page", 1)),
            )
        if previous_screen == "course_alert_students":
            return await self.render_course_alert_students(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                uuid.UUID(str(data["lection_id"])),
                int(data.get("page", 1)),
            )
        if previous_screen == "admin_courses":
            return await self.render_admin_courses(telegram_id, int(data.get("page", 1)))
        if previous_screen == "admin_course_details":
            return await self.render_admin_course_details(
                telegram_id,
                uuid.UUID(str(data["course_id"])),
                int(data.get("page", 1)),
            )
        if previous_screen == "lection_details":
            return await self.render_lection_details(telegram_id, uuid.UUID(str(data["lection_id"])), data.get("course_id"))
        if previous_screen == self.CREATE_ADMIN_FULLNAME_SCREEN:
            await self.context_service.set_context(
                telegram_id,
                action="create_admin",
                step="awaiting_fullname",
            )
            return ActionResponseSchema(
                message=TelegramMessages.get_create_admin_request_fullname(),
                buttons=[
                    TelegramButtonSchema(text=button.text, action=button.action)
                    for button in TelegramButtons.get_back_button()
                ],
                awaiting_input=True,
            )
        if previous_screen == self.ATTACH_TEACHER_FULLNAME_SCREEN:
            restored_data = dict(data)
            restored_data.pop("fullname", None)
            await self.context_service.set_context(
                telegram_id,
                action="attach_teacher",
                step="awaiting_fullname",
                data=restored_data,
            )
            return ActionResponseSchema(
                message=TelegramMessages.get_attach_teacher_request_fullname(),
                buttons=[
                    TelegramButtonSchema(text=button.text, action=button.action)
                    for button in TelegramButtons.get_back_button()
                ],
                awaiting_input=True,
            )
        if previous_screen == "questions_menu":
            return await self.render_questions_menu(telegram_id, uuid.UUID(str(data["lection_id"])))
        if previous_screen == "presentation_menu":
            return await self.render_presentation_menu(telegram_id, uuid.UUID(str(data["lection_id"])))
        if previous_screen == "recording_menu":
            return await self.render_recording_menu(telegram_id, uuid.UUID(str(data["lection_id"])))
        if previous_screen == "analytics_courses":
            return await self.render_analytics_courses(telegram_id, int(data.get("page", 1)))
        if previous_screen == "analytics_course_menu":
            return await self.render_analytics_course_menu(telegram_id, uuid.UUID(str(data["course_id"])))
        if previous_screen == "analytics_lection_list":
            return await self.render_analytics_lection_list(telegram_id, uuid.UUID(str(data["course_id"])), int(data.get("page", 1)))
        if previous_screen == "analytics_student_list":
            return await self.render_analytics_student_list(telegram_id, uuid.UUID(str(data["course_id"])), int(data.get("page", 1)))
        if previous_screen == "analytics_lection_statistics":
            return await self.render_analytics_lection_statistics(telegram_id, uuid.UUID(str(data["lection_id"])), int(data.get("page", 1)))
        if previous_screen == "student_statistics":
            return await self.render_student_statistics(telegram_id, uuid.UUID(str(data["course_id"])), uuid.UUID(str(data["student_id"])))
        if previous_screen == self.TEACHER_NEAREST_LECTION_SCREEN:
            roles = await self.resolve_roles(telegram_id)
            return await self._show_nearest_lection(telegram_id, roles)
        return await self.build_main_menu_response(telegram_id)

    async def _require_admin(self, telegram_id: int) -> AdminReadSchema:
        roles = await self.resolve_roles(telegram_id)
        return self._require_roles_admin(roles)

    def _require_roles_admin(self, roles: ResolvedRoles) -> AdminReadSchema:
        if roles.admin is None:
            raise PermissionDeniedError("Недостаточно прав для выполнения действия администратора")
        return roles.admin

    def _require_roles_student(self, roles: ResolvedRoles):
        if roles.student is None:
            raise PermissionDeniedError("Недостаточно прав для выполнения действия студента")
        return roles.student

    async def _log_student_button_action(
        self,
        roles: ResolvedRoles,
        action: str,
    ) -> None:
        """Записать в историю любое callback-действие пользователя со student-role."""
        if roles.student is None or self.student_history_log_service is None:
            return
        await self.student_history_log_service.log_action(roles.student.id, action)
