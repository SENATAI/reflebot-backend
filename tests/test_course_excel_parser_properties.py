"""
Property-based tests for CourseExcelParser.

Feature: telegram-bot-full-workflow
Task: 10.4 - Написать property tests для Use Cases
"""

import io
import pytest
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from hypothesis import given, strategies as st, settings, assume
from openpyxl import Workbook

from reflebot.apps.reflections.parsers.course_excel import CourseExcelParser
from reflebot.apps.reflections.exceptions import (
    ExcelFileError,
    ExcelFileMissingColumnError,
    ExcelFileEmptyError,
    ExcelFileDateParseError,
)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
COURSE_HEADERS = [
    'Тема лекции',
    'Дата',
    'Время',
    'Дата дедлайна',
    'Время дедлайна',
    'Код курса',
    'Один вопрос из списка',
    'Вопросы',
]


def build_course_row(
    topic: str,
    date_value,
    time_value: str,
    deadline_date_value=None,
    deadline_time_value: str = "23:59",
    join_code: str = "ABCD",
    one_question_from_list: str = "",
    questions: str = "Что это такое?",
) -> list:
    """Собрать строку Excel нового формата."""
    return [
        topic,
        date_value,
        time_value,
        deadline_date_value if deadline_date_value is not None else date_value,
        deadline_time_value,
        join_code,
        one_question_from_list,
        questions,
    ]


# Helper function to create Excel file from data
def create_excel_file(headers: list[str], rows: list[list]) -> io.BytesIO:
    """Create an Excel file in memory."""
    wb = Workbook()
    ws = wb.active
    
    # Write headers
    ws.append(headers)
    
    # Write rows
    for row in rows:
        ws.append(row)
    
    # Save to BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# Property 9: Excel Parser Column Validation
# **Validates: Requirements 6.2, 6.6**


@given(
    missing_column=st.sampled_from(
        [
            'Тема лекции',
            'Дата',
            'Время',
            'Дата дедлайна',
            'Время дедлайна',
            'Один вопрос из списка',
            'Вопросы',
        ]
    ),
    extra_columns=st.lists(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=('L', 'Nd', 'Zs'), min_codepoint=32, max_codepoint=126)
        ),
        max_size=3
    ),
    row_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_property_9_excel_parser_missing_column_validation(
    missing_column,
    extra_columns,
    row_count,
):
    """
    Property 9: Excel Parser Column Validation
    
    For any Excel файла без обязательных колонок нового формата,
    парсер должен выбрасывать исключение с описанием ошибки.
    
    **Validates: Requirements 6.2, 6.6**
    """
    parser = CourseExcelParser()
    
    # Create headers without the missing column
    required_columns = [
        'Тема лекции',
        'Дата',
        'Время',
        'Дата дедлайна',
        'Время дедлайна',
        'Один вопрос из списка',
        'Вопросы',
    ]
    headers = [col for col in required_columns if col != missing_column]
    
    # Add extra columns to make it more realistic
    headers.extend(extra_columns)
    
    # Create some dummy rows
    rows = [['Test Data'] * len(headers) for _ in range(row_count)]
    
    # Create Excel file
    excel_file = create_excel_file(headers, rows)
    
    # Parser should raise ExcelFileMissingColumnError
    with pytest.raises(ExcelFileMissingColumnError) as exc_info:
        parser.parse(excel_file)
    
    # Verify the error message mentions the missing column
    assert missing_column in str(exc_info.value.detail)


# Property 10: Date Format Parsing
# **Validates: Requirements 6.3**


@given(
    date_format=st.sampled_from(['MM/DD/YYYY', 'DD.MM.YYYY', 'YYYY-MM-DD']),
    year=st.integers(min_value=2024, max_value=2025),
    month=st.integers(min_value=1, max_value=12),
    day=st.integers(min_value=1, max_value=28),  # Safe day range for all months
)
@settings(max_examples=100)
def test_property_10_date_format_parsing(
    date_format,
    year,
    month,
    day,
):
    """
    Property 10: Date Format Parsing
    
    For any даты в форматах MM/DD/YYYY, DD.MM.YYYY или YYYY-MM-DD,
    Excel парсер должен корректно распознавать и преобразовывать дату.
    
    **Validates: Requirements 6.3**
    """
    parser = CourseExcelParser()
    
    # Format date according to the selected format
    if date_format == 'MM/DD/YYYY':
        date_str = f"{month:02d}/{day:02d}/{year}"
    elif date_format == 'DD.MM.YYYY':
        date_str = f"{day:02d}.{month:02d}.{year}"
    else:  # YYYY-MM-DD
        date_str = f"{year}-{month:02d}-{day:02d}"
    
    # Create Excel file with one lection
    headers = COURSE_HEADERS
    rows = [
        build_course_row('Test Lection', date_str, '10:00-12:00')
    ]
    
    excel_file = create_excel_file(headers, rows)
    
    # Parse should succeed
    lections = parser.parse(excel_file)
    
    # Verify date was parsed correctly
    assert len(lections) == 1
    lection = lections[0]
    
    # Check that the date components match
    assert lection['started_at'].year == year
    assert lection['started_at'].month == month
    assert lection['started_at'].day == day


# Property 11: Time Format Parsing
# **Validates: Requirements 6.4**


@given(
    time_separator=st.sampled_from(['–', '-']),  # En dash and hyphen
    start_hour=st.integers(min_value=8, max_value=20),
    start_minute=st.sampled_from([0, 15, 30, 45]),
    duration_minutes=st.integers(min_value=30, max_value=240),
)
@settings(max_examples=100)
def test_property_11_time_format_parsing(
    time_separator,
    start_hour,
    start_minute,
    duration_minutes,
):
    """
    Property 11: Time Format Parsing
    
    For any времени в формате HH:MM–HH:MM или HH:MM-HH:MM,
    Excel парсер должен корректно распознавать начало и конец лекции.
    
    **Validates: Requirements 6.4**
    """
    parser = CourseExcelParser()
    
    # Calculate end time
    total_start_minutes = start_hour * 60 + start_minute
    total_end_minutes = total_start_minutes + duration_minutes
    end_hour = (total_end_minutes // 60) % 24
    end_minute = total_end_minutes % 60
    
    # Format time string
    time_str = f"{start_hour:02d}:{start_minute:02d}{time_separator}{end_hour:02d}:{end_minute:02d}"
    
    # Create Excel file with one lection
    headers = COURSE_HEADERS
    rows = [
        build_course_row('Test Lection', '01.01.2024', time_str)
    ]
    
    excel_file = create_excel_file(headers, rows)
    
    # Parse should succeed
    lections = parser.parse(excel_file)
    
    # Verify time was parsed correctly
    assert len(lections) == 1
    lection = lections[0]
    local_started_at = lection['started_at'].astimezone(MOSCOW_TZ)
    local_ended_at = lection['ended_at'].astimezone(MOSCOW_TZ)
    
    # Check that the time components match
    assert local_started_at.hour == start_hour
    assert local_started_at.minute == start_minute
    assert local_ended_at.hour == end_hour
    assert local_ended_at.minute == end_minute


# Additional property: Parser ignores extra "Препод" column
# **Validates: Requirements 6.5**


@given(
    row_count=st.integers(min_value=1, max_value=10),
    teacher_names=st.lists(
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=('L', 'Zs'), min_codepoint=32, max_codepoint=126)
        ),
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_parser_ignores_teacher_column(
    row_count,
    teacher_names,
):
    """
    Property: Parser Ignores Teacher Column
    
    For any Excel файла с лишней колонкой "Препод", парсер должен игнорировать её
    и успешно парсить остальные данные.
    
    **Validates: Requirements 6.5**
    """
    # Ensure we have enough teacher names
    assume(len(teacher_names) >= row_count)
    
    parser = CourseExcelParser()
    
    # Create headers with "Препод" column
    headers = [*COURSE_HEADERS, 'Препод']
    
    # Create rows with teacher names
    rows = []
    for i in range(row_count):
        rows.append([
            *build_course_row(f'Lection {i}', '01.01.2024', '10:00-12:00'),
            teacher_names[i],
        ])
    
    excel_file = create_excel_file(headers, rows)
    
    # Parse should succeed
    lections = parser.parse(excel_file)
    
    # Verify parsing succeeded
    assert len(lections) == row_count
    
    # Verify teacher names are NOT in the lection data
    for lection in lections:
        assert 'teacher' not in lection
        assert 'teacher_name' not in lection
        assert 'препод' not in lection.get('topic', '').lower()


# Edge case: Valid Excel with all supported formats
def test_parser_handles_mixed_date_formats():
    """
    Edge Case: Parser should handle mixed date formats in same file.
    
    Note: In practice, Excel files should use consistent formats,
    but parser should be robust.
    
    **Validates: Requirements 6.3**
    """
    parser = CourseExcelParser()
    
    # Create Excel file with different date formats
    headers = COURSE_HEADERS
    rows = [
        build_course_row('Lection 1', '01/15/2024', '10:00-12:00', '01/16/2024', '20:00', 'ABCD', '', 'Q1'),
        build_course_row('Lection 2', '16.01.2024', '14:00-16:00', '17.01.2024', '20:00', 'ABCD', '', 'Q2'),
        build_course_row('Lection 3', '2024-01-17', '10:00-12:00', '2024-01-18', '20:00', 'ABCD', '', 'Q3'),
    ]
    
    excel_file = create_excel_file(headers, rows)
    
    # Parse should succeed
    lections = parser.parse(excel_file)
    
    # Verify all lections were parsed
    assert len(lections) == 3
    assert lections[0]['started_at'].day == 15
    assert lections[1]['started_at'].day == 16
    assert lections[2]['started_at'].day == 17


def test_parser_normalizes_local_excel_datetimes_to_utc():
    """Парсер должен сохранять введённое московское время как UTC."""
    parser = CourseExcelParser()
    headers = COURSE_HEADERS
    rows = [build_course_row('Test Lection', '01.01.2024', '10:00-12:00', '02.01.2024', '15:30', 'ABCD', '', 'Q1')]

    excel_file = create_excel_file(headers, rows)

    lections = parser.parse(excel_file)

    assert lections[0]['started_at'] == datetime(2024, 1, 1, 7, 0, tzinfo=timezone.utc)
    assert lections[0]['ended_at'] == datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    assert lections[0]['deadline'] == datetime(2024, 1, 2, 12, 30, tzinfo=timezone.utc)
    assert lections[0]['join_code'] == "ABCD"


def test_parser_accepts_deadline_time_with_seconds():
    """Парсер должен принимать время дедлайна в формате HH:MM:SS."""
    parser = CourseExcelParser()
    headers = COURSE_HEADERS
    rows = [
        build_course_row(
            'Test Lection',
            '01.01.2024',
            '10:00-12:00',
            '02.01.2024',
            '15:30:00',
            'ABCD',
            '',
            'Q1',
        )
    ]

    lections = parser.parse(create_excel_file(headers, rows))

    assert lections[0]['deadline'] == datetime(2024, 1, 2, 12, 30, tzinfo=timezone.utc)


def test_parser_accepts_lection_time_range_with_seconds():
    """Парсер должен принимать диапазон времени лекции с секундами."""
    parser = CourseExcelParser()
    headers = COURSE_HEADERS
    rows = [
        build_course_row(
            'Test Lection',
            '01.01.2024',
            '10:00:00-12:00:00',
            '02.01.2024',
            '15:30',
            'ABCD',
            '',
            'Q1',
        )
    ]

    lections = parser.parse(create_excel_file(headers, rows))

    assert lections[0]['started_at'] == datetime(2024, 1, 1, 7, 0, tzinfo=timezone.utc)
    assert lections[0]['ended_at'] == datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)


# Edge case: Empty Excel file
def test_parser_empty_file():
    """
    Edge Case: Empty Excel files should raise ExcelFileEmptyError.
    
    **Validates: Requirements 6.6**
    """
    parser = CourseExcelParser()
    
    # Create empty Excel (only headers, no data)
    headers = COURSE_HEADERS
    rows = []
    
    excel_file = create_excel_file(headers, rows)
    
    with pytest.raises(ExcelFileEmptyError):
        parser.parse(excel_file)


# Edge case: Invalid date format
def test_parser_invalid_date_format():
    """
    Edge Case: Invalid date formats should raise ExcelFileError.
    
    **Validates: Requirements 6.6**
    """
    parser = CourseExcelParser()
    
    # Create Excel with invalid date
    headers = COURSE_HEADERS
    rows = [
        build_course_row('Test Lection', 'invalid-date', '10:00-12:00')
    ]
    
    excel_file = create_excel_file(headers, rows)
    
    with pytest.raises((ExcelFileError, ExcelFileDateParseError)):
        parser.parse(excel_file)


# Edge case: Invalid time format
def test_parser_invalid_time_format():
    """
    Edge Case: Invalid time formats should raise ExcelFileDateParseError.
    
    **Validates: Requirements 6.6**
    """
    parser = CourseExcelParser()
    
    # Create Excel with invalid time
    headers = COURSE_HEADERS
    rows = [
        build_course_row('Test Lection', '01.01.2024', 'invalid-time')
    ]
    
    excel_file = create_excel_file(headers, rows)
    
    with pytest.raises((ExcelFileError, ExcelFileDateParseError)):
        parser.parse(excel_file)


def test_parser_accepts_join_code_longer_than_four_characters():
    """Парсер должен принимать код курса длиной больше 4 символов."""
    parser = CourseExcelParser()
    headers = COURSE_HEADERS
    rows = [
        build_course_row(
            'Test Lection',
            '01.01.2024',
            '10:00-12:00',
            '02.01.2024',
            '15:30',
            'BMGEN',
            '',
            'Q1',
        )
    ]

    lections = parser.parse(create_excel_file(headers, rows))

    assert lections[0]["join_code"] == "BMGEN"


def test_parser_accepts_alphabetic_join_code_like_ideann():
    """Парсер должен принимать обычный буквенный код курса."""
    parser = CourseExcelParser()
    headers = COURSE_HEADERS
    rows = [
        build_course_row(
            'Test Lection',
            '01.01.2024',
            '10:00-12:00',
            '02.01.2024',
            '15:30',
            'ideaNN',
            '',
            'Q1',
        )
    ]

    lections = parser.parse(create_excel_file(headers, rows))

    assert lections[0]["join_code"] == "ideaNN"


def test_parser_rejects_join_code_shorter_than_four_characters():
    """Парсер должен отклонять код курса короче 4 символов."""
    parser = CourseExcelParser()
    headers = COURSE_HEADERS
    rows = [
        build_course_row(
            'Test Lection',
            '01.01.2024',
            '10:00-12:00',
            '02.01.2024',
            '15:30',
            'ABC',
            '',
            'Q1',
        )
    ]

    with pytest.raises(ExcelFileDateParseError) as exc_info:
        parser.parse(create_excel_file(headers, rows))

    assert "Код курса должен состоять минимум из 4 символов." in str(exc_info.value.detail)


def test_parser_rejects_join_code_with_non_alphanumeric_symbols():
    """Парсер должен отклонять код курса со спецсимволами."""
    parser = CourseExcelParser()
    headers = COURSE_HEADERS
    rows = [
        build_course_row(
            'Test Lection',
            '01.01.2024',
            '10:00-12:00',
            '02.01.2024',
            '15:30',
            'IDEA-NN',
            '',
            'Q1',
        )
    ]

    with pytest.raises(ExcelFileDateParseError) as exc_info:
        parser.parse(create_excel_file(headers, rows))

    assert "Используйте только латинские буквы и цифры." in str(exc_info.value.detail)


def test_parser_allows_missing_join_code_column_and_returns_none():
    """Если колонки кода нет, parser должен позволить автогенерацию."""
    parser = CourseExcelParser()
    headers = [
        'Тема лекции',
        'Дата',
        'Время',
        'Дата дедлайна',
        'Время дедлайна',
        'Один вопрос из списка',
        'Вопросы',
    ]
    rows = [[
        'Test Lection',
        '01.01.2024',
        '10:00-12:00',
        '02.01.2024',
        '15:30',
        '',
        'Q1?',
    ]]

    lections = parser.parse(create_excel_file(headers, rows))

    assert lections[0]["join_code"] is None


# Property: Parser does not read course name from file
@given(
    row_count=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_parser_returns_empty_course_name(row_count):
    """
    Property: Parser Returns Empty Course Name
    
    For any Excel файла нового формата парсер не должен брать название курса из файла.
    
    **Validates: Requirements 6.7**
    """
    parser = CourseExcelParser()
    
    headers = COURSE_HEADERS
    rows = []
    for i in range(row_count):
        rows.append(
            build_course_row(
                f'Lection {i}',
                '01.01.2024',
                '10:00-12:00',
                '02.01.2024',
                '20:00',
                'ABCD',
                'нет',
                '- Q1\n- Q2',
            )
        )
    
    excel_file = create_excel_file(headers, rows)
    
    # Parse should succeed
    lections = parser.parse(excel_file)
    assert len(lections) == row_count


def test_parser_splits_questions_by_dash_marker():
    """Парсер должен делить вопросы по маркеру новой строки '- '."""
    parser = CourseExcelParser()

    lections = parser.parse(
        create_excel_file(
            COURSE_HEADERS,
            [
                build_course_row(
                    'Test Lection',
                    '01.01.2024',
                    '10:00-12:00',
                    '02.01.2024',
                    '20:00',
                    'ABCD',
                    'нет',
                    '- Что запомнилось?\n- Что было сложным?',
                )
            ],
        )
    )

    assert lections[0]['questions'] == [
        'Что запомнилось?',
        'Что было сложным?',
    ]
    assert lections[0]['one_question_from_list'] is False


def test_parser_requires_one_question_flag_for_multiple_questions():
    """Для нескольких вопросов нужно явно заполнить поле выбора одного вопроса."""
    parser = CourseExcelParser()

    with pytest.raises(ExcelFileDateParseError) as exc_info:
        parser.parse(
            create_excel_file(
                COURSE_HEADERS,
                [
                    build_course_row(
                        'Test Lection',
                        '01.01.2024',
                        '10:00-12:00',
                        '02.01.2024',
                        '20:00',
                        'ABCD',
                        '',
                        '- Первый вопрос\n- Второй вопрос',
                    )
                ],
            )
        )

    assert "Один вопрос из списка" in str(exc_info.value.detail)


def test_parser_accepts_one_question_flag_yes_for_multiple_questions():
    """При значении 'да' нужно сохранять сценарий выбора одного вопроса."""
    parser = CourseExcelParser()

    lections = parser.parse(
        create_excel_file(
            COURSE_HEADERS,
            [
                build_course_row(
                    'Test Lection',
                    '01.01.2024',
                    '10:00-12:00',
                    '02.01.2024',
                    '20:00',
                    'ABCD',
                    'да',
                    '- Первый вопрос\n- Второй вопрос',
                )
            ],
        )
    )

    assert lections[0]['one_question_from_list'] is True


def test_parser_allows_empty_one_question_flag_when_question_is_single():
    """Для одного вопроса поле выбора из списка может быть пустым."""
    parser = CourseExcelParser()

    lections = parser.parse(
        create_excel_file(
            COURSE_HEADERS,
            [
                build_course_row(
                    'Test Lection',
                    '01.01.2024',
                    '10:00-12:00',
                    '02.01.2024',
                    '20:00',
                    'ABCD',
                    '',
                    'Один вопрос без списка',
                )
            ],
        )
    )

    assert lections[0]['questions'] == ['Один вопрос без списка']
    assert lections[0]['one_question_from_list'] is False
