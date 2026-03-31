"""
Базовый абстрактный парсер файлов.
"""

from abc import ABC, abstractmethod
from typing import BinaryIO, Any, Protocol


class FileParserProtocol(Protocol):
    """Протокол парсера файлов."""
    
    def parse(self, file: BinaryIO) -> Any:
        """
        Парсинг файла.
        
        Args:
            file: Бинарный файл для парсинга
        
        Returns:
            Результат парсинга (зависит от конкретного парсера)
        """
        ...


class BaseFileParser(ABC):
    """
    Базовый абстрактный класс для парсеров файлов.
    
    Все парсеры должны наследоваться от этого класса и реализовывать метод parse.
    """
    
    @abstractmethod
    def parse(self, file: BinaryIO) -> Any:
        """
        Парсинг файла.
        
        Args:
            file: Бинарный файл для парсинга
        
        Returns:
            Результат парсинга (зависит от конкретного парсера)
        
        Raises:
            CoreException: Различные ошибки парсинга
        """
        pass
