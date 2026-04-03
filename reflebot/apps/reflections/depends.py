"""
Dependency injection для модуля рефлексий.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from reflebot.core.db import get_async_session
from reflebot.settings import settings
from .repositories.admin import AdminRepository, AdminRepositoryProtocol
from .repositories.student import StudentRepository, StudentRepositoryProtocol
from .repositories.student_course import StudentCourseRepository, StudentCourseRepositoryProtocol
from .repositories.student_history_log import (
    StudentHistoryLogRepository,
    StudentHistoryLogRepositoryProtocol,
)
from .repositories.student_lection import StudentLectionRepository, StudentLectionRepositoryProtocol
from .repositories.teacher import TeacherRepository, TeacherRepositoryProtocol
from .repositories.teacher_lection import TeacherLectionRepository, TeacherLectionRepositoryProtocol
from .repositories.user import UserRepository, UserRepositoryProtocol
from .repositories.course import CourseSessionRepository, CourseSessionRepositoryProtocol
from .repositories.default_question import DefaultQuestionRepository, DefaultQuestionRepositoryProtocol
from .repositories.lection import LectionSessionRepository, LectionSessionRepositoryProtocol
from .repositories.notification_delivery import (
    NotificationDeliveryRepository,
    NotificationDeliveryRepositoryProtocol,
)
from .repositories.reflection import (
    ReflectionWorkflowRepository,
    ReflectionWorkflowRepositoryProtocol,
)
from .repositories.question import QuestionRepository, QuestionRepositoryProtocol
from .repositories.teacher_course import TeacherCourseRepository, TeacherCourseRepositoryProtocol
from .services.admin import AdminService, AdminServiceProtocol
from .services.auth import AuthService, AuthServiceProtocol
from .services.analytics import AnalyticsService, AnalyticsServiceProtocol
from .services.context import ContextService, ContextServiceProtocol
from .services.course import CourseService, CourseServiceProtocol
from .services.course_invite import CourseInviteService, CourseInviteServiceProtocol
from .services.default_question import DefaultQuestionService, DefaultQuestionServiceProtocol
from .services.lection import LectionService, LectionServiceProtocol
from .services.notification_delivery import (
    NotificationDeliveryService,
    NotificationDeliveryServiceProtocol,
)
from .services.notification_delivery_result import (
    NotificationDeliveryResultHandler,
    NotificationDeliveryResultHandlerProtocol,
)
from .services.notification_publisher import (
    NotificationCommandPublisher,
    NotificationCommandPublisherProtocol,
)
from .services.pagination import PaginationService, PaginationServiceProtocol
from .services.question import QuestionService, QuestionServiceProtocol
from .services.reflection import ReflectionWorkflowService, ReflectionWorkflowServiceProtocol
from .services.reflection_prompt_message import (
    ReflectionPromptMessageService,
    ReflectionPromptMessageServiceProtocol,
)
from .services.reflection_prompt_scan import (
    ReflectionPromptScanService,
    ReflectionPromptScanServiceProtocol,
)
from .services.student import StudentService, StudentServiceProtocol
from .services.student_history_log import StudentHistoryLogService, StudentHistoryLogServiceProtocol
from .services.teacher import TeacherService, TeacherServiceProtocol
from .parsers.course_excel import CourseExcelParser
from .parsers.student_csv import StudentCSVParser
from .parsers.base import FileParserProtocol
from .use_cases.admin import (
    CreateAdminUseCase,
    CreateAdminUseCaseProtocol,
    AdminLoginUseCase,
    AdminLoginUseCaseProtocol,
)
from .use_cases.course import (
    AttachStudentsToCourseUseCase,
    AttachStudentsToCourseUseCaseProtocol,
    AttachTeachersToCourseUseCase,
    AttachTeachersToCourseUseCaseProtocol,
    CreateCourseFromExcelUseCase,
    CreateCourseFromExcelUseCaseProtocol,
)
from .use_cases.lection import (
    ManageFilesUseCase,
    ManageFilesUseCaseProtocol,
    ManageQuestionsUseCase,
    ManageQuestionsUseCaseProtocol,
    UpdateLectionUseCase,
    UpdateLectionUseCaseProtocol,
)
from .use_cases.analytics import (
    ViewLectionAnalyticsUseCase,
    ViewLectionAnalyticsUseCaseProtocol,
    ViewReflectionDetailsUseCase,
    ViewReflectionDetailsUseCaseProtocol,
    ViewStudentAnalyticsUseCase,
    ViewStudentAnalyticsUseCaseProtocol,
)
from .use_cases.notification_delivery import (
    PublishPendingReflectionPromptsUseCase,
    PublishPendingReflectionPromptsUseCaseProtocol,
    RetryFailedReflectionPromptsUseCase,
    RetryFailedReflectionPromptsUseCaseProtocol,
    ScanDueReflectionPromptsUseCase,
    ScanDueReflectionPromptsUseCaseProtocol,
)
from .consumers.delivery_result_consumer import (
    DeliveryResultConsumer,
    DeliveryResultConsumerProtocol,
)
from .handlers.button_handler import ButtonActionHandler, ButtonActionHandlerProtocol
from .handlers.file_handler import FileUploadHandler, FileUploadHandlerProtocol
from .handlers.text_handler import TextInputHandler, TextInputHandlerProtocol


# Repositories

def __get_admin_repository(
    session: AsyncSession = Depends(get_async_session),
) -> AdminRepositoryProtocol:
    """Получить репозиторий администраторов."""
    return AdminRepository(session=session)


def __get_student_repository(
    session: AsyncSession = Depends(get_async_session),
) -> StudentRepositoryProtocol:
    """Получить репозиторий студентов."""
    return StudentRepository(session=session)


def __get_teacher_repository(
    session: AsyncSession = Depends(get_async_session),
) -> TeacherRepositoryProtocol:
    """Получить репозиторий преподавателей."""
    return TeacherRepository(session=session)


def __get_student_course_repository(
    session: AsyncSession = Depends(get_async_session),
) -> StudentCourseRepositoryProtocol:
    """Получить репозиторий привязок студентов к курсам."""
    return StudentCourseRepository(session=session)


def __get_student_history_log_repository(
    session: AsyncSession = Depends(get_async_session),
) -> StudentHistoryLogRepositoryProtocol:
    """Получить репозиторий логов действий студентов."""
    return StudentHistoryLogRepository(session=session)


def __get_student_lection_repository(
    session: AsyncSession = Depends(get_async_session),
) -> StudentLectionRepositoryProtocol:
    """Получить репозиторий привязок студентов к лекциям."""
    return StudentLectionRepository(session=session)


def __get_course_repository(
    session: AsyncSession = Depends(get_async_session),
) -> CourseSessionRepositoryProtocol:
    """Получить репозиторий курсов."""
    return CourseSessionRepository(session=session)


def __get_lection_repository(
    session: AsyncSession = Depends(get_async_session),
) -> LectionSessionRepositoryProtocol:
    """Получить репозиторий лекций."""
    return LectionSessionRepository(session=session)


def __get_default_question_repository(
    session: AsyncSession = Depends(get_async_session),
) -> DefaultQuestionRepositoryProtocol:
    """Получить репозиторий стандартных вопросов."""
    return DefaultQuestionRepository(session=session)


def __get_question_repository(
    session: AsyncSession = Depends(get_async_session),
) -> QuestionRepositoryProtocol:
    """Получить репозиторий вопросов."""
    return QuestionRepository(session=session)


def __get_notification_delivery_repository(
    session: AsyncSession = Depends(get_async_session),
) -> NotificationDeliveryRepositoryProtocol:
    """Получить репозиторий доставок уведомлений."""
    return NotificationDeliveryRepository(session=session)


def __get_reflection_workflow_repository(
    session: AsyncSession = Depends(get_async_session),
) -> ReflectionWorkflowRepositoryProtocol:
    """Получить репозиторий workflow рефлексии студента."""
    return ReflectionWorkflowRepository(session=session)


def __get_user_repository(
    session: AsyncSession = Depends(get_async_session),
) -> UserRepositoryProtocol:
    """Получить репозиторий пользователей."""
    return UserRepository(session=session)


def __get_teacher_course_repository(
    session: AsyncSession = Depends(get_async_session),
) -> TeacherCourseRepositoryProtocol:
    """Получить репозиторий привязок преподавателей к курсам."""
    return TeacherCourseRepository(session=session)


def __get_teacher_lection_repository(
    session: AsyncSession = Depends(get_async_session),
) -> TeacherLectionRepositoryProtocol:
    """Получить репозиторий привязок преподавателей к лекциям."""
    return TeacherLectionRepository(session=session)


# Parsers

def get_course_excel_parser() -> FileParserProtocol:
    """Получить парсер Excel файлов курсов."""
    return CourseExcelParser()


def get_student_csv_parser() -> FileParserProtocol:
    """Получить парсер CSV файлов студентов."""
    return StudentCSVParser()


# Services

def get_admin_service(
    repository: AdminRepositoryProtocol = Depends(__get_admin_repository),
    student_repository: StudentRepositoryProtocol = Depends(__get_student_repository),
    teacher_repository: TeacherRepositoryProtocol = Depends(__get_teacher_repository),
) -> AdminServiceProtocol:
    """Получить сервис администраторов."""
    return AdminService(
        repository=repository,
        student_repository=student_repository,
        teacher_repository=teacher_repository,
    )


def get_course_invite_service() -> CourseInviteServiceProtocol:
    """Получить сервис deep link приглашений на курс."""
    return CourseInviteService(settings=settings)


def get_course_service(
    course_repository: CourseSessionRepositoryProtocol = Depends(__get_course_repository),
    lection_repository: LectionSessionRepositoryProtocol = Depends(__get_lection_repository),
    teacher_course_repository: TeacherCourseRepositoryProtocol = Depends(__get_teacher_course_repository),
) -> CourseServiceProtocol:
    """Получить сервис курсов."""
    return CourseService(
        course_repository=course_repository,
        lection_repository=lection_repository,
        teacher_course_repository=teacher_course_repository,
    )


def get_lection_service(
    lection_repository: LectionSessionRepositoryProtocol = Depends(__get_lection_repository),
    course_repository: CourseSessionRepositoryProtocol = Depends(__get_course_repository),
) -> LectionServiceProtocol:
    """Получить сервис лекций."""
    return LectionService(
        lection_repository=lection_repository,
        course_repository=course_repository,
    )


def get_question_service(
    question_repository: QuestionRepositoryProtocol = Depends(__get_question_repository),
) -> QuestionServiceProtocol:
    """Получить сервис вопросов."""
    return QuestionService(question_repository=question_repository)


def get_default_question_service(
    repository: DefaultQuestionRepositoryProtocol = Depends(__get_default_question_repository),
) -> DefaultQuestionServiceProtocol:
    """Получить сервис стандартных вопросов."""
    return DefaultQuestionService(repository=repository)


def get_teacher_service(
    teacher_repository: TeacherRepositoryProtocol = Depends(__get_teacher_repository),
    teacher_course_repository: TeacherCourseRepositoryProtocol = Depends(__get_teacher_course_repository),
    teacher_lection_repository: TeacherLectionRepositoryProtocol = Depends(__get_teacher_lection_repository),
    admin_repository: AdminRepositoryProtocol = Depends(__get_admin_repository),
    student_repository: StudentRepositoryProtocol = Depends(__get_student_repository),
) -> TeacherServiceProtocol:
    """Получить сервис преподавателей."""
    return TeacherService(
        teacher_repository=teacher_repository,
        teacher_course_repository=teacher_course_repository,
        teacher_lection_repository=teacher_lection_repository,
        admin_repository=admin_repository,
        student_repository=student_repository,
    )


def get_student_service(
    student_repository: StudentRepositoryProtocol = Depends(__get_student_repository),
    student_course_repository: StudentCourseRepositoryProtocol = Depends(__get_student_course_repository),
    student_lection_repository: StudentLectionRepositoryProtocol = Depends(__get_student_lection_repository),
    admin_repository: AdminRepositoryProtocol = Depends(__get_admin_repository),
    teacher_repository: TeacherRepositoryProtocol = Depends(__get_teacher_repository),
) -> StudentServiceProtocol:
    """Получить сервис студентов."""
    return StudentService(
        student_repository=student_repository,
        student_course_repository=student_course_repository,
        student_lection_repository=student_lection_repository,
        admin_repository=admin_repository,
        teacher_repository=teacher_repository,
    )


def get_student_history_log_service(
    repository: StudentHistoryLogRepositoryProtocol = Depends(__get_student_history_log_repository),
) -> StudentHistoryLogServiceProtocol:
    """Получить сервис логов действий студента."""
    return StudentHistoryLogService(repository=repository)


def get_context_service(
    user_repository: UserRepositoryProtocol = Depends(__get_user_repository),
) -> ContextServiceProtocol:
    """Получить сервис контекста."""
    return ContextService(user_repository=user_repository)


def get_auth_service(
    admin_repository: AdminRepositoryProtocol = Depends(__get_admin_repository),
    student_repository: StudentRepositoryProtocol = Depends(__get_student_repository),
    teacher_repository: TeacherRepositoryProtocol = Depends(__get_teacher_repository),
    course_repository: CourseSessionRepositoryProtocol = Depends(__get_course_repository),
    context_service: ContextServiceProtocol = Depends(get_context_service),
    student_service: StudentServiceProtocol = Depends(get_student_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
    course_invite_service: CourseInviteServiceProtocol = Depends(get_course_invite_service),
) -> AuthServiceProtocol:
    """Получить сервис аутентификации."""
    return AuthService(
        admin_repository=admin_repository,
        student_repository=student_repository,
        teacher_repository=teacher_repository,
        course_repository=course_repository,
        context_service=context_service,
        student_service=student_service,
        lection_service=lection_service,
        course_invite_service=course_invite_service,
    )


def get_pagination_service() -> PaginationServiceProtocol:
    """Получить сервис пагинации."""
    return PaginationService()


def get_analytics_service(
    lection_repository: LectionSessionRepositoryProtocol = Depends(__get_lection_repository),
    student_repository: StudentRepositoryProtocol = Depends(__get_student_repository),
) -> AnalyticsServiceProtocol:
    """Получить сервис аналитики."""
    return AnalyticsService(
        lection_repository=lection_repository,
        student_repository=student_repository,
    )


def get_notification_delivery_service(
    repository: NotificationDeliveryRepositoryProtocol = Depends(__get_notification_delivery_repository),
) -> NotificationDeliveryServiceProtocol:
    """Получить сервис доставок уведомлений."""
    return NotificationDeliveryService(repository=repository)


def get_reflection_workflow_service(
    repository: ReflectionWorkflowRepositoryProtocol = Depends(__get_reflection_workflow_repository),
) -> ReflectionWorkflowServiceProtocol:
    """Получить сервис workflow рефлексии студента."""
    return ReflectionWorkflowService(repository=repository)


def get_reflection_prompt_scan_service(
    student_lection_repository: StudentLectionRepositoryProtocol = Depends(__get_student_lection_repository),
) -> ReflectionPromptScanServiceProtocol:
    """Получить сервис bounded scan запросов рефлексии."""
    return ReflectionPromptScanService(
        student_lection_repository=student_lection_repository,
        lookback_hours=settings.celery.scan_lookback_hours,
    )


def get_reflection_prompt_message_service(
    lection_repository: LectionSessionRepositoryProtocol = Depends(__get_lection_repository),
) -> ReflectionPromptMessageServiceProtocol:
    """Получить сервис генерации сообщения запроса рефлексии."""
    return ReflectionPromptMessageService(lection_repository=lection_repository)


def get_notification_command_publisher() -> NotificationCommandPublisherProtocol:
    """Получить publisher команд в RabbitMQ."""
    return NotificationCommandPublisher(settings.rabbitmq)


def get_notification_delivery_result_handler(
    notification_delivery_service: NotificationDeliveryServiceProtocol = Depends(get_notification_delivery_service),
) -> NotificationDeliveryResultHandlerProtocol:
    """Получить обработчик результата доставки."""
    return NotificationDeliveryResultHandler(
        notification_delivery_service=notification_delivery_service,
    )


def get_delivery_result_consumer(
    result_handler: NotificationDeliveryResultHandlerProtocol = Depends(
        get_notification_delivery_result_handler
    ),
) -> DeliveryResultConsumerProtocol:
    """Получить consumer результатов доставки."""
    return DeliveryResultConsumer(
        rabbitmq=settings.rabbitmq,
        result_handler=result_handler,
    )


# Use cases

def get_create_admin_use_case(
    admin_service: AdminServiceProtocol = Depends(get_admin_service),
) -> CreateAdminUseCaseProtocol:
    """Получить use case создания администратора."""
    return CreateAdminUseCase(admin_service=admin_service)


def get_admin_login_use_case(
    auth_service: AuthServiceProtocol = Depends(get_auth_service),
) -> AdminLoginUseCaseProtocol:
    """Получить use case входа пользователя."""
    return AdminLoginUseCase(auth_service=auth_service)


def get_create_course_from_excel_use_case(
    course_service: CourseServiceProtocol = Depends(get_course_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
    question_service: QuestionServiceProtocol = Depends(get_question_service),
    parser: FileParserProtocol = Depends(get_course_excel_parser),
) -> CreateCourseFromExcelUseCaseProtocol:
    """Получить use case создания курса из Excel."""
    return CreateCourseFromExcelUseCase(
        course_service=course_service,
        lection_service=lection_service,
        question_service=question_service,
        parser=parser,
    )


def get_attach_teachers_to_course_use_case(
    teacher_service: TeacherServiceProtocol = Depends(get_teacher_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
) -> AttachTeachersToCourseUseCaseProtocol:
    """Получить use case привязки преподавателей к курсу."""
    return AttachTeachersToCourseUseCase(
        teacher_service=teacher_service,
        lection_service=lection_service,
    )


def get_attach_students_to_course_use_case(
    student_service: StudentServiceProtocol = Depends(get_student_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
    parser: FileParserProtocol = Depends(get_student_csv_parser),
) -> AttachStudentsToCourseUseCaseProtocol:
    """Получить use case привязки студентов к курсу."""
    return AttachStudentsToCourseUseCase(
        student_service=student_service,
        lection_service=lection_service,
        parser=parser,
    )


def get_update_lection_use_case(
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
) -> UpdateLectionUseCaseProtocol:
    """Получить use case обновления лекции."""
    return UpdateLectionUseCase(lection_service=lection_service)


def get_manage_questions_use_case(
    question_service: QuestionServiceProtocol = Depends(get_question_service),
) -> ManageQuestionsUseCaseProtocol:
    """Получить use case управления вопросами."""
    return ManageQuestionsUseCase(question_service=question_service)


def get_manage_files_use_case(
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
) -> ManageFilesUseCaseProtocol:
    """Получить use case управления файлами лекции."""
    return ManageFilesUseCase(lection_service=lection_service)


def get_view_lection_analytics_use_case(
    analytics_service: AnalyticsServiceProtocol = Depends(get_analytics_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
    teacher_course_repository: TeacherCourseRepositoryProtocol = Depends(__get_teacher_course_repository),
) -> ViewLectionAnalyticsUseCaseProtocol:
    """Получить use case просмотра статистики по лекции."""
    return ViewLectionAnalyticsUseCase(
        analytics_service=analytics_service,
        lection_service=lection_service,
        teacher_course_repository=teacher_course_repository,
    )


def get_view_student_analytics_use_case(
    analytics_service: AnalyticsServiceProtocol = Depends(get_analytics_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
    teacher_course_repository: TeacherCourseRepositoryProtocol = Depends(__get_teacher_course_repository),
) -> ViewStudentAnalyticsUseCaseProtocol:
    """Получить use case просмотра статистики студента."""
    return ViewStudentAnalyticsUseCase(
        analytics_service=analytics_service,
        lection_service=lection_service,
        teacher_course_repository=teacher_course_repository,
    )


def get_view_reflection_details_use_case(
    analytics_service: AnalyticsServiceProtocol = Depends(get_analytics_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
    teacher_course_repository: TeacherCourseRepositoryProtocol = Depends(__get_teacher_course_repository),
) -> ViewReflectionDetailsUseCaseProtocol:
    """Получить use case просмотра деталей рефлексии."""
    return ViewReflectionDetailsUseCase(
        analytics_service=analytics_service,
        lection_service=lection_service,
        teacher_course_repository=teacher_course_repository,
    )


def get_scan_due_reflection_prompts_use_case(
    scan_service: ReflectionPromptScanServiceProtocol = Depends(get_reflection_prompt_scan_service),
    notification_delivery_service: NotificationDeliveryServiceProtocol = Depends(
        get_notification_delivery_service
    ),
) -> ScanDueReflectionPromptsUseCaseProtocol:
    """Получить use case bounded scan запросов рефлексии."""
    return ScanDueReflectionPromptsUseCase(
        scan_service=scan_service,
        notification_delivery_service=notification_delivery_service,
        scan_batch_size=settings.celery.scan_batch_size,
    )


def get_publish_pending_reflection_prompts_use_case(
    notification_delivery_repository: NotificationDeliveryRepositoryProtocol = Depends(
        __get_notification_delivery_repository
    ),
    notification_delivery_service: NotificationDeliveryServiceProtocol = Depends(
        get_notification_delivery_service
    ),
    student_repository: StudentRepositoryProtocol = Depends(__get_student_repository),
    message_service: ReflectionPromptMessageServiceProtocol = Depends(
        get_reflection_prompt_message_service
    ),
    publisher: NotificationCommandPublisherProtocol = Depends(get_notification_command_publisher),
) -> PublishPendingReflectionPromptsUseCaseProtocol:
    """Получить use case публикации pending доставок."""
    return PublishPendingReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=settings.celery.publish_batch_size,
    )


def get_retry_failed_reflection_prompts_use_case(
    notification_delivery_repository: NotificationDeliveryRepositoryProtocol = Depends(
        __get_notification_delivery_repository
    ),
    notification_delivery_service: NotificationDeliveryServiceProtocol = Depends(
        get_notification_delivery_service
    ),
    student_repository: StudentRepositoryProtocol = Depends(__get_student_repository),
    message_service: ReflectionPromptMessageServiceProtocol = Depends(
        get_reflection_prompt_message_service
    ),
    publisher: NotificationCommandPublisherProtocol = Depends(get_notification_command_publisher),
) -> RetryFailedReflectionPromptsUseCaseProtocol:
    """Получить use case retry failed доставок."""
    return RetryFailedReflectionPromptsUseCase(
        notification_delivery_repository=notification_delivery_repository,
        notification_delivery_service=notification_delivery_service,
        student_repository=student_repository,
        message_service=message_service,
        publisher=publisher,
        publish_batch_size=settings.celery.publish_batch_size,
        retry_failed_backoff_seconds=settings.celery.retry_failed_backoff_seconds,
        retry_failed_max_attempts=settings.celery.retry_failed_max_attempts,
    )


def get_button_action_handler(
    context_service: ContextServiceProtocol = Depends(get_context_service),
    admin_service: AdminServiceProtocol = Depends(get_admin_service),
    teacher_service: TeacherServiceProtocol = Depends(get_teacher_service),
    student_service: StudentServiceProtocol = Depends(get_student_service),
    course_service: CourseServiceProtocol = Depends(get_course_service),
    course_invite_service: CourseInviteServiceProtocol = Depends(get_course_invite_service),
    default_question_service: DefaultQuestionServiceProtocol = Depends(get_default_question_service),
    lection_service: LectionServiceProtocol = Depends(get_lection_service),
    question_service: QuestionServiceProtocol = Depends(get_question_service),
    pagination_service: PaginationServiceProtocol = Depends(get_pagination_service),
    manage_files_use_case: ManageFilesUseCaseProtocol = Depends(get_manage_files_use_case),
    reflection_workflow_service: ReflectionWorkflowServiceProtocol = Depends(
        get_reflection_workflow_service
    ),
    student_history_log_service: StudentHistoryLogServiceProtocol = Depends(
        get_student_history_log_service
    ),
    view_lection_analytics_use_case: ViewLectionAnalyticsUseCaseProtocol = Depends(get_view_lection_analytics_use_case),
    view_student_analytics_use_case: ViewStudentAnalyticsUseCaseProtocol = Depends(get_view_student_analytics_use_case),
    view_reflection_details_use_case: ViewReflectionDetailsUseCaseProtocol = Depends(get_view_reflection_details_use_case),
) -> ButtonActionHandlerProtocol:
    """Получить handler кнопок."""
    return ButtonActionHandler(
        context_service=context_service,
        admin_service=admin_service,
        teacher_service=teacher_service,
        student_service=student_service,
        course_service=course_service,
        course_invite_service=course_invite_service,
        default_question_service=default_question_service,
        lection_service=lection_service,
        question_service=question_service,
        pagination_service=pagination_service,
        manage_files_use_case=manage_files_use_case,
        reflection_workflow_service=reflection_workflow_service,
        student_history_log_service=student_history_log_service,
        view_lection_analytics_use_case=view_lection_analytics_use_case,
        view_student_analytics_use_case=view_student_analytics_use_case,
        view_reflection_details_use_case=view_reflection_details_use_case,
    )


def get_text_input_handler(
    context_service: ContextServiceProtocol = Depends(get_context_service),
    admin_service: AdminServiceProtocol = Depends(get_admin_service),
    teacher_service: TeacherServiceProtocol = Depends(get_teacher_service),
    student_service: StudentServiceProtocol = Depends(get_student_service),
    create_admin_use_case: CreateAdminUseCaseProtocol = Depends(get_create_admin_use_case),
    attach_teachers_to_course_use_case: AttachTeachersToCourseUseCaseProtocol = Depends(get_attach_teachers_to_course_use_case),
    update_lection_use_case: UpdateLectionUseCaseProtocol = Depends(get_update_lection_use_case),
    manage_questions_use_case: ManageQuestionsUseCaseProtocol = Depends(get_manage_questions_use_case),
    student_history_log_service: StudentHistoryLogServiceProtocol = Depends(
        get_student_history_log_service
    ),
    button_handler: ButtonActionHandlerProtocol = Depends(get_button_action_handler),
) -> TextInputHandlerProtocol:
    """Получить handler текстового ввода."""
    return TextInputHandler(
        context_service=context_service,
        admin_service=admin_service,
        teacher_service=teacher_service,
        student_service=student_service,
        create_admin_use_case=create_admin_use_case,
        attach_teachers_to_course_use_case=attach_teachers_to_course_use_case,
        update_lection_use_case=update_lection_use_case,
        manage_questions_use_case=manage_questions_use_case,
        student_history_log_service=student_history_log_service,
        button_handler=button_handler,  # type: ignore[arg-type]
    )


def get_file_upload_handler(
    context_service: ContextServiceProtocol = Depends(get_context_service),
    create_course_from_excel_use_case: CreateCourseFromExcelUseCaseProtocol = Depends(get_create_course_from_excel_use_case),
    attach_students_to_course_use_case: AttachStudentsToCourseUseCaseProtocol = Depends(get_attach_students_to_course_use_case),
    manage_files_use_case: ManageFilesUseCaseProtocol = Depends(get_manage_files_use_case),
    reflection_workflow_service: ReflectionWorkflowServiceProtocol = Depends(
        get_reflection_workflow_service
    ),
    student_history_log_service: StudentHistoryLogServiceProtocol = Depends(
        get_student_history_log_service
    ),
    button_handler: ButtonActionHandlerProtocol = Depends(get_button_action_handler),
) -> FileUploadHandlerProtocol:
    """Получить handler загрузки файлов."""
    return FileUploadHandler(
        context_service=context_service,
        create_course_from_excel_use_case=create_course_from_excel_use_case,
        attach_students_to_course_use_case=attach_students_to_course_use_case,
        manage_files_use_case=manage_files_use_case,
        reflection_workflow_service=reflection_workflow_service,
        student_history_log_service=student_history_log_service,
        button_handler=button_handler,  # type: ignore[arg-type]
    )


# DI aliases

AdminServiceDep = Annotated[AdminServiceProtocol, Depends(get_admin_service)]
AuthServiceDep = Annotated[AuthServiceProtocol, Depends(get_auth_service)]
ContextServiceDep = Annotated[ContextServiceProtocol, Depends(get_context_service)]
CourseServiceDep = Annotated[CourseServiceProtocol, Depends(get_course_service)]
PaginationServiceDep = Annotated[PaginationServiceProtocol, Depends(get_pagination_service)]
AdminLoginUseCaseDep = Annotated[AdminLoginUseCaseProtocol, Depends(get_admin_login_use_case)]
AttachTeachersToCourseUseCaseDep = Annotated[
    AttachTeachersToCourseUseCaseProtocol,
    Depends(get_attach_teachers_to_course_use_case),
]
AttachStudentsToCourseUseCaseDep = Annotated[
    AttachStudentsToCourseUseCaseProtocol,
    Depends(get_attach_students_to_course_use_case),
]
LectionServiceDep = Annotated[LectionServiceProtocol, Depends(get_lection_service)]
QuestionServiceDep = Annotated[QuestionServiceProtocol, Depends(get_question_service)]
DefaultQuestionServiceDep = Annotated[DefaultQuestionServiceProtocol, Depends(get_default_question_service)]
TeacherServiceDep = Annotated[TeacherServiceProtocol, Depends(get_teacher_service)]
StudentServiceDep = Annotated[StudentServiceProtocol, Depends(get_student_service)]
StudentHistoryLogServiceDep = Annotated[
    StudentHistoryLogServiceProtocol,
    Depends(get_student_history_log_service),
]
UpdateLectionUseCaseDep = Annotated[UpdateLectionUseCaseProtocol, Depends(get_update_lection_use_case)]
ManageQuestionsUseCaseDep = Annotated[
    ManageQuestionsUseCaseProtocol,
    Depends(get_manage_questions_use_case),
]
ManageFilesUseCaseDep = Annotated[ManageFilesUseCaseProtocol, Depends(get_manage_files_use_case)]
AnalyticsServiceDep = Annotated[AnalyticsServiceProtocol, Depends(get_analytics_service)]
NotificationDeliveryServiceDep = Annotated[
    NotificationDeliveryServiceProtocol,
    Depends(get_notification_delivery_service),
]
ReflectionWorkflowServiceDep = Annotated[
    ReflectionWorkflowServiceProtocol,
    Depends(get_reflection_workflow_service),
]
ReflectionPromptScanServiceDep = Annotated[
    ReflectionPromptScanServiceProtocol,
    Depends(get_reflection_prompt_scan_service),
]
ReflectionPromptMessageServiceDep = Annotated[
    ReflectionPromptMessageServiceProtocol,
    Depends(get_reflection_prompt_message_service),
]
NotificationCommandPublisherDep = Annotated[
    NotificationCommandPublisherProtocol,
    Depends(get_notification_command_publisher),
]
NotificationDeliveryResultHandlerDep = Annotated[
    NotificationDeliveryResultHandlerProtocol,
    Depends(get_notification_delivery_result_handler),
]
ScanDueReflectionPromptsUseCaseDep = Annotated[
    ScanDueReflectionPromptsUseCaseProtocol,
    Depends(get_scan_due_reflection_prompts_use_case),
]
PublishPendingReflectionPromptsUseCaseDep = Annotated[
    PublishPendingReflectionPromptsUseCaseProtocol,
    Depends(get_publish_pending_reflection_prompts_use_case),
]
RetryFailedReflectionPromptsUseCaseDep = Annotated[
    RetryFailedReflectionPromptsUseCaseProtocol,
    Depends(get_retry_failed_reflection_prompts_use_case),
]
DeliveryResultConsumerDep = Annotated[
    DeliveryResultConsumerProtocol,
    Depends(get_delivery_result_consumer),
]
ViewLectionAnalyticsUseCaseDep = Annotated[
    ViewLectionAnalyticsUseCaseProtocol,
    Depends(get_view_lection_analytics_use_case),
]
ViewStudentAnalyticsUseCaseDep = Annotated[
    ViewStudentAnalyticsUseCaseProtocol,
    Depends(get_view_student_analytics_use_case),
]
ViewReflectionDetailsUseCaseDep = Annotated[
    ViewReflectionDetailsUseCaseProtocol,
    Depends(get_view_reflection_details_use_case),
]
ButtonActionHandlerDep = Annotated[ButtonActionHandlerProtocol, Depends(get_button_action_handler)]
TextInputHandlerDep = Annotated[TextInputHandlerProtocol, Depends(get_text_input_handler)]
FileUploadHandlerDep = Annotated[FileUploadHandlerProtocol, Depends(get_file_upload_handler)]
CourseExcelParserDep = Annotated[FileParserProtocol, Depends(get_course_excel_parser)]
StudentCSVParserDep = Annotated[FileParserProtocol, Depends(get_student_csv_parser)]
