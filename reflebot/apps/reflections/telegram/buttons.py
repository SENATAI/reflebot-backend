"""
Кнопки для Telegram бота.
"""

from typing import Protocol
from pydantic import BaseModel


class TelegramButton(BaseModel):
    """Модель кнопки Telegram."""
    
    text: str
    action: str | None = None
    url: str | None = None


class TelegramButtonsProtocol(Protocol):
    """Протокол для кнопок Telegram."""
    
    def get_login_buttons(
        self,
        is_admin: bool,
        is_teacher: bool,
        is_student: bool,
    ) -> list[TelegramButton]:
        """Получить кнопки при входе."""
        ...


class TelegramButtons:
    """Кнопки для Telegram бота."""

    TECH_SUPPORT_URL = "https://t.me/mark0vartem"
    
    # Действия для администратора
    ADMIN_CREATE_ADMIN = "admin_create_admin"
    ADMIN_CREATE_COURSE = "admin_create_course"
    ADMIN_VIEW_COURSES = "admin_view_courses"
    ADMIN_VIEW_COURSE = "admin_view_course"
    
    # Действия для преподавателя
    TEACHER_ANALYTICS = "teacher_analytics"
    TEACHER_NEXT_LECTION = "teacher_next_lection"
    
    # Действия для управления курсом
    COURSE_VIEW_PARSED_LECTIONS = "course_view_parsed_lections"
    COURSE_APPEND_LECTIONS = "course_append_lections"
    COURSE_SEND_MESSAGE = "course_send_message"
    COURSE_SEND_ALERT = "course_send_alert"
    COURSE_ALERT_LECTION = "course_alert_lection"
    COURSE_ALERT_STUDENT = "course_alert_student"
    COURSE_ADD_DEFAULT_QUESTIONS = "course_add_default_questions"
    COURSE_ATTACH_TEACHERS = "course_attach_teachers"
    COURSE_ATTACH_STUDENTS = "course_attach_students"
    COURSE_CANCEL_PARSING = "course_cancel_parsing"
    
    # Действия для управления лекцией
    LECTION_INFO = "lection_info"
    LECTION_EDIT_TOPIC = "lection_edit_topic"
    LECTION_EDIT_DATE = "lection_edit_date"
    LECTION_MANAGE_QUESTIONS = "lection_manage_questions"
    LECTION_MANAGE_PRESENTATION = "lection_manage_presentation"
    LECTION_MANAGE_RECORDING = "lection_manage_recording"
    
    # Действия для управления вопросами
    QUESTIONS_ADD = "questions_add"
    QUESTIONS_EDIT = "questions_edit"
    QUESTIONS_DELETE = "questions_delete"
    QUESTION_DELETE_SPECIFIC = "question_delete_specific"
    
    # Действия для управления файлами
    PRESENTATION_UPLOAD = "presentation_upload"
    PRESENTATION_DOWNLOAD = "presentation_download"
    RECORDING_UPLOAD = "recording_upload"
    RECORDING_DOWNLOAD = "recording_download"
    
    # Действия для привязки преподавателей
    TEACHER_ADD_ANOTHER = "teacher_add_another"
    TEACHER_PROCEED_TO_STUDENTS = "teacher_proceed_to_students"
    TEACHER_FINISH_COURSE_CREATION = "teacher_finish_course_creation"
    
    # Действия для аналитики
    ANALYTICS_SELECT_COURSE = "analytics_select_course"
    ANALYTICS_LECTION_STATS = "analytics_lection_stats"
    ANALYTICS_FIND_STUDENT = "analytics_find_student"
    ANALYTICS_VIEW_REFLECTION = "analytics_view_reflection"

    # Действия для student reflection workflow
    STUDENT_START_REFLECTION = "student_start_reflection"
    STUDENT_RECORD_REFLECTION_VIDEO = "student_record_reflection_video"
    STUDENT_SUBMIT_REFLECTION = "student_submit_reflection"
    STUDENT_DELETE_REFLECTION_VIDEO = "student_delete_reflection_video"
    STUDENT_ADD_REFLECTION_VIDEO = "student_add_reflection_video"
    STUDENT_APPEND_REFLECTION = "student_add_reflection"
    STUDENT_SELECT_QUESTION = "student_select_question"
    STUDENT_RECORD_QA_VIDEO = "student_record_qa_video"
    STUDENT_SUBMIT_QA = "student_submit_qa"
    STUDENT_DELETE_QA_VIDEO = "student_delete_qa_video"
    STUDENT_ADD_QA_VIDEO = "student_add_qa_video"
    STUDENT_JOIN_COURSE = "student_join_course"
    
    # Навигация
    BACK = "back"
    NEXT_PAGE = "next_page"
    PREV_PAGE = "prev_page"
    
    @staticmethod
    def get_login_buttons(
        is_admin: bool,
        is_teacher: bool,
        is_student: bool,
    ) -> list[TelegramButton]:
        """
        Получить кнопки при входе в зависимости от ролей.
        
        Args:
            is_admin: Является ли администратором
            is_teacher: Является ли преподавателем
            is_student: Является ли студентом
        
        Returns:
            Список кнопок
        """
        buttons = []
        
        # Кнопки для администратора
        if is_admin:
            buttons.extend([
                TelegramButton(
                    text="➕ Создать администратора",
                    action=TelegramButtons.ADMIN_CREATE_ADMIN
                ),
                TelegramButton(
                    text="📚 Создать курс",
                    action=TelegramButtons.ADMIN_CREATE_COURSE
                ),
                TelegramButton(
                    text="📖 Курсы",
                    action=TelegramButtons.ADMIN_VIEW_COURSES
                ),
            ])
        
        # Кнопки преподавателя также доступны администратору
        if is_teacher or is_admin:
            buttons.extend([
                TelegramButton(
                    text="📊 Аналитика",
                    action=TelegramButtons.TEACHER_ANALYTICS
                ),
                TelegramButton(
                    text="📅 Ближайшая лекция",
                    action=TelegramButtons.TEACHER_NEXT_LECTION
                ),
            ])

        if is_student:
            buttons.append(
                TelegramButton(
                    text="🎓 Записаться на курс",
                    action=TelegramButtons.STUDENT_JOIN_COURSE,
                )
            )

        buttons.append(
            TelegramButton(
                text="🛠 Тех. Поддержка",
                url=TelegramButtons.TECH_SUPPORT_URL,
            )
        )
        
        return buttons
    
    @staticmethod
    def get_admin_buttons() -> list[TelegramButton]:
        """Получить кнопки администратора."""
        return [
            TelegramButton(
                text="➕ Создать администратора",
                action=TelegramButtons.ADMIN_CREATE_ADMIN
            ),
            TelegramButton(
                text="📚 Создать курс",
                action=TelegramButtons.ADMIN_CREATE_COURSE
            ),
            TelegramButton(
                text="📖 Курсы",
                action=TelegramButtons.ADMIN_VIEW_COURSES
            ),
            TelegramButton(
                text="🛠 Тех. Поддержка",
                url=TelegramButtons.TECH_SUPPORT_URL,
            ),
        ]
    
    @staticmethod
    def get_teacher_buttons() -> list[TelegramButton]:
        """Получить кнопки преподавателя."""
        return [
            TelegramButton(
                text="📊 Аналитика",
                action=TelegramButtons.TEACHER_ANALYTICS
            ),
            TelegramButton(
                text="📅 Ближайшая лекция",
                action=TelegramButtons.TEACHER_NEXT_LECTION
            ),
            TelegramButton(
                text="🛠 Тех. Поддержка",
                url=TelegramButtons.TECH_SUPPORT_URL,
            ),
        ]
    
    @staticmethod
    def get_course_menu_buttons(show_add_default_questions: bool = False) -> list[TelegramButton]:
        """Получить кнопки меню курса после парсинга."""
        buttons = [
            TelegramButton(
                text="📝 Спаршенные лекции",
                action=TelegramButtons.COURSE_VIEW_PARSED_LECTIONS
            ),
            TelegramButton(
                text="👨‍🏫 Привязать преподавателей",
                action=TelegramButtons.COURSE_ATTACH_TEACHERS
            ),
            TelegramButton(
                text="❌ Отменить парсинг",
                action=TelegramButtons.COURSE_CANCEL_PARSING
            ),
        ]
        if show_add_default_questions:
            buttons.insert(
                1,
                TelegramButton(
                    text="❓ Добавить вопросы для лекций без вопросов",
                    action=TelegramButtons.COURSE_ADD_DEFAULT_QUESTIONS,
                ),
            )
        return buttons

    @staticmethod
    def get_admin_course_details_buttons() -> list[TelegramButton]:
        """Получить кнопки карточки курса в разделе курсов."""
        return [
            TelegramButton(
                text="📥 Догрузить курс",
                action=TelegramButtons.COURSE_APPEND_LECTIONS,
            ),
            TelegramButton(
                text="🔔 Отправить алерт",
                action=TelegramButtons.COURSE_SEND_ALERT,
            ),
            TelegramButton(
                text="✉️ Отправить сообщение студентам",
                action=TelegramButtons.COURSE_SEND_MESSAGE,
            ),
            TelegramButton(
                text="⬅️ Назад",
                action=TelegramButtons.BACK,
            ),
        ]
    
    @staticmethod
    def get_lection_details_buttons() -> list[TelegramButton]:
        """Получить кнопки детальной информации о лекции."""
        return [
            TelegramButton(
                text="✏️ Изменить тему",
                action=TelegramButtons.LECTION_EDIT_TOPIC
            ),
            TelegramButton(
                text="📅 Изменить дату",
                action=TelegramButtons.LECTION_EDIT_DATE
            ),
            TelegramButton(
                text="❓ Вопросы",
                action=TelegramButtons.LECTION_MANAGE_QUESTIONS
            ),
            TelegramButton(
                text="📎 Презентация",
                action=TelegramButtons.LECTION_MANAGE_PRESENTATION
            ),
            TelegramButton(
                text="🎥 Запись лекции",
                action=TelegramButtons.LECTION_MANAGE_RECORDING
            ),
            TelegramButton(
                text="◀️ Назад",
                action=TelegramButtons.BACK
            ),
        ]
    
    @staticmethod
    def get_questions_menu_buttons() -> list[TelegramButton]:
        """Получить кнопки меню управления вопросами."""
        return [
            TelegramButton(
                text="➕ Добавить",
                action=TelegramButtons.QUESTIONS_ADD
            ),
            TelegramButton(
                text="✏️ Изменить",
                action=TelegramButtons.QUESTIONS_EDIT
            ),
            TelegramButton(
                text="🗑 Удалить",
                action=TelegramButtons.QUESTIONS_DELETE
            ),
            TelegramButton(
                text="◀️ Назад",
                action=TelegramButtons.BACK
            ),
        ]
    
    @staticmethod
    def get_presentation_menu_buttons(has_presentation: bool) -> list[TelegramButton]:
        """Получить кнопки меню управления презентацией."""
        buttons = [
            TelegramButton(
                text="📤 Изменить презентацию",
                action=TelegramButtons.PRESENTATION_UPLOAD
            ),
        ]
        
        if has_presentation:
            buttons.insert(0, TelegramButton(
                text="📥 Скачать презентацию",
                action=TelegramButtons.PRESENTATION_DOWNLOAD
            ))
        
        buttons.append(TelegramButton(
            text="◀️ Назад",
            action=TelegramButtons.BACK
        ))
        
        return buttons
    
    @staticmethod
    def get_recording_menu_buttons(has_recording: bool) -> list[TelegramButton]:
        """Получить кнопки меню управления записью лекции."""
        buttons = [
            TelegramButton(
                text="📤 Изменить запись",
                action=TelegramButtons.RECORDING_UPLOAD
            ),
        ]
        
        if has_recording:
            buttons.insert(0, TelegramButton(
                text="📥 Скачать запись",
                action=TelegramButtons.RECORDING_DOWNLOAD
            ))
        
        buttons.append(TelegramButton(
            text="◀️ Назад",
            action=TelegramButtons.BACK
        ))
        
        return buttons
    
    @staticmethod
    def get_teacher_attached_buttons() -> list[TelegramButton]:
        """Получить кнопки после привязки преподавателя."""
        return [
            TelegramButton(
                text="➕ Добавить ещё преподавателя",
                action=TelegramButtons.TEACHER_ADD_ANOTHER
            ),
            TelegramButton(
                text="👨‍🎓 Привязать студентов",
                action=TelegramButtons.COURSE_ATTACH_STUDENTS
            ),
            TelegramButton(
                text="✅ Закончить создание",
                action=TelegramButtons.TEACHER_FINISH_COURSE_CREATION
            ),
        ]
    
    @staticmethod
    def get_analytics_course_menu_buttons() -> list[TelegramButton]:
        """Получить кнопки меню аналитики курса."""
        return [
            TelegramButton(
                text="📊 Статистика по лекции",
                action=TelegramButtons.ANALYTICS_LECTION_STATS
            ),
            TelegramButton(
                text="🔍 Найти студента",
                action=TelegramButtons.ANALYTICS_FIND_STUDENT
            ),
            TelegramButton(
                text="◀️ Назад",
                action=TelegramButtons.BACK
            ),
        ]
    
    @staticmethod
    def get_back_button() -> list[TelegramButton]:
        """Получить кнопку назад."""
        return [
            TelegramButton(
                text="◀️ Назад",
                action=TelegramButtons.BACK
            ),
        ]
    
    @staticmethod
    def get_pagination_buttons(
        current_page: int,
        total_pages: int,
        has_back: bool = True,
    ) -> list[TelegramButton]:
        """Получить кнопки пагинации."""
        buttons = []
        
        if current_page > 1:
            buttons.append(TelegramButton(
                text="⬅️ Предыдущая страница",
                action=TelegramButtons.PREV_PAGE
            ))
        
        if current_page < total_pages:
            buttons.append(TelegramButton(
                text="➡️ Следующая страница",
                action=TelegramButtons.NEXT_PAGE
            ))
        
        if has_back:
            buttons.append(TelegramButton(
                text="◀️ Назад",
                action=TelegramButtons.BACK
            ))
        
        return buttons
    
    @staticmethod
    def create_button(text: str, action: str) -> TelegramButton:
        """Создать кнопку с произвольным текстом и действием."""
        return TelegramButton(text=text, action=action)
    
    @staticmethod
    def create_lection_button(lection_topic: str, lection_id: str) -> TelegramButton:
        """Создать кнопку для лекции."""
        return TelegramButton(
            text=f"📝 {lection_topic}",
            action=f"{TelegramButtons.LECTION_INFO}:{lection_id}"
        )
    
    @staticmethod
    def create_course_button(course_name: str, course_id: str) -> TelegramButton:
        """Создать кнопку для курса."""
        return TelegramButton(
            text=f"📚 {course_name}",
            action=f"{TelegramButtons.ANALYTICS_SELECT_COURSE}:{course_id}"
        )

    @staticmethod
    def create_admin_course_button(course_name: str, course_id: str) -> TelegramButton:
        """Создать кнопку для просмотра курса администратором."""
        return TelegramButton(
            text=f"📚 {course_name}",
            action=f"{TelegramButtons.ADMIN_VIEW_COURSE}:{course_id}"
        )
    
    @staticmethod
    def create_student_button(
        student_name: str,
        student_id: str,
        telegram_username: str | None = None,
    ) -> TelegramButton:
        """Создать кнопку для студента."""
        username_suffix = f" (@{telegram_username})" if telegram_username else ""
        return TelegramButton(
            text=f"👨‍🎓 {student_name}{username_suffix}",
            action=f"{TelegramButtons.ANALYTICS_FIND_STUDENT}:{student_id}"
        )

    @staticmethod
    def create_course_alert_lection_button(lection_topic: str, lection_id: str) -> TelegramButton:
        """Создать кнопку выбора лекции для повторной отправки алерта."""
        return TelegramButton(
            text=f"📝 {lection_topic}",
            action=f"{TelegramButtons.COURSE_ALERT_LECTION}:{lection_id}",
        )

    @staticmethod
    def create_course_alert_student_button(
        student_name: str,
        student_id: str,
        telegram_username: str | None = None,
    ) -> TelegramButton:
        """Создать кнопку выбора студента для повторной отправки алерта."""
        username_suffix = f" (@{telegram_username})" if telegram_username else ""
        return TelegramButton(
            text=f"👨‍🎓 {student_name}{username_suffix}",
            action=f"{TelegramButtons.COURSE_ALERT_STUDENT}:{student_id}",
        )
    
    @staticmethod
    def create_question_delete_button(question_text: str, question_id: str) -> TelegramButton:
        """Создать кнопку для удаления вопроса."""
        # Обрезаем текст вопроса если он слишком длинный
        display_text = question_text[:50] + "..." if len(question_text) > 50 else question_text
        return TelegramButton(
            text=f"🗑 {display_text}",
            action=f"{TelegramButtons.QUESTION_DELETE_SPECIFIC}:{question_id}"
        )

    @staticmethod
    def create_start_reflection_button(lection_id: str) -> TelegramButton:
        """Создать кнопку старта workflow рефлексии по лекции."""
        return TelegramButton(
            text="🎥 Загрузить кружок/видео",
            action=f"{TelegramButtons.STUDENT_START_REFLECTION}:{lection_id}",
        )

    @staticmethod
    def create_add_reflection_button(lection_id: str) -> TelegramButton:
        """Создать кнопку дозаписи кружка/видео по лекции."""
        return TelegramButton(
            text="➕ Добавить кружок",
            action=f"{TelegramButtons.STUDENT_APPEND_REFLECTION}:{lection_id}",
        )

    @staticmethod
    def create_support_button() -> TelegramButton:
        """Создать кнопку перехода в техподдержку."""
        return TelegramButton(
            text="🛠 Тех. Поддержка",
            url=TelegramButtons.TECH_SUPPORT_URL,
        )

    @staticmethod
    def get_reflection_prompt_buttons(lection_id: str) -> list[TelegramButton]:
        """Получить кнопку старта рефлексии по лекции."""
        return [TelegramButtons.create_start_reflection_button(lection_id)]

    @staticmethod
    def get_reflection_review_buttons() -> list[TelegramButton]:
        """Получить кнопки после записи кружка рефлексии по лекции."""
        return [
            TelegramButton(
                text="✅ Отправить рефлексию",
                action=TelegramButtons.STUDENT_SUBMIT_REFLECTION,
            ),
            TelegramButton(
                text="🗑 Удалить кружок/видео",
                action=TelegramButtons.STUDENT_DELETE_REFLECTION_VIDEO,
            ),
            TelegramButton(
                text="➕ Добавить ещё один кружок/видео",
                action=TelegramButtons.STUDENT_ADD_REFLECTION_VIDEO,
            ),
        ]

    @staticmethod
    def get_question_prompt_buttons() -> list[TelegramButton]:
        """Получить кнопку записи ответа на вопрос."""
        return [
            TelegramButton(
                text="🎥 Загрузить кружок/видео",
                action=TelegramButtons.STUDENT_RECORD_QA_VIDEO,
            ),
        ]

    @staticmethod
    def create_question_selection_button(
        question_id: str,
        question_text: str,
        index: int,
    ) -> TelegramButton:
        """Создать кнопку выбора конкретного вопроса."""
        return TelegramButton(
            text=f"Вопрос {index}",
            action=f"{TelegramButtons.STUDENT_SELECT_QUESTION}:{question_id}",
        )

    @staticmethod
    def get_question_review_buttons() -> list[TelegramButton]:
        """Получить кнопки после записи кружка ответа на вопрос."""
        return [
            TelegramButton(
                text="✅ Отправить рефлексию",
                action=TelegramButtons.STUDENT_SUBMIT_QA,
            ),
            TelegramButton(
                text="🗑 Удалить кружок/видео",
                action=TelegramButtons.STUDENT_DELETE_QA_VIDEO,
            ),
            TelegramButton(
                text="➕ Добавить ещё один кружок/видео",
                action=TelegramButtons.STUDENT_ADD_QA_VIDEO,
            ),
        ]

    @staticmethod
    def get_reflection_status_buttons(
        lection_id: str,
        deadline_active: bool,
    ) -> list[TelegramButton]:
        """Получить кнопки итогового статуса рефлексии по лекции."""
        if deadline_active:
            return [TelegramButtons.create_add_reflection_button(lection_id)]
        return [TelegramButtons.create_support_button()]
