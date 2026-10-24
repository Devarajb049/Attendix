"""
Bunk Advice and Target Attendance Calculator for Attendix.
Implements the exact MITS IMS target formulas with full boundary checking
and floating-point precision guarantees.
"""

import math
from typing import Dict, Any, List, Optional


DISCLAIMER_TEXT = (
    "⚠️ <i>Note: These calculations assume every upcoming class has equal weight "
    "and that current MITS IMS portal records are accurate. "
    "This calculation provides guidance and cannot guarantee final attendance status.</i>"
)


def calculate_bunk_advice(attended: int, conducted: int, target_percent: float) -> Dict[str, Any]:
    """
    Calculates maximum classes that can be missed or minimum consecutive classes
    needed to achieve the target attendance percentage.

    Formulas:
        Let A = attended classes, C = conducted classes, T = target_percent / 100.0
        Current attendance = (A / C) * 100 (0.0 if C == 0)
        Bunks allowed = floor((A / T) - C)
        Classes needed = max(0, ceil((T * C - A) / (1 - T)))

    Special cases:
        - C == 0 (no classes conducted yet)
        - target_percent >= 100 (100% target division by zero protection)
        - target_percent <= 0
    """
    attended = max(0, int(attended))
    conducted = max(0, int(conducted))
    # Attended cannot exceed conducted in valid academic records, but handle defensively
    if attended > conducted:
        conducted = attended

    target_percent = float(target_percent)
    t = target_percent / 100.0

    current_perc = round((attended / conducted * 100.0), 2) if conducted > 0 else 0.0

    # 1. Edge Case: No classes conducted yet
    if conducted == 0:
        return {
            "attended": attended,
            "conducted": conducted,
            "current_percentage": 0.0,
            "target_percentage": target_percent,
            "bunks_available": 0,
            "classes_needed": 0,
            "status": "no_classes",
            "is_achievable": True,
            "message": "No classes have been conducted yet."
        }

    # 2. Edge Case: 100% Target
    if t >= 1.0:
        if attended == conducted:
            return {
                "attended": attended,
                "conducted": conducted,
                "current_percentage": 100.0,
                "target_percentage": 100.0,
                "bunks_available": 0,
                "classes_needed": 0,
                "status": "at_target",
                "is_achievable": True,
                "message": "You currently have 100% attendance. You cannot miss any classes to keep 100%."
            }
        else:
            return {
                "attended": attended,
                "conducted": conducted,
                "current_percentage": current_perc,
                "target_percentage": 100.0,
                "bunks_available": 0,
                "classes_needed": -1,  # -1 denotes mathematically impossible
                "status": "below_target",
                "is_achievable": False,
                "message": "100% attendance is mathematically impossible because at least one class has been missed."
            }

    # 3. Edge Case: Target <= 0
    if t <= 0:
        return {
            "attended": attended,
            "conducted": conducted,
            "current_percentage": current_perc,
            "target_percentage": target_percent,
            "bunks_available": 999,
            "classes_needed": 0,
            "status": "above_target",
            "is_achievable": True,
            "message": "Target is 0% or lower; no attendance requirement."
        }

    # 4. Standard calculation with floating-point round protection
    # Bunks: floor((A / T) - C)
    raw_bunks = round((attended / t) - conducted, 9)
    floor_bunks = math.floor(raw_bunks)

    # Classes needed: max(0, ceil((T * C - A) / (1 - T)))
    raw_needed = round(((t * conducted) - attended) / (1.0 - t), 9)
    ceil_needed = max(0, math.ceil(raw_needed))

    if floor_bunks >= 0:
        bunks_available = int(floor_bunks)
        classes_needed = 0
        if bunks_available > 0:
            status = "above_target"
            msg = f"You can safely miss up to <b>{bunks_available}</b> class{'es' if bunks_available != 1 else ''} while staying at or above {target_percent:g}%."
        else:
            status = "at_target"
            msg = f"You are exactly on the border of {target_percent:g}%. You cannot afford to miss the next class."
    else:
        bunks_available = 0
        classes_needed = int(ceil_needed)
        status = "below_target"
        msg = (
            f"You are currently below {target_percent:g}%. "
            f"You must attend the next <b>{classes_needed}</b> consecutive class{'es' if classes_needed != 1 else ''} to reach {target_percent:g}%."
        )

    return {
        "attended": attended,
        "conducted": conducted,
        "current_percentage": current_perc,
        "target_percentage": target_percent,
        "bunks_available": bunks_available,
        "classes_needed": classes_needed,
        "status": status,
        "is_achievable": True,
        "message": msg
    }


def calculate_overall_bunk_advice(records: List[Dict[str, Any]], target_percent: float) -> Dict[str, Any]:
    """
    Aggregates all attendance records and calculates bunk advice for the total overall attendance.
    """
    total_attended = 0
    total_conducted = 0

    for item in records:
        try:
            total_attended += int(item.get("attended", 0))
            total_conducted += int(item.get("total", item.get("conducted", 0)))
        except (ValueError, TypeError):
            continue

    overall_advice = calculate_bunk_advice(total_attended, total_conducted, target_percent)
    overall_advice["total_subjects"] = len(records)
    return overall_advice


def format_bunk_report(records: List[Dict[str, Any]], target_percent: float) -> str:
    """
    Formats an HTML-escaped Telegram message detailing bunk advice for overall
    attendance and each individual subject.
    """
    overall = calculate_overall_bunk_advice(records, target_percent)

    lines = [
        f"🎯 <b>ATTENDIX — BUNK & TARGET ADVICE</b>",
        f"<b>Target:</b> {target_percent:g}%\n",
        f"📊 <b>Overall Attendance:</b> {overall['current_percentage']:.2f}% ({overall['attended']}/{overall['conducted']})",
        f"<b>Advice:</b> {overall['message']}\n",
        f"📚 <b>SUBJECT-BY-SUBJECT BREAKDOWN</b>"
    ]

    for item in records:
        sub_name = item.get("subject", "Subject")
        try:
            att = int(item.get("attended", 0))
            tot = int(item.get("total", item.get("conducted", 0)))
        except (ValueError, TypeError):
            continue

        advice = calculate_bunk_advice(att, tot, target_percent)
        perc = advice["current_percentage"]

        if perc >= 75.0:
            badge = "🟢"
        elif perc >= 65.0:
            badge = "🟡"
        else:
            badge = "🔴"

        if advice["bunks_available"] > 0:
            action_desc = f"Can bunk: <b>{advice['bunks_available']}</b>"
        elif advice["classes_needed"] > 0:
            action_desc = f"Must attend: <b>{advice['classes_needed']}</b>"
        elif advice["classes_needed"] == -1:
            action_desc = "100% Unachievable"
        else:
            action_desc = "On target (0 bunks)"

        lines.append(f"{badge} <b>{sub_name}</b>: {perc:.1f}% ({att}/{tot}) — {action_desc}")

    lines.append(f"\n{DISCLAIMER_TEXT}")
    return "\n".join(lines)
