from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import Dict, Any
import logging
import time
import datetime
import json
from config.config import Config
from config.interfaces import IMessageHandler
from utils.date_converter import DateConverter
from utils.menu_factory import MenuFactory
try:
    import jdatetime
except ImportError:
    jdatetime = None
logger = logging.getLogger(__name__)
class ReminderCallbackHandler(IMessageHandler):
    def __init__(self, storage, db, ai, repeat_handler, locales, message_handler, session, config, admin_handler=None, log_manager=None):
        self.storage = storage
        self.db = db
        self.ai = ai
        self.repeat_handler = repeat_handler
        self.locales = locales
        self.message_handler = message_handler
        self.session = session
        self.config = config
        self.admin_handler = admin_handler
        self.log_manager = log_manager
        self.user_request_times = {}
        self.date_converter = DateConverter()
    def t(self, lang, key):
        return self.locales.get(lang, self.locales["en"]).get(key, key)
    def _calculate_correct_time(self, reminder_data: dict, user_calendar: str) -> str:
        now = datetime.datetime.now()
        repeat_data = reminder_data.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        repeat_type = repeat_data.get("type", "none")
        if repeat_type == "monthly" and "day" in repeat_data:
            target_day = repeat_data.get("day", now.day)
            if user_calendar == "shamsi" and jdatetime:
                shamsi_now = jdatetime.datetime.fromgregorian(datetime=now)
                current_day = shamsi_now.day
                if target_day <= current_day:
                    if shamsi_now.month == 12:
                        next_month = shamsi_now.replace(year=shamsi_now.year + 1, month=1, day=target_day)
                    else:
                        next_month = shamsi_now.replace(month=shamsi_now.month + 1, day=target_day)
                else:
                    next_month = shamsi_now.replace(day=target_day)
                gregorian_date = next_month.togregorian()
                return f"{gregorian_date.year}-{gregorian_date.month:02d}-{gregorian_date.day:02d} {now.hour:02d}:{now.minute:02d}"
            else:
                current_day = now.day
                if target_day <= current_day:
                    if now.month == 12:
                        next_month = now.replace(year=now.year + 1, month=1, day=target_day)
                    else:
                        next_month = now.replace(month=now.month + 1, day=target_day)
                else:
                    next_month = now.replace(day=target_day)
                return next_month.strftime("%Y-%m-%d %H:%M")
        elif repeat_type == "interval":
            value = repeat_data.get("value", 0)
            unit = repeat_data.get("unit", "minutes")
            if unit == "minutes":
                next_time = now + datetime.timedelta(minutes=value)
            elif unit == "hours":
                next_time = now + datetime.timedelta(hours=value)
            elif unit == "days":
                next_time = now + datetime.timedelta(days=value)
            else:
                next_time = now
            return next_time.strftime("%Y-%m-%d %H:%M")
        return reminder_data.get("time", now.strftime("%Y-%m-%d %H:%M"))
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
        kb = MenuFactory.create_main_menu(lang_code, self.t, self.admin_handler.is_admin(user_id) if self.admin_handler else False)
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
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=self.t(lang, "calendar_shamsi"), callback_data="setup_calendar_shamsi")],
                    [InlineKeyboardButton(text=self.t(lang, "calendar_miladi"), callback_data="setup_calendar_miladi")],
                    [InlineKeyboardButton(text=self.t(lang, "calendar_qamari"), callback_data="setup_calendar_qamari")]
                ])
                await callback_query.message.edit_text(
                    f"✅ {self.t(lang, 'timezone_changed').format(timezone=timezone)}\n\n"
                    f"{self.t(lang, 'choose_calendar')}",
                    reply_markup=kb
                )
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
                if reminder_id:
                    try:
                        with self.db.lock:
                            cur = self.db.conn.cursor()
                            cur.execute(
                                "UPDATE reminders SET status='cancelled' WHERE category='installment_retry' AND content LIKE ?",
                                (f"%{reminder_id}%",)
                            )
                            self.db.conn.commit()
                            cur.close()
                    except Exception as e:
                        logger.error(f"Error cancelling retry reminders for {reminder_id}: {e}")
                await callback_query.message.edit_text(self.t(lang, "reminder_stopped"))
            elif action == "paid":
                self.db.update_status(reminder_id, "completed")
                if reminder_id:
                    try:
                        with self.db.lock:
                            cur = self.db.conn.cursor()
                            cur.execute(
                                "UPDATE reminders SET status='cancelled' WHERE category='installment_retry' AND content LIKE ?",
                                (f"%{reminder_id}%",)
                            )
                            self.db.conn.commit()
                            cur.close()
                    except Exception as e:
                        logger.error(f"Error cancelling retry reminders for {reminder_id}: {e}")
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
            if pending_data.get("type") == "edit":
                reminder_id = pending_data["reminder_id"]
                edit_result = pending_data["edited"]
                original = pending_data["original"]
                self.db.update_reminder(
                    reminder_id,
                    edit_result.get("category", original["category"]),
                    edit_result.get("content", original["content"]),
                    edit_result.get("time", original["time"]),
                    edit_result.get("timezone", original["timezone"]),
                    edit_result.get("repeat", original["repeat"])
                )
                self.session.editing_reminders.pop(user_id, None)
                repeat_value = edit_result.get("repeat", original["repeat"])
                if isinstance(repeat_value, dict):
                    import json
                    repeat_value = json.dumps(repeat_value)
                repeat_pattern = self.repeat_handler.from_json(repeat_value)
                repeat_text = self.repeat_handler.get_display_text(repeat_pattern, lang)
                kb = MenuFactory.create_main_menu(lang, self.message_handler.t, self.admin_handler.is_admin(user_id) if self.admin_handler else False)
                calendar_type = data["settings"].get("calendar", "miladi")
                display_time = self.date_converter.convert_to_user_calendar(edit_result.get("time", original["time"]), calendar_type, data['settings']['timezone'])
                await callback_query.message.delete()
                await callback_query.message.answer(
                    self.t(lang, "edit_success_details").format(
                        id=reminder_id,
                        content=edit_result.get("content", original["content"]),
                        time=display_time,
                        repeat=repeat_text
                    ),
                    reply_markup=kb
                )
            elif "reminders" in pending_data and isinstance(pending_data["reminders"], list):
                created_count = 0
                calendar_type = data["settings"].get("calendar", "miladi")
                for reminder in pending_data["reminders"]:
                    reminder_data = {
                        "category": reminder.get("category", self.config.default_category),
                        "content": reminder.get("content", "")[:self.config.max_reminder_length],
                        "time": reminder.get("time"),
                        "timezone": reminder.get("timezone", self.config.default_timezone),
                        "repeat": reminder.get("repeat", self.config.default_repeat)
                    }
                    corrected_time = self._calculate_correct_time(reminder_data, calendar_type)
                    reminder_data["time"] = corrected_time
                    meta = None
                    try:
                        if reminder.get("category") == "birthday" and reminder.get("specific_date"):
                            from utils.date_parser import DateParser
                            dp = DateParser()
                            birth_dt = dp.convert_to_gregorian(reminder.get("specific_date"))
                            if birth_dt:
                                meta = json.dumps({"birthdate_gregorian": birth_dt.strftime("%Y-%m-%d")})
                    except Exception:
                        meta = None
                    reminder_id = self.db.add(
                        user_id,
                        reminder_data["category"],
                        reminder_data["content"],
                        reminder_data["time"],
                        reminder_data["timezone"],
                        reminder_data["repeat"],
                        meta=meta
                    )
                    self.storage.add_reminder(user_id, reminder_data)

                    created_count += 1
                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer(self.t(lang, "multiple_reminders_saved").format(count=created_count))
            else:
                calendar_type = data["settings"].get("calendar", "miladi")
                reminder_data = {
                    "category": pending_data.get("category", self.config.default_category),
                    "content": pending_data.get("content", "")[:self.config.max_reminder_length],
                    "time": pending_data.get("time"),
                    "timezone": pending_data.get("timezone", self.config.default_timezone),
                    "repeat": pending_data.get("repeat", self.config.default_repeat)
                }
                corrected_time = self._calculate_correct_time(reminder_data, calendar_type)
                reminder_data["time"] = corrected_time
                meta = None
                try:
                    if pending_data.get("category") == "birthday" and pending_data.get("specific_date"):
                        from utils.date_parser import DateParser
                        dp = DateParser()
                        birth_dt = dp.convert_to_gregorian(pending_data.get("specific_date"))
                        if birth_dt:
                            meta = json.dumps({"birthdate_gregorian": birth_dt.strftime("%Y-%m-%d")})
                except Exception:
                    meta = None
                reminder_id = self.db.add(
                    user_id,
                    reminder_data["category"],
                    reminder_data["content"],
                    reminder_data["time"],
                    reminder_data["timezone"],
                    reminder_data["repeat"],
                    meta=meta
                )
                self.storage.add_reminder(user_id, reminder_data)

                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer(self.t(lang, "reminder_saved"))
        else:
            if user_id in self.session.pending:
                pending_data = self.session.pending.pop(user_id)
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
        user_id = callback_query.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            self.session.editing_reminders.pop(user_id, None)
            if user_id in self.session.pending:
                self.session.pending.pop(user_id)
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text=self.message_handler.t(lang, "btn_new"))],
                [KeyboardButton(text=self.message_handler.t(lang, "btn_delete")), KeyboardButton(text=self.message_handler.t(lang, "btn_edit"))],
                [KeyboardButton(text=self.message_handler.t(lang, "btn_list"))],
                [KeyboardButton(text=self.message_handler.t(lang, "btn_settings")), KeyboardButton(text=self.message_handler.t(lang, "btn_stats"))]
            ], resize_keyboard=True)
            await callback_query.message.answer(self.t(lang, "edit_cancelled"), reply_markup=kb)
        except Exception as e:
            logger.error(f"Error in handle_exit_edit for user {user_id}: {e}")
        await callback_query.answer()
    async def handle_change_calendar(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.load(user_id)["settings"]["language"]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=self.t(lang, "calendar_shamsi"), callback_data="calendar_shamsi")],
                [InlineKeyboardButton(text=self.t(lang, "calendar_miladi"), callback_data="calendar_miladi")],
                [InlineKeyboardButton(text=self.t(lang, "calendar_qamari"), callback_data="calendar_qamari")]
            ])
            await callback_query.message.edit_text(self.t(lang, "choose_calendar"), reply_markup=kb)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_change_calendar for user {user_id}: {e}")
            await callback_query.answer()
    async def handle_calendar_selection(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            calendar_type = callback_query.data.replace("calendar_", "")
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            calendar_names = {
                "shamsi": self.t(lang, "calendar_shamsi"),
                "miladi": self.t(lang, "calendar_miladi"),
                "qamari": self.t(lang, "calendar_qamari")
            }
            self.storage.update_setting(user_id, "calendar", calendar_type)
            calendar_display_name = calendar_names.get(calendar_type, calendar_type)
            await callback_query.message.edit_text(
                self.t(lang, "calendar_changed").format(calendar=calendar_display_name)
            )
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_calendar_selection for user {user_id}: {e}")
            await callback_query.answer()

    async def handle_setup_calendar_selection(self, callback_query: CallbackQuery):
        """Handle calendar selection during initial setup"""
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            calendar_type = callback_query.data.replace("setup_calendar_", "")
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            # Set the calendar type
            self.storage.update_setting(user_id, "calendar", calendar_type)
            
            # Mark setup as complete
            self.storage.update_setting(user_id, "setup_complete", True)
            
            calendar_names = {
                "shamsi": self.t(lang, "calendar_shamsi"),
                "miladi": self.t(lang, "calendar_miladi"),
                "qamari": self.t(lang, "calendar_qamari")
            }
            calendar_display_name = calendar_names.get(calendar_type, calendar_type)
            
            # Complete setup and show main menu
            await callback_query.message.edit_text(
                f"✅ {self.t(lang, 'calendar_changed').format(calendar=calendar_display_name)}\n\n"
                f"🎉 {self.t(lang, 'setup_complete')}"
            )
            
            kb = MenuFactory.create_main_menu(lang, self.t, self.admin_handler.is_admin(user_id) if self.admin_handler else False)
            await callback_query.message.answer(self.t(lang, "menu"), reply_markup=kb)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_setup_calendar_selection for user {user_id}: {e}")
            await callback_query.answer()