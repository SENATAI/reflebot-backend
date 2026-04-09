"""
Парсер Excel файлов для импорта курсов.
"""

import re
from datetime import datetime, time
from typing import BinaryIO
import openpyxl

from ..datetime_utils import ensure_utc_datetime
from .base import BaseFileParser
from ..exceptions import (
    ExcelFileError,
    ExcelFileFormatError,
    ExcelFileMissingColumnError,
    ExcelFileEmptyError,
    ExcelFileDateParseError,
)


class CourseExcelParser(BaseFileParser):
    """Парсер Excel файлов с данными курсов."""

    REQUIRED_COLUMNS = {
        'Тема лекции': 'topic',
        'Дата': 'date',
        'Время': 'time',
        'Дата дедлайна': 'deadline_date',
        'Время дедлайна': 'deadline_time',
        'Количество задаваемых вопросов': 'questions_to_ask_count',
        'Вопросы': 'questions',
    }
    OPTIONAL_COLUMNS = {
        'Код курса': 'join_code',
    }
    
    def parse(self, file: BinaryIO) -> list[dict]:
        """
        Парсинг Excel файла.
        
        Args:
            file: Бинарный файл Excel
        
        Returns:
            Список данных лекций
        
        Raises:
            ExcelFileError: Ошибка чтения файла
            ExcelFileFormatError: Неверный формат файла
            ExcelFileMissingColumnError: Отсутствует обязательная колонка
            ExcelFileEmptyError: Файл пустой
            ExcelFileDateParseError: Ошибка парсинга даты
        """
        try:
            workbook = openpyxl.load_workbook(file, data_only=True)
        except Exception as e:
            raise ExcelFileError(f"Не удалось прочитать Excel файл: {str(e)}")
        
        if not workbook.worksheets:
            raise ExcelFileEmptyError()
        
        worksheet = workbook.active
        
        column_mapping = self._parse_headers(worksheet)
        lections_data = self._parse_rows(worksheet, column_mapping)
        
        if not lections_data:
            raise ExcelFileEmptyError()

        return lections_data
    
    def _parse_headers(self, worksheet) -> dict:
        """Парсинг заголовков таблицы."""
        if not worksheet:
            raise ExcelFileError("Worksheet не инициализирован")
        
        headers = []
        for cell in worksheet[1]:
            if cell.value:
                headers.append(str(cell.value).strip())
        
        if not headers:
            raise ExcelFileFormatError("Не найдены заголовки в первой строке")
        
        # Проверяем наличие обязательных колонок
        column_mapping = {}
        for required_col in self.REQUIRED_COLUMNS.keys():
            if required_col not in headers:
                raise ExcelFileMissingColumnError(required_col)
            
            # Сохраняем индекс колонки
            column_mapping[self.REQUIRED_COLUMNS[required_col]] = headers.index(required_col)

        for optional_col, alias in self.OPTIONAL_COLUMNS.items():
            if optional_col in headers:
                column_mapping[alias] = headers.index(optional_col)

        return column_mapping
    
    def _parse_rows(self, worksheet, column_mapping: dict) -> list[dict]:
        """Парсинг строк нового Excel-формата."""
        if not worksheet:
            raise ExcelFileError("Worksheet не инициализирован")
        
        lections = []
        
        # Начинаем со второй строки (первая - заголовки)
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            # Пропускаем пустые строки
            if not any(row):
                continue
            
            try:
                lection_data = self._parse_row(row, column_mapping, row_idx)
                lections.append(lection_data)
            except Exception as e:
                raise ExcelFileDateParseError(row_idx, str(e))
        
        return lections

    def _parse_row(self, row: tuple, column_mapping: dict, row_idx: int) -> dict:
        """
        Парсинг одной строки нового формата.
        
        Args:
            row: Кортеж значений строки
            column_mapping: Маппинг колонок
            row_idx: Номер строки (для ошибок)
        
        Returns:
            Словарь с данными лекции
        """
        topic = str(row[column_mapping['topic']]).strip()
        date_value = row[column_mapping['date']]
        time_value = str(row[column_mapping['time']]).strip()
        deadline_date_value = row[column_mapping['deadline_date']]
        deadline_time_value = row[column_mapping['deadline_time']]
        join_code = self._extract_join_code(row, column_mapping)
        questions_value = row[column_mapping['questions']]

        if not topic:
            raise ValueError("Тема лекции не может быть пустой")
        if join_code is not None:
            self._validate_join_code(join_code)

        started_at, ended_at = self._parse_datetime_values(date_value, time_value)
        deadline = self._parse_deadline_values(deadline_date_value, deadline_time_value)

        questions = self._parse_questions(questions_value)
        questions_to_ask_count = self._parse_questions_to_ask_count(
            row[column_mapping['questions_to_ask_count']],
            questions,
        )

        return {
            'topic': topic,
            'started_at': started_at,
            'ended_at': ended_at,
            'deadline': deadline,
            'join_code': join_code,
            "questions": questions,
            "questions_to_ask_count": questions_to_ask_count,
        }

    def _parse_datetime_values(self, date_value, time_value: str) -> tuple[datetime, datetime]:
        """Распарсить дату и время лекции."""
        date_obj = self._parse_date_value(date_value)

        time_parts = time_value.replace('–', '-').split('-')
        if len(time_parts) != 2:
            raise ValueError(f"Неверный формат времени: {time_value}")

        start_time = self._parse_single_time_value(time_parts[0].strip())
        end_time = self._parse_single_time_value(time_parts[1].strip())

        return (
            ensure_utc_datetime(datetime.combine(date_obj, start_time)),
            ensure_utc_datetime(datetime.combine(date_obj, end_time)),
        )

    def _parse_deadline_values(self, date_value, time_value) -> datetime:
        """Распарсить отдельные дату и время дедлайна."""
        date_obj = self._parse_date_value(date_value)
        time_obj = self._parse_single_time_value(time_value)
        return ensure_utc_datetime(datetime.combine(date_obj, time_obj))

    @staticmethod
    def _parse_single_time_value(time_value) -> time:
        """Распарсить одно время в формате HH:MM или HH:MM:SS."""
        if isinstance(time_value, datetime):
            return time_value.time().replace(second=0, microsecond=0)
        if isinstance(time_value, time):
            return time_value.replace(second=0, microsecond=0)

        raw_time = str(time_value).strip()
        if not raw_time:
            raise ValueError("Пустое значение времени")
        for time_format in ('%H:%M', '%H:%M:%S'):
            try:
                return datetime.strptime(raw_time, time_format).time()
            except ValueError:
                continue
        raise ValueError(f"Не удалось распарсить время: {time_value}")

    @staticmethod
    def _parse_date_value(date_value):
        """Распарсить дату из поддерживаемых Excel-форматов."""
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            for date_format in ['%m/%d/%Y', '%d.%m.%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_value.strip(), date_format).date()
                except ValueError:
                    continue
            raise ValueError(f"Не удалось распарсить дату: {date_value}")
        raise ValueError(f"Неверный формат даты: {date_value}")

    @classmethod
    def _validate_join_code(cls, join_code: str) -> None:
        """Провалидировать код курса из Excel."""
        if not join_code:
            raise ValueError("Код курса не может быть пустым")
        if len(join_code) < 4:
            raise ValueError("Код курса должен состоять минимум из 4 символов.")
        if re.fullmatch(r"[A-Za-z0-9]+", join_code) is None:
            raise ValueError(
                "Код курса содержит недопустимые символы. "
                "Используйте только латинские буквы и цифры."
            )

    @staticmethod
    def _extract_join_code(row: tuple, column_mapping: dict) -> str | None:
        """Достать код курса из строки, если он присутствует в файле."""
        join_code_index = column_mapping.get("join_code")
        if join_code_index is None:
            return None
        raw_value = row[join_code_index]
        if raw_value is None:
            return None
        normalized = str(raw_value).strip()
        return normalized or None

    @staticmethod
    def _parse_questions(questions_value) -> list[str]:
        """Распарсить вопросы из ячейки по маркеру новой строки '- '."""
        if questions_value is None:
            return []

        raw_text = str(questions_value).strip()
        if not raw_text:
            return []

        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        if re.search(r"(?:^|\n)-\s+", normalized):
            questions = re.split(r"(?:^|\n)-\s+", normalized)
            return [question.strip() for question in questions if question.strip()]
        return [normalized]

    @staticmethod
    def _parse_questions_to_ask_count(
        raw_value,
        questions: list[str],
    ) -> int | None:
        """Распарсить количество вопросов, которое нужно задать студенту."""
        total_questions = len(questions)
        normalized = "" if raw_value is None else str(raw_value).strip()

        if not normalized:
            if total_questions == 0:
                return None
            if total_questions == 1:
                return 1
            raise ValueError(
                "Для нескольких вопросов нужно заполнить поле 'Количество задаваемых вопросов'."
            )

        try:
            parsed_value = int(float(normalized))
        except ValueError as exc:
            raise ValueError(
                "Поле 'Количество задаваемых вопросов' должно содержать целое число."
            ) from exc

        if parsed_value < 1:
            raise ValueError(
                "Поле 'Количество задаваемых вопросов' должно быть больше нуля."
            )
        if parsed_value > total_questions:
            raise ValueError(
                "Количество задаваемых вопросов больше, чем число вопросов в лекции."
            )
        return parsed_value
