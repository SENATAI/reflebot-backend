"""
Парсеры файлов для модуля рефлексий.
"""

from .base import BaseFileParser, FileParserProtocol
from .course_excel import CourseExcelParser
from .student_csv import StudentCSVParser

__all__ = [
    'BaseFileParser',
    'FileParserProtocol',
    'CourseExcelParser',
    'StudentCSVParser',
]
