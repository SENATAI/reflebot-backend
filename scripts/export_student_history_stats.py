"""
Экспорт логов StudentHistoryLog в CSV, Markdown и DOCX-статистику.

Скрипт:
1. Читает конфиг из scripts/.env
2. При необходимости поднимает SSH-туннель по alias из SSH config
3. Загружает все логи StudentHistoryLog вместе со студентом и user_context
4. Сохраняет сырые данные в scripts/data/*.csv
5. Строит человекочитаемую статистику в scripts/stats/stat_<date>.md и .docx
"""

from __future__ import annotations

import csv
import json
import os
import socket
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from dotenv import load_dotenv
import psycopg
from psycopg import OperationalError
from psycopg.rows import dict_row


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
DATA_DIR = SCRIPTS_DIR / "data"
STATS_DIR = SCRIPTS_DIR / "stats"
ENV_PATH = SCRIPTS_DIR / ".env"


@dataclass(slots=True)
class ScriptConfig:
    """Конфигурация подключения и выгрузки."""

    ssh_host_alias: str
    use_ssh_tunnel: bool
    ssh_remote_host: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_sslmode: str
    local_tunnel_port: int
    query_timeout_seconds: int


@dataclass(slots=True)
class StudentLogRow:
    """Строка выгрузки StudentHistoryLog."""

    log_id: str
    log_created_at: str
    log_updated_at: str
    log_action: str
    student_id: str
    student_full_name: str
    telegram_username: str | None
    telegram_id: int | None
    student_is_active: bool
    user_context: dict[str, Any] | None


@dataclass(slots=True)
class StudentCurrentState:
    """Текущее состояние студента для отчёта."""

    student_id: str
    student_full_name: str
    telegram_username: str | None
    telegram_id: int | None
    log_action: str
    log_created_at: str
    context_action: str | None
    context_step: str | None
    stage_name: str
    window_name: str
    message_text: str


@dataclass(slots=True)
class ReportData:
    """Подготовленные данные для генерации отчётов."""

    screen_summary: list[tuple[str, str, int]]
    action_summary: list[tuple[str, int, int]]
    states: list[StudentCurrentState]


def load_config() -> ScriptConfig:
    """Загрузить конфигурацию из scripts/.env."""
    load_dotenv(ENV_PATH)
    return ScriptConfig(
        ssh_host_alias=_get_env("STATS_SSH_HOST_ALIAS"),
        use_ssh_tunnel=_get_env("STATS_USE_SSH_TUNNEL", "false").lower() == "true",
        ssh_remote_host=_get_env("STATS_SSH_REMOTE_HOST", "127.0.0.1"),
        db_host=_get_env("STATS_DB_HOST", "127.0.0.1"),
        db_port=int(_get_env("STATS_DB_PORT", "5434")),
        db_name=_get_env("STATS_DB_NAME"),
        db_user=_get_env("STATS_DB_USER"),
        db_password=_get_env("STATS_DB_PASSWORD"),
        db_sslmode=_get_env("STATS_DB_SSLMODE", "disable"),
        local_tunnel_port=int(_get_env("STATS_LOCAL_TUNNEL_PORT", "6544")),
        query_timeout_seconds=int(_get_env("STATS_QUERY_TIMEOUT_SECONDS", "30")),
    )


def _get_env(name: str, default: str | None = None) -> str:
    """Получить обязательную переменную окружения."""
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Не найдена переменная {name} в {ENV_PATH}")
    return value


class SshTunnel:
    """Простой SSH-туннель через alias из SSH config."""

    def __init__(self, config: ScriptConfig):
        self.config = config
        self.process: subprocess.Popen[str] | None = None

    def __enter__(self) -> "SshTunnel":
        if not self.config.use_ssh_tunnel:
            return self
        command = [
            "ssh",
            "-o",
            "ExitOnForwardFailure=yes",
            "-L",
            f"{self.config.local_tunnel_port}:{self.config.ssh_remote_host}:{self.config.db_port}",
            self.config.ssh_host_alias,
            "-N",
        ]
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=ROOT_DIR,
        )
        self._wait_until_port_ready(self.config.local_tunnel_port, timeout_seconds=10)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    @staticmethod
    def _wait_until_port_ready(port: int, timeout_seconds: int) -> None:
        """Подождать, пока локальный порт начнёт принимать соединения."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError(f"SSH-туннель не поднялся на порту {port}")


def fetch_student_history_rows(config: ScriptConfig) -> list[StudentLogRow]:
    """Загрузить все логи StudentHistoryLog из БД."""
    host = "127.0.0.1" if config.use_ssh_tunnel else config.db_host
    port = config.local_tunnel_port if config.use_ssh_tunnel else config.db_port
    query = """
        SELECT
            shl.id::text AS log_id,
            shl.created_at AS log_created_at,
            shl.updated_at AS log_updated_at,
            shl.action AS log_action,
            s.id::text AS student_id,
            s.full_name AS student_full_name,
            s.telegram_username AS telegram_username,
            s.telegram_id AS telegram_id,
            s.is_active AS student_is_active,
            u.user_context AS user_context
        FROM student_history_logs shl
        JOIN students s ON s.id = shl.student_id
        LEFT JOIN users u ON u.telegram_id = s.telegram_id
        ORDER BY shl.created_at DESC, shl.id DESC
    """
    with psycopg.connect(
        host=host,
        port=port,
        dbname=config.db_name,
        user=config.db_user,
        password=config.db_password,
        sslmode=config.db_sslmode,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = '{config.query_timeout_seconds}s'")
            cursor.execute(query)
            rows = cursor.fetchall()
    return [
        StudentLogRow(
            log_id=str(row["log_id"]),
            log_created_at=_serialize_datetime(row["log_created_at"]),
            log_updated_at=_serialize_datetime(row["log_updated_at"]),
            log_action=str(row["log_action"]),
            student_id=str(row["student_id"]),
            student_full_name=str(row["student_full_name"]),
            telegram_username=row["telegram_username"],
            telegram_id=row["telegram_id"],
            student_is_active=bool(row["student_is_active"]),
            user_context=row["user_context"],
        )
        for row in rows
    ]


def _serialize_datetime(value: Any) -> str:
    """Нормализовать datetime для CSV/Markdown."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def write_csv(rows: list[StudentLogRow], timestamp: str) -> Path:
    """Сохранить полную выгрузку логов в CSV."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"student_history_logs_{timestamp}.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "log_id",
                "log_created_at",
                "log_updated_at",
                "log_action",
                "student_id",
                "student_full_name",
                "telegram_username",
                "telegram_id",
                "student_is_active",
                "user_context",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "log_id": row.log_id,
                    "log_created_at": row.log_created_at,
                    "log_updated_at": row.log_updated_at,
                    "log_action": row.log_action,
                    "student_id": row.student_id,
                    "student_full_name": row.student_full_name,
                    "telegram_username": row.telegram_username or "",
                    "telegram_id": row.telegram_id or "",
                    "student_is_active": row.student_is_active,
                    "user_context": json.dumps(row.user_context, ensure_ascii=False),
                }
            )
    return path


def build_current_states(rows: list[StudentLogRow]) -> list[StudentCurrentState]:
    """Собрать текущее состояние по последнему логу каждого студента."""
    latest_by_student: dict[str, StudentLogRow] = {}
    for row in rows:
        latest_by_student.setdefault(row.student_id, row)

    states: list[StudentCurrentState] = []
    for row in latest_by_student.values():
        context_action, context_step, stage_name, window_name, message_text = describe_context(
            row.user_context,
            row.log_action,
        )
        states.append(
            StudentCurrentState(
                student_id=row.student_id,
                student_full_name=row.student_full_name,
                telegram_username=row.telegram_username,
                telegram_id=row.telegram_id,
                log_action=row.log_action,
                log_created_at=row.log_created_at,
                context_action=context_action,
                context_step=context_step,
                stage_name=stage_name,
                window_name=window_name,
                message_text=message_text,
            )
        )
    return sorted(
        states,
        key=lambda item: ((item.telegram_username or "").lower(), item.student_full_name.lower()),
    )


def describe_context(
    user_context: dict[str, Any] | None,
    last_action: str,
) -> tuple[str | None, str | None, str, str, str]:
    """Преобразовать user_context в человекочитаемое описание экрана."""
    if not user_context:
        return (
            None,
            None,
            "Без активного сценария",
            "Главное меню / завершённый сценарий",
            "Активный контекст не найден. Скорее всего студент видит главное меню или уже завершил сценарий.",
        )

    action = user_context.get("action")
    step = user_context.get("step")
    mapping = {
        ("register_course_by_code", "awaiting_course_code"): (
            "Регистрация на курс",
            "Ввод кода курса",
            "Привет студент, введи код курса.",
        ),
        ("register_course_by_code", "awaiting_fullname"): (
            "Регистрация на курс",
            "Ввод ФИО",
            "Введите своё ФИО.",
        ),
        ("join_course", "awaiting_course_code"): (
            "Запись на дополнительный курс",
            "Ввод кода курса",
            "Введите код курса.",
        ),
        ("student_reflection_workflow", "awaiting_reflection_video"): (
            "Рефлексия по лекции",
            "Ожидание основного кружка/видео",
            "Загрузите кружок/видео, я вас слушаю.",
        ),
        ("student_reflection_workflow", "review_reflection_videos"): (
            "Рефлексия по лекции",
            "Проверка записанных файлов",
            "Студент уже загрузил основной кружок/видео и видит кнопки удаления или отправки.",
        ),
        ("student_reflection_workflow", "question_prompt"): (
            "Ответ на вопрос",
            "Показ текущего вопроса",
            "Показан текущий вопрос и ожидается запись кружка/видео.",
        ),
        ("student_reflection_workflow", "awaiting_question_video"): (
            "Ответ на вопрос",
            "Ожидание кружка/видео",
            "Загрузите кружок/видео с ответом на текущий вопрос.",
        ),
        ("student_reflection_workflow", "review_question_videos"): (
            "Ответ на вопрос",
            "Проверка записанных файлов",
            "Студент уже записал ответ и видит кнопки удаления или отправки.",
        ),
        ("student_reflection_workflow", "question_select"): (
            "Legacy workflow",
            "Выбор вопроса",
            "Старый сценарий выбора одного вопроса из списка.",
        ),
    }
    if (action, step) in mapping:
        stage_name, window_name, message_text = mapping[(action, step)]
        return action, step, stage_name, window_name, message_text

    return (
        str(action) if action is not None else None,
        str(step) if step is not None else None,
        "Неизвестный сценарий",
        f"{action or 'unknown'} / {step or 'unknown'}",
        (
            "Контекст не описан в маппинге. "
            f"Последнее действие студента: {last_action}."
        ),
    )


def build_report_data(
    rows: list[StudentLogRow],
    states: list[StudentCurrentState],
) -> ReportData:
    """Подготовить агрегированные данные для отчётов."""
    screen_summary_map: dict[tuple[str, str], list[StudentCurrentState]] = defaultdict(list)
    for state in states:
        screen_summary_map[(state.window_name, state.message_text)].append(state)

    action_summary_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"students": set(), "total": 0}
    )
    for row in rows:
        action_summary_map[row.log_action]["students"].add(row.student_id)
        action_summary_map[row.log_action]["total"] += 1

    screen_summary = [
        (window_name, message_text, len(group))
        for (window_name, message_text), group in sorted(
            screen_summary_map.items(),
            key=lambda item: (-len(item[1]), item[0][0]),
        )
    ]
    action_summary = [
        (action, len(stats["students"]), stats["total"])
        for action, stats in sorted(
            action_summary_map.items(),
            key=lambda item: (-item[1]["total"], item[0]),
        )
    ]
    return ReportData(
        screen_summary=screen_summary,
        action_summary=action_summary,
        states=states,
    )


def render_markdown(
    rows: list[StudentLogRow],
    states: list[StudentCurrentState],
    csv_path: Path,
    generated_at: datetime,
) -> str:
    """Собрать Markdown-отчёт."""
    report = build_report_data(rows, states)

    lines = [
        f"# Student History Stats {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- CSV выгрузка: `{csv_path}`",
        f"- Всего логов: **{len(rows)}**",
        f"- Студентов с логами: **{len(states)}**",
        "",
        "## Сводка по текущим экранам",
        "",
        "| Окно | Что сейчас выводится | Студентов |",
        "| --- | --- | ---: |",
    ]

    for window_name, message_text, students_count in report.screen_summary:
        lines.append(
            f"| {escape_md(window_name)} | {escape_md(message_text)} | {students_count} |"
        )

    lines.extend(
        [
            "",
            "## Сводка по действиям из StudentHistoryLog",
            "",
            "| Action | Уникальных студентов | Всего событий |",
            "| --- | ---: | ---: |",
        ]
    )

    for action, unique_students, total_events in report.action_summary:
        lines.append(
            f"| {escape_md(action)} | {unique_students} | {total_events} |"
        )

    lines.extend(
        [
            "",
            "## Текущее состояние студентов",
            "",
            "| Ник | ФИО | Последнее действие | Стадия | Окно | Сообщение | Последний лог |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for state in report.states:
        lines.append(
            "| "
            f"{escape_md('@' + state.telegram_username if state.telegram_username else '(без ника)')} | "
            f"{escape_md(state.student_full_name)} | "
            f"{escape_md(state.log_action)} | "
            f"{escape_md(state.stage_name)} | "
            f"{escape_md(state.window_name)} | "
            f"{escape_md(state.message_text)} | "
            f"{escape_md(state.log_created_at)} |"
        )

    return "\n".join(lines) + "\n"


def escape_md(value: str) -> str:
    """Экранировать текст для markdown-таблицы."""
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(content: str, generated_at: datetime) -> Path:
    """Сохранить markdown-статистику."""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    path = STATS_DIR / f"stat_{generated_at.strftime('%Y_%m_%d_%H_%M_%S')}.md"
    path.write_text(content, encoding="utf-8")
    return path


def write_docx(
    rows: list[StudentLogRow],
    states: list[StudentCurrentState],
    csv_path: Path,
    generated_at: datetime,
) -> Path:
    """Сохранить DOCX-статистику."""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    path = STATS_DIR / f"stat_{generated_at.strftime('%Y_%m_%d_%H_%M_%S')}.docx"
    report = build_report_data(rows, states)

    body_parts = [
        _docx_paragraph(
            f"Student History Stats {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            bold=True,
            size=32,
        ),
        _docx_paragraph(f"CSV выгрузка: {csv_path}"),
        _docx_paragraph(f"Всего логов: {len(rows)}"),
        _docx_paragraph(f"Студентов с логами: {len(states)}"),
        _docx_paragraph("Сводка по текущим экранам", bold=True, size=28),
        _docx_table(
            headers=["Окно", "Что сейчас выводится", "Студентов"],
            rows_data=[
                [window_name, message_text, str(students_count)]
                for window_name, message_text, students_count in report.screen_summary
            ],
        ),
        _docx_paragraph("Сводка по действиям из StudentHistoryLog", bold=True, size=28),
        _docx_table(
            headers=["Action", "Уникальных студентов", "Всего событий"],
            rows_data=[
                [action, str(unique_students), str(total_events)]
                for action, unique_students, total_events in report.action_summary
            ],
        ),
        _docx_paragraph("Текущее состояние студентов", bold=True, size=28),
        _docx_table(
            headers=[
                "Ник",
                "ФИО",
                "Последнее действие",
                "Стадия",
                "Окно",
                "Сообщение",
                "Последний лог",
            ],
            rows_data=[
                [
                    f"@{state.telegram_username}" if state.telegram_username else "(без ника)",
                    state.student_full_name,
                    state.log_action,
                    state.stage_name,
                    state.window_name,
                    state.message_text,
                    state.log_created_at,
                ]
                for state in report.states
            ],
        ),
        "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/><w:pgMar w:top=\"1134\" "
        "w:right=\"850\" w:bottom=\"1134\" w:left=\"850\" w:header=\"708\" "
        "w:footer=\"708\" w:gutter=\"0\"/></w:sectPr>",
    ]

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" "
        "xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" "
        "xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" "
        "xmlns:v=\"urn:schemas-microsoft-com:vml\" "
        "xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" "
        "xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" "
        "xmlns:w10=\"urn:schemas-microsoft-com:office:word\" "
        "xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" "
        "xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" "
        "xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" "
        "xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" "
        "xmlns:wne=\"http://schemas.microsoft.com/office/word/2006/wordml\" "
        "xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" "
        "mc:Ignorable=\"w14 wp14\">"
        f"<w:body>{''.join(body_parts)}</w:body>"
        "</w:document>"
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        archive.writestr("word/document.xml", document_xml)
    return path


def _docx_paragraph(text: str, *, bold: bool = False, size: int = 22) -> str:
    """Построить XML абзаца для DOCX."""
    escaped = xml_escape(text)
    run_props = f"<w:rPr><w:sz w:val=\"{size}\"/><w:szCs w:val=\"{size}\"/>"
    if bold:
        run_props += "<w:b/>"
    run_props += "</w:rPr>"
    return (
        "<w:p><w:r>"
        f"{run_props}"
        f"<w:t xml:space=\"preserve\">{escaped}</w:t>"
        "</w:r></w:p>"
    )


def _docx_table(headers: list[str], rows_data: list[list[str]]) -> str:
    """Построить XML таблицы для DOCX."""
    rows_xml = [_docx_table_row(headers, is_header=True)]
    rows_xml.extend(_docx_table_row(row) for row in rows_data)
    return (
        "<w:tbl>"
        "<w:tblPr>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
        "</w:tblBorders>"
        "</w:tblPr>"
        f"{''.join(rows_xml)}"
        "</w:tbl>"
    )


def _docx_table_row(cells: list[str], *, is_header: bool = False) -> str:
    """Построить XML строки таблицы."""
    cell_xml = "".join(_docx_table_cell(cell, is_header=is_header) for cell in cells)
    return f"<w:tr>{cell_xml}</w:tr>"


def _docx_table_cell(text: str, *, is_header: bool = False) -> str:
    """Построить XML ячейки таблицы."""
    paragraph = _docx_paragraph(text, bold=is_header, size=22)
    return f"<w:tc><w:tcPr/><w:p>{paragraph.removeprefix('<w:p>').removesuffix('</w:p>')}</w:p></w:tc>"


def main() -> int:
    """Точка входа."""
    config = load_config()
    generated_at = datetime.now()
    timestamp = generated_at.strftime("%Y_%m_%d_%H_%M_%S")

    try:
        with SshTunnel(config):
            rows = fetch_student_history_rows(config)
    except OperationalError as exc:
        print(
            "Не удалось подключиться к PostgreSQL. "
            "Проверьте scripts/.env, доступность localhost/SSH-туннеля и креды.",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 1

    csv_path = write_csv(rows, timestamp)
    states = build_current_states(rows)
    markdown = render_markdown(rows, states, csv_path, generated_at)
    markdown_path = write_markdown(markdown, generated_at)
    docx_path = write_docx(rows, states, csv_path, generated_at)

    print(f"CSV сохранён: {csv_path}")
    print(f"Markdown сохранён: {markdown_path}")
    print(f"DOCX сохранён: {docx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
