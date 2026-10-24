"""
Unit tests for Attendix Attendance Service, data normalization, classification,
and Telegram message formatting/pagination.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from telegram_bot.attendance_service import (
    classify_attendance,
    calculate_totals,
    format_attendance_report,
    format_subjects_page,
    sync_attendance,
    authenticate_and_link
)
from telegram_bot.database import (
    init_db,
    save_user,
    save_attendance_cache,
    get_attendance_cache
)


def test_classify_attendance():
    """Verify threshold classification for Green, Yellow, and Red categories."""
    assert classify_attendance(85.0) == ("🟢", "Safe")
    assert classify_attendance(75.0) == ("🟢", "Safe")
    assert classify_attendance(74.9) == ("🟡", "Warning")
    assert classify_attendance(65.0) == ("🟡", "Warning")
    assert classify_attendance(64.99) == ("🔴", "Critical")
    assert classify_attendance(0.0) == ("🔴", "Critical")


def test_calculate_totals():
    """Verify attendance counters: attended, conducted, percentage, and courses count."""
    records = [
        {"subject": "Sub1", "attended": "10", "total": "12"},
        {"subject": "Sub2", "attended": "20", "total": "25"},
        {"subject": "Sub3", "attended": "5", "total": "5"}
    ]
    # Attended = 35, Total = 42, Perc = 35/42 * 100 = 83.33%
    totals = calculate_totals(records)
    assert totals["attended"] == 35
    assert totals["conducted"] == 42
    assert totals["percentage"] == 83.33
    assert totals["courses_count"] == 3


def test_empty_or_missing_records():
    """Verify handling when attendance records are empty or malformed."""
    totals = calculate_totals([])
    assert totals["attended"] == 0
    assert totals["conducted"] == 0
    assert totals["percentage"] == 0.0
    assert totals["courses_count"] == 0

    # Malformed non-numeric values
    malformed = [{"subject": "Test", "attended": "-", "total": "-"}]
    totals_m = calculate_totals(malformed)
    assert totals_m["attended"] == 0
    assert totals_m["conducted"] == 0
    assert totals_m["percentage"] == 0.0


def test_format_attendance_report():
    """Verify attendance report format complies with Section 5 specification."""
    records = [
        {"subject": "23CSE109", "attended": "28", "total": "30", "percentage": "93.3"},
        {"subject": "23CSE701", "attended": "20", "total": "25", "percentage": "80.0"},
        {"subject": "APPTITUDE", "attended": "14", "total": "20", "percentage": "70.0"}
    ]
    report_text, total_pages = format_attendance_report(
        student_name="Bhoj Raj",
        roll_number="25695A0514",
        records=records,
        synced_at="2026-10-24T08:00:00Z",
        is_stale=False,
        page=1
    )
    assert "ATTENDIX — ATTENDANCE REPORT" in report_text
    assert "Bhoj Raj" in report_text
    assert "25695A0514" in report_text
    assert "Overall Attendance:" in report_text
    assert "Attendance Counters" in report_text
    assert "SUBJECT-WISE ATTENDANCE" in report_text
    assert "🟢 23CSE109 — <b>93.3%</b> (28/30)" in report_text
    assert "🟡 APPTITUDE — <b>70.0%</b> (14/20)" in report_text
    assert total_pages == 1


def test_attendance_report_pagination():
    """Verify that a large list of subjects is cleanly paginated to prevent Telegram message limit overflow."""
    # Create 15 mock subjects
    records = [
        {"subject": f"Course {i}", "attended": "10", "total": "12", "percentage": "83.3"}
        for i in range(1, 16)
    ]
    # With page_size=8, 15 records should yield 2 pages
    p1_text, total_pages = format_attendance_report("Student", "ROLL01", records, page=1, page_size=8)
    assert total_pages == 2
    assert "Course 1" in p1_text
    assert "Course 8" in p1_text
    assert "Course 9" not in p1_text

    p2_text, _ = format_attendance_report("Student", "ROLL01", records, page=2, page_size=8)
    assert "Course 9" in p2_text
    assert "Course 15" in p2_text


def test_format_subjects_page():
    """Verify subject-wise pagination and detail listing."""
    records = [
        {"subject": "Python Lab", "attended": "18", "total": "20", "percentage": "90.0"},
        {"subject": "Maths IV", "attended": "12", "total": "20", "percentage": "60.0"}
    ]
    text, page_records, total_pages = format_subjects_page(records, page=1, page_size=5)
    assert "ATTENDIX — SUBJECT ATTENDANCE" in text
    assert "Python Lab" in text
    assert "Maths IV" in text
    assert "Critical" in text
    assert len(page_records) == 2


@pytest.mark.asyncio
async def test_cached_attendance_fallback(tmp_path):
    """
    Test that when live scraping fails (e.g. portal unreachable),
    the service safely falls back to the existing cache and flags it as stale.
    """
    db_file = str(tmp_path / "test_cache.db")
    await init_db(db_file)

    telegram_id = 999999
    await save_user(telegram_id, "23691A0599", "secret_pass", student_name="Alice", db_path=db_file)

    cached_records = [
        {"subject": "Physics", "attended": "15", "total": "20", "percentage": "75.0"}
    ]
    await save_attendance_cache(telegram_id, cached_records, student_name="Alice", db_path=db_file)

    # Mock get_attendance to simulate portal failure
    with patch("telegram_bot.attendance_service.get_attendance", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = {"error": "MITS IMS 503 Service Unavailable"}

        result = await sync_attendance(telegram_id, force_refresh=True, db_path=db_file)
        assert result["success"] is True
        assert result["from_cache"] is True
        assert result["is_stale"] is True
        assert "warning" in result
        assert len(result["records"]) == 1
        assert result["records"][0]["subject"] == "Physics"


@pytest.mark.asyncio
async def test_successful_and_failed_ims_login(tmp_path):
    """Verify authentication flow for both successful and invalid credentials."""
    db_file = str(tmp_path / "test_auth.db")
    await init_db(db_file)

    # 1. Failed Login (invalid credentials)
    with patch("telegram_bot.attendance_service.get_attendance", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = {"error": "Invalid Student ID or Password."}
        res_fail = await authenticate_and_link(
            telegram_id=12345,
            roll_number="INVALID_ROLL",
            password="wrong_password",
            db_path=db_file
        )
        assert res_fail["success"] is False
        assert "Invalid Student ID or Password" in res_fail["error"]

    # 2. Successful Login
    mock_success_data = {
        "student_name": "John Doe",
        "records": [
            {"subject": "23CSE101", "attended": "18", "total": "20", "percentage": "90.0"}
        ]
    }
    with patch("telegram_bot.attendance_service.get_attendance", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = mock_success_data
        res_ok = await authenticate_and_link(
            telegram_id=54321,
            roll_number="25695A0514",
            password="correct_password",
            db_path=db_file
        )
        assert res_ok["success"] is True
        assert res_ok["student_name"] == "John Doe"
        assert len(res_ok["records"]) == 1


@pytest.mark.asyncio
async def test_concurrent_requests_handling(tmp_path):
    """Verify that multiple concurrent sync requests are executed safely without race conditions."""
    db_file = str(tmp_path / "test_concurrent.db")
    await init_db(db_file)

    telegram_id = 777777
    await save_user(telegram_id, "23691A0577", "pass77", student_name="Sam", db_path=db_file)

    mock_data = {
        "student_name": "Sam",
        "records": [
            {"subject": "Data Structures", "attended": "25", "total": "30", "percentage": "83.3"}
        ]
    }

    with patch("telegram_bot.attendance_service.get_attendance", new_callable=AsyncMock) as mock_scrape:
        mock_scrape.return_value = mock_data

        # Fire 5 concurrent sync calls for the same user
        tasks = [sync_attendance(telegram_id, force_refresh=True, db_path=db_file) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        for res in results:
            assert res["success"] is True
            assert res["student_name"] == "Sam"
            assert len(res["records"]) == 1


@pytest.mark.asyncio
async def test_cache_ttl_freshness(tmp_path):
    """Verify that sync_attendance serves from cache without hitting scraper when cache is fresh."""
    db_file = str(tmp_path / "test_ttl.db")
    await init_db(db_file)

    telegram_id = 888888
    await save_user(telegram_id, "23691A0588", "pass88", student_name="Fresh Student", db_path=db_file)
    await save_attendance_cache(
        telegram_id,
        [{"subject": "OS", "attended": "10", "total": "10", "percentage": "100.0"}],
        student_name="Fresh Student",
        db_path=db_file
    )

    with patch("telegram_bot.attendance_service.get_attendance", new_callable=AsyncMock) as mock_scrape:
        # force_refresh=False: should hit cache and NOT call get_attendance
        result = await sync_attendance(telegram_id, force_refresh=False, db_path=db_file)
        assert result["success"] is True
        assert result["from_cache"] is True
        assert mock_scrape.call_count == 0
