"""
Парсер CSV файлов для импорта студентов.
"""

import csv
from typing import BinaryIO
import io

from .base import BaseFileParser
from ..exceptions import (
    CSVParsingError,
    CSVFileMissingColumnError,
    CSVFileEmptyError,
)


class StudentCSVParser(BaseFileParser):
    """Парсер CSV файлов со списком студентов."""
    
    REQUIRED_COLUMNS = ['ФИО', 'username']
    
    def parse(self, file: BinaryIO) -> list[dict]:
        """
        Парсинг CSV файла со студентами.
        
        Args:
            file: Бинарный файл CSV
        
        Returns:
            Список словарей со студентами [{'full_name': str, 'telegram_username': str}, ...]
        
        Raises:
            CSVParsingError: Ошибка чтения или парсинга файла
            CSVFileMissingColumnError: Отсутствует обязательная колонка
            CSVFileEmptyError: Файл пустой
        """
        try:
            # Читаем файл как текст с кодировкой UTF-8
            content = file.read()
            text_content = content.decode('utf-8')
            text_file = io.StringIO(text_content)
        except UnicodeDecodeError as e:
            raise CSVParsingError(f"Ошибка декодирования файла. Убедитесь, что файл в кодировке UTF-8: {str(e)}")
        except Exception as e:
            raise CSVParsingError(f"Не удалось прочитать CSV файл: {str(e)}")
        
        try:
            # Парсим CSV
            csv_reader = csv.DictReader(text_file)
            
            # Проверяем наличие обязательных колонок
            if not csv_reader.fieldnames:
                raise CSVFileEmptyError()
            
            self._validate_columns(csv_reader.fieldnames)
            
            # Читаем строки
            students = []
            for row in csv_reader:
                # Пропускаем пустые строки
                if not row.get('ФИО') or not row.get('username'):
                    continue
                
                student_data = {
                    'full_name': row['ФИО'].strip(),
                    'telegram_username': row['username'].strip(),
                }
                students.append(student_data)
            
            if not students:
                raise CSVFileEmptyError()
            
            return students
            
        except CSVFileMissingColumnError:
            raise
        except CSVFileEmptyError:
            raise
        except Exception as e:
            raise CSVParsingError(f"Ошибка парсинга CSV файла: {str(e)}")
    
    def _validate_columns(self, fieldnames: list[str]) -> None:
        """
        Валидация наличия обязательных колонок.
        
        Args:
            fieldnames: Список названий колонок из CSV
        
        Raises:
            CSVFileMissingColumnError: Если отсутствует обязательная колонка
        """
        for required_col in self.REQUIRED_COLUMNS:
            if required_col not in fieldnames:
                raise CSVFileMissingColumnError(required_col)
