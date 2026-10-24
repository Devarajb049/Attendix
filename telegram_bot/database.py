"""
Database access layer for Attendix Telegram Bot.
Uses aiosqlite for non-blocking asynchronous operations, implements per-user isolation,
and transparently encrypts MITS IMS credentials using Fernet.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import aiosqlite

from .config import DATABASE_PATH, get_cipher

logger = logging.getLogger("attendix_bot.database")


def _get_db_path(custom_path: Optional[str] = None) -> str:
    path_str = custom_path or DATABASE_PATH
    p = Path(path_str)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parent / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


async def init_db(db_path: Optional[str] = None) -> None:
    """
    Initializes SQLite database tables with foreign keys and strict schemas.
    """
    resolved_path = _get_db_path(db_path)
    async with aiosqlite.connect(resolved_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        
        # Table 1: Users (Linked Telegram accounts)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                roll_number TEXT NOT NULL,
                student_name TEXT,
                encrypted_password TEXT NOT NULL,
                default_target REAL DEFAULT 75.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Table 2: Attendance Cache
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance_cache (
                telegram_id INTEGER PRIMARY KEY,
                student_name TEXT,
                attendance_json TEXT NOT NULL,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_stale INTEGER DEFAULT 0,
                FOREIGN KEY (telegram_id) REFERENCES users (telegram_id) ON DELETE CASCADE
            );
        """)

        await db.commit()
    logger.info(f"Database initialized at {resolved_path}")


async def save_user(
    telegram_id: int,
    roll_number: str,
    plain_password: str,
    student_name: Optional[str] = None,
    default_target: float = 75.0,
    db_path: Optional[str] = None
) -> None:
    """
    Encrypts password and upserts user record with strict telegram_id isolation.
    """
    resolved_path = _get_db_path(db_path)
    cipher = get_cipher()
    encrypted_pw = cipher.encrypt(plain_password.strip().encode()).decode()
    now_iso = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(resolved_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("""
            INSERT INTO users (telegram_id, roll_number, student_name, encrypted_password, default_target, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                roll_number = excluded.roll_number,
                student_name = COALESCE(excluded.student_name, users.student_name),
                encrypted_password = excluded.encrypted_password,
                default_target = excluded.default_target,
                updated_at = excluded.updated_at;
        """, (int(telegram_id), roll_number.strip().upper(), student_name, encrypted_pw, float(default_target), now_iso, now_iso))
        await db.commit()


async def get_user(telegram_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves user record for the specific telegram_id and decrypts credentials in memory.
    Returns None if user does not exist or credentials cannot be decrypted.
    """
    resolved_path = _get_db_path(db_path)
    async with aiosqlite.connect(resolved_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT telegram_id, roll_number, student_name, encrypted_password, default_target, created_at, updated_at "
            "FROM users WHERE telegram_id = ? LIMIT 1;",
            (int(telegram_id),)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            try:
                cipher = get_cipher()
                decrypted_pw = cipher.decrypt(row["encrypted_password"].encode()).decode()
            except Exception as e:
                logger.error(f"Failed to decrypt credentials for user {telegram_id}: {e}")
                return None

            return {
                "telegram_id": row["telegram_id"],
                "roll_number": row["roll_number"],
                "student_name": row["student_name"],
                "password": decrypted_pw,
                "default_target": float(row["default_target"] or 75.0),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }


async def update_default_target(telegram_id: int, target: float, db_path: Optional[str] = None) -> bool:
    """Updates the user's preferred attendance target percentage."""
    resolved_path = _get_db_path(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(resolved_path) as db:
        cursor = await db.execute(
            "UPDATE users SET default_target = ?, updated_at = ? WHERE telegram_id = ?;",
            (float(target), now_iso, int(telegram_id))
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_user(telegram_id: int, db_path: Optional[str] = None) -> bool:
    """
    Completely removes user record and associated attendance cache (GDPR / privacy compliant).
    """
    resolved_path = _get_db_path(db_path)
    async with aiosqlite.connect(resolved_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("DELETE FROM attendance_cache WHERE telegram_id = ?;", (int(telegram_id),))
        cursor = await db.execute("DELETE FROM users WHERE telegram_id = ?;", (int(telegram_id),))
        await db.commit()
        return cursor.rowcount > 0


async def save_attendance_cache(
    telegram_id: int,
    records: List[Dict[str, Any]],
    student_name: Optional[str] = None,
    db_path: Optional[str] = None
) -> None:
    """
    Saves or refreshes the latest attendance records in the local cache.
    """
    resolved_path = _get_db_path(db_path)
    records_json = json.dumps(records)
    now_iso = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(resolved_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("""
            INSERT INTO attendance_cache (telegram_id, student_name, attendance_json, synced_at, is_stale)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(telegram_id) DO UPDATE SET
                student_name = COALESCE(excluded.student_name, attendance_cache.student_name),
                attendance_json = excluded.attendance_json,
                synced_at = excluded.synced_at,
                is_stale = 0;
        """, (int(telegram_id), student_name, records_json, now_iso))

        # Also update student_name in users table if discovered
        if student_name:
            await db.execute(
                "UPDATE users SET student_name = ? WHERE telegram_id = ? AND (student_name IS NULL OR student_name = '');",
                (student_name, int(telegram_id))
            )

        await db.commit()


async def get_attendance_cache(telegram_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves the cached attendance data for a specific telegram_id.
    """
    resolved_path = _get_db_path(db_path)
    async with aiosqlite.connect(resolved_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT telegram_id, student_name, attendance_json, synced_at, is_stale "
            "FROM attendance_cache WHERE telegram_id = ? LIMIT 1;",
            (int(telegram_id),)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            try:
                records = json.loads(row["attendance_json"])
            except Exception:
                records = []

            return {
                "telegram_id": row["telegram_id"],
                "student_name": row["student_name"],
                "records": records,
                "synced_at": row["synced_at"],
                "is_stale": bool(row["is_stale"])
            }


async def mark_cache_stale(telegram_id: int, db_path: Optional[str] = None) -> None:
    """Marks existing cached records as stale after a sync failure."""
    resolved_path = _get_db_path(db_path)
    async with aiosqlite.connect(resolved_path) as db:
        await db.execute(
            "UPDATE attendance_cache SET is_stale = 1 WHERE telegram_id = ?;",
            (int(telegram_id),)
        )
        await db.commit()
