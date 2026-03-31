# Модуль Reflections

Модуль для работы с рефлексиями студентов по лекциям.

## Модели данных

### Основные сущности

#### CourseSession
Сессия курса (семестр, поток).
- `name` - название курса
- `started_at` - дата начала
- `ended_at` - дата окончания

#### LectionSession
Отдельная лекция в рамках курса.
- `course_session_id` - связь с курсом
- `topic` - тема лекции
- `presentation_file` - путь к файлу презентации (опционально)
- `recording_file` - путь к записи лекции (опционально)
- `started_at` - время начала
- `ended_at` - время окончания

#### Question
Вопросы к лекции для студентов.
- `lection_session_id` - связь с лекцией
- `question_text` - текст вопроса

### Пользователи

#### Student
Студенты, зарегистрированные на курс.
- `full_name` - ФИО
- `telegram_username` - никнейм в Telegram
- `telegram_id` - ID в Telegram (опционально)
- `is_active` - активен ли студент

#### Teacher
Преподаватели курса.
- `full_name` - ФИО
- `telegram_username` - никнейм в Telegram
- `telegram_id` - ID в Telegram (опционально)
- `is_active` - активен ли преподаватель

#### Admin
Администраторы системы.
- `full_name` - ФИО
- `telegram_username` - никнейм в Telegram
- `telegram_id` - ID в Telegram (опционально)
- `is_active` - активен ли администратор

### Связи

#### StudentCourse
Привязка студента к курсу.
- `student_id` - ID студента
- `course_session_id` - ID курса
- Уникальное ограничение: один студент может быть привязан к курсу только один раз

#### StudentLection
Привязка студента к лекции (посещаемость).
- `student_id` - ID студента
- `lection_session_id` - ID лекции
- Уникальное ограничение: один студент может быть привязан к лекции только один раз

#### TeacherCourse
Привязка преподавателя к курсу.
- `teacher_id` - ID преподавателя
- `course_session_id` - ID курса

#### TeacherLection
Привязка преподавателя к лекции.
- `teacher_id` - ID преподавателя
- `lection_session_id` - ID лекции

### Рефлексии

#### LectionReflection
Рефлексия студента по лекции.
- `student_id` - ID студента
- `lection_session_id` - ID лекции
- `submitted_at` - время отправки
- `ai_analysis_status` - статус AI-анализа (pending/done/failed)
- Уникальное ограничение: один студент может отправить только одну рефлексию на лекцию

#### ReflectionVideo
Видео-файлы рефлексии (может быть несколько).
- `reflection_id` - ID рефлексии
- `video_id` - идентификатор видео
- `video_path` - путь к файлу
- `order_index` - порядковый номер видео
- Уникальное ограничение: порядковый номер уникален в рамках одной рефлексии

#### LectionQA
Ответ студента на вопрос по лекции.
- `reflection_id` - ID рефлексии
- `question_id` - ID вопроса
- `answer_submitted_at` - время отправки ответа
- Уникальное ограничение: один ответ на один вопрос в рамках рефлексии

#### QAVideo
Видео-ответ на вопрос.
- `lection_qa_id` - ID ответа на вопрос
- `answer_video_id` - идентификатор видео
- `answer_video_path` - путь к файлу

## Enums

### AIAnalysisStatus
Статус AI-анализа рефлексии:
- `PENDING` - ожидает обработки
- `DONE` - обработан
- `FAILED` - ошибка обработки

## Связи между моделями

```
CourseSession
├── LectionSession (1:N)
│   ├── Question (1:N)
│   ├── StudentLection (1:N)
│   ├── TeacherLection (1:N)
│   └── LectionReflection (1:N)
│       ├── ReflectionVideo (1:N)
│       └── LectionQA (1:N)
│           └── QAVideo (1:N)
├── StudentCourse (1:N)
└── TeacherCourse (1:N)

Student
├── StudentCourse (1:N)
├── StudentLection (1:N)
└── LectionReflection (1:N)

Teacher
├── TeacherCourse (1:N)
└── TeacherLection (1:N)
```

## Миграции

Для применения миграций:

```bash
# Применить все миграции
uv run alembic upgrade head

# Откатить последнюю миграцию
uv run alembic downgrade -1

# Создать новую миграцию после изменения моделей
uv run alembic revision --autogenerate -m "описание изменений"
```
