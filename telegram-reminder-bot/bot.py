from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from config import Config
from database import Database
from json_storage import JSONStorage
from ai_handler import AIHandler
from reminder_scheduler import ReminderScheduler
import json
import os

config = Config()
bot = Bot(config.bot_token)
dp = Dispatcher(bot)
db = Database(config.database_path)
storage = JSONStorage(config.users_path)
ai = AIHandler(config.openrouter_key)
scheduler = ReminderScheduler(db, storage, bot)
base = os.path.dirname(__file__)


def load_locales():
    l = {}
    for f in os.listdir(os.path.join(base, "localization")):
        with open(os.path.join(base, "localization", f)) as d:
            l[f.split(".")[0]] = json.load(d)
    return l


locales = load_locales()


def t(lang, key):
    return locales.get(lang, locales["en"]).get(key, key)


pending = {}


@dp.message_handler(commands=["start"])
async def start_message(message: types.Message):
    user_id = message.from_user.id
    data = storage.load(user_id)
    storage.save(user_id, data)
    
    # Language selection for new users
    if data["settings"]["language"] == "en":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang_fa"))
        kb.add(types.InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"))
        kb.add(types.InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"))
        kb.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
        await message.answer("🌍 Choose your language / زبان خود را انتخاب کنید:", reply_markup=kb)
    else:
        await message.answer(t(data["settings"]["language"], "start"))


@dp.message_handler(commands=["lang"])
async def change_lang(message: types.Message):
    parts = message.text.split()
    if len(parts) > 1 and parts[1] in locales:
        storage.update_setting(message.from_user.id, "language", parts[1])
        await message.answer(t(parts[1], "saved"))


@dp.message_handler(commands=["tz"])
async def change_tz(message: types.Message):
    parts = message.text.split()
    if len(parts) > 1:
        storage.update_setting(message.from_user.id, "timezone", parts[1])
        await message.answer(
            t(storage.load(message.from_user.id)["settings"]["language"], "saved")
        )


@dp.message_handler(commands=["list"])
async def list_reminders(message: types.Message):
    user_id = message.from_user.id
    lang = storage.load(user_id)["settings"]["language"]
    reminders = db.list(user_id)
    if not reminders:
        await message.answer(t(lang, "no_reminders"))
    else:
        lines = []
        for rid, cat, content, time, tz, repeat, status in reminders:
            emoji = {"birthday": "🎂", "medicine": "💊", "installment": "💳", 
                    "work": "💼", "appointment": "📅"}.get(cat, "⏰")
            lines.append(f"{emoji} {rid}: {content}\n📅 {time} ({repeat})")
        await message.answer("\n\n".join(lines))


@dp.message_handler(commands=["delete"])
async def delete_reminder(message: types.Message):
    user_id = message.from_user.id
    lang = storage.load(user_id)["settings"]["language"]
    parts = message.text.split()
    if len(parts) > 1:
        try:
            reminder_id = int(parts[1])
            db.update_status(reminder_id, "cancelled")
            await message.answer(t(lang, "deleted"))
        except ValueError:
            await message.answer("❌ شناسه نامعتبر")
    else:
        await message.answer("❌ لطفاً شناسه یادآوری را وارد کنید")


@dp.message_handler(commands=["menu"])
async def show_menu(message: types.Message):
    user_id = message.from_user.id
    lang = storage.load(user_id)["settings"]["language"]
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 لیست یادآوری‌ها", "➕ یادآوری جدید")
    kb.add("⚙️ تنظیمات", "📊 آمار")
    kb.add("❌ حذف منو")
    
    await message.answer(t(lang, "menu"), reply_markup=kb)


@dp.message_handler(lambda message: message.text in ["📋 لیست یادآوری‌ها", "➕ یادآوری جدید", "⚙️ تنظیمات", "📊 آمار", "❌ حذف منو"])
async def handle_menu_buttons(message: types.Message):
    user_id = message.from_user.id
    lang = storage.load(user_id)["settings"]["language"]
    
    if message.text == "📋 لیست یادآوری‌ها":
        await list_reminders(message)
    elif message.text == "➕ یادآوری جدید":
        await message.answer("📝 متن یادآوری خود را بنویسید:")
    elif message.text == "⚙️ تنظیمات":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🌍 تغییر زبان", callback_data="change_lang"))
        kb.add(types.InlineKeyboardButton("🕐 تایم‌زون", callback_data="change_tz"))
        await message.answer("⚙️ تنظیمات:", reply_markup=kb)
    elif message.text == "📊 آمار":
        active = len(db.list(user_id, "active"))
        completed = len(db.list(user_id, "completed"))
        await message.answer(f"📊 آمار شما:\n🟢 فعال: {active}\n✅ تکمیل شده: {completed}")
    elif message.text == "❌ حذف منو":
        await message.answer("منو حذف شد", reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    data = storage.load(user_id)
    lang = data["settings"]["language"]
    try:
        parsed = await ai.parse(
            lang, data["settings"]["timezone"], message.text
        )
    except Exception as e:
        print(f"AI parsing error: {e}")
        error_msg = {
            "fa": "❌ متاسفانه نتوانستم متن شما را درک کنم. لطفاً واضح‌تر بنویسید.",
            "en": "❌ Sorry, I couldn't understand your text. Please be more specific.",
            "ar": "❌ عذراً، لم أتمكن من فهم النص. يرجى التوضيح أكثر.",
            "ru": "❌ Извините, я не смог понять ваш текст. Пожалуйста, уточните."
        }
        await message.answer(error_msg.get(lang, error_msg["en"]))
        return
    pending[user_id] = parsed
    summary = f"{t(lang, 'summary')}: {parsed['content']} @ {parsed['time']}"\
              f" ({parsed['category']})"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(t(lang, "confirm"), callback_data="confirm"))
    kb.add(types.InlineKeyboardButton(t(lang, "cancel"), callback_data="cancel"))
    await message.answer(summary, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data in ["confirm", "cancel"])
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    lang = storage.load(user_id)["settings"]["language"]
    if callback_query.data == "confirm" and user_id in pending:
        rem = pending.pop(user_id)
        db.add(
            user_id,
            rem["category"],
            rem["content"],
            rem["time"],
            rem.get("timezone", "+00:00"),
            rem.get("repeat", "none"),
        )
        storage.add_reminder(user_id, rem)
        await callback_query.message.edit_reply_markup()
        await callback_query.message.answer(t(lang, "saved"))
    else:
        pending.pop(user_id, None)
        await callback_query.message.edit_reply_markup()
        await callback_query.message.answer(t(lang, "ask_more"))


@dp.callback_query_handler(lambda c: c.data.startswith("lang_"))
async def handle_language_selection(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    lang_code = callback_query.data.split("_")[1]
    storage.update_setting(user_id, "language", lang_code)
    await callback_query.message.edit_text(t(lang_code, "saved"))
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith(("stop_", "paid_", "taken_")))
async def handle_reminder_actions(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    lang = storage.load(user_id)["settings"]["language"]
    action, reminder_id = callback_query.data.split("_", 1)
    
    if action == "stop":
        db.update_status(int(reminder_id), "cancelled")
        await callback_query.message.edit_text("❌ یادآوری متوقف شد")
        
    elif action == "paid":
        db.update_status(int(reminder_id), "completed")
        await callback_query.message.edit_text("✅ پرداخت ثبت شد")
        
    elif action == "taken":
        await callback_query.message.edit_text("✅ دارو خورده شد")
        
    await callback_query.answer()


def main():
    scheduler.start()
    executor.start_polling(dp)
    scheduler.stop()
    db.close()


if __name__ == "__main__":
    main()
