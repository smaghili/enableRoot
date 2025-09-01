from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from config import Config
from database import Database
from json_storage import JSONStorage
from ai_handler import AIHandler
from reminder_scheduler import ReminderScheduler
from repeat_handler import RepeatHandler
from message_handlers import ReminderMessageHandler
from callback_handlers import ReminderCallbackHandler
from admin_handler import AdminHandler
from config import Config
from date_converter import DateConverter
import json
import os
import datetime
import asyncio
import logging
import time
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

def load_locales():
    l = {}
    for f in os.listdir(os.path.join(base, "localization")):
        with open(os.path.join(base, "localization", f)) as d:
            l[f.split(".")[0]] = json.load(d)
    return l

locales = load_locales()

class UserSession:
    def __init__(self):
        self.pending = {}
        self.pending_cleanup_time = {}
        self.editing_reminders = {}

    def cleanup_expired(self):
        now = datetime.datetime.now()
        expired_pending = []
        for uid, cleanup_time in self.pending_cleanup_time.items():
            if now > cleanup_time:
                expired_pending.append(uid)
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

message_handler = ReminderMessageHandler(storage, db, ai, repeat_handler, locales, session, config)
callback_handler = ReminderCallbackHandler(storage, db, ai, repeat_handler, locales, message_handler, session, config)
admin_handler = AdminHandler(storage, db, bot, config, locales)

@dp.message(Command("start"))
async def start_message(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
        return
    
    if config.forced_join.get("enabled", False):
        if not await admin_handler.check_user_membership(user_id):
            data = storage.load(user_id)
            lang = data["settings"]["language"]
            kb = await admin_handler.get_join_keyboard(lang)
            await message.answer(message_handler.t(lang, "forced_join_required"), reply_markup=kb)
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
            await message.answer(message_handler.t(lang, "start"))
            
            keyboard = [
                [KeyboardButton(text=message_handler.t(lang, "btn_new"))],
                [KeyboardButton(text=message_handler.t(lang, "btn_delete")), KeyboardButton(text=message_handler.t(lang, "btn_edit"))],
                [KeyboardButton(text=message_handler.t(lang, "btn_list"))],
                [KeyboardButton(text=message_handler.t(lang, "btn_settings")), KeyboardButton(text=message_handler.t(lang, "btn_stats"))]
            ]
            
            if admin_handler.is_admin(user_id):
                keyboard.append([KeyboardButton(text=message_handler.t(lang, "btn_admin"))])
            
            kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            await message.answer(message_handler.t(lang, "menu"), reply_markup=kb)
        storage.save(user_id, data)
    except Exception as e:
        logger.error(f"Error in start_message for user {user_id}: {e}")
        return

@dp.message(Command("list"))
async def list_reminders(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
        return
    try:
        data = storage.load(user_id)
        lang = data["settings"]["language"]
        calendar_type = data["settings"].get("calendar", "miladi")
        reminders = db.list(user_id)
        if not reminders:
            await message.answer(message_handler.t(lang, "no_reminders"))
        else:
            lines = []
            for rid, cat, content, time, tz, repeat, status in reminders:
                emoji = config.emoji_mapping.get(cat, "⏰")
                safe_content = message_handler.sanitize_input(str(content))[:50]
                display_time = DateConverter.convert_to_user_calendar(time, calendar_type)
                lines.append(f"{rid}. {emoji} {safe_content} @ {display_time}")
            await message.answer("\n".join(lines))
    except Exception as e:
        logger.error(f"Error in list_reminders for user {user_id}: {e}")

async def show_reminders_list(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
        return
    try:
        data = storage.load(user_id)
        lang = data["settings"]["language"]
        calendar_type = data["settings"].get("calendar", "miladi")
        reminders = db.list(user_id)
    except Exception as e:
        logger.error(f"Error in show_reminders_list for user {user_id}: {e}")
        return
    if not reminders:
        await message.answer(message_handler.t(lang, "no_reminders"))
        return
    lines = [message_handler.t(lang, "reminders_list_title")]
    for rid, cat, content, time, tz, repeat, status in reminders:
        emoji = config.emoji_mapping.get(cat, "⏰")
        repeat_pattern = repeat_handler.from_json(repeat)
        repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)
        display_time = DateConverter.convert_to_user_calendar(time, calendar_type)
        lines.append(message_handler.t(lang, "reminder_id").format(id=rid))
        lines.append(f"{emoji} {content}")
        lines.append(message_handler.t(lang, "reminder_time").format(time=display_time))
        lines.append(message_handler.t(lang, "reminder_repeat").format(repeat=repeat_text))
        lines.append("─" * 25)
    await message.answer("\n".join(lines))

@dp.message(Command("delete"))
async def delete_reminder(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
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
                        await message.answer(message_handler.t(lang, "reminder_deleted").format(id=reminder_id))
                    else:
                        await message.answer(message_handler.t(lang, "invalid_id"))
                else:
                    await message.answer(message_handler.t(lang, "invalid_id"))
            except ValueError:
                await message.answer(message_handler.t(lang, "invalid_id"))
        else:
            await message.answer(message_handler.t(lang, "enter_reminder_id"))
    except Exception as e:
        logger.error(f"Error in delete_reminder for user {user_id}: {e}")

async def show_delete_reminders(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
        return
    try:
        data = storage.load(user_id)
        lang = data["settings"]["language"]
        calendar_type = data["settings"].get("calendar", "miladi")
        reminders = db.list(user_id)
    except Exception as e:
        logger.error(f"Error in show_delete_reminders for user {user_id}: {e}")
        return
    if not reminders:
        await message.answer(message_handler.t(lang, "no_reminders"))
        return
    buttons = []
    for rid, cat, content, time, tz, repeat, status in reminders:
        emoji = config.emoji_mapping.get(cat, "⏰")
        repeat_pattern = repeat_handler.from_json(repeat)
        repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)
        display_time = DateConverter.convert_to_user_calendar(time, calendar_type)
        display_content = content[:config.max_button_length] + "..." if len(content) > config.max_button_length else content
        button_text = f"🗑 {emoji} {display_content}\n📅 {display_time} | 🔄 {repeat_text}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"delete_confirm_{rid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(message_handler.t(lang, "delete_which"), reply_markup=kb)

async def show_edit_reminders(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
        return
    try:
        data = storage.load(user_id)
        lang = data["settings"]["language"]
        calendar_type = data["settings"].get("calendar", "miladi")
        reminders = db.list(user_id)
    except Exception as e:
        logger.error(f"Error in show_edit_reminders for user {user_id}: {e}")
        return
    if not reminders:
        await message.answer(message_handler.t(lang, "no_reminders"))
        return
    buttons = []
    for rid, cat, content, time, tz, repeat, status in reminders:
        emoji = config.emoji_mapping.get(cat, "⏰")
        repeat_pattern = repeat_handler.from_json(repeat)
        repeat_text = repeat_handler.get_display_text(repeat_pattern, lang)
        display_time = DateConverter.convert_to_user_calendar(time, calendar_type)
        display_content = content[:config.max_button_length] + "..." if len(content) > config.max_button_length else content
        button_text = f"✏️ {emoji} {display_content}\n📅 {display_time} | 🔄 {repeat_text}"
        buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"edit_select_{rid}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(message_handler.t(lang, "edit_which"), reply_markup=kb)

@dp.message(Command("menu"))
async def show_menu(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
        return
    try:
        lang = storage.load(user_id)["settings"]["language"]
    except Exception as e:
        logger.error(f"Error in show_menu for user {user_id}: {e}")
        return
    
    keyboard = [
        [KeyboardButton(text=message_handler.t(lang, "btn_new"))],
        [KeyboardButton(text=message_handler.t(lang, "btn_delete")), KeyboardButton(text=message_handler.t(lang, "btn_edit"))],
        [KeyboardButton(text=message_handler.t(lang, "btn_list"))],
        [KeyboardButton(text=message_handler.t(lang, "btn_settings")), KeyboardButton(text=message_handler.t(lang, "btn_stats"))]
    ]
    
    if admin_handler.is_admin(user_id):
        keyboard.append([KeyboardButton(text=message_handler.t(lang, "btn_admin"))])
    
    kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    await message.answer(message_handler.t(lang, "menu"), reply_markup=kb)

@dp.message(F.text)
async def handle_menu_buttons(message: Message):
    user_id = message.from_user.id
    if not message_handler.rate_limit_check(user_id):
        await message_handler.handle_rate_limit(message)
        return
    
    if config.forced_join.get("enabled", False) and not admin_handler.is_admin(user_id):
        if not await admin_handler.check_user_membership(user_id):
            data = storage.load(user_id)
            lang = data["settings"]["language"]
            kb = await admin_handler.get_join_keyboard(lang)
            await message.answer(message_handler.t(lang, "forced_join_required"), reply_markup=kb)
            return
    
    try:
        lang = storage.load(user_id)["settings"]["language"]
        
        if message.text == message_handler.t(lang, "btn_admin") and admin_handler.is_admin(user_id):
            await admin_handler.show_admin_panel(message)
            return
        
        if admin_handler.is_admin(user_id) and admin_handler.is_admin_button(message.text, lang):
            await admin_handler.handle_admin_button(message)
            return
            
        if admin_handler.is_admin(user_id) and admin_handler.is_forced_join_button(message.text, lang):
            await admin_handler.handle_forced_join_button(message)
            return
        
        if (user_id in admin_handler.waiting_for_admin_id or 
            user_id in admin_handler.waiting_for_broadcast or 
            user_id in admin_handler.waiting_for_private_message or 
            user_id in admin_handler.waiting_for_channel or
            user_id in admin_handler.waiting_for_limit):
            await admin_handler.handle_admin_message(message)
            return
        
        action = message_handler.get_button_action(message.text, lang)
        if action is None:
            await message_handler.handle_message(message)
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
        await message.answer(message_handler.t(lang, "new_reminder_text"))
    elif action == "settings":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=message_handler.t(lang, "change_language"), callback_data="change_lang")],
            [InlineKeyboardButton(text=message_handler.t(lang, "change_timezone"), callback_data="change_tz")],
            [InlineKeyboardButton(text=message_handler.t(lang, "change_calendar"), callback_data="change_calendar")]
        ])
        await message.answer(message_handler.t(lang, "settings"), reply_markup=kb)
    elif action == "stats":
        stats = db.get_stats(user_id)
        await message.answer(message_handler.t(lang, "stats").format(**stats))


@dp.callback_query(F.data.in_(["confirm", "cancel"]))
async def process_callback(callback_query: CallbackQuery):
    await callback_handler.handle_confirm_cancel(callback_query)

@dp.callback_query(F.data.startswith("setup_lang_"))
async def handle_setup_language_selection(callback_query: CallbackQuery):
    await callback_handler.handle_setup_language_selection(callback_query)

@dp.callback_query(F.data.startswith("lang_"))
async def handle_language_selection(callback_query: CallbackQuery):
    await callback_handler.handle_language_selection(callback_query)

@dp.callback_query(F.data == "change_lang")
async def handle_change_language(callback_query: CallbackQuery):
    await callback_handler.handle_change_language(callback_query)

@dp.callback_query(F.data == "change_tz")
async def handle_change_timezone(callback_query: CallbackQuery):
    await callback_handler.handle_change_timezone(callback_query)

@dp.callback_query(F.data.startswith("confirm_tz_"))
async def handle_timezone_confirmation(callback_query: CallbackQuery):
    await callback_handler.handle_timezone_confirmation(callback_query)

@dp.callback_query(F.data == "cancel_tz")
async def handle_timezone_cancel(callback_query: CallbackQuery):
    await callback_handler.handle_timezone_cancel(callback_query)

@dp.callback_query(F.data == "change_calendar")
async def handle_change_calendar(callback_query: CallbackQuery):
    await callback_handler.handle_change_calendar(callback_query)

@dp.callback_query(F.data.startswith("calendar_"))
async def handle_calendar_selection(callback_query: CallbackQuery):
    await callback_handler.handle_calendar_selection(callback_query)

@dp.callback_query(F.data.startswith(("stop_", "paid_", "taken_")))
async def handle_reminder_actions(callback_query: CallbackQuery):
    await callback_handler.handle_reminder_actions(callback_query)

@dp.callback_query(F.data.startswith("delete_confirm_"))
async def handle_delete_confirmation(callback_query: CallbackQuery):
    await callback_handler.handle_delete_confirmation(callback_query)

@dp.callback_query(F.data.startswith("edit_select_"))
async def handle_edit_selection(callback_query: CallbackQuery):
    await callback_handler.handle_edit_selection(callback_query)

@dp.callback_query(F.data == "exit_edit")
async def handle_exit_edit(callback_query: CallbackQuery):
    await callback_handler.handle_exit_edit(callback_query)



@dp.callback_query(F.data.startswith(("remove_admin_", "confirm_remove_", "cancel_remove")))
async def handle_admin_removal_callbacks(callback_query: CallbackQuery):
    await admin_handler.handle_admin_removal_callback(callback_query)

@dp.callback_query(F.data == "check_membership")
async def handle_check_membership(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if await admin_handler.check_user_membership(user_id):
        data = storage.load(user_id)
        lang = data["settings"]["language"]
        await callback_query.message.delete()
        await callback_query.message.answer(message_handler.t(lang, "start"))
        
        keyboard = [
            [KeyboardButton(text=message_handler.t(lang, "btn_new"))],
            [KeyboardButton(text=message_handler.t(lang, "btn_delete")), KeyboardButton(text=message_handler.t(lang, "btn_edit"))],
            [KeyboardButton(text=message_handler.t(lang, "btn_list"))],
            [KeyboardButton(text=message_handler.t(lang, "btn_settings")), KeyboardButton(text=message_handler.t(lang, "btn_stats"))]
        ]
        
        if admin_handler.is_admin(user_id):
            keyboard.append([KeyboardButton(text=message_handler.t(lang, "btn_admin"))])
        
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await callback_query.message.answer(message_handler.t(lang, "menu"), reply_markup=kb)
    else:
        data = storage.load(user_id)
        lang = data["settings"]["language"]
        kb = await admin_handler.get_join_keyboard(lang)
        await callback_query.message.edit_reply_markup(reply_markup=kb)
    
    await callback_query.answer()

async def cleanup_memory():
    while True:
        try:
            await asyncio.sleep(config.cleanup_interval_hours * 3600)
            session.cleanup_expired()
            now = time.time()
            for user_id in list(message_handler.user_request_times.keys()):
                message_handler.user_request_times[user_id] = [t for t in message_handler.user_request_times[user_id] if now - t < 3600]
                if not message_handler.user_request_times[user_id]:
                    del message_handler.user_request_times[user_id]
            expired_waiting = []
            for user_id in list(message_handler.waiting_for_city.keys()):
                if message_handler.waiting_for_city[user_id] and user_id not in message_handler.user_request_times:
                    expired_waiting.append(user_id)
            for user_id in expired_waiting:
                message_handler.waiting_for_city.pop(user_id, None)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    try:
        asyncio.create_task(cleanup_memory())
        scheduler.start()
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        scheduler.stop()
        await bot.session.close()
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
