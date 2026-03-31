"""
Парсер Excel файлов для импорта курсов.
"""

from datetime import datetime
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
        'Вопросы': 'questions',
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
        questions_value = row[column_mapping['questions']]
        
        started_at, ended_at = self._parse_datetime_values(date_value, time_value)
        
        return {
            'topic': topic,
            'started_at': started_at,
            'ended_at': ended_at,
            "questions": self._parse_questions(questions_value),
        }

    def _parse_datetime_values(self, date_value, time_value: str) -> tuple[datetime, datetime]:
        """Распарсить дату и время лекции."""
        # Парсим дату
        if isinstance(date_value, datetime):
            date_obj = date_value.date()
        elif isinstance(date_value, str):
            for date_format in ['%m/%d/%Y', '%d.%m.%Y', '%Y-%m-%d']:
                try:
                    date_obj = datetime.strptime(date_value.strip(), date_format).date()
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Не удалось распарсить дату: {date_value}")
        else:
            raise ValueError(f"Неверный формат даты: {date_value}")

        time_parts = time_value.replace('–', '-').split('-')
        if len(time_parts) != 2:
            raise ValueError(f"Неверный формат времени: {time_value}")

        start_time = datetime.strptime(time_parts[0].strip(), '%H:%M').time()
        end_time = datetime.strptime(time_parts[1].strip(), '%H:%M').time()

        return (
            ensure_utc_datetime(datetime.combine(date_obj, start_time)),
            ensure_utc_datetime(datetime.combine(date_obj, end_time)),
        )

    @staticmethod
    def _parse_questions(questions_value) -> list[str]:
        """Распарсить вопросы из ячейки через знак вопроса."""
        if questions_value is None:
            return []

        raw_text = str(questions_value).strip()
        if not raw_text:
            return []

        return [
            f"{question.strip()}?"
            for question in raw_text.split("?")
            if question.strip()
        ]
