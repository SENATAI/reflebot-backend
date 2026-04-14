"""
Сообщения для Telegram бота.
"""

from datetime import datetime, timezone
from typing import Protocol

from ..datetime_utils import REFLECTIONS_LOCAL_TIMEZONE


class TelegramMessagesProtocol(Protocol):
    """Протокол для сообщений Telegram."""
    
    def get_login_message(
        self,
        full_name: str,
        is_admin: bool,
        is_teacher: bool,
        is_student: bool,
    ) -> str:
        """Получить сообщение при входе."""
        ...


class TelegramMessages:
    """Сообщения для Telegram бота."""

    @staticmethod
    def _to_local(value: datetime) -> datetime:
        """Привести datetime к локальной зоне интерфейса."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(REFLECTIONS_LOCAL_TIMEZONE)

    @classmethod
    def _format_date(cls, value: datetime) -> str:
        """Отформатировать дату в локальной зоне."""
        return cls._to_local(value).strftime("%d.%m.%Y")

    @classmethod
    def _format_time(cls, value: datetime) -> str:
        """Отформатировать время в локальной зоне."""
        return cls._to_local(value).strftime("%H:%M")

    @classmethod
    def _format_datetime(cls, value: datetime) -> str:
        """Отформатировать дату и время в локальной зоне."""
        return cls._to_local(value).strftime("%d.%m.%Y %H:%M")
    
    @staticmethod
    def get_login_message(
        full_name: str,
        is_admin: bool,
        is_teacher: bool,
        is_student: bool,
    ) -> str:
        """
        Получить сообщение при входе.
        
        Args:
            full_name: ФИО пользователя
            is_admin: Является ли администратором
            is_teacher: Является ли преподавателем
            is_student: Является ли студентом
        
        Returns:
            Текст сообщения
        """
        roles = []
        if is_admin:
            roles.append("👨‍💼 Администратор")
        if is_teacher:
            roles.append("👨‍🏫 Преподаватель")
        if is_student:
            roles.append("👨‍🎓 Студент")
        
        roles_text = "\n".join(f"• {role}" for role in roles)
        
        return f"""✅ Вы успешно зарегистрированы!

👤 {full_name}

Ваши роли:
{roles_text}

Выберите действие из меню ниже."""
    
    @staticmethod
    def get_admin_created_message(admin_name: str) -> str:
        """Сообщение о создании администратора."""
        return f"✅ Администратор {admin_name} успешно создан!"
    
    @staticmethod
    def get_course_created_message(course_name: str, lections_count: int) -> str:
        """Сообщение о создании курса."""
        return f"""✅ Курс успешно создан!

📚 {course_name}
📝 Лекций: {lections_count}

Курс готов к использованию."""
    
    # Сообщения для создания администратора
    
    @staticmethod
    def get_create_admin_request_fullname() -> str:
        """Запрос ФИО администратора."""
        return "👤 Как зовут нового администратора? (Полное имя, например: Иван Иванович Петров)"
    
    @staticmethod
    def get_create_admin_request_username() -> str:
        """Запрос никнейма администратора."""
        return "📝 Введите никнейм в Telegram (без @):"
    
    # Сообщения для создания курса
    
    @staticmethod
    def get_create_course_request_file() -> str:
        """Запрос файла курса."""
        return "📚 Загрузите Excel файл с лекциями:"

    @staticmethod
    def get_append_course_request_file() -> str:
        """Запрос файла для догрузки новых лекций в курс."""
        return "📥 Загрузите Excel файл с новыми лекциями для этого курса:"

    @staticmethod
    def get_course_broadcast_request_text() -> str:
        """Запрос текста сообщения для студентов курса."""
        return "✉️ Введите текст сообщения, которое нужно отправить всем студентам курса:"

    @staticmethod
    def get_course_alert_select_lection() -> str:
        """Запрос выбора лекции для повторной отправки алерта."""
        return "🔔 Выберите лекцию, по которой нужно повторно отправить алерт:"

    @staticmethod
    def get_course_alert_select_student(lection_topic: str) -> str:
        """Запрос выбора студента для повторной отправки алерта."""
        return (
            "👨‍🎓 Выберите студента, которому нужно повторно отправить алерт.\n\n"
            f"Лекция: <b>{lection_topic}</b>"
        )

    @staticmethod
    def get_course_alert_sent(student_name: str, lection_topic: str) -> str:
        """Сообщение об успешной повторной отправке алерта студенту."""
        return (
            f"✅ Алерт поставлен в отправку.\n"
            f"Студент: <b>{student_name}</b>\n"
            f"Лекция: <b>{lection_topic}</b>\n\n"
        )

    @staticmethod
    def get_create_course_request_name() -> str:
        """Запрос названия курса."""
        return "📚 Введите название курса:"
    
    # Общие сообщения
    
    @staticmethod
    def get_no_active_action() -> str:
        """Сообщение об отсутствии активного действия."""
        return "⚠️ Не выбрана никакая команда. Попробуйте воспользоваться кнопками под сообщением выше или напишите в тех. поддержку."
    
    @staticmethod
    def get_unknown_action(action: str) -> str:
        """Сообщение о неизвестном действии."""
        return f"⚠️ Действие '{action}' пока не реализовано"
    
    @staticmethod
    def get_unknown_context_action() -> str:
        """Сообщение о неизвестном действии в контексте."""
        return "⚠️ Неизвестное действие. Попробуйте воспользоваться кнопками под сообщением выше или напишите в тех. поддержку."

    @staticmethod
    def get_course_appended_success(lections_count: int) -> str:
        """Сообщение об успешной догрузке курса."""
        return (
            f"✅ Курс успешно догружен.\n"
            f"Добавлено лекций: {lections_count}\n"
            "Новые лекции уже привязаны к записанным студентам.\n\n"
        )

    @staticmethod
    def get_course_broadcast_success(sent_count: int) -> str:
        """Сообщение об успешной отправке сообщения студентам курса."""
        return (
            f"✅ Сообщение поставлено в отправку.\n"
            f"Получателей: {sent_count}\n\n"
        )
    
    # Сообщения для управления курсом
    
    @staticmethod
    def get_course_created_success(
        course_name: str,
        started_at: datetime,
        ended_at: datetime,
        course_code: str | None = None,
    ) -> str:
        """Сообщение об успешном создании курса."""
        code_block = (
            f"\n\n🔐 Код курса для студентов:\n<code>{course_code}</code>"
            if course_code
            else "\n\n🔐 Код курса пока недоступен."
        )
        return f"""✅ Курс успешно создан!

📚 <b>{course_name}</b>
📅 Начало: {TelegramMessages._format_date(started_at)}
📅 Окончание: {TelegramMessages._format_date(ended_at)}

Что дальше?{code_block}"""
    
    @staticmethod
    def get_course_cancelled() -> str:
        """Сообщение об отмене парсинга курса."""
        return "❌ Парсинг курса отменён. Курс и все лекции удалены."

    @staticmethod
    def get_default_questions_added() -> str:
        """Сообщение после добавления стандартных вопросов."""
        return "✅ Вопросы успешно добавлены. Что дальше?"

    @staticmethod
    def get_next_actions_prompt() -> str:
        """Сообщение с предложением выбрать следующее действие."""
        return "Что делаем далее?"

    @staticmethod
    def get_select_course_for_admin() -> str:
        """Сообщение выбора курса администратором."""
        return "📚 Выберите курс:"

    @staticmethod
    def get_admin_course_info(course_name: str, course_code: str | None = None) -> str:
        """Сообщение с информацией о курсе для администратора."""
        code_block = (
            f"🔐 Код курса:\n<code>{course_code}</code>"
            if course_code
            else "🔐 Код курса пока недоступен."
        )
        return f"📚 <b>{course_name}</b>\n\n{code_block}"
    
    @staticmethod
    def get_parsed_lections_title(course_name: str) -> str:
        """Заголовок списка спаршенных лекций."""
        return f"📚 <b>{course_name}</b>\n\nСписок лекций:"
    
    # Сообщения для управления лекциями
    
    @staticmethod
    def get_lection_details(
        topic: str,
        started_at: datetime,
        ended_at: datetime,
        questions_count: int,
        has_presentation: bool,
        has_recording: bool,
    ) -> str:
        """Детальная информация о лекции."""
        presentation_status = "✅ Загружена" if has_presentation else "❌ Не загружена"
        recording_status = "✅ Загружена" if has_recording else "❌ Не загружена"
        
        return f"""📝 <b>{topic}</b>

📅 Дата: {TelegramMessages._format_date(started_at)}
🕐 Время: {TelegramMessages._format_time(started_at)}–{TelegramMessages._format_time(ended_at)}

❓ Вопросов: {questions_count}
📎 Презентация: {presentation_status}
🎥 Запись: {recording_status}"""
    
    @staticmethod
    def get_edit_lection_topic_request() -> str:
        """Запрос новой темы лекции."""
        return "📝 Введите новую тему лекции:"
    
    @staticmethod
    def get_lection_topic_updated() -> str:
        """Сообщение об обновлении темы лекции."""
        return "✅ Тема лекции обновлена!"
    
    @staticmethod
    def get_edit_lection_date_request() -> str:
        """Запрос новой даты лекции."""
        return "📅 Введите новую дату и время в формате:\nDD.MM.YYYY HH:MM-HH:MM\n\nНапример: 15.03.2024 10:00-11:30"
    
    @staticmethod
    def get_lection_date_updated() -> str:
        """Сообщение об обновлении даты лекции."""
        return "✅ Дата и время лекции обновлены!"
    
    @staticmethod
    def get_invalid_date_format() -> str:
        """Сообщение о неверном формате даты."""
        return "⚠️ Неверный формат даты. Используйте формат: DD.MM.YYYY HH:MM-HH:MM"

    @staticmethod
    def get_invalid_date_range() -> str:
        """Сообщение о неверном диапазоне времени лекции."""
        return "⚠️ Время окончания должно быть позже времени начала. Попробуйте снова:"
    
    # Сообщения для управления вопросами
    
    @staticmethod
    def get_questions_list(questions: list[tuple[int, str]]) -> str:
        """Список вопросов к лекции."""
        if not questions:
            return "❓ <b>Вопросы к лекции</b>\n\nВопросов пока нет."
        
        questions_text = "\n".join(f"{idx}. {text}" for idx, text in questions)
        return f"❓ <b>Вопросы к лекции</b>\n\n{questions_text}"
    
    @staticmethod
    def get_add_question_request() -> str:
        """Запрос текста нового вопроса."""
        return "❓ Введите текст вопроса:"
    
    @staticmethod
    def get_question_added() -> str:
        """Сообщение о добавлении вопроса."""
        return "✅ Вопрос добавлен!"
    
    @staticmethod
    def get_edit_question_request() -> str:
        """Запрос номера и текста вопроса для изменения."""
        return "📝 Введите номер вопроса и новый текст через пробел:\n\nНапример: 1 Новый текст вопроса"
    
    @staticmethod
    def get_question_updated() -> str:
        """Сообщение об обновлении вопроса."""
        return "✅ Вопрос обновлён!"
    
    @staticmethod
    def get_delete_question_prompt() -> str:
        """Запрос выбора вопроса для удаления."""
        return "🗑 Выберите вопрос для удаления:"
    
    @staticmethod
    def get_question_deleted() -> str:
        """Сообщение об удалении вопроса."""
        return "✅ Вопрос удалён!"
    
    # Сообщения для управления файлами
    
    @staticmethod
    def get_presentation_info(telegram_file_id: str | None) -> str:
        """Информация о презентации."""
        if telegram_file_id:
            return f"📎 <b>Презентация</b>\n\n🆔 <code>{telegram_file_id}</code>"
        return "📎 <b>Презентация</b>\n\n❌ Презентация не загружена"
    
    @staticmethod
    def get_recording_info(telegram_file_id: str | None) -> str:
        """Информация о записи лекции."""
        if telegram_file_id:
            return f"🎥 <b>Запись лекции</b>\n\n🆔 <code>{telegram_file_id}</code>"
        return "🎥 <b>Запись лекции</b>\n\n❌ Запись не загружена"

    @staticmethod
    def get_reflection_prompt_request(lection_topic: str, deadline: datetime | None) -> str:
        """Сообщение с просьбой записать кружок рефлексии по лекции."""
        deadline_block = (
            f"\n\n⏰ Дедлайн: {TelegramMessages._format_datetime(deadline)}"
            if deadline is not None
            else ""
        )
        return (
            "Здравствуйте! Отправьте рефлексию по лекции:\n"
            f"<b>{lection_topic}</b>."
            f"{deadline_block}\n"
            "👇 Нажмите кнопку ниже, чтобы начать запись кружка рефлексии!"
        )

    @staticmethod
    def get_reflection_recording_request() -> str:
        """Сообщение перед записью кружка."""
        return "🎙️Загрузите кружок/видео, я вас внимательно слушаю."

    @staticmethod
    def get_reflection_video_required() -> str:
        """Сообщение, если вместо кружка/видео пришёл текст или команда."""
        return "Сначала запишите кружок"

    @staticmethod
    def get_reflection_video_saved() -> str:
        """Сообщение после успешной записи кружка."""
        return "💾 Кружок/видео сохранён!\n\n👇 Используя кнопки под сообщением, выберите, что хотите сделать дальше:"

    @staticmethod
    def get_reflection_video_deleted() -> str:
        """Сообщение после удаления кружка."""
        return "Кружок/видео удалён."

    @staticmethod
    def get_reflection_submission_completed() -> str:
        """Сообщение после завершения рефлексии без вопросов."""
        return "✅ Рефлексия принята! Спасибо за ваш ответ."

    @staticmethod
    def get_question_reflection_prompt(
        question_text: str,
        index: int,
        total: int,
    ) -> str:
        """Сообщение с вопросом для записи кружка-ответа."""
        return (
            f"❓ Вопрос {index} из {total}\n\n"
            f"{question_text}\n\n"
            "Загрузите кружок/видео, я вас слушаю."
        )

    @staticmethod
    def get_question_selection_prompt(questions: list[dict[str, str]]) -> str:
        """Сообщение для выбора одного вопроса из списка."""
        question_lines = [
            f"{index}. {question.get('text', '')}"
            for index, question in enumerate(questions, start=1)
        ]
        return (
            "Выберите вопрос, на который хотите ответить.\n\n"
            + "\n\n".join(question_lines)
        )

    @staticmethod
    def get_questions_completed_message() -> str:
        """Сообщение после завершения всех вопросов."""
        return "Вы ответили на все вопросы. Спасибо за рефлексию!"

    @staticmethod
    def get_reflection_status_active(
        lection_topic: str,
        deadline: datetime,
        recorded_videos_count: int,
    ) -> str:
        """Статус рефлексии, если дедлайн ещё не закончился."""
        return (
            f"📝 Лекция: <b>{lection_topic}</b>\n"
            f"⏰ Дедлайн: {TelegramMessages._format_datetime(deadline)}\n\n"
            f"🎥 Записано кружков/видео: {recorded_videos_count}\n\n"
            "👇 Нажмите кнопку ниже, если хотите дозаписать ещё один кружок/видео до дедлайна."
        )

    @staticmethod
    def get_reflection_status_expired(
        lection_topic: str,
        deadline: datetime,
        recorded_videos_count: int,
    ) -> str:
        """Статус рефлексии, если дедлайн закончился и записи есть."""
        return (
            f"⏰ Дедлайн по лекции <b>{lection_topic}</b> закончился "
            f"{TelegramMessages._format_datetime(deadline)}.\n\n"
            f"🎥 Записано кружков/видео: {recorded_videos_count}"
        )

    @staticmethod
    def get_reflection_status_expired_without_videos(
        lection_topic: str,
        deadline: datetime,
    ) -> str:
        """Статус рефлексии, если дедлайн закончился и записи отсутствуют."""
        return (
            f"⏰ Дедлайн по лекции <b>{lection_topic}</b> закончился "
            f"{TelegramMessages._format_datetime(deadline)}.\n\n"
            "Кружки/видео по этой лекции не записаны.\n"
            "Если запись всё же нужна, обратитесь в техподдержку."
        )

    @staticmethod
    def get_reflection_already_submitted() -> str:
        """Сообщение, если рефлексия по лекции уже отправлена."""
        return "Рефлексия по этой лекции уже отправлена вами."

    @staticmethod
    def get_student_course_code_request() -> str:
        """Сообщение с просьбой ввести код курса."""
        return "Привет, студент! Введите код курса, который вам сообщили, чтобы записаться на него"

    @staticmethod
    def get_student_course_fullname_request(course_name: str) -> str:
        """Сообщение с просьбой ввести ФИО после выбора курса."""
        return f"Вы выбрали курс <b>{course_name}</b>.\n\nВведите своё ФИО."

    @staticmethod
    def get_join_course_code_request() -> str:
        """Сообщение для команды join_course."""
        return "Введите код курса, чтобы записаться на него:"

    @staticmethod
    def get_course_code_not_found() -> str:
        """Сообщение о несуществующем коде курса."""
        return "⚠️ Такого курса не существует. Проверьте код и попробуйте снова:"

    @staticmethod
    def get_student_course_registered(course_name: str) -> str:
        """Сообщение об успешной записи студента на курс."""
        return f"Вы успешно записались на курс: <b>{course_name}</b>. \n\nТеперь осталось дождаться уведомления о завершении первой лекции — и можно будет отправить рефлексию."

    @staticmethod
    def get_join_course_permission_denied() -> str:
        """Сообщение, если join_course вызван не студентом."""
        return "Команда join_course доступна только уже зарегистрированному студенту. Нажмите команду /start"
    
    @staticmethod
    def get_upload_presentation_request() -> str:
        """Запрос загрузки презентации."""
        return "📎 Загрузите файл презентации:"
    
    @staticmethod
    def get_presentation_uploaded() -> str:
        """Сообщение об успешной загрузке презентации."""
        return "✅ Презентация загружена!"
    
    @staticmethod
    def get_upload_recording_request() -> str:
        """Запрос загрузки записи лекции."""
        return "🎥 Загрузите файл записи лекции:"
    
    @staticmethod
    def get_recording_uploaded() -> str:
        """Сообщение об успешной загрузке записи."""
        return "✅ Запись лекции загружена!"
    
    # Сообщения для привязки преподавателей
    
    @staticmethod
    def get_attach_teacher_request_fullname() -> str:
        """Запрос ФИО преподавателя."""
        return "👨‍🏫 Введите ФИО преподавателя:"
    
    @staticmethod
    def get_attach_teacher_request_username() -> str:
        """Запрос username преподавателя."""
        return "📝 Введите никнейм преподавателя в Telegram (без @):"
    
    @staticmethod
    def get_teacher_attached(teacher_name: str) -> str:
        """Сообщение об успешной привязке преподавателя."""
        return f"✅ Преподаватель {teacher_name} успешно добавлен к курсу!"
    
    # Сообщения для привязки студентов
    
    @staticmethod
    def get_attach_students_request_file() -> str:
        """Запрос CSV файла со студентами."""
        return "👨‍🎓 Загрузите CSV файл со списком студентов:\n\nФормат: ФИО, username"
    
    @staticmethod
    def get_students_attached(count: int) -> str:
        """Сообщение об успешной привязке студентов."""
        return f"✅ Добавлено студентов: {count}"
    
    # Сообщения для аналитики
    
    @staticmethod
    def get_select_course_for_analytics() -> str:
        """Запрос выбора курса для аналитики."""
        return "📊 <b>Аналитика</b>\n\nВыберите сессию курса:"
    
    @staticmethod
    def get_course_analytics_menu(course_name: str) -> str:
        """Меню аналитики курса."""
        return f"📊 <b>Аналитика</b>\n\n📚 {course_name}\n\nВыберите действие:"
    
    @staticmethod
    def get_select_lection_for_analytics() -> str:
        """Запрос выбора лекции для аналитики."""
        return "📝 Выберите лекцию:"
    
    @staticmethod
    def get_lection_statistics(
        topic: str,
        started_at: datetime,
        total_students: int,
        reflections_count: int,
        qa_count: int,
    ) -> str:
        """Статистика по лекции."""
        return f"""📊 <b>Статистика по лекции</b>

📝 {topic}
📅 {TelegramMessages._format_datetime(started_at)}

👥 Всего студентов: {total_students}
✍️ Рефлексий: {reflections_count}
❓ Ответов на вопросы: {qa_count}

Студенты, отправившие рефлексии:"""
    
    @staticmethod
    def get_select_student_for_analytics() -> str:
        """Запрос выбора студента для аналитики."""
        return "👨‍🎓 Выберите студента:"
    
    @staticmethod
    def get_student_statistics(
        student_name: str,
        total_lections: int,
        reflections_count: int,
        qa_count: int,
    ) -> str:
        """Статистика студента по курсу."""
        return f"""📊 <b>Статистика студента</b>

👨‍🎓 {student_name}

📝 Всего лекций: {total_lections}
✍️ Рефлексий: {reflections_count}
❓ Ответов на вопросы: {qa_count}

Лекции с рефлексиями:"""
    
    @staticmethod
    def get_reflection_details(
        student_name: str,
        lection_topic: str,
        created_at: datetime,
    ) -> str:
        """Детали рефлексии студента."""
        return f"""✍️ <b>Рефлексия</b>

👨‍🎓 {student_name}
📝 {lection_topic}
📅 {TelegramMessages._format_datetime(created_at)}"""
    
    @staticmethod
    def get_nearest_lection_info(
        topic: str,
        started_at: datetime,
        ended_at: datetime,
    ) -> str:
        """Информация о ближайшей лекции."""
        return f"""📅 <b>Ближайшая лекция</b>

📝 {topic}
📅 {TelegramMessages._format_date(started_at)}
🕐 {TelegramMessages._format_time(started_at)}–{TelegramMessages._format_time(ended_at)}"""
    
    @staticmethod
    def get_no_upcoming_lections() -> str:
        """Сообщение об отсутствии запланированных лекций."""
        return "📅 Нет запланированных лекций"
    
    # Сообщения валидации
    
    @staticmethod
    def get_validation_error_fullname() -> str:
        """Ошибка валидации ФИО."""
        return "⚠️ ФИО должно содержать минимум 3 символа. Попробуйте снова:"
    
    @staticmethod
    def get_validation_error_username() -> str:
        """Ошибка валидации username."""
        return "⚠️ Никнейм не должен содержать символ @. Попробуйте снова:"

    @staticmethod
    def get_validation_error_course_name() -> str:
        """Ошибка валидации названия курса."""
        return "⚠️ Название курса должно содержать минимум 2 символа. Попробуйте снова:"
    
    @staticmethod
    def get_username_already_exists() -> str:
        """Ошибка - username уже существует."""
        return "⚠️ Администратор с таким никнеймом уже существует. Введите другой никнейм:"
    
    # Сообщения об ошибках
    
    @staticmethod
    def get_permission_denied() -> str:
        """Сообщение о недостаточных правах."""
        return "⚠️ Недостаточно прав для выполнения этого действия"
    
    @staticmethod
    def get_file_parsing_error(error: str) -> str:
        """Сообщение об ошибке парсинга файла."""
        return f"⚠️ Ошибка обработки файла:\n\n{error}\n\nПопробуйте загрузить другой файл."

    @staticmethod
    def get_course_join_code_already_exists() -> str:
        """Сообщение о том, что код курса уже занят."""
        return (
            "⚠️ Курс с таким кодом уже существует.\n\n"
            "Укажите в Excel другой код курса и попробуйте снова."
        )
    
    @staticmethod
    def get_generic_error() -> str:
        """Общее сообщение об ошибке."""
        return "⚠️ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
    
    @staticmethod
    def get_not_found_error(entity: str) -> str:
        """Сообщение о том, что сущность не найдена."""
        return f"⚠️ {entity} не найден(а)"
