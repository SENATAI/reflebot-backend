"""
Доменные исключения для модуля рефлексий.
"""

from reflebot.core.utils.exceptions import CoreException
from fastapi import status


class ExcelParsingError(CoreException):
    """
    Ошибка парсинга Excel файла.
    """
    error_code = "EXCEL_PARSING_ERROR"

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=self.error_code,
        )


class ExcelFileError(ExcelParsingError):
    """
    Ошибка при обработке Excel файла.
    """
    error_code = "EXCEL_FILE_ERROR"


class ExcelFileFormatError(ExcelParsingError):
    """
    Ошибка формата Excel файла.
    """
    error_code = "EXCEL_FILE_FORMAT_ERROR"
    
    def __init__(self, detail: str):
        super().__init__(detail)


class ExcelFileMissingColumnError(ExcelParsingError):
    """
    Отсутствует обязательная колонка в Excel файле.
    """
    error_code = "EXCEL_FILE_MISSING_COLUMN"
    
    def __init__(self, column_name: str):
        super().__init__(f"Отсутствует обязательная колонка: {column_name}")


class ExcelFileEmptyError(ExcelParsingError):
    """
    Excel файл пустой или не содержит данных.
    """
    error_code = "EXCEL_FILE_EMPTY"
    
    def __init__(self):
        super().__init__("Excel файл пустой или не содержит данных")


class ExcelFileDateParseError(ExcelParsingError):
    """
    Ошибка парсинга даты в Excel файле.
    """
    error_code = "EXCEL_FILE_DATE_PARSE_ERROR"
    
    def __init__(self, row: int, detail: str):
        super().__init__(f"Ошибка парсинга даты в строке {row}: {detail}")


class CSVParsingError(CoreException):
    """
    Ошибка при парсинге CSV файла.
    """
    error_code = "CSV_PARSING_ERROR"
    
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=self.error_code,
        )


class CSVFileMissingColumnError(CSVParsingError):
    """
    Отсутствует обязательная колонка в CSV файле.
    """
    error_code = "CSV_FILE_MISSING_COLUMN"
    
    def __init__(self, column_name: str):
        super().__init__(f"Отсутствует обязательная колонка: {column_name}")


class CSVFileEmptyError(CSVParsingError):
    """
    CSV файл пустой или не содержит данных.
    """
    error_code = "CSV_FILE_EMPTY"
    
    def __init__(self):
        super().__init__("CSV файл пустой или не содержит данных")
