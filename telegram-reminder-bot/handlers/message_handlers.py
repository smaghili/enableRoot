from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from typing import Dict, Any
import logging
import time
import datetime
import json
from config.config import Config
from config.interfaces import IMessageHandler
from utils.date_converter import DateConverter

logger = logging.getLogger(__name__)

class ReminderMessageHandler(IMessageHandler):
    def __init__(self, storage, db, ai, repeat_handler, locales, session, config):
        self.storage = storage
        self.db = db
        self.ai = ai
        self.repeat_handler = repeat_handler
        self.locales = locales
        self.session = session
        self.config = config
        self.user_request_times = {}
        self.user_message_count = {}
        self.waiting_for_city = {}

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    def rate_limit_check(self, user_id: int) -> bool:
        now = time.time()
        user_times = self.user_request_times.get(user_id, [])
        user_times[:] = [t for t in user_times if now - t < self.config.rate_limit_window]
        if len(user_times) >= self.config.max_requests_per_minute:
            logger.warning(f"Rate limit exceeded for user {user_id}: {len(user_times)} requests in last minute")
            return False
        user_times.append(now)
        self.user_request_times[user_id] = user_times
        return True

    async def handle_rate_limit(self, message_or_callback):
        try:
            if hasattr(message_or_callback, 'from_user'):
                user_id = message_or_callback.from_user.id
            else:
                return
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            rate_limit_msg = self.t(lang, "rate_limit_exceeded")
            if hasattr(message_or_callback, 'answer'):
                await message_or_callback.answer(rate_limit_msg)
            elif hasattr(message_or_callback, 'message'):
                await message_or_callback.answer(rate_limit_msg, show_alert=True)
        except Exception as e:
            logger.error(f"Error in handle_rate_limit: {e}")

    def validate_user_input(self, text: str) -> bool:
        if not text or not isinstance(text, str):
            return False
        if len(text.strip()) == 0:
            return False
        if len(text) > self.config.max_content_length:
            return False
        return True

    def sanitize_input(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        return text.strip()[:self.config.max_content_length]

    def get_button_action(self, message_text, user_lang):
        button_mappings = {
            "btn_list": "list",
            "btn_delete": "delete",
            "btn_edit": "edit",
            "btn_new": "new",
            "btn_settings": "settings",
            "btn_stats": "stats",
            "btn_admin": "admin"
        }
        for key, action in button_mappings.items():
            if message_text == self.t(user_lang, key):
                return action
        return None

    async def handle_message(self, message: Message) -> None:
        user_id = message.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(message)
            return
        if not self.validate_user_input(message.text):
            return
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            if self.waiting_for_city.get(user_id, False):
                await self.handle_city_input(message)
                return
            if user_id in self.session.editing_reminders:
                if message.text == self.t(lang, "exit_edit"):
                    await self.handle_exit_edit_text(message, lang)
                    return
                else:
                    await self.handle_edit_input(message)
                    return
            user_reminders = self.db.list(user_id)
            if len(user_reminders) >= self.config.max_reminders_per_user:
                await message.answer(self.t(lang, "max_reminders_reached"))
                return
            logger.info(f"Parsing text for user {user_id}: {message.text}")
            user_calendar = data["settings"].get("calendar", "miladi")
            parsed = await self.ai.parse(lang, data["settings"]["timezone"], message.text, user_calendar)
            if not parsed:
                await message.answer(self.t(lang, "parse_error"))
                return
            if not parsed.get("reminders") or len(parsed["reminders"]) == 0:
                message_key = parsed.get("message") or "ai_error"
                if message_key == "past_date_error":
                    error_message = self.t(lang, message_key, 
                                         detected_date=parsed.get("detected_date", ""), 
                                         current_date=parsed.get("current_date", ""))
                else:
                    error_message = self.t(lang, message_key)
                await message.answer(error_message)
                return
                
            self.session.pending[user_id] = parsed
            self.session.pending_cleanup_time[user_id] = datetime.datetime.now() + datetime.timedelta(minutes=10)
            await self.handle_parsed_reminder(message, parsed, lang)
        except Exception as e:
            logger.error(f"Error in handle_message for user {user_id}: {e}")

    async def handle_callback(self, callback: CallbackQuery) -> None:
        user_id = callback.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback)
            return
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
        except Exception as e:
            logger.error(f"Error in handle_callback for user {user_id}: {e}")
            await callback.answer()
            return
        await callback.answer()

    async def handle_city_input(self, message: Message):
        user_id = message.from_user.id
        try:
            lang = self.storage.load(user_id)["settings"]["language"]
            city_name = self.sanitize_input(message.text)
            if not city_name or len(city_name) > self.config.max_city_length:
                await message.answer(self.t(lang, "timezone_error"))
                self.waiting_for_city[user_id] = False
                return
            timezone_info = await self.get_timezone_from_city(city_name, lang)
            if not timezone_info:
                await message.answer(self.t(lang, "timezone_error"))
                self.waiting_for_city[user_id] = False
                return
            city, timezone = timezone_info
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=self.t(lang, "yes"), callback_data=f"confirm_tz_{timezone}")],
                [InlineKeyboardButton(text=self.t(lang, "no"), callback_data="cancel_tz")]
            ])
            user_data = self.storage.load(user_id)
            if user_id in self.waiting_for_city and not user_data["settings"].get("setup_complete", False):
                confirmation_text = self.t(lang, "setup_timezone_confirmation").format(city=city, timezone=timezone)
            else:
                confirmation_text = self.t(lang, "timezone_confirmation").format(city=city, timezone=timezone)
            await message.answer(confirmation_text, reply_markup=kb)
            self.waiting_for_city[user_id] = False
        except Exception as e:
            logger.error(f"Error in handle_city_input for user {user_id}: {e}")
            self.waiting_for_city[user_id] = False

    async def handle_edit_input(self, message: Message):
        """Handle edit input from user"""
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            reminder_id = self.session.editing_reminders[user_id] 
            user_reminders = self.db.list(user_id)
            current_reminder = None
            for rid, cat, content, time, tz, repeat, status in user_reminders:
                if rid == reminder_id:
                    current_reminder = {
                        "id": rid,
                        "category": cat,
                        "content": content,
                        "time": time,
                        "timezone": tz,
                        "repeat": repeat
                    }
                    break
            
            if not current_reminder:
                await message.answer(self.t(lang, "reminder_not_found"))
                self.session.editing_reminders.pop(user_id, None)
                return
            edit_result = await self.ai.parse_edit(current_reminder, message.text, data["settings"]["timezone"])
            if not edit_result:
                await message.answer(self.t(lang, "parse_error"))
                return
            
            edit_data = {
                "reminder_id": reminder_id,
                "original": current_reminder,
                "edited": edit_result,
                "type": "edit"
            }
            self.session.pending[user_id] = edit_data
            self.session.pending_cleanup_time[user_id] = datetime.datetime.now() + datetime.timedelta(minutes=10)
            repeat_value = edit_result.get("repeat", current_reminder["repeat"])
            if isinstance(repeat_value, dict):
                repeat_value = json.dumps(repeat_value)
            repeat_pattern = self.repeat_handler.from_json(repeat_value)
            repeat_text = self.repeat_handler.get_display_text(repeat_pattern, lang)
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=self.t(lang, "confirm"), callback_data="confirm")],
                [InlineKeyboardButton(text=self.t(lang, "cancel"), callback_data="cancel")]
            ])
            
            calendar_type = data["settings"].get("calendar", "miladi")
            display_time = DateConverter.convert_to_user_calendar(edit_result.get("time", current_reminder["time"]), calendar_type)
            preview_text = self.t(lang, "edit_preview").format(
                id=reminder_id,
                old_content=current_reminder["content"],
                new_content=edit_result.get("content", current_reminder["content"]),
                time=display_time,
                repeat=repeat_text
            )
            
            await message.answer(preview_text, reply_markup=kb)
            
        except Exception as e:
            logger.error(f"Error in handle_edit_input for user {user_id}: {e}")
            self.session.editing_reminders.pop(user_id, None)
            await message.answer(self.t(lang, "edit_error"))

    async def handle_exit_edit_text(self, message: Message, lang: str):
        """Handle exit edit via text message"""
        user_id = message.from_user.id
        try:
            self.session.editing_reminders.pop(user_id, None)
            if user_id in self.session.pending:
                self.session.pending.pop(user_id)
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text=self.t(lang, "btn_new"))],
                [KeyboardButton(text=self.t(lang, "btn_delete")), KeyboardButton(text=self.t(lang, "btn_edit"))],
                [KeyboardButton(text=self.t(lang, "btn_list"))],
                [KeyboardButton(text=self.t(lang, "btn_settings")), KeyboardButton(text=self.t(lang, "btn_stats"))]
            ], resize_keyboard=True)
            
            await message.answer(self.t(lang, "edit_cancelled"), reply_markup=kb)
            
        except Exception as e:
            logger.error(f"Error in handle_exit_edit_text for user {user_id}: {e}")

    async def get_timezone_from_city(self, city_name: str, user_lang: str):
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
            result = await self.ai.parse_timezone(prompt)
            return result
        except Exception as e:
            logger.error(f"Error getting timezone for {city_name}: {e}")
            return None

    async def handle_parsed_reminder(self, message: Message, parsed: Dict[str, Any], lang: str):
        user_id = message.from_user.id
        data = self.storage.load(user_id)
        calendar_type = data["settings"].get("calendar", "miladi")
        if "reminders" in parsed and isinstance(parsed["reminders"], list):
            summary_lines = [self.t(lang, "multiple_reminders_summary").format(count=len(parsed["reminders"]))]
            for i, reminder in enumerate(parsed["reminders"], 1):
                category_text = self.t(lang, f"category_{reminder['category']}")
                if category_text == f"category_{reminder['category']}":
                    category_text = reminder['category']
                repeat_value = reminder.get('repeat', self.config.default_repeat)
                if isinstance(repeat_value, dict):
                    repeat_value = json.dumps(repeat_value)
                repeat_pattern = self.repeat_handler.from_json(repeat_value)
                repeat_text = self.repeat_handler.get_display_text(repeat_pattern, lang)
                display_time = DateConverter.convert_to_user_calendar(reminder['time'], calendar_type)
                summary_lines.append(f"{i}. {reminder['content']} @ {display_time} ({category_text}) - {repeat_text}")
            summary = "\n".join(summary_lines)
        else:
            category_text = self.t(lang, f"category_{parsed['category']}")
            if category_text == f"category_{parsed['category']}":
                category_text = parsed['category']
            repeat_value = parsed.get('repeat', self.config.default_repeat)
            if isinstance(repeat_value, dict):
                repeat_value = json.dumps(repeat_value)
            repeat_pattern = self.repeat_handler.from_json(repeat_value)
            repeat_text = self.repeat_handler.get_display_text(repeat_pattern, lang)
            display_time = DateConverter.convert_to_user_calendar(parsed['time'], calendar_type)
            summary_prefix = self.t(lang, 'summary')
            summary = f"{summary_prefix}: {parsed['content']} @ {display_time} ({category_text}) - {repeat_text}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=self.t(lang, "confirm"), callback_data="confirm")],
            [InlineKeyboardButton(text=self.t(lang, "cancel"), callback_data="cancel")]
        ])
        await message.answer(summary, reply_markup=kb)
