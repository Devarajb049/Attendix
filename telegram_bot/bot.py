"""
Attendix Telegram Bot
Main bot implementation using python-telegram-bot (v21+ / v22+).
Provides real MITS IMS attendance tracking, subject insights, and bunk calculations.
Strictly excludes PDF download, copy summary, and manual refresh buttons.
"""

import os
import sys
import html
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure package roots are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.constants import ParseMode, ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from telegram_bot.config import TELEGRAM_BOT_TOKEN
from telegram_bot.database import (
    init_db,
    get_user,
    delete_user,
    update_default_target,
    get_attendance_cache
)
from telegram_bot.attendance_service import (
    authenticate_and_link,
    sync_attendance,
    format_attendance_report,
    format_subjects_page,
    classify_attendance,
    clean_student_name
)
from telegram_bot.bunk_calculator import (
    calculate_bunk_advice,
    calculate_overall_bunk_advice,
    format_bunk_report,
    DISCLAIMER_TEXT
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("attendix_bot")

# Conversation States
LOGIN_ROLL, LOGIN_PASSWORD = range(2)
CUSTOM_TARGET_INPUT = range(2, 3)

WEBSITE_URL = "https://attendix-dev.vercel.app/"


# ==========================================
# KEYBOARD BUILDERS
# ==========================================

def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Initial keyboard for unauthenticated users."""
    buttons = [
        [InlineKeyboardButton("🔐 Login to MITS IMS", callback_data="btn_login")],
        [InlineKeyboardButton("ℹ️ About Attendix", callback_data="btn_about")]
    ]
    return InlineKeyboardMarkup(buttons)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Main menu keyboard displayed after successful authentication.
    Strictly excludes:
      - Download PDF Report
      - Copy Summary
      - Refresh Attendance
    """
    buttons = [
        [
            InlineKeyboardButton("📊 Get Attendance", callback_data="menu_attendance"),
            InlineKeyboardButton("📚 Subject Attendance", callback_data="menu_subjects")
        ],
        [
            InlineKeyboardButton("🎯 Bunk Advice & Target", callback_data="menu_bunk"),
            InlineKeyboardButton("👤 My Profile", callback_data="menu_profile")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
            InlineKeyboardButton("🚪 Logout", callback_data="menu_logout")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def get_attendance_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination buttons for attendance report."""
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"att_page_{current_page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"att_page_{current_page + 1}"))

    buttons = []
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton("📚 Subject Attendance", callback_data="menu_subjects"),
        InlineKeyboardButton("🎯 Bunk Advice", callback_data="menu_bunk")
    ])
    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")])
    return InlineKeyboardMarkup(buttons)


def get_subjects_keyboard(records: List[Dict[str, Any]], current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Builds interactive subject selector keyboard."""
    buttons = []

    # Two subject buttons per row for nice mobile readability
    row = []
    for idx, r in enumerate(records):
        sub_name = r.get("subject", f"Sub {idx + 1}")
        short_name = sub_name.split(" - ")[0][:14]
        row.append(InlineKeyboardButton(short_name, callback_data=f"sub_idx_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Navigation row
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"sub_page_{current_page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"sub_page_{current_page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")])
    return InlineKeyboardMarkup(buttons)


def get_bunk_targets_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting attendance target."""
    buttons = [
        [
            InlineKeyboardButton("75% Target", callback_data="bunk_tgt_75"),
            InlineKeyboardButton("80% Target", callback_data="bunk_tgt_80")
        ],
        [
            InlineKeyboardButton("85% Target", callback_data="bunk_tgt_85"),
            InlineKeyboardButton("90% Target", callback_data="bunk_tgt_90")
        ],
        [InlineKeyboardButton("✏️ Custom Target", callback_data="bunk_tgt_custom")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
    ]
    return InlineKeyboardMarkup(buttons)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Settings menu options."""
    buttons = [
        [
            InlineKeyboardButton("Target: 75%", callback_data="set_tgt_75"),
            InlineKeyboardButton("Target: 80%", callback_data="set_tgt_80"),
            InlineKeyboardButton("Target: 85%", callback_data="set_tgt_85")
        ],
        [InlineKeyboardButton("🚪 Disconnect Account (/logout)", callback_data="menu_logout")],
        [InlineKeyboardButton("🗑️ Delete All Stored Data", callback_data="menu_delete_data")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
    ]
    return InlineKeyboardMarkup(buttons)


# ==========================================
# COMMAND HANDLERS
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command. Displays welcome screen or main menu."""
    telegram_id = update.effective_user.id
    user = await get_user(telegram_id)

    # Handle deep link from group chats: /start login
    if context.args and context.args[0] == "login" and not user:
        await login_start(update, context)
        return

    if user:
        roll = user.get("roll_number", "")
        clean_name = clean_student_name(user.get("student_name"))
        greeting = f"{clean_name} ({roll})" if clean_name else roll
        welcome_text = (
            f"👋 <b>Welcome back, {html.escape(greeting)}!</b>\n\n"
            f"🎓 <b>Linked Roll Number:</b> <code>{html.escape(roll)}</code>\n"
            f"🎯 <b>Default Target:</b> {user.get('default_target', 75.0):g}%\n\n"
            f"Choose an option below:"
        )
        await update.effective_message.reply_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        text = (
            "👋 <b>Welcome to Attendix</b>\n"
            "Your MITS attendance, simplified.\n\n"
            "Attendix is built for <b>all MITS students</b> across all branches and academic years. "
            "Connect your MITS IMS account to instantly view verified attendance, "
            "track course attendance percentages, and calculate how many classes you can safely bunk.\n\n"
            "👨‍💻 <b>Developer:</b> Bhojanapu Deva Raj (@Devarajb049)"
        )
        logo_path = PROJECT_ROOT / "static" / "logo.png"
        if logo_path.exists():
            try:
                with open(logo_path, "rb") as photo_file:
                    await update.effective_message.reply_photo(
                        photo=photo_file,
                        caption=text,
                        reply_markup=get_welcome_keyboard(),
                        parse_mode=ParseMode.HTML
                    )
                    return
            except Exception as e:
                logger.debug(f"Could not send logo photo: {e}")

        await update.effective_message.reply_text(
            text,
            reply_markup=get_welcome_keyboard(),
            parse_mode=ParseMode.HTML
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /help command."""
    text = (
        "📖 <b>Attendix Telegram Bot — Available Commands</b>\n\n"
        "• /start — Welcome message and main menu\n"
        "• /login — Connect your MITS IMS account\n"
        "• /attendance — Fetch and display real attendance report\n"
        "• /subjects — View subject-wise attendance breakdown\n"
        "• /bunk — Calculate bunk advice and attendance targets\n"
        "• /profile — View linked student profile information\n"
        "• /logout — Disconnect your linked account\n"
        "• /delete_data — Permanently remove your stored bot data\n"
        "• /help — Display this help message\n\n"
        f"🌐 <i>Attendix Web Application:</i> <a href='{WEBSITE_URL}'>{WEBSITE_URL}</a>\n"
        f"👨‍💻 <b>Developed by:</b> Bhojanapu Deva Raj (@Devarajb049)"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /profile command."""
    telegram_id = update.effective_user.id
    user = await get_user(telegram_id)

    if not user:
        await update.effective_message.reply_text(
            "⚠️ No account linked yet. Please use /login to link your MITS IMS account.",
            reply_markup=get_welcome_keyboard()
        )
        return

    cache = await get_attendance_cache(telegram_id)
    sync_time = cache.get("synced_at") if cache else "Never"
    if sync_time != "Never":
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(sync_time)
            sync_time = dt.strftime("%d %b %Y, %I:%M %p UTC")
        except Exception:
            pass

    records_count = len(cache.get("records", [])) if cache else 0
    clean_name = clean_student_name(user.get("student_name")) or "Verified Student"

    text = (
        "👤 <b>VERIFIED STUDENT PROFILE</b>\n\n"
        f"• <b>Name:</b> {html.escape(clean_name)}\n"
        f"• <b>Roll Number:</b> <code>{html.escape(user['roll_number'])}</code>\n"
        f"• <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
        f"• <b>Default Target:</b> {user.get('default_target', 75.0):g}%\n"
        f"• <b>Active Courses:</b> {records_count}\n"
        f"• <b>Last Sync:</b> {sync_time}\n"
        f"• <b>Security:</b> Credentials Encrypted with AES-GCM / Fernet\n"
    )
    buttons = [
        [InlineKeyboardButton("📊 View Attendance", callback_data="menu_attendance")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
    ]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)


async def attendance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /attendance command."""
    telegram_id = update.effective_user.id
    user = await get_user(telegram_id)
    if not user:
        await update.effective_message.reply_text(
            "⚠️ You must link your account first. Use /login to connect.",
            reply_markup=get_welcome_keyboard()
        )
        return

    status_msg = await update.effective_message.reply_text("⏳ <i>Retrieving attendance from MITS IMS...</i>", parse_mode=ParseMode.HTML)
    result = await sync_attendance(telegram_id)

    if not result.get("success"):
        await status_msg.edit_text(
            f"❌ <b>Attendance Retrieval Failed</b>\n{html.escape(result.get('error', 'Unknown error'))}",
            parse_mode=ParseMode.HTML
        )
        return

    records = result.get("records", [])
    report_text, total_pages = format_attendance_report(
        student_name=result.get("student_name"),
        roll_number=result.get("roll_number", user["roll_number"]),
        records=records,
        synced_at=result.get("synced_at"),
        is_stale=result.get("is_stale", False),
        page=1
    )

    context.user_data["att_records"] = records
    context.user_data["att_name"] = result.get("student_name")
    context.user_data["att_roll"] = result.get("roll_number", user["roll_number"])
    context.user_data["att_synced_at"] = result.get("synced_at")
    context.user_data["att_is_stale"] = result.get("is_stale", False)

    await status_msg.edit_text(
        report_text,
        reply_markup=get_attendance_pagination_keyboard(1, total_pages),
        parse_mode=ParseMode.HTML
    )


async def subjects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /subjects command."""
    telegram_id = update.effective_user.id
    user = await get_user(telegram_id)
    if not user:
        await update.effective_message.reply_text(
            "⚠️ You must link your account first. Use /login to connect.",
            reply_markup=get_welcome_keyboard()
        )
        return

    status_msg = await update.effective_message.reply_text("⏳ <i>Loading subject metrics...</i>", parse_mode=ParseMode.HTML)
    result = await sync_attendance(telegram_id)

    if not result.get("success"):
        await status_msg.edit_text(
            f"❌ <b>Could not load subjects</b>\n{html.escape(result.get('error', 'Unknown error'))}",
            parse_mode=ParseMode.HTML
        )
        return

    records = result.get("records", [])
    context.user_data["subjects_records"] = records

    text, page_records, total_pages = format_subjects_page(records, page=1)
    await status_msg.edit_text(
        text,
        reply_markup=get_subjects_keyboard(page_records, 1, total_pages),
        parse_mode=ParseMode.HTML
    )


async def bunk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /bunk command."""
    telegram_id = update.effective_user.id
    user = await get_user(telegram_id)
    if not user:
        await update.effective_message.reply_text(
            "⚠️ You must link your account first. Use /login to connect.",
            reply_markup=get_welcome_keyboard()
        )
        return

    text = (
        "🎯 <b>ATTENDIX — BUNK ADVICE & TARGET</b>\n\n"
        "Select your desired minimum attendance target percentage to calculate "
        "how many classes you can safely miss, or how many consecutive classes you need to attend:"
    )
    await update.effective_message.reply_text(
        text,
        reply_markup=get_bunk_targets_keyboard(),
        parse_mode=ParseMode.HTML
    )


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /logout command."""
    buttons = [
        [
            InlineKeyboardButton("✅ Confirm Logout", callback_data="confirm_logout"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_home")
        ]
    ]
    await update.effective_message.reply_text(
        "🚪 <b>Confirm Logout</b>\n\n"
        "Are you sure you want to disconnect your MITS IMS account? "
        "Your stored credentials and cached data will be cleared.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


async def delete_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /delete_data command."""
    buttons = [
        [
            InlineKeyboardButton("🗑️ Yes, Delete Everything", callback_data="confirm_delete_data"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_home")
        ]
    ]
    await update.effective_message.reply_text(
        "🗑️ <b>Delete All Bot Data (GDPR / Privacy)</b>\n\n"
        "This will permanently erase your Telegram ID, stored IMS credentials, "
        "preferences, and all attendance cache records from the bot database.\n\n"
        "<b>This action cannot be undone.</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )


# ==========================================
# CONVERSATION HANDLER: LOGIN
# ==========================================

async def _execute_auth_and_respond(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    roll: str,
    password: str,
    status_msg
) -> int:
    """Authenticates candidate credentials and replies with personalized confirmation."""
    telegram_id = update.effective_user.id
    auth_result = await authenticate_and_link(
        telegram_id=telegram_id,
        roll_number=roll,
        password=password
    )

    if auth_result.get("success"):
        clean_name = clean_student_name(auth_result.get("student_name"))
        greeting = f"{clean_name} ({roll})" if clean_name else roll
        await status_msg.edit_text(
            f"🎉 <b>Authentication Successful!</b>\n\n"
            f"Welcome, <b>{html.escape(greeting)}</b>! Your MITS IMS account has been linked to your Telegram profile.\n\n"
            f"You can now check your verified attendance, course metrics, and bunk calculations anytime.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        err = auth_result.get("error", "Invalid credentials or portal unreachable.")
        await status_msg.edit_text(
            f"❌ <b>Authentication Failed</b>\n\n"
            f"Reason: <i>{html.escape(str(err))}</i>\n\n"
            f"Please verify your credentials and try again:\n"
            f"<code>/login ROLL_NUMBER PASSWORD</code>",
            reply_markup=get_welcome_keyboard(),
            parse_mode=ParseMode.HTML
        )

    context.user_data.pop("login_roll", None)
    return ConversationHandler.END


async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiates /login conversation or immediately authenticates if arguments are passed."""
    chat = update.effective_chat
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        bot_username = context.bot.username or "AttendixBot"
        buttons = [[InlineKeyboardButton("🔐 Open Bot to Login", url=f"https://t.me/{bot_username}?start=login")]]
        await update.effective_message.reply_text(
            "⚠️ <b>Security Notice:</b> Account login cannot be performed in public group chats to protect your password. "
            "Please click below to connect directly with the bot in a private message:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # Check if user sent args with /login (e.g., /login 25695A0512 Saranya@512)
    args = context.args or []
    if len(args) >= 2:
        roll = args[0].strip().upper()
        password = " ".join(args[1:]).strip()
        try:
            await update.effective_message.delete()
        except Exception:
            pass
        status_msg = await update.effective_chat.send_message(
            "⏳ <i>Authenticating with MITS IMS portal... Please wait.</i>",
            parse_mode=ParseMode.HTML
        )
        return await _execute_auth_and_respond(update, context, roll, password, status_msg)
    elif len(args) == 1:
        roll = args[0].strip().upper()
        context.user_data["login_roll"] = roll
        await update.effective_message.reply_text(
            f"✅ Roll Number set to: <code>{html.escape(roll)}</code>\n\n"
            "Now, please send your <b>MITS IMS Password</b>.\n\n"
            "🔒 <i>Security Guarantee: For your safety, the bot will delete your password message "
            "immediately upon receipt. Passwords are never logged or stored in plaintext.</i>",
            parse_mode=ParseMode.HTML
        )
        return LOGIN_PASSWORD

    await update.effective_message.reply_text(
        "🔐 <b>Connect MITS IMS Account</b>\n\n"
        "Please enter your <b>MITS IMS Roll Number</b>\n"
        "<i>(e.g., 25695A0512 or your college roll number)</i>:\n\n"
        "💡 <i>Tip: You can also login in a single message by typing:</i>\n"
        "<code>/login ROLL_NUMBER PASSWORD</code>",
        parse_mode=ParseMode.HTML
    )
    return LOGIN_ROLL


async def login_receive_roll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives candidate roll number, or both roll and password if pasted together."""
    raw_text = update.message.text.strip()
    parts = raw_text.split(maxsplit=1)

    # Detect if user entered both roll number and password in a single message
    if len(parts) == 2 and len(parts[0]) >= 4:
        roll = parts[0].strip().upper()
        password = parts[1].strip()
        try:
            await update.message.delete()
        except Exception:
            pass
        status_msg = await update.effective_chat.send_message(
            "⏳ <i>Authenticating with MITS IMS portal... Please wait.</i>",
            parse_mode=ParseMode.HTML
        )
        return await _execute_auth_and_respond(update, context, roll, password, status_msg)

    roll = raw_text.upper()
    if len(roll) < 4:
        await update.message.reply_text("⚠️ Invalid roll number format. Please enter a valid MITS roll number:")
        return LOGIN_ROLL

    context.user_data["login_roll"] = roll
    await update.message.reply_text(
        f"✅ Roll Number set to: <code>{html.escape(roll)}</code>\n\n"
        "Now, please send your <b>MITS IMS Password</b>.\n\n"
        "🔒 <i>Security Guarantee: For your safety, the bot will delete your password message "
        "immediately upon receipt. Passwords are never logged or stored in plaintext.</i>",
        parse_mode=ParseMode.HTML
    )
    return LOGIN_PASSWORD


async def login_receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives candidate password, deletes message immediately, and authenticates."""
    password = update.message.text.strip()
    roll = context.user_data.get("login_roll", "")

    # Attempt immediate password message deletion
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Could not auto-delete password message: {e}")

    status_msg = await update.effective_chat.send_message(
        "⏳ <i>Authenticating with MITS IMS portal... Please wait.</i>",
        parse_mode=ParseMode.HTML
    )

    return await _execute_auth_and_respond(update, context, roll, password, status_msg)


async def login_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels login conversation."""
    context.user_data.pop("login_roll", None)
    await update.effective_message.reply_text("❌ Login cancelled.", reply_markup=get_welcome_keyboard())
    return ConversationHandler.END


# ==========================================
# CONVERSATION HANDLER: CUSTOM TARGET
# ==========================================

async def custom_target_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts for custom target percentage."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎯 <b>Custom Attendance Target</b>\n\n"
        "Please type your desired attendance percentage as a number between 1 and 100\n"
        "<i>(e.g., 78 or 82.5):</i>",
        parse_mode=ParseMode.HTML
    )
    return CUSTOM_TARGET_INPUT


async def custom_target_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calculates bunk advice for custom target."""
    raw_text = update.message.text.strip().replace("%", "")
    try:
        target = float(raw_text)
        if target <= 0 or target > 100:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number between 1 and 100 (e.g., 78):")
        return CUSTOM_TARGET_INPUT

    telegram_id = update.effective_user.id
    status_msg = await update.message.reply_text("⏳ <i>Calculating bunk metrics...</i>", parse_mode=ParseMode.HTML)
    result = await sync_attendance(telegram_id)

    if not result.get("success"):
        await status_msg.edit_text(f"❌ Could not retrieve attendance: {result.get('error')}")
        return ConversationHandler.END

    records = result.get("records", [])
    report_text = format_bunk_report(records, target)
    buttons = [
        [InlineKeyboardButton("🎯 Choose Another Target", callback_data="menu_bunk")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
    ]
    await status_msg.edit_text(report_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    return ConversationHandler.END


# ==========================================
# CALLBACK QUERY ROUTER
# ==========================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Central router for inline keyboard callback actions."""
    query = update.callback_query
    data = query.data
    telegram_id = update.effective_user.id
    await query.answer()

    if data == "noop":
        return

    # 1. Main Navigation
    if data == "menu_home":
        user = await get_user(telegram_id)
        if user:
            roll = user.get("roll_number", "")
            clean_name = clean_student_name(user.get("student_name"))
            greeting = f"{clean_name} ({roll})" if clean_name else roll
            text = (
                f"👋 <b>Welcome back, {html.escape(greeting)}!</b>\n\n"
                f"🎓 <b>Linked Roll Number:</b> <code>{html.escape(roll)}</code>\n\n"
                f"Choose an option below:"
            )
            await query.edit_message_text(text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(
                "👋 <b>Welcome to Attendix</b>\n"
                "Your MITS attendance, simplified.\n\n"
                "👥 Available for all MITS students across all branches and academic years.",
                reply_markup=get_welcome_keyboard(),
                parse_mode=ParseMode.HTML
            )
        return

    # 2. About
    if data == "btn_about":
        text = (
            "ℹ️ <b>About Attendix</b>\n\n"
            "Attendix is an attendance management companion for all students at "
            "<b>Madanapalle Institute of Technology & Science (MITS)</b>.\n\n"
            "✨ <b>Features:</b>\n"
            "• Direct synchronization with MITS IMS portal\n"
            "• Course-by-course attendance analytics\n"
            "• Mathematical bunk advice based on MITS attendance thresholds\n"
            "• Encrypted credentials and absolute per-user isolation\n\n"
            f"🌐 <b>Website:</b> <a href='{WEBSITE_URL}'>{WEBSITE_URL}</a>\n"
            "👨‍💻 <b>Developed by:</b> Bhojanapu Deva Raj (@Devarajb049)"
        )
        buttons = [
            [InlineKeyboardButton("🔐 Login Now", callback_data="btn_login")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        return

    # 3. Login start trigger
    if data == "btn_login":
        await query.edit_message_text(
            "🔐 <b>Connect MITS IMS Account</b>\n\n"
            "To connect your account, please send:\n"
            "<code>/login ROLL_NUMBER PASSWORD</code>\n\n"
            "<i>(Or send /login to input your roll number and password step-by-step)</i>",
            parse_mode=ParseMode.HTML
        )
        return

    # 4. Get Attendance
    if data == "menu_attendance":
        user = await get_user(telegram_id)
        if not user:
            await query.edit_message_text(
                "⚠️ No linked account. Use /login to connect your MITS IMS account.",
                reply_markup=get_welcome_keyboard()
            )
            return

        await query.edit_message_text("⏳ <i>Retrieving attendance from MITS IMS...</i>", parse_mode=ParseMode.HTML)
        result = await sync_attendance(telegram_id)

        if not result.get("success"):
            await query.edit_message_text(
                f"❌ <b>Attendance Retrieval Failed</b>\n{html.escape(result.get('error', 'Unknown error'))}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]]),
                parse_mode=ParseMode.HTML
            )
            return

        records = result.get("records", [])
        report_text, total_pages = format_attendance_report(
            student_name=result.get("student_name"),
            roll_number=result.get("roll_number", user["roll_number"]),
            records=records,
            synced_at=result.get("synced_at"),
            is_stale=result.get("is_stale", False),
            page=1
        )
        context.user_data["att_records"] = records
        context.user_data["att_name"] = result.get("student_name")
        context.user_data["att_roll"] = result.get("roll_number", user["roll_number"])
        context.user_data["att_synced_at"] = result.get("synced_at")
        context.user_data["att_is_stale"] = result.get("is_stale", False)

        await query.edit_message_text(
            report_text,
            reply_markup=get_attendance_pagination_keyboard(1, total_pages),
            parse_mode=ParseMode.HTML
        )
        return

    # 5. Attendance Pagination
    if data.startswith("att_page_"):
        page_num = int(data.split("_")[-1])
        records = context.user_data.get("att_records") or []
        if not records:
            cached = await get_attendance_cache(telegram_id)
            records = cached.get("records", []) if cached else []

        user = await get_user(telegram_id)
        report_text, total_pages = format_attendance_report(
            student_name=context.user_data.get("att_name") or (user.get("student_name") if user else None),
            roll_number=context.user_data.get("att_roll") or (user.get("roll_number") if user else "N/A"),
            records=records,
            synced_at=context.user_data.get("att_synced_at"),
            is_stale=context.user_data.get("att_is_stale", False),
            page=page_num
        )
        await query.edit_message_text(
            report_text,
            reply_markup=get_attendance_pagination_keyboard(page_num, total_pages),
            parse_mode=ParseMode.HTML
        )
        return

    # 6. Subject Attendance
    if data == "menu_subjects":
        user = await get_user(telegram_id)
        if not user:
            await query.edit_message_text("⚠️ No linked account. Use /login to connect.", reply_markup=get_welcome_keyboard())
            return

        await query.edit_message_text("⏳ <i>Loading subject metrics...</i>", parse_mode=ParseMode.HTML)
        result = await sync_attendance(telegram_id)
        if not result.get("success"):
            await query.edit_message_text(
                f"❌ <b>Error:</b> {html.escape(result.get('error', 'Could not load subjects'))}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]]),
                parse_mode=ParseMode.HTML
            )
            return

        records = result.get("records", [])
        context.user_data["subjects_records"] = records
        text, page_records, total_pages = format_subjects_page(records, page=1)
        await query.edit_message_text(
            text,
            reply_markup=get_subjects_keyboard(page_records, 1, total_pages),
            parse_mode=ParseMode.HTML
        )
        return

    # 7. Subjects Pagination
    if data.startswith("sub_page_"):
        page_num = int(data.split("_")[-1])
        records = context.user_data.get("subjects_records") or []
        if not records:
            cached = await get_attendance_cache(telegram_id)
            records = cached.get("records", []) if cached else []

        text, page_records, total_pages = format_subjects_page(records, page=page_num)
        await query.edit_message_text(
            text,
            reply_markup=get_subjects_keyboard(page_records, page_num, total_pages),
            parse_mode=ParseMode.HTML
        )
        return

    # 8. Subject Detail View
    if data.startswith("sub_idx_"):
        sub_idx = int(data.split("_")[-1])
        records = context.user_data.get("subjects_records") or []
        if not records:
            cached = await get_attendance_cache(telegram_id)
            records = cached.get("records", []) if cached else []

        if 0 <= sub_idx < len(records):
            item = records[sub_idx]
            sub_name = item.get("subject", "Subject Details")
            try:
                att = int(item.get("attended", 0))
                tot = int(item.get("total", item.get("conducted", 0)))
                perc = float(item.get("percentage", 0.0))
            except (ValueError, TypeError):
                att, tot, perc = 0, 0, 0.0

            badge, label = classify_attendance(perc)
            advice_75 = calculate_bunk_advice(att, tot, 75.0)

            detail_text = (
                f"📚 <b>SUBJECT DETAILS</b>\n\n"
                f"• <b>Course:</b> {html.escape(sub_name)}\n"
                f"• <b>Attendance:</b> <b>{perc:.1f}%</b> ({badge} <i>{label}</i>)\n"
                f"• <b>Attended Classes:</b> <b>{att}</b>\n"
                f"• <b>Conducted Classes:</b> <b>{tot}</b>\n\n"
                f"🎯 <b>75% Target Status:</b>\n"
                f"{advice_75['message']}\n\n"
                f"{DISCLAIMER_TEXT}"
            )
            buttons = [
                [InlineKeyboardButton("⬅️ Back to Subjects", callback_data="menu_subjects")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
            ]
            await query.edit_message_text(detail_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    # 9. Bunk Advice Menu
    if data == "menu_bunk":
        text = (
            "🎯 <b>ATTENDIX — BUNK ADVICE & TARGET</b>\n\n"
            "Select your desired minimum attendance target percentage:"
        )
        await query.edit_message_text(text, reply_markup=get_bunk_targets_keyboard(), parse_mode=ParseMode.HTML)
        return

    # 10. Bunk Target Calculations
    if data.startswith("bunk_tgt_") and data != "bunk_tgt_custom":
        target = float(data.split("_")[-1])
        await query.edit_message_text("⏳ <i>Calculating bunk metrics...</i>", parse_mode=ParseMode.HTML)
        result = await sync_attendance(telegram_id)

        if not result.get("success"):
            await query.edit_message_text(
                f"❌ <b>Error:</b> {html.escape(result.get('error', 'Could not load attendance'))}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]]),
                parse_mode=ParseMode.HTML
            )
            return

        records = result.get("records", [])
        report_text = format_bunk_report(records, target)
        buttons = [
            [InlineKeyboardButton("🎯 Choose Another Target", callback_data="menu_bunk")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
        ]
        await query.edit_message_text(report_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    # 11. Profile
    if data == "menu_profile":
        user = await get_user(telegram_id)
        if not user:
            await query.edit_message_text("⚠️ No linked account. Use /login to connect.", reply_markup=get_welcome_keyboard())
            return

        cache = await get_attendance_cache(telegram_id)
        sync_time = cache.get("synced_at") if cache else "Never"
        if sync_time != "Never":
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(sync_time)
                sync_time = dt.strftime("%d %b %Y, %I:%M %p UTC")
            except Exception:
                pass

        records_count = len(cache.get("records", [])) if cache else 0
        text = (
            "👤 <b>VERIFIED STUDENT PROFILE</b>\n\n"
            f"• <b>Name:</b> {html.escape(user.get('student_name') or 'Verified Student')}\n"
            f"• <b>Roll Number:</b> <code>{html.escape(user['roll_number'])}</code>\n"
            f"• <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
            f"• <b>Default Target:</b> {user.get('default_target', 75.0):g}%\n"
            f"• <b>Active Courses:</b> {records_count}\n"
            f"• <b>Last Sync:</b> {sync_time}\n"
            f"• <b>Security:</b> Credentials Encrypted with AES-GCM / Fernet\n"
        )
        buttons = [
            [InlineKeyboardButton("📊 View Attendance", callback_data="menu_attendance")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_home")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    # 12. Settings
    if data == "menu_settings":
        user = await get_user(telegram_id)
        if not user:
            await query.edit_message_text("⚠️ No linked account. Use /login to connect.", reply_markup=get_welcome_keyboard())
            return

        text = (
            "⚙️ <b>BOT SETTINGS</b>\n\n"
            f"• Current Default Target: <b>{user.get('default_target', 75.0):g}%</b>\n"
            f"• Linked Account: <code>{html.escape(user['roll_number'])}</code>\n\n"
            "Choose a setting to modify:"
        )
        await query.edit_message_text(text, reply_markup=get_settings_keyboard(), parse_mode=ParseMode.HTML)
        return

    # 13. Set Default Target
    if data.startswith("set_tgt_"):
        target_val = float(data.split("_")[-1])
        await update_default_target(telegram_id, target_val)
        await query.edit_message_text(
            f"✅ Default target updated to <b>{target_val:g}%</b>.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Settings", callback_data="menu_settings")]]),
            parse_mode=ParseMode.HTML
        )
        return

    # 14. Logout Confirmations
    if data == "menu_logout":
        buttons = [
            [
                InlineKeyboardButton("✅ Confirm Logout", callback_data="confirm_logout"),
                InlineKeyboardButton("❌ Cancel", callback_data="menu_home")
            ]
        ]
        await query.edit_message_text(
            "🚪 <b>Confirm Logout</b>\n\n"
            "Are you sure you want to disconnect your MITS IMS account? "
            "Your stored credentials and cached data will be cleared.",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "confirm_logout":
        await delete_user(telegram_id)
        context.user_data.clear()
        await query.edit_message_text(
            "✅ <b>Successfully Logged Out</b>\n\n"
            "Your MITS IMS account has been disconnected and session credentials cleared.",
            reply_markup=get_welcome_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return

    # 15. Delete Data Confirmations
    if data == "menu_delete_data":
        buttons = [
            [
                InlineKeyboardButton("🗑️ Yes, Delete Everything", callback_data="confirm_delete_data"),
                InlineKeyboardButton("❌ Cancel", callback_data="menu_home")
            ]
        ]
        await query.edit_message_text(
            "🗑️ <b>Delete All Bot Data (GDPR / Privacy)</b>\n\n"
            "This will permanently erase your Telegram ID, stored IMS credentials, "
            "preferences, and all attendance cache records from the bot database.\n\n"
            "<b>This action cannot be undone.</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        return

    if data == "confirm_delete_data":
        await delete_user(telegram_id)
        context.user_data.clear()
        await query.edit_message_text(
            "✅ <b>All Data Deleted</b>\n\n"
            "All records associated with your Telegram account have been permanently erased.",
            reply_markup=get_welcome_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return


# ==========================================
# APPLICATION BUILDER
# ==========================================

def build_application(token: Optional[str] = None) -> Application:
    """Builds and configures the Telegram Application with all handlers."""
    bot_token = token or TELEGRAM_BOT_TOKEN
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN is not configured! Bot cannot connect without a valid token.")

    app = Application.builder().token(bot_token or "DUMMY_TOKEN").build()

    # 1. Login Conversation Handler
    login_conv = ConversationHandler(
        entry_points=[
            CommandHandler("login", login_start),
            CallbackQueryHandler(login_start, pattern="^btn_login$")
        ],
        states={
            LOGIN_ROLL: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_receive_roll)],
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_receive_password)],
        },
        fallbacks=[CommandHandler("cancel", login_cancel)],
        allow_reentry=True,
        per_message=False
    )

    # 2. Custom Target Conversation Handler
    custom_target_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(custom_target_start, pattern="^bunk_tgt_custom$")],
        states={
            CUSTOM_TARGET_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_target_receive)]
        },
        fallbacks=[CommandHandler("cancel", login_cancel)],
        allow_reentry=True,
        per_message=False
    )

    app.add_handler(login_conv)
    app.add_handler(custom_target_conv)

    # 3. Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("attendance", attendance_command))
    app.add_handler(CommandHandler("subjects", subjects_command))
    app.add_handler(CommandHandler("bunk", bunk_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(CommandHandler("delete_data", delete_data_command))

    # 4. Central Callback Query Handler
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    return app


async def main() -> None:
    """Entrypoint when running bot directly."""
    # 1. Start lightweight health server immediately for Render Free Web Service
    port = int(os.environ.get("PORT", 0))
    health_server = None
    if port:
        async def handle_ping(reader, writer):
            try:
                await reader.read(1024)
                response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 17\r\n\r\nAttendix Bot OK\r\n"
                writer.write(response)
                await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        try:
            health_server = await asyncio.start_server(handle_ping, "0.0.0.0", port)
            logger.info(f"Render web service health check active on port {port}")
        except Exception as e:
            logger.warning(f"Could not bind health server to port {port}: {e}")

    await init_db()
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set in environment or .env file.")
        print("Please configure your bot token in telegram_bot/.env. See telegram_bot/README.md for setup instructions.")
        sys.exit(1)

    app = build_application()
    logger.info("Starting Attendix Telegram Bot polling...")
    await app.initialize()
    await app.start()

    # Register bot commands for autocomplete suggestions & set official descriptions
    try:
        commands = [
            BotCommand("start", "Welcome screen and main menu"),
            BotCommand("login", "Connect MITS IMS account"),
            BotCommand("attendance", "View attendance report"),
            BotCommand("subjects", "Browse subject-wise attendance"),
            BotCommand("bunk", "Calculate bunk advice and targets"),
            BotCommand("profile", "Verified student profile"),
            BotCommand("logout", "Disconnect linked account"),
            BotCommand("delete_data", "Delete all stored bot data"),
            BotCommand("help", "Available commands and help"),
        ]
        await app.bot.set_my_commands(commands)
        await app.bot.set_my_description(
            "Attendix is an attendance management companion for students at Madanapalle Institute of Technology & Science (MITS).\n\n"
            "✨ Features:\n"
            "• Direct synchronization with MITS IMS portal\n"
            "• Course-by-course attendance analytics\n"
            "• Mathematical bunk advice based on MITS attendance thresholds\n"
            "• Encrypted credentials and absolute per-user isolation\n\n"
            "🌐 Website: https://attendix-dev.vercel.app/\n"
            "👨‍💻 Developed by Bhojanapu Deva Raj (@Devarajb049)"
        )
        await app.bot.set_my_short_description(
            "MITS IMS attendance companion & bunk calculator. Developed by Bhojanapu Deva Raj (@Devarajb049)."
        )
    except Exception as e:
        logger.warning(f"Notice setting bot commands/descriptions: {e}")

    await app.updater.start_polling(drop_pending_updates=True)

    # Run until interrupted
    import asyncio
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Stopping bot...")
        if health_server:
            health_server.close()
            await health_server.wait_closed()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    import asyncio
    import warnings
    from telegram.warnings import PTBUserWarning
    warnings.filterwarnings("ignore", category=PTBUserWarning)
    if sys.platform == "win32" and sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    asyncio.run(main())
