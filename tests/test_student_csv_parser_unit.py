"""
Unit tests for StudentCSVParser.

These tests complement the property-based tests with specific examples
and edge cases.
"""

import io
import csv
import pytest

from reflebot.apps.reflections.parsers.student_csv import StudentCSVParser
from reflebot.apps.reflections.exceptions import (
    CSVParsingError,
    CSVFileMissingColumnError,
    CSVFileEmptyError,
)


def create_csv_file(headers: list[str], rows: list[list[str]]) -> io.BytesIO:
    """Helper to create CSV file in memory."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    csv_content = output.getvalue()
    return io.BytesIO(csv_content.encode('utf-8'))


class TestStudentCSVParserSuccess:
    """Test successful parsing scenarios."""
    
    def test_parse_single_student(self):
        """Test parsing a CSV with a single student."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [['Иванов Иван Иванович', 'ivanov']]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 1
        assert result[0]['full_name'] == 'Иванов Иван Иванович'
        assert result[0]['telegram_username'] == 'ivanov'
    
    def test_parse_multiple_students(self):
        """Test parsing a CSV with multiple students."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [
            ['Иванов Иван Иванович', 'ivanov'],
            ['Петров Пётр Петрович', 'petrov'],
            ['Сидоров Сидор Сидорович', 'sidorov'],
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 3
        assert result[0]['full_name'] == 'Иванов Иван Иванович'
        assert result[1]['full_name'] == 'Петров Пётр Петрович'
        assert result[2]['full_name'] == 'Сидоров Сидор Сидорович'
    
    def test_parse_with_extra_columns(self):
        """Test parsing CSV with extra columns (should be ignored)."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username', 'email', 'phone']
        rows = [
            ['Иванов Иван', 'ivanov', 'ivanov@example.com', '123456'],
            ['Петров Пётр', 'petrov', 'petrov@example.com', '789012'],
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 2
        assert result[0]['full_name'] == 'Иванов Иван'
        assert result[0]['telegram_username'] == 'ivanov'
        # Extra columns should not be in result
        assert 'email' not in result[0]
        assert 'phone' not in result[0]
    
    def test_parse_with_whitespace(self):
        """Test that parser strips whitespace from values."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [
            ['  Иванов Иван  ', '  ivanov  '],
            ['Петров Пётр\t', '\tpetrov'],
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 2
        assert result[0]['full_name'] == 'Иванов Иван'
        assert result[0]['telegram_username'] == 'ivanov'
        assert result[1]['full_name'] == 'Петров Пётр'
        assert result[1]['telegram_username'] == 'petrov'


class TestStudentCSVParserEmptyLines:
    """Test handling of empty lines."""
    
    def test_skip_empty_lines_at_start(self):
        """Test skipping empty lines at the start."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [
            ['', ''],
            ['', ''],
            ['Иванов Иван', 'ivanov'],
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 1
        assert result[0]['full_name'] == 'Иванов Иван'
    
    def test_skip_empty_lines_in_middle(self):
        """Test skipping empty lines in the middle."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [
            ['Иванов Иван', 'ivanov'],
            ['', ''],
            ['Петров Пётр', 'petrov'],
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 2
        assert result[0]['full_name'] == 'Иванов Иван'
        assert result[1]['full_name'] == 'Петров Пётр'
    
    def test_skip_partially_empty_lines(self):
        """Test skipping lines with only one field filled."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [
            ['Иванов Иван', ''],  # Missing username
            ['', 'petrov'],  # Missing full name
            ['Сидоров Сидор', 'sidorov'],  # Valid
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 1
        assert result[0]['full_name'] == 'Сидоров Сидор'


class TestStudentCSVParserErrors:
    """Test error handling."""
    
    def test_missing_fio_column(self):
        """Test error when ФИО column is missing."""
        parser = StudentCSVParser()
        headers = ['username', 'email']
        rows = [['ivanov', 'ivanov@example.com']]
        
        csv_file = create_csv_file(headers, rows)
        
        with pytest.raises(CSVFileMissingColumnError) as exc_info:
            parser.parse(csv_file)
        
        assert 'ФИО' in str(exc_info.value.detail)
    
    def test_missing_username_column(self):
        """Test error when username column is missing."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'email']
        rows = [['Иванов Иван', 'ivanov@example.com']]
        
        csv_file = create_csv_file(headers, rows)
        
        with pytest.raises(CSVFileMissingColumnError) as exc_info:
            parser.parse(csv_file)
        
        assert 'username' in str(exc_info.value.detail)
    
    def test_empty_file_no_headers(self):
        """Test error when file has no headers."""
        parser = StudentCSVParser()
        csv_file = io.BytesIO(b'')
        
        with pytest.raises(CSVFileEmptyError):
            parser.parse(csv_file)
    
    def test_empty_file_only_headers(self):
        """Test error when file has only headers, no data."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = []
        
        csv_file = create_csv_file(headers, rows)
        
        with pytest.raises(CSVFileEmptyError):
            parser.parse(csv_file)
    
    def test_empty_file_only_empty_rows(self):
        """Test error when file has only empty rows."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [['', ''], ['', ''], ['', '']]
        
        csv_file = create_csv_file(headers, rows)
        
        with pytest.raises(CSVFileEmptyError):
            parser.parse(csv_file)
    
    def test_invalid_utf8_encoding(self):
        """Test error when file is not UTF-8 encoded."""
        parser = StudentCSVParser()
        # Create invalid UTF-8 bytes
        invalid_bytes = b'\xff\xfe\x00\x00'
        csv_file = io.BytesIO(invalid_bytes)
        
        with pytest.raises(CSVParsingError) as exc_info:
            parser.parse(csv_file)
        
        assert 'UTF-8' in str(exc_info.value.detail)


class TestStudentCSVParserEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_very_long_name(self):
        """Test parsing with very long student name."""
        parser = StudentCSVParser()
        long_name = 'А' * 200
        headers = ['ФИО', 'username']
        rows = [[long_name, 'user1']]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 1
        assert result[0]['full_name'] == long_name
    
    def test_special_characters_in_name(self):
        """Test parsing names with special characters."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [
            ['О\'Коннор Шон', 'oconnor'],
            ['Мюллер-Шмидт Ханс', 'muller'],
            ['Д\'Артаньян', 'dartagnan'],
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 3
        assert result[0]['full_name'] == 'О\'Коннор Шон'
        assert result[1]['full_name'] == 'Мюллер-Шмидт Ханс'
    
    def test_numbers_in_username(self):
        """Test usernames with numbers."""
        parser = StudentCSVParser()
        headers = ['ФИО', 'username']
        rows = [
            ['Иванов Иван', 'ivanov123'],
            ['Петров Пётр', 'user_2024'],
        ]
        
        csv_file = create_csv_file(headers, rows)
        result = parser.parse(csv_file)
        
        assert len(result) == 2
        assert result[0]['telegram_username'] == 'ivanov123'
        assert result[1]['telegram_username'] == 'user_2024'
    
    def test_mixed_case_column_names(self):
        """Test that column names are case-sensitive."""
        parser = StudentCSVParser()
        # Wrong case for column names
        headers = ['фио', 'Username']  # lowercase 'фио', capitalized 'Username'
        rows = [['Иванов Иван', 'ivanov']]
        
        csv_file = create_csv_file(headers, rows)
        
        # Should fail because column names don't match exactly
        with pytest.raises(CSVFileMissingColumnError):
            parser.parse(csv_file)
