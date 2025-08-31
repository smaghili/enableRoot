from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import Dict, Any
import logging
import time
import datetime
from config import Config
from interfaces import IMessageHandler

logger = logging.getLogger(__name__)

class ReminderCallbackHandler(IMessageHandler):
    def __init__(self, storage, db, ai, repeat_handler, locales, message_handler, session, config):
        self.storage = storage
        self.db = db
        self.ai = ai
        self.repeat_handler = repeat_handler
        self.locales = locales
        self.message_handler = message_handler
        self.session = session
        self.config = config
        self.user_request_times = {}

    def t(self, lang, key):
        return self.locales.get(lang, self.locales["en"]).get(key, key)

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

    async def handle_rate_limit(self, callback):
        try:
            user_id = callback.from_user.id
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            rate_limit_msg = self.t(lang, "rate_limit_exceeded")
            await callback.answer(rate_limit_msg, show_alert=True)
        except Exception as e:
            logger.error(f"Error in handle_rate_limit: {e}")

    async def handle_message(self, message) -> None:
        pass

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

    async def handle_setup_language_selection(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang_code = callback_query.data.split("_")[2]
            if lang_code in self.locales:
                self.storage.update_setting(user_id, "language", lang_code)
                await callback_query.message.edit_text(
                    f"✅ {self.t(lang_code, 'language_selected')}\n\n"
                    f"🌍 {self.t(lang_code, 'setup_timezone_prompt')}"
                )
                self.message_handler.waiting_for_city[user_id] = True
            else:
                await callback_query.answer()
                return
        except Exception as e:
            logger.error(f"Error in handle_setup_language_selection for user {user_id}: {e}")
            await callback_query.answer()
            return
        await callback_query.answer()

    async def handle_language_selection(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang_code = callback_query.data.split("_")[1]
            if lang_code in self.locales:
                self.storage.update_setting(user_id, "language", lang_code)
            else:
                await callback_query.answer()
                return
        except Exception as e:
            logger.error(f"Error in handle_language_selection for user {user_id}: {e}")
            await callback_query.answer()
            return
        await callback_query.message.edit_text(self.t(lang_code, "saved"))
        await callback_query.answer()
        await callback_query.message.answer(self.t(lang_code, "start"))
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=self.t(lang_code, "btn_list"))],
            [KeyboardButton(text=self.t(lang_code, "btn_delete")), KeyboardButton(text=self.t(lang_code, "btn_edit"))],
            [KeyboardButton(text=self.t(lang_code, "btn_new"))],
            [KeyboardButton(text=self.t(lang_code, "btn_settings")), KeyboardButton(text=self.t(lang_code, "btn_stats"))],
            [KeyboardButton(text=self.t(lang_code, "btn_remove_menu"))]
        ], resize_keyboard=True)
        await callback_query.message.answer(self.t(lang_code, "menu"), reply_markup=kb)

    async def handle_change_language(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang_fa")],
                [InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")],
                [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar")],
                [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
            ])
            lang = self.storage.load(user_id)["settings"]["language"]
            await callback_query.message.edit_text(self.t(lang, "choose_language"), reply_markup=kb)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_change_language for user {user_id}: {e}")
            await callback_query.answer()

    async def handle_change_timezone(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.load(user_id)["settings"]["language"]
            self.message_handler.waiting_for_city[user_id] = True
            await callback_query.message.edit_text(self.t(lang, "enter_city_name"))
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_change_timezone for user {user_id}: {e}")
            await callback_query.answer()

    async def handle_timezone_confirmation(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            timezone = callback_query.data.replace("confirm_tz_", "")
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            self.storage.update_setting(user_id, "timezone", timezone)
            is_setup = not data["settings"].get("setup_complete", False)
            if is_setup:
                self.storage.update_setting(user_id, "setup_complete", True)
                await callback_query.message.edit_text(self.t(lang, "setup_complete"))
                kb = ReplyKeyboardMarkup(keyboard=[
                    [KeyboardButton(text=self.t(lang, "btn_list"))],
                    [KeyboardButton(text=self.t(lang, "btn_delete")), KeyboardButton(text=self.t(lang, "btn_edit"))],
                    [KeyboardButton(text=self.t(lang, "btn_new"))],
                    [KeyboardButton(text=self.t(lang, "btn_settings")), KeyboardButton(text=self.t(lang, "btn_stats"))],
                    [KeyboardButton(text=self.t(lang, "btn_remove_menu"))]
                ], resize_keyboard=True)
                await callback_query.message.answer(self.t(lang, "menu"), reply_markup=kb)
            else:
                success_text = self.t(lang, "timezone_changed").format(timezone=timezone)
                await callback_query.message.edit_text(success_text)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_timezone_confirmation for user {user_id}: {e}")
            await callback_query.answer()

    async def handle_timezone_cancel(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        try:
            lang = self.storage.load(user_id)["settings"]["language"]
            await callback_query.message.edit_text(self.t(lang, "timezone_cancelled"))
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_timezone_cancel for user {user_id}: {e}")
            await callback_query.answer()

    async def handle_reminder_actions(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.load(user_id)["settings"]["language"]
            action, reminder_id = callback_query.data.split("_", 1)
            reminder_id = int(reminder_id)
        except (ValueError, Exception) as e:
            logger.error(f"Error in handle_reminder_actions for user {user_id}: {e}")
            await callback_query.answer()
            return
        try:
            if action == "stop":
                self.db.update_status(reminder_id, "cancelled")
                await callback_query.message.edit_text(self.t(lang, "reminder_stopped"))
            elif action == "paid":
                self.db.update_status(reminder_id, "completed")
                await callback_query.message.edit_text(self.t(lang, "payment_recorded"))
            elif action == "taken":
                await callback_query.message.edit_text(self.t(lang, "medicine_taken"))
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error updating reminder {reminder_id} for user {user_id}: {e}")
            await callback_query.answer()

    async def handle_delete_confirmation(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.load(user_id)["settings"]["language"]
            reminder_id = int(callback_query.data.split("_")[2])
            user_reminders = self.db.list(user_id)
            reminder_exists = any(r[0] == reminder_id for r in user_reminders)
            if not reminder_exists:
                await callback_query.message.edit_text(self.t(lang, "invalid_id"))
                await callback_query.answer()
                return
        except Exception as e:
            logger.error(f"Error in handle_delete_confirmation for user {user_id}: {e}")
            await callback_query.answer()
            return
        self.db.update_status(reminder_id, "cancelled")
        await callback_query.message.edit_text(self.t(lang, "reminder_deleted").format(id=reminder_id))
        await callback_query.answer(self.t(lang, "delete_confirmed"))

    async def handle_edit_selection(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.load(user_id)["settings"]["language"]
            reminder_id = int(callback_query.data.split("_")[2])
            user_reminders = self.db.list(user_id)
            reminder_exists = any(r[0] == reminder_id for r in user_reminders)
            if not reminder_exists:
                await callback_query.message.edit_text(self.t(lang, "invalid_id"))
                await callback_query.answer()
                return
        except Exception as e:
            logger.error(f"Error in handle_edit_selection for user {user_id}: {e}")
            await callback_query.answer()
            return
        self.session.editing_reminders[user_id] = reminder_id
        await callback_query.message.edit_text(
            self.t(lang, "reminder_selected").format(id=reminder_id)
        )
        await callback_query.answer()

    async def handle_confirm_cancel(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
        except Exception as e:
            logger.error(f"Error in handle_confirm_cancel for user {user_id}: {e}")
            await callback_query.answer()
            return
        if callback_query.data == "confirm" and user_id in self.session.pending:
            pending_data = self.session.pending.pop(user_id)
            
            # Handle edit confirmation
            if pending_data.get("type") == "edit":
                reminder_id = pending_data["reminder_id"]
                edit_result = pending_data["edited"]
                original = pending_data["original"]
                
                # Update the reminder in database
                self.db.update_reminder(
                    reminder_id,
                    edit_result.get("category", original["category"]),
                    edit_result.get("content", original["content"]),
                    edit_result.get("time", original["time"]),
                    edit_result.get("timezone", original["timezone"]),
                    edit_result.get("repeat", original["repeat"])
                )
                
                # Clear editing state
                self.session.editing_reminders.pop(user_id, None)
                
                # Show success message
                repeat_pattern = self.repeat_handler.from_json(edit_result.get("repeat", original["repeat"]))
                repeat_text = self.repeat_handler.get_display_text(repeat_pattern, lang)
                
                # Restore classic menu
                from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
                kb = ReplyKeyboardMarkup(keyboard=[
                    [KeyboardButton(text=self.message_handler.t(lang, "btn_list"))],
                    [KeyboardButton(text=self.message_handler.t(lang, "btn_delete")), KeyboardButton(text=self.message_handler.t(lang, "btn_edit"))],
                    [KeyboardButton(text=self.message_handler.t(lang, "btn_new"))],
                    [KeyboardButton(text=self.message_handler.t(lang, "btn_settings")), KeyboardButton(text=self.message_handler.t(lang, "btn_stats"))],
                    [KeyboardButton(text=self.message_handler.t(lang, "btn_remove_menu"))]
                ], resize_keyboard=True)
                
                await callback_query.message.delete()
                await callback_query.message.answer(
                    self.t(lang, "edit_success_details").format(
                        id=reminder_id,
                        content=edit_result.get("content", original["content"]),
                        time=edit_result.get("time", original["time"]),
                        repeat=repeat_text
                    ),
                    reply_markup=kb
                )
            elif "reminders" in pending_data and isinstance(pending_data["reminders"], list):
                created_count = 0
                for reminder in pending_data["reminders"]:
                    reminder_data = {
                        "category": reminder.get("category", self.config.default_category),
                        "content": reminder.get("content", "")[:self.config.max_reminder_length],
                        "time": reminder.get("time"),
                        "timezone": reminder.get("timezone", self.config.default_timezone),
                        "repeat": reminder.get("repeat", self.config.default_repeat)
                    }
                    self.db.add(
                        user_id,
                        reminder_data["category"],
                        reminder_data["content"],
                        reminder_data["time"],
                        reminder_data["timezone"],
                        reminder_data["repeat"]
                    )
                    self.storage.add_reminder(user_id, reminder_data)
                    created_count += 1
                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer(self.t(lang, "multiple_reminders_saved").format(count=created_count))
            else:
                reminder_data = {
                    "category": pending_data.get("category", self.config.default_category),
                    "content": pending_data.get("content", "")[:self.config.max_reminder_length],
                    "time": pending_data.get("time"),
                    "timezone": pending_data.get("timezone", self.config.default_timezone),
                    "repeat": pending_data.get("repeat", self.config.default_repeat)
                }
                self.db.add(
                    user_id,
                    reminder_data["category"],
                    reminder_data["content"],
                    reminder_data["time"],
                    reminder_data["timezone"],
                    reminder_data["repeat"]
                )
                self.storage.add_reminder(user_id, reminder_data)
                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer(self.t(lang, "reminder_saved"))
        else:
            if user_id in self.session.pending:
                pending_data = self.session.pending.pop(user_id)
                # If canceling edit, keep editing state and show cancel option
                if pending_data.get("type") == "edit":
                    await callback_query.message.edit_reply_markup(reply_markup=None)
                    
                    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
                    cancel_kb = ReplyKeyboardMarkup(keyboard=[
                        [KeyboardButton(text=self.t(lang, "exit_edit"))]
                    ], resize_keyboard=True)
                    
                    await callback_query.message.answer(
                        self.t(lang, "ask_more"), 
                        reply_markup=cancel_kb
                    )
                else:
                    await callback_query.message.edit_reply_markup(reply_markup=None)
                    await callback_query.message.answer(self.t(lang, "ask_more"))
            else:
                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer(self.t(lang, "ask_more"))
        await callback_query.answer()

    async def handle_exit_edit(self, callback_query: CallbackQuery):
        """Handle exit edit request"""
        user_id = callback_query.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            # Clear editing state completely
            self.session.editing_reminders.pop(user_id, None)
            if user_id in self.session.pending:
                self.session.pending.pop(user_id)
            
            # Restore classic menu
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text=self.message_handler.t(lang, "btn_list"))],
                [KeyboardButton(text=self.message_handler.t(lang, "btn_delete")), KeyboardButton(text=self.message_handler.t(lang, "btn_edit"))],
                [KeyboardButton(text=self.message_handler.t(lang, "btn_new"))],
                [KeyboardButton(text=self.message_handler.t(lang, "btn_settings")), KeyboardButton(text=self.message_handler.t(lang, "btn_stats"))],
                [KeyboardButton(text=self.message_handler.t(lang, "btn_remove_menu"))]
            ], resize_keyboard=True)
            
            await callback_query.message.answer(self.t(lang, "edit_cancelled"), reply_markup=kb)
            
        except Exception as e:
            logger.error(f"Error in handle_exit_edit for user {user_id}: {e}")
        
        await callback_query.answer()
