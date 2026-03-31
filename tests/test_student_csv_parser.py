"""
Property-based tests for StudentCSVParser.

Feature: telegram-bot-full-workflow
"""

import io
import csv
import pytest
from hypothesis import given, strategies as st, settings, assume

from reflebot.apps.reflections.parsers.student_csv import StudentCSVParser
from reflebot.apps.reflections.exceptions import (
    CSVParsingError,
    CSVFileMissingColumnError,
    CSVFileEmptyError,
)


# Helper function to create CSV file from data
def create_csv_file(headers: list[str], rows: list[list[str]]) -> io.BytesIO:
    """Create a CSV file in memory."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    
    # Convert to bytes
    csv_content = output.getvalue()
    return io.BytesIO(csv_content.encode('utf-8'))


# Property 21: CSV Parser Validation
# **Validates: Requirements 17.2, 17.4**
@given(
    missing_column=st.sampled_from(['ФИО', 'username']),
    extra_columns=st.lists(
        st.text(min_size=1, max_size=20).filter(
            lambda value: value not in {'ФИО', 'username'}
        ),
        max_size=3,
    ),
    row_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_csv_parser_missing_column_validation(missing_column, extra_columns, row_count):
    """
    Property 21: CSV Parser Validation
    
    For any CSV файла без обязательных колонок (ФИО, username), 
    парсер должен выбрасывать исключение с описанием ошибки.
    
    **Validates: Requirements 17.2, 17.4**
    """
    parser = StudentCSVParser()
    
    # Create headers without the missing column
    required_columns = ['ФИО', 'username']
    headers = [col for col in required_columns if col != missing_column]
    
    # Add extra columns to make it more realistic
    headers.extend(extra_columns)
    
    # Create some dummy rows
    rows = [['Test Data'] * len(headers) for _ in range(row_count)]
    
    # Create CSV file
    csv_file = create_csv_file(headers, rows)
    
    # Parser should raise CSVFileMissingColumnError
    with pytest.raises(CSVFileMissingColumnError) as exc_info:
        parser.parse(csv_file)
    
    # Verify the error message mentions the missing column
    assert missing_column in str(exc_info.value.detail)


@given(
    full_names=st.lists(
        st.text(min_size=3, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'Zs'))),
        min_size=1,
        max_size=20
    ),
    usernames=st.lists(
        st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=('L', 'Nd', 'Pc'))),
        min_size=1,
        max_size=20
    )
)
@settings(max_examples=100)
def test_csv_parser_valid_data(full_names, usernames):
    """
    Property: Valid CSV files should be parsed successfully.
    
    For any valid CSV file with required columns (ФИО, username),
    parser should return a list of student dictionaries.
    
    **Validates: Requirements 17.1, 17.2, 17.5**
    """
    # Ensure we have the same number of names and usernames
    assume(len(full_names) > 0)
    assume(len(usernames) > 0)
    
    # Trim to same length
    min_len = min(len(full_names), len(usernames))
    full_names = full_names[:min_len]
    usernames = usernames[:min_len]
    
    # Filter out empty strings
    valid_data = [(fn.strip(), un.strip()) for fn, un in zip(full_names, usernames) if fn.strip() and un.strip()]
    assume(len(valid_data) > 0)
    
    parser = StudentCSVParser()
    
    # Create CSV with required columns
    headers = ['ФИО', 'username']
    rows = [[fn, un] for fn, un in valid_data]
    
    csv_file = create_csv_file(headers, rows)
    
    # Parse should succeed
    result = parser.parse(csv_file)
    
    # Verify result structure
    assert isinstance(result, list)
    assert len(result) == len(valid_data)
    
    for i, student in enumerate(result):
        assert 'full_name' in student
        assert 'telegram_username' in student
        assert student['full_name'] == valid_data[i][0]
        assert student['telegram_username'] == valid_data[i][1]


@given(
    empty_rows=st.integers(min_value=0, max_value=5),
    valid_rows=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_csv_parser_skips_empty_lines(empty_rows, valid_rows):
    """
    Property: CSV parser should skip empty lines.
    
    For any CSV file with empty lines, parser should skip them
    and only return non-empty student records.
    
    **Validates: Requirements 17.3**
    """
    parser = StudentCSVParser()
    
    headers = ['ФИО', 'username']
    rows = []
    
    # Add some empty rows
    for _ in range(empty_rows):
        rows.append(['', ''])
    
    # Add valid rows
    expected_students = []
    for i in range(valid_rows):
        full_name = f"Student {i}"
        username = f"user{i}"
        rows.append([full_name, username])
        expected_students.append({'full_name': full_name, 'telegram_username': username})
    
    csv_file = create_csv_file(headers, rows)
    
    result = parser.parse(csv_file)
    
    # Should only return valid rows
    assert len(result) == valid_rows
    assert result == expected_students


def test_csv_parser_empty_file():
    """
    Property: Empty CSV files should raise CSVFileEmptyError.
    
    **Validates: Requirements 17.4**
    """
    parser = StudentCSVParser()
    
    # Create empty CSV (only headers, no data)
    headers = ['ФИО', 'username']
    rows = []
    
    csv_file = create_csv_file(headers, rows)
    
    with pytest.raises(CSVFileEmptyError):
        parser.parse(csv_file)


def test_csv_parser_utf8_encoding():
    """
    Property: CSV parser should handle UTF-8 encoding correctly.
    
    **Validates: Requirements 17.1**
    """
    parser = StudentCSVParser()
    
    # Create CSV with Cyrillic characters
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


def test_csv_parser_invalid_encoding():
    """
    Property: CSV parser should raise error for non-UTF-8 files.
    
    **Validates: Requirements 17.1, 17.4**
    """
    parser = StudentCSVParser()
    
    # Create a file with invalid encoding (not UTF-8)
    invalid_content = b'\xff\xfe\x00\x00'  # Invalid UTF-8 bytes
    csv_file = io.BytesIO(invalid_content)
    
    with pytest.raises(CSVParsingError) as exc_info:
        parser.parse(csv_file)
    
    assert 'UTF-8' in str(exc_info.value.detail)
