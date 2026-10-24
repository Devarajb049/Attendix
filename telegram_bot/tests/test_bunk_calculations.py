"""
Unit tests for Attendix Bunk Advice and Target calculations.
Tests exact mathematical formulas, boundary conditions, edge cases, and disclaimer text.
"""

import pytest
from telegram_bot.bunk_calculator import (
    calculate_bunk_advice,
    calculate_overall_bunk_advice,
    format_bunk_report,
    DISCLAIMER_TEXT
)


def test_bunk_above_target_75():
    """
    Test standard scenario where attendance is above 75%.
    A = 18, C = 20 (90.0%).
    Bunks: floor((18 / 0.75) - 20) = floor(24 - 20) = 4.
    Classes needed: 0.
    """
    result = calculate_bunk_advice(attended=18, conducted=20, target_percent=75.0)
    assert result["current_percentage"] == 90.0
    assert result["bunks_available"] == 4
    assert result["classes_needed"] == 0
    assert result["status"] == "above_target"
    assert "safely miss up to <b>4</b> classes" in result["message"]


def test_bunk_below_target_75():
    """
    Test scenario where attendance is below 75%.
    A = 14, C = 20 (70.0%).
    Bunks: 0 (since raw is negative).
    Classes needed: ceil((0.75 * 20 - 14) / 0.25) = ceil((15 - 14) / 0.25) = ceil(4.0) = 4.
    """
    result = calculate_bunk_advice(attended=14, conducted=20, target_percent=75.0)
    assert result["current_percentage"] == 70.0
    assert result["bunks_available"] == 0
    assert result["classes_needed"] == 4
    assert result["status"] == "below_target"
    assert "must attend the next <b>4</b> consecutive classes" in result["message"]


def test_bunk_exactly_at_target_75():
    """
    Test border scenario where attendance is exactly 75%.
    A = 15, C = 20 (75.0%).
    Bunks: floor((15 / 0.75) - 20) = floor(20 - 20) = 0.
    Classes needed: 0.
    """
    result = calculate_bunk_advice(attended=15, conducted=20, target_percent=75.0)
    assert result["current_percentage"] == 75.0
    assert result["bunks_available"] == 0
    assert result["classes_needed"] == 0
    assert result["status"] == "at_target"
    assert "border of 75%" in result["message"]


def test_all_standard_targets():
    """Test 75%, 80%, 85%, 90% targets on known counts."""
    # A = 40, C = 50 (80.0%)
    res_75 = calculate_bunk_advice(40, 50, 75.0)
    # floor(40 / 0.75 - 50) = floor(53.333 - 50) = 3
    assert res_75["bunks_available"] == 3
    assert res_75["classes_needed"] == 0

    res_80 = calculate_bunk_advice(40, 50, 80.0)
    # floor(40 / 0.8 - 50) = floor(50 - 50) = 0
    assert res_80["bunks_available"] == 0
    assert res_80["classes_needed"] == 0

    res_85 = calculate_bunk_advice(40, 50, 85.0)
    # ceil((0.85 * 50 - 40) / 0.15) = ceil((42.5 - 40) / 0.15) = ceil(2.5 / 0.15) = ceil(16.666) = 17
    assert res_85["bunks_available"] == 0
    assert res_85["classes_needed"] == 17

    res_90 = calculate_bunk_advice(40, 50, 90.0)
    # ceil((0.90 * 50 - 40) / 0.10) = ceil(5 / 0.10) = 50
    assert res_90["bunks_available"] == 0
    assert res_90["classes_needed"] == 50


def test_edge_case_zero_conducted():
    """Test division by zero protection when no classes have occurred."""
    result = calculate_bunk_advice(attended=0, conducted=0, target_percent=75.0)
    assert result["current_percentage"] == 0.0
    assert result["bunks_available"] == 0
    assert result["classes_needed"] == 0
    assert result["status"] == "no_classes"


def test_edge_case_target_100_percent():
    """
    Test 100% target:
    - If perfect attendance: 0 bunks, 0 needed.
    - If missed at least 1 class: 100% is impossible to achieve.
    """
    perfect = calculate_bunk_advice(attended=20, conducted=20, target_percent=100.0)
    assert perfect["bunks_available"] == 0
    assert perfect["classes_needed"] == 0
    assert perfect["is_achievable"] is True

    imperfect = calculate_bunk_advice(attended=19, conducted=20, target_percent=100.0)
    assert imperfect["bunks_available"] == 0
    assert imperfect["classes_needed"] == -1
    assert imperfect["is_achievable"] is False
    assert "mathematically impossible" in imperfect["message"]


def test_edge_case_target_zero_or_negative():
    """Test target <= 0%."""
    result = calculate_bunk_advice(attended=10, conducted=20, target_percent=0.0)
    assert result["bunks_available"] == 999
    assert result["classes_needed"] == 0


def test_overall_bunk_aggregation():
    """Test overall bunk advice aggregation across multiple subjects."""
    records = [
        {"subject": "Math", "attended": 18, "total": 20},     # 90%
        {"subject": "Physics", "attended": 12, "total": 20},  # 60%
        {"subject": "Chemistry", "attended": 15, "total": 20} # 75%
    ]
    # Total Attended = 45, Total Conducted = 60 (75.0%)
    overall = calculate_overall_bunk_advice(records, target_percent=75.0)
    assert overall["attended"] == 45
    assert overall["conducted"] == 60
    assert overall["current_percentage"] == 75.0
    assert overall["bunks_available"] == 0
    assert overall["classes_needed"] == 0
    assert overall["total_subjects"] == 3


def test_bunk_report_formatting_and_disclaimer():
    """Verify that report output contains required components and explicit disclaimer."""
    records = [
        {"subject": "23CSE109", "attended": 28, "total": 30},
        {"subject": "23CSE701", "attended": 15, "total": 25}
    ]
    formatted = format_bunk_report(records, target_percent=75.0)
    assert "ATTENDIX — BUNK & TARGET ADVICE" in formatted
    assert "Target:</b> 75%" in formatted
    assert "23CSE109" in formatted
    assert "23CSE701" in formatted
    # Check for disclaimer
    assert "These calculations assume every upcoming class has equal weight" in formatted
