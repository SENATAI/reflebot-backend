"""
Smoke-проверка task 25 через локально поднятый backend.

Скрипт проверяет живые workflow'ы через HTTP API, а также подтверждает
результаты через PostgreSQL, RabbitMQ и текущий Telegram file_id workflow.
"""

from __future__ import annotations

import asyncio
import csv
import json
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aio_pika
from aio_pika.exceptions import QueueEmpty
import openpyxl
import sqlalchemy as sa


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from reflebot.apps.reflections.enums import AIAnalysisStatus  # noqa: E402
from reflebot.apps.reflections.models import (  # noqa: E402
    Admin,
    CourseSession,
    LectionQA,
    LectionReflection,
    LectionSession,
    NotificationDelivery,
    QAVideo,
    Question,
    ReflectionVideo,
    Student,
    StudentCourse,
    StudentLection,
    Teacher,
    TeacherCourse,
    TeacherLection,
)
from reflebot.apps.reflections.schemas import ReflectionPromptCommandSchema  # noqa: E402
from reflebot.core.db import AsyncSessionFactory  # noqa: E402
from reflebot.settings import settings  # noqa: E402


BASE_URL = "http://127.0.0.1:8080"
API_URL = f"{BASE_URL}/api/reflections"
API_KEY = settings.telegram_secret_token

ADMIN_TELEGRAM_ID = 700001


@dataclass
class CourseState:
    """Снимок состояния курса из БД."""

    course_id: uuid.UUID
    lection_ids: list[uuid.UUID]


@dataclass
class BrokerProbeState:
    """Сущности для проверки prompt delivery через RabbitMQ."""

    course_id: uuid.UUID
    lection_id: uuid.UUID
    student_id: uuid.UUID
    topic: str
    telegram_id: int


class SmokeFailure(RuntimeError):
    """Исключение сценария smoke-проверки."""


def log(message: str) -> None:
    """Напечатать шаг проверки."""
    print(f"[task25] {message}", flush=True)


def require(condition: bool, message: str) -> None:
    """Проверить инвариант сценария."""
    if not condition:
        raise SmokeFailure(message)


def run_curl(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Запустить curl и убедиться, что он завершился успешно."""
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT_DIR,
        check=False,
    )
    if result.returncode != 0:
        raise SmokeFailure(
            f"curl завершился с кодом {result.returncode}: {result.stderr.strip()}"
        )
    return result


def parse_http_output(stdout: str) -> tuple[int, str]:
    """Разобрать вывод curl, где последней строкой идёт HTTP статус."""
    body, status_text = stdout.rsplit("\n", maxsplit=1)
    return int(status_text.strip()), body


def get_raw(path: str) -> tuple[int, str]:
    """Выполнить GET запрос."""
    result = run_curl(
        [
            "curl",
            "-sS",
            f"{BASE_URL}{path}",
            "-w",
            "\n%{http_code}",
        ]
    )
    return parse_http_output(result.stdout)


def post_json(
    path: str,
    payload: dict,
    *,
    telegram_id: int | None = None,
    expected_status: int = 200,
) -> dict:
    """Выполнить JSON POST запрос."""
    command = [
        "curl",
        "-sS",
        "-X",
        "POST",
        f"{API_URL}{path}",
        "-H",
        f"X-Service-API-Key: {API_KEY}",
        "-H",
        "Content-Type: application/json",
        "--data",
        json.dumps(payload, ensure_ascii=False),
        "-w",
        "\n%{http_code}",
    ]
    if telegram_id is not None:
        command.extend(["-H", f"X-Telegram-Id: {telegram_id}"])
    result = run_curl(command)
    status, body = parse_http_output(result.stdout)
    require(
        status == expected_status,
        f"Ожидался HTTP {expected_status} для {path}, получен {status}: {body}",
    )
    return json.loads(body)


def post_file(
    path: str,
    file_path: Path,
    *,
    telegram_id: int,
    content_type: str,
    expected_status: int = 200,
) -> dict:
    """Выполнить multipart POST запрос."""
    result = run_curl(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            f"{API_URL}{path}",
            "-H",
            f"X-Service-API-Key: {API_KEY}",
            "-H",
            f"X-Telegram-Id: {telegram_id}",
            "-F",
            f"file=@{file_path};type={content_type}",
            "-w",
            "\n%{http_code}",
        ]
    )
    status, body = parse_http_output(result.stdout)
    require(
        status == expected_status,
        f"Ожидался HTTP {expected_status} для загрузки {file_path.name}, получен {status}: {body}",
    )
    return json.loads(body)


def post_telegram_file_id(
    path: str,
    telegram_file_id: str,
    *,
    telegram_id: int,
    expected_status: int = 200,
) -> dict:
    """Отправить multipart запрос только с Telegram file_id."""
    result = run_curl(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            f"{API_URL}{path}",
            "-H",
            f"X-Service-API-Key: {API_KEY}",
            "-H",
            f"X-Telegram-Id: {telegram_id}",
            "-F",
            f"telegram_file_id={telegram_file_id}",
            "-w",
            "\n%{http_code}",
        ]
    )
    status, body = parse_http_output(result.stdout)
    require(
        status == expected_status,
        f"Ожидался HTTP {expected_status} для telegram_file_id {telegram_file_id}, "
        f"получен {status}: {body}",
    )
    return json.loads(body)


def button_actions(response: dict) -> list[str]:
    """Получить список actions из ответа."""
    return [button["action"] for button in response.get("buttons", [])]


def find_button_action(
    response: dict,
    *,
    exact: str | None = None,
    prefix: str | None = None,
    text_contains: str | None = None,
) -> str:
    """Найти действие кнопки по условию."""
    for button in response.get("buttons", []):
        if exact is not None and button["action"] != exact:
            continue
        if prefix is not None and not button["action"].startswith(prefix):
            continue
        if text_contains is not None and text_contains not in button["text"]:
            continue
        return button["action"]
    raise SmokeFailure(
        f"Не удалось найти кнопку: exact={exact}, prefix={prefix}, text_contains={text_contains}. "
        f"Доступные кнопки: {button_actions(response)}"
    )


def create_excel(path: Path, course_name: str, rows: list[dict[str, str]]) -> None:
    """Создать Excel файл курса."""
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["Название", "Тема лекции", "Дата", "Время"])
    for row in rows:
        worksheet.append(
            [
                course_name,
                row["topic"],
                row["date"],
                row["time"],
            ]
        )
    workbook.save(path)


def create_csv_file(path: Path, rows: list[dict[str, str]]) -> None:
    """Создать CSV файл студентов."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["ФИО", "username"])
        writer.writeheader()
        writer.writerows(rows)


class RabbitPromptProbe:
    """Проба для чтения reflection prompt команд из RabbitMQ."""

    def __init__(self) -> None:
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.abc.AbstractChannel | None = None
        self.queue: aio_pika.abc.AbstractQueue | None = None

    async def start(self) -> None:
        """Подключиться к prompt queue."""
        self.connection = await aio_pika.connect_robust(settings.rabbitmq.dsn)
        self.channel = await self.connection.channel()
        exchange = await self.channel.declare_exchange(
            settings.rabbitmq.notifications_exchange,
            type="direct",
            durable=True,
        )
        self.queue = await self.channel.declare_queue(
            settings.rabbitmq.reflection_prompt_queue,
            durable=True,
        )
        await self.queue.bind(
            exchange,
            routing_key=settings.rabbitmq.reflection_prompt_routing_key,
        )

    async def purge(self) -> None:
        """Очистить очередь перед детерминированной проверкой."""
        require(self.queue is not None, "Prompt queue не подготовлена")
        await self.queue.purge()

    async def wait_for_command(
        self,
        *,
        expected_lection_id: uuid.UUID,
        timeout_seconds: int,
    ) -> ReflectionPromptCommandSchema:
        """Дождаться команды для конкретной лекции."""
        require(self.queue is not None, "Prompt queue не подготовлена")
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while asyncio.get_running_loop().time() < deadline:
            try:
                message = await self.queue.get(timeout=1)
            except QueueEmpty:
                await asyncio.sleep(0.2)
                continue
            try:
                command = ReflectionPromptCommandSchema.model_validate_json(message.body)
            finally:
                await message.ack()
            if command.lection_session_id == expected_lection_id:
                return command

        raise SmokeFailure(
            f"Не дождались reflection prompt для lection_session_id={expected_lection_id}"
        )

    async def close(self) -> None:
        """Закрыть RabbitMQ соединение."""
        if self.channel is not None:
            await self.channel.close()
        if self.connection is not None:
            await self.connection.close()


async def get_course_state(course_name: str) -> CourseState:
    """Получить курс и список его лекций из БД."""
    async with AsyncSessionFactory() as session:
        course = (
            await session.execute(
                sa.select(CourseSession).where(CourseSession.name == course_name)
            )
        ).scalar_one()
        lections = (
            await session.execute(
                sa.select(LectionSession)
                .where(LectionSession.course_session_id == course.id)
                .order_by(LectionSession.started_at)
            )
        ).scalars().all()
        return CourseState(
            course_id=course.id,
            lection_ids=[lection.id for lection in lections],
        )


async def get_course_counts(course_id: uuid.UUID) -> dict[str, int]:
    """Получить counts по привязкам курса."""
    async with AsyncSessionFactory() as session:
        lections_count = (
            await session.execute(
                sa.select(sa.func.count(LectionSession.id)).where(
                    LectionSession.course_session_id == course_id
                )
            )
        ).scalar_one()
        teacher_courses_count = (
            await session.execute(
                sa.select(sa.func.count(TeacherCourse.id)).where(
                    TeacherCourse.course_session_id == course_id
                )
            )
        ).scalar_one()
        teacher_lections_count = (
            await session.execute(
                sa.select(sa.func.count(TeacherLection.id))
                .join(
                    LectionSession,
                    LectionSession.id == TeacherLection.lection_session_id,
                )
                .where(LectionSession.course_session_id == course_id)
            )
        ).scalar_one()
        student_courses_count = (
            await session.execute(
                sa.select(sa.func.count(StudentCourse.id)).where(
                    StudentCourse.course_session_id == course_id
                )
            )
        ).scalar_one()
        student_lections_count = (
            await session.execute(
                sa.select(sa.func.count(StudentLection.id))
                .join(
                    LectionSession,
                    LectionSession.id == StudentLection.lection_session_id,
                )
                .where(LectionSession.course_session_id == course_id)
            )
        ).scalar_one()
    return {
        "lections": lections_count,
        "teacher_courses": teacher_courses_count,
        "teacher_lections": teacher_lections_count,
        "student_courses": student_courses_count,
        "student_lections": student_lections_count,
    }


async def get_admin_by_username(username: str) -> Admin:
    """Получить администратора по username."""
    async with AsyncSessionFactory() as session:
        admin = (
            await session.execute(
                sa.select(Admin).where(Admin.telegram_username == username)
            )
        ).scalar_one()
        return admin


async def get_teacher_by_username(username: str) -> Teacher:
    """Получить преподавателя по username."""
    async with AsyncSessionFactory() as session:
        teacher = (
            await session.execute(
                sa.select(Teacher).where(Teacher.telegram_username == username)
            )
        ).scalar_one()
        return teacher


async def get_student_by_username(username: str) -> Student:
    """Получить студента по username."""
    async with AsyncSessionFactory() as session:
        student = (
            await session.execute(
                sa.select(Student).where(Student.telegram_username == username)
            )
        ).scalar_one()
        return student


async def get_lection_by_topic(course_id: uuid.UUID, topic: str) -> LectionSession:
    """Получить лекцию по topic внутри курса."""
    async with AsyncSessionFactory() as session:
        lection = (
            await session.execute(
                sa.select(LectionSession).where(
                    LectionSession.course_session_id == course_id,
                    LectionSession.topic == topic,
                )
            )
        ).scalar_one()
        return lection


async def create_broker_probe_state(suffix: str) -> BrokerProbeState:
    """Создать isolated лекцию, которая завершится через 2 минуты."""
    current_time = datetime.now(timezone.utc)
    course_id = uuid.uuid4()
    lection_id = uuid.uuid4()
    student_id = uuid.uuid4()
    topic = f"Task25 Broker Topic {suffix}"
    telegram_id = 900_000_000 + int(suffix[-6:])

    async with AsyncSessionFactory() as session, session.begin():
        session.add(
            CourseSession(
                id=course_id,
                name=f"Task25 Broker Course {suffix}",
                started_at=current_time - timedelta(minutes=30),
                ended_at=current_time + timedelta(hours=2),
            )
        )
        session.add(
            LectionSession(
                id=lection_id,
                course_session_id=course_id,
                topic=topic,
                started_at=current_time - timedelta(minutes=10),
                ended_at=current_time + timedelta(minutes=2),
            )
        )
        session.add(
            Student(
                id=student_id,
                full_name=f"Task25 Broker Student {suffix}",
                telegram_username=f"task25_broker_student_{suffix}",
                telegram_id=telegram_id,
                is_active=True,
            )
        )
        session.add(
            StudentLection(
                id=uuid.uuid4(),
                student_id=student_id,
                lection_session_id=lection_id,
            )
        )

    return BrokerProbeState(
        course_id=course_id,
        lection_id=lection_id,
        student_id=student_id,
        topic=topic,
        telegram_id=telegram_id,
    )


async def cleanup_broker_probe_state(state: BrokerProbeState | None) -> None:
    """Удалить только данные broker probe из БД."""
    if state is None:
        return
    async with AsyncSessionFactory() as session, session.begin():
        await session.execute(
            sa.delete(NotificationDelivery).where(
                NotificationDelivery.lection_session_id == state.lection_id,
            )
        )
        await session.execute(
            sa.delete(StudentLection).where(
                StudentLection.lection_session_id == state.lection_id,
            )
        )
        await session.execute(
            sa.delete(LectionSession).where(LectionSession.id == state.lection_id)
        )
        await session.execute(sa.delete(Student).where(Student.id == state.student_id))
        await session.execute(
            sa.delete(CourseSession).where(CourseSession.id == state.course_id)
        )


async def wait_for_delivery_status(
    *,
    lection_id: uuid.UUID,
    student_id: uuid.UUID,
    expected_status: str,
    timeout_seconds: int = 240,
) -> NotificationDelivery:
    """Дождаться статуса delivery для broker smoke."""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        async with AsyncSessionFactory() as session:
            delivery = (
                await session.execute(
                    sa.select(NotificationDelivery).where(
                        NotificationDelivery.lection_session_id == lection_id,
                        NotificationDelivery.student_id == student_id,
                    )
                )
            ).scalar_one_or_none()
            actual_status = getattr(delivery.status, "value", delivery.status) if delivery is not None else None
            if delivery is not None and actual_status == expected_status:
                return delivery
        await asyncio.sleep(0.5)
    raise SmokeFailure(
        f"Не дождались статуса {expected_status} для lection={lection_id} student={student_id}"
    )


async def seed_reflection(
    *,
    course_id: uuid.UUID,
    lection_id: uuid.UUID,
    student_username: str,
) -> None:
    """Добавить реальную рефлексию и QA в БД для analytics workflow."""
    now = datetime.now(timezone.utc)

    async with AsyncSessionFactory() as session, session.begin():
        student = (
            await session.execute(
                sa.select(Student).where(Student.telegram_username == student_username)
            )
        ).scalar_one()
        lection = (
            await session.execute(
                sa.select(LectionSession).where(LectionSession.id == lection_id)
            )
        ).scalar_one()
        require(
            lection.presentation_file_id is not None,
            "Для analytics smoke нужна загруженная презентация на лекции",
        )
        require(
            lection.recording_file_id is not None,
            "Для analytics smoke нужна загруженная запись лекции",
        )

        question = (
            await session.execute(
                sa.select(Question)
                .where(Question.lection_session_id == lection_id)
                .order_by(Question.created_at.asc())
            )
        ).scalar_one()

        reflection = LectionReflection(
            student_id=student.id,
            lection_session_id=lection_id,
            submitted_at=now,
            ai_analysis_status=AIAnalysisStatus.PENDING,
        )
        session.add(reflection)
        await session.flush()

        reflection_video = ReflectionVideo(
            reflection_id=reflection.id,
            file_id=lection.presentation_file_id,
            order_index=1,
        )
        session.add(reflection_video)

        lection_qa = LectionQA(
            reflection_id=reflection.id,
            question_id=question.id,
            answer_submitted_at=now + timedelta(minutes=2),
        )
        session.add(lection_qa)
        await session.flush()

        qa_video = QAVideo(
            lection_qa_id=lection_qa.id,
            file_id=lection.recording_file_id,
            order_index=1,
        )
        session.add(qa_video)

    counts = await get_course_counts(course_id)
    require(counts["student_courses"] >= 1, "После seed ожидается как минимум один студент на курсе")


def build_main_course_rows() -> list[dict[str, str]]:
    """Подготовить данные Excel для основного workflow."""
    return [
        {
            "topic": "Topic 1",
            "date": "31.03.2026",
            "time": "10:00-11:30",
        },
        {
            "topic": "Topic 2",
            "date": "02.04.2026",
            "time": "12:00-13:30",
        },
    ]


def build_perf_rows(total: int) -> list[dict[str, str]]:
    """Подготовить большой Excel для bulk smoke."""
    base = datetime(2026, 4, 1, 9, 0, 0)
    rows: list[dict[str, str]] = []
    for index in range(total):
        current = base + timedelta(days=index)
        rows.append(
            {
                "topic": f"Perf Topic {index + 1:02d}",
                "date": current.strftime("%d.%m.%Y"),
                "time": "09:00-10:30",
            }
        )
    return rows


async def main() -> None:
    """Запустить полный smoke-сценарий task 25."""
    started = time.perf_counter()
    suffix = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_telegram_base = 800_000_000 + int(suffix[-6:])
    second_admin_telegram_id = unique_telegram_base + 1
    teacher_telegram_id = unique_telegram_base + 2

    created_admin_username = f"task25_admin_{suffix}"
    teacher_username = f"task25_teacher_{suffix}"
    perf_teacher_username = f"task25_perf_teacher_{suffix}"
    main_student_usernames = [f"task25_student_a_{suffix}", f"task25_student_b_{suffix}"]
    perf_student_usernames = [f"task25_perf_{index:03d}_{suffix}" for index in range(110)]
    main_course_name = f"Task25 Course {suffix}"
    perf_course_name = f"Task25 Perf Course {suffix}"
    created_admin_full_name = f"Task 25 Admin {suffix}"
    teacher_full_name = f"Task 25 Teacher {suffix}"
    perf_teacher_full_name = f"Task 25 Perf Teacher {suffix}"
    updated_topic = f"Updated Topic {suffix}"
    added_question = f"What worked well? {suffix}"
    second_question = f"What needs improvement? {suffix}"
    edited_question = f"Updated question text {suffix}"
    broker_probe: RabbitPromptProbe | None = None
    broker_probe_state: BrokerProbeState | None = None
    broker_started_at: float | None = None
    late_temp_dir: tempfile.TemporaryDirectory | None = None

    try:
        log("Подготавливаю RabbitMQ probe для проверки prompt delivery")
        broker_probe = RabbitPromptProbe()
        await broker_probe.start()
        await broker_probe.purge()
        broker_probe_state = await create_broker_probe_state(suffix)
        broker_started_at = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix="task25_") as temp_dir:
            temp_path = Path(temp_dir)
            invalid_excel = temp_path / "invalid.xlsx"
            invalid_excel.write_bytes(b"not-an-excel")

            valid_excel = temp_path / "course.xlsx"
            create_excel(valid_excel, main_course_name, build_main_course_rows())

            invalid_csv = temp_path / "invalid.csv"
            invalid_csv.write_text("bad,data\n1,2\n", encoding="utf-8")

            valid_csv = temp_path / "students.csv"
            create_csv_file(
                valid_csv,
                [
                    {"ФИО": f"Student One {suffix}", "username": main_student_usernames[0]},
                    {"ФИО": f"Student Two {suffix}", "username": main_student_usernames[1]},
                ],
            )

            presentation_file = temp_path / "presentation.txt"
            presentation_file.write_text(f"presentation-{suffix}", encoding="utf-8")

            recording_file = temp_path / "recording.txt"
            recording_file.write_text(f"recording-{suffix}", encoding="utf-8")

            perf_excel = temp_path / "perf_course.xlsx"
            create_excel(perf_excel, perf_course_name, build_perf_rows(55))

            perf_csv = temp_path / "perf_students.csv"
            create_csv_file(
                perf_csv,
                [
                    {
                        "ФИО": f"Perf Student {index:03d} {suffix}",
                        "username": username,
                    }
                    for index, username in enumerate(perf_student_usernames, start=1)
                ],
            )

            log("Проверяю Swagger UI и OpenAPI")
            docs_status, docs_body = get_raw("/docs")
            require(docs_status == 200, f"/docs вернул {docs_status}")
            require("Swagger UI" in docs_body, "В /docs не найден Swagger UI")

            openapi_status, openapi_body = get_raw("/docs.json")
            require(openapi_status == 200, f"/docs.json вернул {openapi_status}")
            openapi = json.loads(openapi_body)
            for required_path in [
                "/api/reflections/auth/{telegram_username}/login",
                "/api/reflections/actions/button/{action}",
                "/api/reflections/actions/text",
                "/api/reflections/actions/file",
            ]:
                require(required_path in openapi["paths"], f"В OpenAPI отсутствует путь {required_path}")

            log("Выполняю логин администратора Syrnick")
            login_response = post_json(
                "/auth/Syrnick/login",
                {"telegram_id": ADMIN_TELEGRAM_ID},
            )
            require(login_response["is_admin"] is True, "Syrnick должен быть администратором")
            require(
                "admin_create_admin" in button_actions(login_response),
                "После логина админа должна быть кнопка создания администратора",
            )

            log("Проверяю многошаговое создание администратора")
            response = post_json(
                "/actions/button/admin_create_admin",
                {},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(response["awaiting_input"] is True, "Ожидался prompt на ФИО администратора")

            response = post_json(
                "/actions/text",
                {"text": created_admin_full_name},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(
                "никнейм" in response["message"].lower(),
                "После ФИО должен запрашиваться username администратора",
            )

            duplicate_response = post_json(
                "/actions/text",
                {"text": "Syrnick"},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(
                "уже существует" in duplicate_response["message"].lower(),
                "Для дубликата username ожидалась понятная ошибка",
            )

            response = post_json(
                "/actions/text",
                {"text": created_admin_username},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(
                "успешно создан" in response["message"].lower(),
                "Администратор должен успешно создаться",
            )

            created_admin = await get_admin_by_username(created_admin_username)
            require(created_admin.telegram_id is None, "Новый админ должен создаваться с telegram_id=None")

            second_admin_login = post_json(
                f"/auth/{created_admin_username}/login",
                {"telegram_id": second_admin_telegram_id},
            )
            require(
                second_admin_login["is_admin"] is True,
                "Созданный администратор должен успешно логиниться",
            )

            log("Проверяю workflow создания курса из Excel")
            response = post_json(
                "/actions/button/admin_create_course",
                {},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(response["awaiting_input"] is True, "После admin_create_course должен ожидаться файл")

            invalid_excel_response = post_file(
                "/actions/file",
                invalid_excel,
                telegram_id=ADMIN_TELEGRAM_ID,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            require(
                "ошибка обработки файла" in invalid_excel_response["message"].lower(),
                "Некорректный Excel должен возвращать понятную ошибку",
            )

            response = post_file(
                "/actions/file",
                valid_excel,
                telegram_id=ADMIN_TELEGRAM_ID,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            require(main_course_name in response["message"], "Созданный курс должен отображаться в ответе")
            require(
                "course_view_parsed_lections" in button_actions(response),
                "После создания курса должно быть меню курса",
            )

            main_course_state = await get_course_state(main_course_name)
            require(len(main_course_state.lection_ids) == 2, "Ожидалось 2 лекции после парсинга Excel")

            log("Проверяю просмотр лекций, редактирование и управление вопросами")
            response = post_json(
                "/actions/button/course_view_parsed_lections",
                {},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            first_lection_action = find_button_action(response, prefix="lection_info:")

            response = post_json(
                f"/actions/button/{first_lection_action}",
                {},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require("вопросов" in response["message"].lower(), "Должны открыться детали лекции")

            response = post_json(
                "/actions/button/lection_edit_topic",
                {},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(response["awaiting_input"] is True, "При редактировании темы должен ожидаться текст")

            response = post_json(
                "/actions/text",
                {"text": updated_topic},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(updated_topic in response["message"], "Тема лекции должна обновиться")

            response = post_json(
                "/actions/button/lection_edit_date",
                {},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require(response["awaiting_input"] is True, "При редактировании даты должен ожидаться текст")

            response = post_json(
                "/actions/text",
                {"text": "31.03.2026 14:00-15:30"},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require("31.03.2026" in response["message"], "Обновлённая дата должна отображаться в деталях")
            require("14:00" in response["message"], "Обновлённое время должно отображаться в деталях")

            response = post_json(
                "/actions/button/lection_manage_questions",
                {},
                telegram_id=ADMIN_TELEGRAM_ID,
            )
            require("вопросы" in response["message"].lower(), "Должно открыться меню вопросов")

        late_temp_dir = tempfile.TemporaryDirectory(prefix="task25_late_")
        late_temp_path = Path(late_temp_dir.name)
        invalid_csv = late_temp_path / "invalid.csv"
        invalid_csv.write_text("bad,data\n1,2\n", encoding="utf-8")
        valid_csv = late_temp_path / "students.csv"
        create_csv_file(
            valid_csv,
            [
                {"ФИО": f"Student One {suffix}", "username": main_student_usernames[0]},
                {"ФИО": f"Student Two {suffix}", "username": main_student_usernames[1]},
            ],
        )
        perf_excel = late_temp_path / "perf_course.xlsx"
        create_excel(perf_excel, perf_course_name, build_perf_rows(55))
        perf_csv = late_temp_path / "perf_students.csv"
        create_csv_file(
            perf_csv,
            [
                {
                    "ФИО": f"Perf Student {index:03d} {suffix}",
                    "username": username,
                }
                for index, username in enumerate(perf_student_usernames, start=1)
            ],
        )

        response = post_json(
            "/actions/button/questions_add",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        response = post_json(
            "/actions/text",
            {"text": added_question},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(added_question in response["message"], "Добавленный вопрос должен появиться в списке")

        response = post_json(
            "/actions/button/questions_add",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        response = post_json(
            "/actions/text",
            {"text": second_question},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(second_question in response["message"], "Второй вопрос должен появиться в списке")

        response = post_json(
            "/actions/button/questions_edit",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        response = post_json(
            "/actions/text",
            {"text": f"1 {edited_question}"},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(edited_question in response["message"], "Вопрос должен редактироваться по номеру")

        response = post_json(
            "/actions/button/questions_delete",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        delete_action = find_button_action(
            response,
            prefix="question_delete_specific:",
            text_contains=second_question,
        )
        response = post_json(
            f"/actions/button/{delete_action}",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(edited_question in response["message"], "После удаления должен остаться отредактированный вопрос")
        require(second_question not in response["message"], "Удалённый вопрос не должен отображаться")

        response = post_json(
            "/actions/button/back",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(updated_topic in response["message"], "Назад из вопросов должен вернуть в детали лекции")

        log("Проверяю загрузку и выдачу файлов через Telegram file_id")
        presentation_telegram_file_id = f"task25_presentation_{suffix}"
        recording_telegram_file_id = f"task25_recording_{suffix}"
        response = post_json(
            "/actions/button/lection_manage_presentation",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require("презентация" in response["message"].lower(), "Должно открыться меню презентации")
        response = post_json(
            "/actions/button/presentation_upload",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(response["awaiting_input"] is True, "При загрузке презентации должен ожидаться файл")
        response = post_telegram_file_id(
            "/actions/file",
            presentation_telegram_file_id,
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(
            presentation_telegram_file_id in response["message"],
            "Загруженная презентация должна отображать Telegram file_id",
        )
        require(
            "presentation_download" in button_actions(response),
            "После загрузки презентации должна появиться кнопка скачивания",
        )
        response = post_json(
            "/actions/button/presentation_download",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(
            "файл готов к отправке" in response["message"].lower(),
            "При скачивании презентации backend должен сообщать, что файл готов к отправке",
        )
        require(
            len(response.get("files", [])) == 1,
            "При скачивании презентации должен возвращаться ровно один Telegram file_id",
        )
        require(
            response["files"][0]["telegram_file_id"] == presentation_telegram_file_id,
            "При скачивании презентации должен возвращаться исходный Telegram file_id",
        )
        require(
            response["files"][0]["kind"] == "presentation",
            "При скачивании презентации должен возвращаться kind=presentation",
        )

        response = post_json(
            "/actions/button/back",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(updated_topic in response["message"], "Назад из презентации должен вернуть в лекцию")

        response = post_json(
            "/actions/button/lection_manage_recording",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        response = post_json(
            "/actions/button/recording_upload",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(response["awaiting_input"] is True, "При загрузке записи должен ожидаться файл")
        response = post_telegram_file_id(
            "/actions/file",
            recording_telegram_file_id,
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(
            recording_telegram_file_id in response["message"],
            "Загруженная запись должна отображать Telegram file_id",
        )
        require(
            "recording_download" in button_actions(response),
            "После загрузки записи должна появиться кнопка скачивания",
        )
        response = post_json(
            "/actions/button/recording_download",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(
            "файл готов к отправке" in response["message"].lower(),
            "При скачивании записи backend должен сообщать, что файл готов к отправке",
        )
        require(
            len(response.get("files", [])) == 1,
            "При скачивании записи должен возвращаться ровно один Telegram file_id",
        )
        require(
            response["files"][0]["telegram_file_id"] == recording_telegram_file_id,
            "При скачивании записи должен возвращаться исходный Telegram file_id",
        )
        require(
            response["files"][0]["kind"] == "recording",
            "При скачивании записи должен возвращаться kind=recording",
        )

        response = post_json(
            "/actions/button/back",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(updated_topic in response["message"], "Назад из записи должен вернуть в лекцию")
        response = post_json(
            "/actions/button/back",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require("список лекций" in response["message"].lower(), "Назад из лекции должен вернуть к списку лекций")
        response = post_json(
            "/actions/button/back",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(main_course_name in response["message"], "Назад из списка лекций должен вернуть в меню курса")

        log("Проверяю привязку преподавателя и студентов")
        response = post_json(
            "/actions/button/course_attach_teachers",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(response["awaiting_input"] is True, "При привязке преподавателя должен запрашиваться текст")

        response = post_json(
            "/actions/text",
            {"text": teacher_full_name},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require("никнейм преподавателя" in response["message"].lower(), "После ФИО преподавателя должен запрашиваться username")

        response = post_json(
            "/actions/text",
            {"text": teacher_username},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require("успешно добавлен" in response["message"].lower(), "Преподаватель должен привязаться к курсу")
        require(
            "course_attach_students" in button_actions(response),
            "После преподавателя должен предлагаться переход к привязке студентов",
        )

        teacher = await get_teacher_by_username(teacher_username)
        require(teacher.telegram_id is None, "Новый преподаватель до логина должен иметь telegram_id=None")

        response = post_json(
            "/actions/button/course_attach_students",
            {},
            telegram_id=ADMIN_TELEGRAM_ID,
        )
        require(response["awaiting_input"] is True, "При привязке студентов должен ожидаться CSV")

        invalid_csv_response = post_file(
            "/actions/file",
            invalid_csv,
            telegram_id=ADMIN_TELEGRAM_ID,
            content_type="text/csv",
        )
        require(
            "ошибка обработки файла" in invalid_csv_response["message"].lower(),
            "Некорректный CSV должен возвращать понятную ошибку",
        )

        response = post_file(
            "/actions/file",
            valid_csv,
            telegram_id=ADMIN_TELEGRAM_ID,
            content_type="text/csv",
        )
        require("добавлено студентов: 2" in response["message"].lower(), "Должны привязаться 2 студента")

        main_counts = await get_course_counts(main_course_state.course_id)
        require(main_counts["teacher_courses"] == 1, "Ожидалась одна привязка teacher-course")
        require(main_counts["teacher_lections"] == 2, "Преподаватель должен быть привязан ко всем лекциям")
        require(main_counts["student_courses"] == 2, "Ожидалось две привязки student-course")
        require(main_counts["student_lections"] == 4, "Студенты должны быть привязаны ко всем лекциям")

        main_lection = await get_lection_by_topic(main_course_state.course_id, updated_topic)
        await seed_reflection(
            course_id=main_course_state.course_id,
            lection_id=main_lection.id,
            student_username=main_student_usernames[0],
        )

        log("Проверяю teacher workflow: ближайшая лекция и аналитика")
        teacher_login = post_json(
            f"/auth/{teacher_username}/login",
            {"telegram_id": teacher_telegram_id},
        )
        require(teacher_login["is_teacher"] is True, "Преподаватель должен успешно логиниться")
        require(
            "teacher_analytics" in button_actions(teacher_login),
            "После логина преподавателя должна быть кнопка аналитики",
        )

        nearest_lection = post_json(
            "/actions/button/teacher_next_lection",
            {},
            telegram_id=teacher_telegram_id,
        )
        require(updated_topic in nearest_lection["message"], "Ближайшая лекция должна находиться для преподавателя")

        analytics_courses = post_json(
            "/actions/button/teacher_analytics",
            {},
            telegram_id=teacher_telegram_id,
        )
        course_button = find_button_action(
            analytics_courses,
            prefix="analytics_select_course:",
            text_contains=main_course_name,
        )

        analytics_menu = post_json(
            f"/actions/button/{course_button}",
            {},
            telegram_id=teacher_telegram_id,
        )
        require(main_course_name in analytics_menu["message"], "Должно открываться меню аналитики курса")

        analytics_lections = post_json(
            "/actions/button/analytics_lection_stats",
            {},
            telegram_id=teacher_telegram_id,
        )
        analytics_lection_action = find_button_action(
            analytics_lections,
            prefix="lection_info:",
            text_contains=updated_topic,
        )
        lection_stats = post_json(
            f"/actions/button/{analytics_lection_action}",
            {},
            telegram_id=teacher_telegram_id,
        )
        require("рефлексий: 1" in lection_stats["message"].lower(), "Статистика лекции должна видеть рефлексию")

        reflection_action = find_button_action(
            lection_stats,
            prefix="analytics_view_reflection:",
        )
        reflection_details = post_json(
            f"/actions/button/{reflection_action}",
            {},
            telegram_id=teacher_telegram_id,
        )
        require(
            main_student_usernames[0] not in reflection_details["message"],
            "В деталях рефлексии должен отображаться full_name, а не username",
        )
        require(
            len(reflection_details.get("dialog_messages", [])) >= 2,
            "В деталях рефлексии должен возвращаться диалог из сообщений и кружков",
        )
        require(
            any(item.get("files") for item in reflection_details.get("dialog_messages", [])),
            "В деталях рефлексии должны быть кружки в dialog_messages",
        )
        require(
            any(edited_question in (item.get("message") or "") for item in reflection_details.get("dialog_messages", [])),
            "В деталях рефлексии должен отображаться текст вопроса перед ответом",
        )

        analytics_back = post_json(
            "/actions/button/back",
            {},
            telegram_id=teacher_telegram_id,
        )
        require("статистика по лекции" in analytics_back["message"].lower(), "Назад из рефлексии должен вернуть к статистике лекции")

        analytics_back = post_json(
            "/actions/button/back",
            {},
            telegram_id=teacher_telegram_id,
        )
        require("выберите лекцию" in analytics_back["message"].lower(), "Назад из статистики должен вернуть список лекций")

        analytics_back = post_json(
            "/actions/button/back",
            {},
            telegram_id=teacher_telegram_id,
        )
        require(main_course_name in analytics_back["message"], "Назад должен вернуть в меню аналитики курса")

        student_list = post_json(
            "/actions/button/analytics_find_student",
            {},
            telegram_id=teacher_telegram_id,
        )
        seeded_student = await get_student_by_username(main_student_usernames[0])
        student_action = find_button_action(
            student_list,
            exact=f"analytics_find_student:{seeded_student.id}",
        )
        student_stats = post_json(
            f"/actions/button/{student_action}",
            {},
            telegram_id=teacher_telegram_id,
        )
        require("рефлексий: 1" in student_stats["message"].lower(), "Статистика студента должна учитывать рефлексию")

        permission_denied = post_json(
            "/actions/button/admin_create_course",
            {},
            telegram_id=teacher_telegram_id,
        )
        require(
            "недостаточно прав" in permission_denied["message"].lower(),
            "Преподавателю должно запрещаться админское действие",
        )

        log("Проверяю bulk workflow на 55 лекций и 110 студентов")
        second_admin_login = post_json(
            f"/auth/{created_admin_username}/login",
            {"telegram_id": second_admin_telegram_id},
        )
        require(second_admin_login["is_admin"] is True, "Второй администратор должен быть активен")

        response = post_json(
            "/actions/button/admin_create_course",
            {},
            telegram_id=second_admin_telegram_id,
        )
        require(response["awaiting_input"] is True, "В bulk workflow должен запрашиваться Excel")

        perf_started = time.perf_counter()
        response = post_file(
            "/actions/file",
            perf_excel,
            telegram_id=second_admin_telegram_id,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        perf_excel_seconds = time.perf_counter() - perf_started
        require(perf_course_name in response["message"], "Bulk-курс должен успешно создаваться")

        perf_course_state = await get_course_state(perf_course_name)
        require(len(perf_course_state.lection_ids) == 55, "Ожидалось 55 лекций в bulk-курсе")

        response = post_json(
            "/actions/button/course_view_parsed_lections",
            {},
            telegram_id=second_admin_telegram_id,
        )
        require(
            "next_page" in button_actions(response),
            "Для большого списка лекций должна работать пагинация",
        )

        response = post_json(
            "/actions/button/next_page",
            {},
            telegram_id=second_admin_telegram_id,
        )
        require("список лекций" in response["message"].lower(), "Следующая страница лекций должна открываться")

        response = post_json(
            "/actions/button/back",
            {},
            telegram_id=second_admin_telegram_id,
        )
        require(perf_course_name in response["message"], "Назад должен вернуть к меню bulk-курса")

        response = post_json(
            "/actions/button/course_attach_teachers",
            {},
            telegram_id=second_admin_telegram_id,
        )
        response = post_json(
            "/actions/text",
            {"text": perf_teacher_full_name},
            telegram_id=second_admin_telegram_id,
        )
        response = post_json(
            "/actions/text",
            {"text": perf_teacher_username},
            telegram_id=second_admin_telegram_id,
        )
        require("успешно добавлен" in response["message"].lower(), "Bulk-курс должен принимать преподавателя")

        response = post_json(
            "/actions/button/course_attach_students",
            {},
            telegram_id=second_admin_telegram_id,
        )
        bulk_students_started = time.perf_counter()
        response = post_file(
            "/actions/file",
            perf_csv,
            telegram_id=second_admin_telegram_id,
            content_type="text/csv",
        )
        perf_csv_seconds = time.perf_counter() - bulk_students_started
        require("добавлено студентов: 110" in response["message"].lower(), "Ожидалось массовое добавление 110 студентов")

        perf_counts = await get_course_counts(perf_course_state.course_id)
        require(perf_counts["teacher_courses"] == 1, "В bulk-курсе ожидалась одна привязка teacher-course")
        require(perf_counts["teacher_lections"] == 55, "Преподаватель должен быть привязан к 55 лекциям")
        require(perf_counts["student_courses"] == 110, "Ожидалось 110 привязок student-course")
        require(perf_counts["student_lections"] == 6050, "Ожидалось 110*55 привязок student-lection")

        log("Проверяю prompt delivery через RabbitMQ и Celery")
        require(broker_probe is not None, "RabbitMQ probe должен быть инициализирован")
        require(broker_probe_state is not None, "Broker probe state должен быть создан")
        command = await broker_probe.wait_for_command(
            expected_lection_id=broker_probe_state.lection_id,
            timeout_seconds=240,
        )
        queued_delivery = await wait_for_delivery_status(
            lection_id=broker_probe_state.lection_id,
            student_id=broker_probe_state.student_id,
            expected_status="queued",
            timeout_seconds=240,
        )
        require(command.event_type == "send_reflection_prompt", "В очереди должна лежать команда send_reflection_prompt")
        require(command.telegram_id == broker_probe_state.telegram_id, "В prompt-команде должен совпадать telegram_id студента")
        require(command.student_id == broker_probe_state.student_id, "В prompt-команде должен совпадать student_id")
        require(command.delivery_id == queued_delivery.id, "delivery_id команды должен совпадать с queued delivery из БД")
        require(broker_probe_state.topic in command.message_text, "В тексте prompt-команды должна быть тема лекции")
        require(len(command.buttons) == 1, "В prompt-команде ожидалась одна inline-кнопка")
        require(
            command.buttons[0].action == f"student_start_reflection:{broker_probe_state.lection_id}",
            "Кнопка prompt-команды должна вести на старт workflow рефлексии для нужной лекции",
        )
        broker_seconds = (
            time.perf_counter() - broker_started_at
            if broker_started_at is not None
            else None
        )

        total_seconds = time.perf_counter() - started
        summary = {
            "docs_checked": True,
            "main_course": main_course_name,
            "bulk_course": perf_course_name,
            "created_admin_username": created_admin_username,
            "teacher_username": teacher_username,
            "performance_seconds": {
                "create_course_55_lections": round(perf_excel_seconds, 3),
                "attach_110_students": round(perf_csv_seconds, 3),
                "rabbitmq_prompt_wait": round(broker_seconds, 3) if broker_seconds is not None else None,
                "total_smoke": round(total_seconds, 3),
            },
            "counts": {
                "main": main_counts,
                "bulk": perf_counts,
            },
        }
        log("Smoke-прогон завершён успешно")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        if late_temp_dir is not None:
            late_temp_dir.cleanup()
        if broker_probe is not None:
            await broker_probe.close()
        await cleanup_broker_probe_state(broker_probe_state)


if __name__ == "__main__":
    asyncio.run(main())
