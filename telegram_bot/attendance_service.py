"""
Attendance Service Adapter for Attendix Telegram Bot.
Bridges the Telegram Bot with the root scraper, manages caching, concurrency locks,
and handles MITS IMS network/portal degradation gracefully.
"""

import sys
import html
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Ensure project root is in sys.path to safely reuse existing root-level scraper
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scraper import get_attendance
except ImportError as e:
    raise ImportError(f"Could not import root scraper: {e}")

from .config import CACHE_TTL_SECONDS, MAX_CONCURRENT_SCRAPES
from .database import (
    get_user,
    save_user,
    save_attendance_cache,
    get_attendance_cache,
    mark_cache_stale
)

logger = logging.getLogger("attendix_bot.attendance_service")

# Concurrency controls
_user_locks: Dict[int, asyncio.Lock] = {}
_global_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)


def _get_user_lock(telegram_id: int) -> asyncio.Lock:
    if telegram_id not in _user_locks:
        _user_locks[telegram_id] = asyncio.Lock()
    return _user_locks[telegram_id]


def classify_attendance(percentage: float) -> Tuple[str, str]:
    """
    Returns (status_emoji, status_label) based on MITS attendance regulations:
    - 🟢 Safe: >= 75.0%
    - 🟡 Warning / Condonation zone: 65.0% to 74.99%
    - 🔴 Critical / Detention risk: < 65.0%
    """
    try:
        val = float(percentage)
    except (ValueError, TypeError):
        val = 0.0

    if val >= 75.0:
        return "🟢", "Safe"
    elif val >= 65.0:
        return "🟡", "Warning"
    else:
        return "🔴", "Critical"


def clean_student_name(name: Optional[str]) -> Optional[str]:
    """Filters out UI headers or keywords mistakenly extracted as student names."""
    if not name:
        return None
    cleaned = name.strip()
    upper = cleaned.upper()
    if upper in [
        "SUBJECT", "SUBJECTS", "STUDENT", "N/A", "NONE", "UNKNOWN", "TOTAL",
        "STUDENT NAME", "DASHBOARD", "NAME", "COURSE", "COURSES",
        "SOFTSKILLS", "SOFT SKILLS", "APPTITUDE", "APTITUDE"
    ]:
        return None
    if any(k in upper for k in ["SKILLS", "APPTITUDE", "APTITUDE", "SEMESTER", "BRANCH"]):
        return None
    return cleaned


def calculate_totals(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates overall attended, conducted, and aggregate percentage."""
    total_att = 0
    total_cond = 0
    for r in records:
        try:
            total_att += int(r.get("attended", 0))
            total_cond += int(r.get("total", r.get("conducted", 0)))
        except (ValueError, TypeError):
            continue

    perc = (total_att / total_cond * 100.0) if total_cond > 0 else 0.0
    return {
        "attended": total_att,
        "conducted": total_cond,
        "percentage": round(perc, 2),
        "courses_count": len(records)
    }


async def authenticate_and_link(
    telegram_id: int,
    roll_number: str,
    password: str,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Authenticates candidate credentials against real MITS IMS portal using existing scraper.
    If valid, stores encrypted credentials and initializes attendance cache.
    """
    user_lock = _get_user_lock(telegram_id)
    async with user_lock:
        async with _global_semaphore:
            logger.info(f"Authenticating IMS account for Telegram user {telegram_id} ({roll_number})...")
            try:
                result = await get_attendance(roll_number.strip(), password.strip())
            except Exception as e:
                logger.error(f"Scraper error during login: {e}")
                return {"success": False, "error": f"Portal connection error: {str(e)}"}

    if not result:
        return {"success": False, "error": "Unable to connect to MITS IMS portal."}

    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}

    if isinstance(result, dict) and "records" in result:
        records = result["records"]
        student_name = clean_student_name(result.get("student_name"))
    else:
        records = result if isinstance(result, list) else []
        student_name = None

    if not records:
        return {"success": False, "error": "Login succeeded, but no attendance records were found."}

    # Store user securely and cache the first fetch
    await save_user(
        telegram_id=telegram_id,
        roll_number=roll_number,
        plain_password=password,
        student_name=student_name,
        db_path=db_path
    )
    await save_attendance_cache(
        telegram_id=telegram_id,
        records=records,
        student_name=student_name,
        db_path=db_path
    )

    return {
        "success": True,
        "student_name": student_name,
        "roll_number": roll_number,
        "records": records
    }


async def sync_attendance(
    telegram_id: int,
    force_refresh: bool = False,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves attendance data for linked user.
    Uses cache if fresh within TTL, or performs live scraping with fallback to stale cache.
    """
    user = await get_user(telegram_id, db_path=db_path)
    if not user:
        return {
            "success": False,
            "error": "No MITS IMS account linked. Please use /login to connect your account."
        }

    # Check cache freshness
    cached = await get_attendance_cache(telegram_id, db_path=db_path)
    if cached and cached.get("records") and not force_refresh:
        synced_at_str = cached.get("synced_at")
        try:
            if synced_at_str:
                synced_dt = datetime.fromisoformat(synced_at_str)
                now_dt = datetime.now(timezone.utc)
                if synced_dt.tzinfo is None:
                    synced_dt = synced_dt.replace(tzinfo=timezone.utc)
                age = (now_dt - synced_dt).total_seconds()
                if age < CACHE_TTL_SECONDS:
                    return {
                        "success": True,
                        "student_name": cached.get("student_name") or user.get("student_name"),
                        "roll_number": user["roll_number"],
                        "records": cached["records"],
                        "synced_at": synced_at_str,
                        "from_cache": True,
                        "is_stale": False
                    }
        except Exception as e:
            logger.debug(f"Cache time check notice: {e}")

    # Fetch live data through scraper
    user_lock = _get_user_lock(telegram_id)
    async with user_lock:
        async with _global_semaphore:
            logger.info(f"Syncing live attendance for user {telegram_id} ({user['roll_number']})...")
            try:
                result = await get_attendance(user["roll_number"], user["password"])
            except Exception as e:
                result = {"error": str(e)}

    # Check live result
    if result and isinstance(result, dict) and "records" in result and result["records"]:
        records = result["records"]
        student_name = clean_student_name(result.get("student_name")) or clean_student_name(user.get("student_name"))
        await save_attendance_cache(telegram_id, records, student_name=student_name, db_path=db_path)
        return {
            "success": True,
            "student_name": student_name,
            "roll_number": user["roll_number"],
            "records": records,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "from_cache": False,
            "is_stale": False
        }

    # Live scrape failed: Fallback to existing cache if available
    if cached and cached.get("records"):
        await mark_cache_stale(telegram_id, db_path=db_path)
        return {
            "success": True,
            "student_name": clean_student_name(cached.get("student_name")) or clean_student_name(user.get("student_name")),
            "roll_number": user["roll_number"],
            "records": cached["records"],
            "synced_at": cached.get("synced_at"),
            "from_cache": True,
            "is_stale": True,
            "warning": "Could not connect to MITS IMS portal to refresh data. Displaying latest saved cached records."
        }

    # If both live scrape and cache failed
    err_msg = result.get("error") if isinstance(result, dict) else "Unable to retrieve attendance."
    return {
        "success": False,
        "error": f"Failed to retrieve attendance: {err_msg}"
    }


def format_attendance_report(
    student_name: Optional[str],
    roll_number: str,
    records: List[Dict[str, Any]],
    synced_at: Optional[str] = None,
    is_stale: bool = False,
    page: int = 1,
    page_size: int = 8
) -> Tuple[str, int]:
    """
    Renders the official Attendix Attendance Report formatted for Telegram.
    Returns (formatted_text, total_pages).
    """
    totals = calculate_totals(records)
    name_display = html.escape(clean_student_name(student_name) or "Verified Student")
    roll_display = html.escape(roll_number.upper())

    # Format sync timestamp
    if synced_at:
        try:
            dt = datetime.fromisoformat(synced_at)
            time_display = dt.strftime("%d %b %Y, %I:%M %p UTC")
        except Exception:
            time_display = html.escape(str(synced_at))
    else:
        time_display = "Just now"

    # Pagination calculation
    total_subjects = len(records)
    total_pages = max(1, (total_subjects + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_records = records[start_idx:start_idx + page_size]

    lines = [
        "📊 <b>ATTENDIX — ATTENDANCE REPORT</b>",
        f"👤 <b>Student:</b> {name_display}",
        f"🎓 <b>Roll Number:</b> <code>{roll_display}</code>",
        f"<b>Overall Attendance:</b> <b>{totals['percentage']:.2f}%</b>\n",
        "📈 <b>Attendance Counters</b>",
        f"• Attended: <b>{totals['attended']}</b>",
        f"• Conducted: <b>{totals['conducted']}</b>",
        f"• Courses: <b>{totals['courses_count']}</b>\n",
        f"📚 <b>SUBJECT-WISE ATTENDANCE</b>"
    ]

    if total_pages > 1:
        lines.append(f"<i>(Showing page {page} of {total_pages})</i>")

    for r in page_records:
        sub_raw = r.get("subject", "Unknown Course")
        sub_esc = html.escape(sub_raw)
        try:
            att = int(r.get("attended", 0))
            tot = int(r.get("total", r.get("conducted", 0)))
            perc_val = float(r.get("percentage", 0.0))
        except (ValueError, TypeError):
            att, tot, perc_val = 0, 0, 0.0

        badge, _ = classify_attendance(perc_val)
        lines.append(f"{badge} {sub_esc} — <b>{perc_val:.1f}%</b> ({att}/{tot})")

    if is_stale:
        lines.append("\n⚠️ <i>[CACHED DATA] MITS IMS could not be reached just now. Showing last verified synchronization.</i>")

    lines.append(f"\n🕒 <i>Last Synchronized: {time_display}</i>")
    return "\n".join(lines), total_pages


def format_subjects_page(
    records: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 6
) -> Tuple[str, List[Dict[str, Any]], int]:
    """
    Renders the paginated Subject Attendance overview with course details.
    Returns (formatted_text, current_page_records, total_pages).
    """
    total_subjects = len(records)
    total_pages = max(1, (total_subjects + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_records = records[start_idx:start_idx + page_size]

    lines = [
        "📚 <b>ATTENDIX — SUBJECT ATTENDANCE</b>",
        f"Select a subject below for detailed attendance breakdown and bunk metrics.",
        f"<i>Page {page} of {total_pages} ({total_subjects} total subjects)</i>\n"
    ]

    for idx, r in enumerate(page_records, start=start_idx + 1):
        sub_name = html.escape(r.get("subject", "Unknown Course"))
        try:
            att = int(r.get("attended", 0))
            tot = int(r.get("total", r.get("conducted", 0)))
            perc = float(r.get("percentage", 0.0))
        except (ValueError, TypeError):
            att, tot, perc = 0, 0, 0.0

        badge, label = classify_attendance(perc)
        lines.append(
            f"<b>{idx}.</b> {badge} <b>{sub_name}</b>\n"
            f"   Attendance: <b>{perc:.1f}%</b> | Classes: {att}/{tot} | Status: <i>{label}</i>"
        )

    return "\n".join(lines), page_records, total_pages
