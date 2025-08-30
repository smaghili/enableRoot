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
        lines = [
            f"{rid}: {content} @ {time} ({repeat})"
            for rid, cat, content, time, tz, repeat, status in reminders
        ]
        await message.answer("\n".join(lines))


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
        print(e)
        await message.answer("error")
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


def main():
    scheduler.start()
    executor.start_polling(dp)
    scheduler.stop()
    db.close()


if __name__ == "__main__":
    main()
