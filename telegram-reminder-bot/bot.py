from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from config import Config
from database import Database
from json_storage import JSONStorage
from ai_handler import AIHandler
from reminder_scheduler import ReminderScheduler
from repeat_handler import RepeatHandler
import json
import os
import datetime
import asyncio
import logging
import time
import re
from typing import Dict, Optional
from collections import defaultdict
from security_utils import create_secure_directory, secure_file_permissions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

config = Config()
config.validate()

create_secure_directory("data")
create_secure_directory(config.users_path)

bot = Bot(token=config.bot_token)
dp = Dispatcher()
db = Database(config.database_path)
storage = JSONStorage(config.users_path)
ai = AIHandler(config.openrouter_key)
scheduler = ReminderScheduler(db, storage, bot)
repeat_handler = RepeatHandler()
base = os.path.dirname(__file__)

if os.path.exists(config.database_path):
    secure_file_permissions(config.database_path)

user_request_times: Dict[int, list] = defaultdict(list)
user_message_count: Dict[int, int] = defaultdict(int)
waiting_for_city: Dict[int, bool] = defaultdict(bool)

def load_locales():
    l = {}
    for f in os.listdir(os.path.join(base, "localization")):
        with open(os.path.join(base, "localization", f)) as d:
            l[f.split(".")[0]] = json.load(d)
    return l

locales = load_locales()

def t(lang, key):
    return locales.get(lang, locales["en"]).get(key, key)

def rate_limit_check(user_id: int) -> bool:
    now = time.time()
    user_times = user_request_times[user_id]
    user_times[:] = [t for t in user_times if now - t < 60]

    if len(user_times) >= config.max_requests_per_minute:
        logger.warning(f"Rate limit exceeded for user {user_id}: {len(user_times)} requests in last minute")
        return False

    user_times.append(now)
    return True

async def handle_rate_limit(message_or_callback):
    try:
        if hasattr(message_or_callback, 'from_user'):
            user_id = message_or_callback.from_user.id
        else:
            return
        
        lang = storage.load(user_id)["settings"]["language"]
        rate_limit_msg = t(lang, "rate_limit_exceeded")
        
        if hasattr(message_or_callback, 'answer'):
            await message_or_callback.answer(rate_limit_msg)
        elif hasattr(message_or_callback, 'message'):
            await message_or_callback.answer(rate_limit_msg, show_alert=True)
    except Exception as e:
        logger.error(f"Error in handle_rate_limit: {e}")

def validate_user_input(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    if len(text.strip()) == 0:
        return False
    if len(text) > 1000:
        return False
    return True

def sanitize_input(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.strip()[:1000]

def get_button_action(message_text, user_lang):
    button_mappings = {
        "btn_list": "list",
        "btn_delete": "delete",
        "btn_edit": "edit",
        "btn_new": "new",
        "btn_settings": "settings",
        "btn_stats": "stats",
        "btn_remove_menu": "remove_menu"
    }

    for key, action in button_mappings.items():
        if message_text == t(user_lang, key):
            return action
    return None

class UserSession:
    def __init__(self):
        self.pending: Dict[int, dict] = {}
        self.pending_cleanup_time: Dict[int, datetime.datetime] = {}
        self.editing_reminders: Dict[int, int] = {}

    def cleanup_expired(self):
        now = datetime.datetime.now()
        expired_pending = [uid for uid, exp_time in self.pending_cleanup_time.items() if exp_time < now]
        for uid in expired_pending:
            self.pending.pop(uid, None)
            self.pending_cleanup_time.pop(uid, None)

        expired_editing = []
        for uid in list(self.editing_reminders.keys()):
            if uid not in self.pending and uid not in self.pending_cleanup_time:
                expired_editing.append(uid)

        for uid in expired_editing[-50:]:
            self.editing_reminders.pop(uid, None)

session = UserSession()

@dp.message(Command("start"))
async def start_message(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        data = storage.load(user_id)
        is_new_user = not data["settings"].get("setup_complete", False)
        if is_new_user:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="setup_lang_fa")],
                [InlineKeyboardButton(text="🇺🇸 English", callback_data="setup_lang_en")],
                [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="setup_lang_ar")],
                [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setup_lang_ru")]
            ])
            await message.answer(
                "🎉 Welcome to Smart Reminder Bot!\n"
                "🌍 Please choose your language:\n\n"
                "به ربات یادآوری هوشمند خوش آمدید!\n"
                "لطفاً زبان خود را انتخاب کنید:\n\n"
                "مرحباً بك في بوت التذكير الذكي!\n"
                "يرجى اختيار لغتك:\n\n"
                "Добро пожаловать в умного бота-напоминалку!\n"
                "Пожалуйста, выберите ваш язык:",
                reply_markup=kb
            )
        else:
            lang = data["settings"]["language"]
            await message.answer(t(lang, "start"))

            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text=t(lang, "btn_list"))],
                [KeyboardButton(text=t(lang, "btn_delete")), KeyboardButton(text=t(lang, "btn_edit"))],
                [KeyboardButton(text=t(lang, "btn_new"))],
                [KeyboardButton(text=t(lang, "btn_settings")), KeyboardButton(text=t(lang, "btn_stats"))],
                [KeyboardButton(text=t(lang, "btn_remove_menu"))]
            ], resize_keyboard=True)

            await message.answer(t(lang, "menu"), reply_markup=kb)

        storage.save(user_id, data)
    except Exception as e:
        logger.error(f"Error in start_message for user {user_id}: {e}")
        return

@dp.message(Command("list"))
async def list_reminders(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        reminders = db.list(user_id)
        if not reminders:
            await message.answer(t(lang, "no_reminders"))
        else:
            lines = []
            for rid, cat, content, time, tz, repeat, status in reminders:
                emoji = {"birthday": "🎂", "medicine": "💊", "installment": "💳",
                        "work": "💼", "appointment": "📅"}.get(cat, "⏰")
                safe_content = sanitize_input(str(content))[:50]
                lines.append(f"{emoji} {rid}: {safe_content}\n📅 {time} ({repeat})")
            await message.answer("\n\n".join(lines))
    except Exception as e:
        logger.error(f"Error in list_reminders for user {user_id}: {e}")

async def show_reminders_list(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        reminders = db.list(user_id)
    except Exception as e:
        logger.error(f"Error in show_reminders_list for user {user_id}: {e}")
        return

    if not reminders:
        await message.answer(t(lang, "no_reminders"))
        return

    lines = [t(lang, "reminders_list_title")]
    for rid, cat, content, time, tz, repeat, status in reminders:
        emoji = {"birthday": "🎂", "medicine": "💊", "installment": "💳", "work": "💼", "appointment": "📅", "exercise": "🏃‍♂️", "prayer": "🕌", "shopping": "🛒", "call": "📞", "study": "📚", "bill": "💰", "general": "⏰"}.get(cat, "⏰")

        repeat_pattern = repeat_handler.from_json(repeat)
        repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)

        lines.append(t(lang, "reminder_id").format(id=rid))
        lines.append(f"{emoji} {content}")
        lines.append(t(lang, "reminder_time").format(time=time))
        lines.append(t(lang, "reminder_repeat").format(repeat=repeat_text))
        lines.append("─" * 25)

    await message.answer("\n".join(lines))

@dp.message(Command("delete"))
async def delete_reminder(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        parts = message.text.split()
        if len(parts) > 1:
            try:
                reminder_id = int(parts[1])
                if reminder_id > 0:
                    user_reminders = db.list(user_id)
                    reminder_exists = any(r[0] == reminder_id for r in user_reminders)
                    if reminder_exists:
                        db.update_status(reminder_id, "cancelled")
                        await message.answer(t(lang, "deleted"))
                    else:
                        await message.answer(t(lang, "invalid_id"))
                else:
                    await message.answer(t(lang, "invalid_id"))
            except ValueError:
                await message.answer(t(lang, "invalid_id"))
        else:
            await message.answer(t(lang, "enter_reminder_id"))
    except Exception as e:
        logger.error(f"Error in delete_reminder for user {user_id}: {e}")

async def show_delete_reminders(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        reminders = db.list(user_id)
    except Exception as e:
        logger.error(f"Error in show_delete_reminders for user {user_id}: {e}")
        return

    if not reminders:
        await message.answer(t(lang, "no_reminders"))
        return

    buttons = []
    for rid, cat, content, time, tz, repeat, status in reminders:
        emoji = {"birthday": "🎂", "medicine": "💊", "installment": "💳", "work": "💼", "appointment": "📅", "exercise": "🏃‍♂️", "prayer": "🕌", "shopping": "🛒", "call": "📞", "study": "📚", "bill": "💰", "general": "⏰"}.get(cat, "⏰")
        repeat_pattern = repeat_handler.from_json(repeat)
        repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)
        display_content = content[:20] + "..." if len(content) > 20 else content
        button_text = f"🗑 {emoji} {display_content}\n📅 {time} | 🔄 {repeat_text}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"delete_confirm_{rid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(t(lang, "delete_which"), reply_markup=kb)

async def show_edit_reminders(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        reminders = db.list(user_id)
    except Exception as e:
        logger.error(f"Error in show_edit_reminders for user {user_id}: {e}")
        return

    if not reminders:
        await message.answer(t(lang, "no_reminders"))
        return

    buttons = []
    for rid, cat, content, time, tz, repeat, status in reminders:
        emoji = {"birthday": "🎂", "medicine": "💊", "installment": "💳", "work": "💼", "appointment": "📅", "exercise": "🏃‍♂️", "prayer": "🕌", "shopping": "🛒", "call": "📞", "study": "📚", "bill": "💰", "general": "⏰"}.get(cat, "⏰")
        repeat_pattern = repeat_handler.from_json(repeat)
        repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)
        display_content = content[:20] + "..." if len(content) > 20 else content
        button_text = f"✏️ {emoji} {display_content}\n📅 {time} | 🔄 {repeat_text}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"edit_select_{rid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(t(lang, "edit_which"), reply_markup=kb)

@dp.message(Command("menu"))
async def show_menu(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
    except Exception as e:
        logger.error(f"Error in show_menu for user {user_id}: {e}")
        return

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t(lang, "btn_list"))],
        [KeyboardButton(text=t(lang, "btn_delete")), KeyboardButton(text=t(lang, "btn_edit"))],
        [KeyboardButton(text=t(lang, "btn_new"))],
        [KeyboardButton(text=t(lang, "btn_settings")), KeyboardButton(text=t(lang, "btn_stats"))],
        [KeyboardButton(text=t(lang, "btn_remove_menu"))]
    ], resize_keyboard=True)

    await message.answer(t(lang, "menu"), reply_markup=kb)

@dp.message(F.text)
async def handle_menu_buttons(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        action = get_button_action(message.text, lang)

        if action is None:
            await handle_message(message)
            return
    except Exception as e:
        logger.error(f"Error in handle_menu_buttons for user {user_id}: {e}")
        return

    if action == "list":
        await show_reminders_list(message)
    elif action == "delete":
        await show_delete_reminders(message)
    elif action == "edit":
        await show_edit_reminders(message)
    elif action == "new":
        await message.answer(t(lang, "new_reminder_text"))
    elif action == "settings":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "change_language"), callback_data="change_lang")],
            [InlineKeyboardButton(text=t(lang, "change_timezone"), callback_data="change_tz")]
        ])
        await message.answer(t(lang, "settings"), reply_markup=kb)
    elif action == "stats":
        active = len(db.list(user_id, "active"))
        completed = len(db.list(user_id, "completed"))
        await message.answer(t(lang, "stats").format(active=active, completed=completed))
    elif action == "remove_menu":
        await message.answer(t(lang, "menu_removed"), reply_markup=ReplyKeyboardRemove())

async def handle_message(message: Message):
    user_id = message.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(message)
        return

    if not validate_user_input(message.text):
        return

    try:
        data = storage.load(user_id)
        lang = data["settings"]["language"]

        if waiting_for_city.get(user_id, False):
            await handle_city_input(message)
            return

        user_reminders = db.list(user_id)
        if len(user_reminders) >= config.max_reminders_per_user:
            await message.answer(t(lang, "max_reminders_reached").format(max=config.max_reminders_per_user))
            return
    except Exception as e:
        logger.error(f"Error in handle_message for user {user_id}: {e}")
        return

    if user_id in session.editing_reminders:
        reminder_id = session.editing_reminders[user_id]
        try:
            user_reminders = db.list(user_id)
            current_reminder = None
            for reminder in user_reminders:
                if reminder[0] == reminder_id:
                    current_reminder = reminder
                    break

            if not current_reminder:
                await message.answer(t(lang, "invalid_id"))
                del session.editing_reminders[user_id]
                return

            _, category, content, time_str, timezone_val, repeat, _ = current_reminder
            current_data = {
                "content": content,
                "time": time_str,
                "category": category,
                "repeat": repeat
            }
            logger.info(f"Analyzing edit request for user {user_id}: {message.text}")
            edit_result = await ai.parse_edit(current_data, message.text, data["settings"]["timezone"])
            if not edit_result:
                await message.answer(t(lang, "edit_error"))
                del session.editing_reminders[user_id]
                return

            logger.info(f"Edit analysis result for user {user_id}: {edit_result}")
            db.update_reminder(
                reminder_id,
                edit_result.get("category", category),
                edit_result["content"],
                edit_result["time"],
                edit_result.get("timezone", data["settings"]["timezone"]),
                edit_result.get("repeat", repeat)
            )

            del session.editing_reminders[user_id]

            await message.answer(
                t(lang, "edit_success_details").format(
                    id=reminder_id,
                    content=edit_result["content"],
                    time=edit_result["time"],
                    repeat=edit_result.get("repeat", repeat)
                )
            )
            return

        except Exception as e:
            logger.error(f"Error during edit for user {user_id}: {e}")
            await message.answer(t(lang, "edit_error"))
            return

    try:
        logger.info(f"Parsing text for user {user_id}: {message.text}")
        parsed = await ai.parse(
            lang, data["settings"]["timezone"], message.text
        )
        logger.info(f"Parse result for user {user_id}: {parsed}")
    except Exception as e:
        logger.error(f"AI parsing error for user {user_id}: {e}")
        await message.answer(t(lang, "ai_error"))
        return
    session.pending[user_id] = parsed
    session.pending_cleanup_time[user_id] = datetime.datetime.now() + datetime.timedelta(minutes=10)

    if "reminders" in parsed and isinstance(parsed["reminders"], list):
        summary_lines = [t(lang, "multiple_reminders_summary").format(count=len(parsed["reminders"]))]
        for i, reminder in enumerate(parsed["reminders"], 1):
            category_text = t(lang, f"category_{reminder['category']}")
            if category_text == f"category_{reminder['category']}":
                category_text = reminder['category']

            repeat_pattern = repeat_handler.from_json(reminder.get('repeat', '{"type": "none"}'))
            repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)

            summary_lines.append(f"{i}. {reminder['content']} @ {reminder['time']} ({category_text}) - {repeat_text}")
        summary = "\n".join(summary_lines)
    else:
        category_text = t(lang, f"category_{parsed['category']}")
        if category_text == f"category_{parsed['category']}":
            category_text = parsed['category']

        repeat_pattern = repeat_handler.from_json(parsed.get('repeat', '{"type": "none"}'))
        repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)

        summary = f"{t(lang, 'summary')}: {parsed['content']} @ {parsed['time']} ({category_text}) - {repeat_text}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "confirm"), callback_data="confirm")],
        [InlineKeyboardButton(text=t(lang, "cancel"), callback_data="cancel")]
    ])
    await message.answer(summary, reply_markup=kb)

@dp.callback_query(F.data.in_(["confirm", "cancel"]))
async def process_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        data = storage.load(user_id)
        lang = data["settings"]["language"]
    except Exception as e:
        logger.error(f"Error in process_callback for user {user_id}: {e}")
        await callback_query.answer()
        return
    if callback_query.data == "confirm" and user_id in session.pending:
        pending_data = session.pending.pop(user_id)

        if "reminders" in pending_data and isinstance(pending_data["reminders"], list):
            created_count = 0
            for reminder_data in pending_data["reminders"]:
                db.add(
                    user_id,
                    reminder_data["category"],
                    reminder_data["content"],
                    reminder_data["time"],
                    reminder_data.get("timezone", data["settings"]["timezone"]),
                    reminder_data.get("repeat", "none"),
                )
                storage.add_reminder(user_id, reminder_data)
                created_count += 1

            await callback_query.message.edit_reply_markup(reply_markup=None)
            await callback_query.message.answer(t(lang, "multiple_reminders_saved").format(count=created_count))
        else:
            db.add(
                user_id,
                pending_data["category"],
                pending_data["content"],
                pending_data["time"],
                pending_data.get("timezone", data["settings"]["timezone"]),
                pending_data.get("repeat", "none"),
            )
            storage.add_reminder(user_id, pending_data)
            await callback_query.message.edit_reply_markup(reply_markup=None)
            await callback_query.message.answer(t(lang, "saved"))
    else:
        session.pending.pop(user_id, None)
        session.pending_cleanup_time.pop(user_id, None)
        await callback_query.message.edit_reply_markup(reply_markup=None)
        await callback_query.message.answer(t(lang, "ask_more"))

@dp.callback_query(F.data.startswith("setup_lang_"))
async def handle_setup_language_selection(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        lang_code = callback_query.data.split("_")[2]  # setup_lang_fa -> fa
        if lang_code in locales:
            storage.update_setting(user_id, "language", lang_code)

            await callback_query.message.edit_text(
                f"✅ {t(lang_code, 'language_selected')}\n\n"
                f"🌍 {t(lang_code, 'setup_timezone_prompt')}"
            )

            waiting_for_city[user_id] = True

        else:
            await callback_query.answer()
            return
    except Exception as e:
        logger.error(f"Error in handle_setup_language_selection for user {user_id}: {e}")
        await callback_query.answer()
        return

    await callback_query.answer()

@dp.callback_query(F.data.startswith("lang_"))
async def handle_language_selection(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        lang_code = callback_query.data.split("_")[1]
        if lang_code in locales:
            storage.update_setting(user_id, "language", lang_code)
        else:
            await callback_query.answer()
            return
    except Exception as e:
        logger.error(f"Error in handle_language_selection for user {user_id}: {e}")
        await callback_query.answer()
        return

    await callback_query.message.edit_text(t(lang_code, "saved"))
    await callback_query.answer()

    await callback_query.message.answer(t(lang_code, "start"))

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t(lang_code, "btn_list"))],
        [KeyboardButton(text=t(lang_code, "btn_delete")), KeyboardButton(text=t(lang_code, "btn_edit"))],
        [KeyboardButton(text=t(lang_code, "btn_new"))],
        [KeyboardButton(text=t(lang_code, "btn_settings")), KeyboardButton(text=t(lang_code, "btn_stats"))],
        [KeyboardButton(text=t(lang_code, "btn_remove_menu"))]
    ], resize_keyboard=True)

    await callback_query.message.answer(t(lang_code, "menu"), reply_markup=kb)

@dp.callback_query(F.data == "change_lang")
async def handle_change_language(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang_fa")],
            [InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")],
            [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
        ])

        lang = storage.load(user_id)["settings"]["language"]
        await callback_query.message.edit_text(t(lang, "choose_language"), reply_markup=kb)
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in handle_change_language for user {user_id}: {e}")
        await callback_query.answer()

@dp.callback_query(F.data == "change_tz")
async def handle_change_timezone(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        waiting_for_city[user_id] = True

        await callback_query.message.edit_text(t(lang, "enter_city_name"))
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in handle_change_timezone for user {user_id}: {e}")
        await callback_query.answer()

async def handle_city_input(message: Message):
    user_id = message.from_user.id

    try:
        lang = storage.load(user_id)["settings"]["language"]
        city_name = sanitize_input(message.text)

        if not city_name or len(city_name) > 50:
            await message.answer(t(lang, "timezone_error"))
            waiting_for_city[user_id] = False
            return

        timezone_info = await get_timezone_from_city(city_name, lang)

        if not timezone_info:
            await message.answer(t(lang, "timezone_error"))
            waiting_for_city[user_id] = False
            return

        city, timezone = timezone_info

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "yes"), callback_data=f"confirm_tz_{timezone}")],
            [InlineKeyboardButton(text=t(lang, "no"), callback_data="cancel_tz")]
        ])

        user_data = storage.load(user_id)
        if user_id in waiting_for_city and not user_data["settings"].get("setup_complete", False):
            confirmation_text = t(lang, "setup_timezone_confirmation").format(city=city, timezone=timezone)
        else:
            confirmation_text = t(lang, "timezone_confirmation").format(city=city, timezone=timezone)

        await message.answer(confirmation_text, reply_markup=kb)

        waiting_for_city[user_id] = False

    except Exception as e:
        logger.error(f"Error in handle_city_input for user {user_id}: {e}")
        waiting_for_city[user_id] = False
        await message.answer(t(lang, "timezone_error"))

async def get_timezone_from_city(city_name: str, user_lang: str):
    try:
        prompt = f"""You are a global timezone expert. Detect timezone for any city worldwide.

City: "{city_name}"
User language: {user_lang}

TASK: Find the timezone offset for this city. Consider:
- Major cities and small towns
- Alternative spellings and local names
- Country context if city name is ambiguous
- Current standard time (not daylight saving)

OUTPUT: Return ONLY this JSON format:
{{"city": "CityName, Country", "timezone": "+XX:XX"}}

TIMEZONE RULES:
- Iran (all cities): +03:30
- India (all cities): +05:30  
- China (all cities): +08:00
- Russia: varies by region
- USA: varies by state
- Europe: varies by country

If city not found or ambiguous, return: null

Examples:
- تهران/Tehran → {{"city": "Tehran, Iran", "timezone": "+03:30"}}
- شیراز/Shiraz → {{"city": "Shiraz, Iran", "timezone": "+03:30"}}
- رشت/Rasht → {{"city": "Rasht, Iran", "timezone": "+03:30"}}
- New York → {{"city": "New York, USA", "timezone": "-05:00"}}
- London → {{"city": "London, UK", "timezone": "+00:00"}}
- Tokyo → {{"city": "Tokyo, Japan", "timezone": "+09:00"}}
- Mumbai → {{"city": "Mumbai, India", "timezone": "+05:30"}}"""
        
        result = await ai.parse_timezone(prompt)
        return result
        
    except Exception as e:
        logger.error(f"Error getting timezone for {city_name}: {e}")
        return None

@dp.callback_query(F.data.startswith("confirm_tz_"))
async def handle_timezone_confirmation(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        timezone = callback_query.data.replace("confirm_tz_", "")
        data = storage.load(user_id)
        lang = data["settings"]["language"]

        storage.update_setting(user_id, "timezone", timezone)

        is_setup = not data["settings"].get("setup_complete", False)

        if is_setup:
            storage.update_setting(user_id, "setup_complete", True)

            await callback_query.message.edit_text(t(lang, "setup_complete"))

            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text=t(lang, "btn_list"))],
                [KeyboardButton(text=t(lang, "btn_delete")), KeyboardButton(text=t(lang, "btn_edit"))],
                [KeyboardButton(text=t(lang, "btn_new"))],
                [KeyboardButton(text=t(lang, "btn_settings")), KeyboardButton(text=t(lang, "btn_stats"))],
                [KeyboardButton(text=t(lang, "btn_remove_menu"))]
            ], resize_keyboard=True)

            await callback_query.message.answer(t(lang, "menu"), reply_markup=kb)
        else:
            success_text = t(lang, "timezone_changed").format(timezone=timezone)
            await callback_query.message.edit_text(success_text)

        await callback_query.answer()

    except Exception as e:
        logger.error(f"Error in handle_timezone_confirmation for user {user_id}: {e}")
        await callback_query.answer()

@dp.callback_query(F.data == "cancel_tz")
async def handle_timezone_cancel(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    try:
        lang = storage.load(user_id)["settings"]["language"]
        await callback_query.message.edit_text(t(lang, "ask_more"))
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error in handle_timezone_cancel for user {user_id}: {e}")
        await callback_query.answer()

@dp.callback_query(F.data.startswith(("stop_", "paid_", "taken_")))
async def handle_reminder_actions(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        action, reminder_id = callback_query.data.split("_", 1)
        reminder_id = int(reminder_id)
    except (ValueError, Exception) as e:
        logger.error(f"Error in handle_reminder_actions for user {user_id}: {e}")
        await callback_query.answer()
        return

    try:
        if action == "stop":
            db.update_status(reminder_id, "cancelled")
            await callback_query.message.edit_text(t(lang, "reminder_stopped"))

        elif action == "paid":
            db.update_status(reminder_id, "completed")
            await callback_query.message.edit_text(t(lang, "payment_recorded"))

        elif action == "taken":
            await callback_query.message.edit_text(t(lang, "medicine_taken"))

        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error updating reminder {reminder_id} for user {user_id}: {e}")
        await callback_query.answer()

@dp.callback_query(F.data.startswith("delete_confirm_"))
async def handle_delete_confirmation(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        reminder_id = int(callback_query.data.split("_")[2])

        user_reminders = db.list(user_id)
        reminder_exists = any(r[0] == reminder_id for r in user_reminders)
        if not reminder_exists:
            await callback_query.answer(t(lang, "invalid_id"))
            return
    except (ValueError, Exception) as e:
        logger.error(f"Error in handle_delete_confirmation for user {user_id}: {e}")
        await callback_query.answer()
        return

    db.update_status(reminder_id, "cancelled")

    await callback_query.message.edit_text(t(lang, "reminder_deleted").format(id=reminder_id))
    await callback_query.answer(t(lang, "delete_confirmed"))

@dp.callback_query(F.data.startswith("edit_select_"))
async def handle_edit_selection(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if not rate_limit_check(user_id):
        await handle_rate_limit(callback_query)
        return

    try:
        lang = storage.load(user_id)["settings"]["language"]
        reminder_id = int(callback_query.data.split("_")[2])

        user_reminders = db.list(user_id)
        reminder_exists = any(r[0] == reminder_id for r in user_reminders)
        if not reminder_exists:
            await callback_query.answer(t(lang, "invalid_id"))
            return
    except (ValueError, Exception) as e:
        logger.error(f"Error in handle_edit_selection for user {user_id}: {e}")
        await callback_query.answer()
        return

    session.editing_reminders[user_id] = reminder_id

    await callback_query.message.edit_text(
        t(lang, "reminder_selected").format(id=reminder_id)
    )
    await callback_query.answer()

async def cleanup_memory():
    while True:
        try:
            await asyncio.sleep(300)
            session.cleanup_expired()

            now = time.time()
            for user_id in list(user_request_times.keys()):
                user_request_times[user_id] = [t for t in user_request_times[user_id] if now - t < 3600]
                if not user_request_times[user_id]:
                    del user_request_times[user_id]

            expired_waiting = []
            for user_id in list(waiting_for_city.keys()):
                if waiting_for_city[user_id] and user_id not in user_request_times:
                    expired_waiting.append(user_id)

            for user_id in expired_waiting:
                waiting_for_city.pop(user_id, None)

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    try:
        logger.info("Starting Telegram Reminder Bot")
        scheduler.start()
        asyncio.create_task(cleanup_memory())
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info("Shutting down bot")
        scheduler.stop()
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
