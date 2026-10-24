"""
Unit tests for user account isolation, encryption security, and data privacy.
Verifies that multi-tenant Telegram users can never access or leak each other's credentials or attendance data.
"""

import pytest
import aiosqlite
from telegram_bot.database import (
    init_db,
    save_user,
    get_user,
    delete_user,
    update_default_target,
    save_attendance_cache,
    get_attendance_cache
)


@pytest.mark.asyncio
async def test_user_isolation_and_encryption(tmp_path):
    """
    Test that credentials for distinct Telegram accounts are strictly isolated
    and encrypted on disk in SQLite.
    """
    db_file = str(tmp_path / "test_isolation.db")
    await init_db(db_file)

    user_a_id = 10001
    user_b_id = 20002

    # Save User A
    await save_user(
        telegram_id=user_a_id,
        roll_number="25695A0514",
        plain_password="SecretPasswordA!#1",
        student_name="Student Alpha",
        default_target=75.0,
        db_path=db_file
    )

    # Save User B
    await save_user(
        telegram_id=user_b_id,
        roll_number="23691A0502",
        plain_password="SecretPasswordB!#2",
        student_name="Student Beta",
        default_target=85.0,
        db_path=db_file
    )

    # 1. Verify User A retrieval
    user_a = await get_user(user_a_id, db_path=db_file)
    assert user_a is not None
    assert user_a["telegram_id"] == user_a_id
    assert user_a["roll_number"] == "25695A0514"
    assert user_a["student_name"] == "Student Alpha"
    assert user_a["password"] == "SecretPasswordA!#1"
    assert user_a["default_target"] == 75.0

    # 2. Verify User B retrieval
    user_b = await get_user(user_b_id, db_path=db_file)
    assert user_b is not None
    assert user_b["telegram_id"] == user_b_id
    assert user_b["roll_number"] == "23691A0502"
    assert user_b["student_name"] == "Student Beta"
    assert user_b["password"] == "SecretPasswordB!#2"
    assert user_b["default_target"] == 85.0

    # 3. Verify that passwords are NOT stored in plaintext in the SQLite database
    async with aiosqlite.connect(db_file) as raw_db:
        raw_db.row_factory = aiosqlite.Row
        async with raw_db.execute("SELECT telegram_id, encrypted_password FROM users;") as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                assert "SecretPassword" not in r["encrypted_password"]
                # Fernet ciphertexts start with gAAAAA
                assert r["encrypted_password"].startswith("gAAAAA")


@pytest.mark.asyncio
async def test_cache_isolation(tmp_path):
    """
    Test that attendance cache records are strictly isolated per Telegram ID.
    """
    db_file = str(tmp_path / "test_cache_iso.db")
    await init_db(db_file)

    user_a_id = 11111
    user_b_id = 22222

    await save_user(user_a_id, "23691A0511", "passA", "Alice", db_path=db_file)
    await save_user(user_b_id, "23691A0522", "passB", "Bob", db_path=db_file)

    cache_a = [{"subject": "Math", "attended": "10", "total": "10", "percentage": "100.0"}]
    cache_b = [{"subject": "Physics", "attended": "5", "total": "10", "percentage": "50.0"}]

    await save_attendance_cache(user_a_id, cache_a, student_name="Alice", db_path=db_file)
    await save_attendance_cache(user_b_id, cache_b, student_name="Bob", db_path=db_file)

    res_a = await get_attendance_cache(user_a_id, db_path=db_file)
    res_b = await get_attendance_cache(user_b_id, db_path=db_file)

    assert res_a["records"][0]["subject"] == "Math"
    assert res_b["records"][0]["subject"] == "Physics"
    assert res_a["records"] != res_b["records"]


@pytest.mark.asyncio
async def test_user_deletion_and_gdpr(tmp_path):
    """
    Test that /delete_data or /logout completely removes the user and their cached attendance,
    without impacting any other user.
    """
    db_file = str(tmp_path / "test_delete.db")
    await init_db(db_file)

    user_a_id = 30001
    user_b_id = 40002

    await save_user(user_a_id, "23691A0531", "pass31", "User31", db_path=db_file)
    await save_user(user_b_id, "23691A0542", "pass42", "User42", db_path=db_file)

    await save_attendance_cache(user_a_id, [{"subject": "Chem"}], db_path=db_file)
    await save_attendance_cache(user_b_id, [{"subject": "Bio"}], db_path=db_file)

    # Delete User A
    deleted = await delete_user(user_a_id, db_path=db_file)
    assert deleted is True

    # User A should no longer exist
    assert await get_user(user_a_id, db_path=db_file) is None
    assert await get_attendance_cache(user_a_id, db_path=db_file) is None

    # User B must remain completely intact
    user_b = await get_user(user_b_id, db_path=db_file)
    assert user_b is not None
    assert user_b["roll_number"] == "23691A0542"
    cache_b = await get_attendance_cache(user_b_id, db_path=db_file)
    assert cache_b is not None
    assert cache_b["records"][0]["subject"] == "Bio"
