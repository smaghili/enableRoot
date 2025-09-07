from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import Dict, Any
import logging
import time
import datetime
import json
from config.config import Config
# Removed IMessageHandler import - not needed
from utils.date_converter import DateConverter
from utils.timezone_manager import TimezoneManager
from utils.menu_factory import MenuFactory
from utils.update_checker import UpdateChecker
from utils.comprehensive_logger import ComprehensiveLogger
try:
    import jdatetime
except ImportError:
    jdatetime = None
logger = logging.getLogger(__name__)

def validate_user(func):
    async def wrapper(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        try:
            self.storage.secure_load(user_id)
        except ValueError as e:
            logger.warning(f"User validation failed for user {user_id}: {e}")
            await callback_query.answer(self.storage.get_restart_message(), show_alert=True)
            return
        except Exception as e:
            logger.error(f"Unexpected error in validate_user for user {user_id}: {e}")
            await callback_query.answer()
            return
        return await func(self, callback_query)
    return wrapper
class ReminderCallbackHandler:
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
        self.update_checker = UpdateChecker(storage)
        self.comp_logger = ComprehensiveLogger()
    
    def t(self, lang, key):
        return self.locales.get(lang, self.locales["en"]).get(key, key)
    def _calculate_correct_time(self, reminder_data: dict, user_calendar: str, user_timezone: str = "+03:30") -> str:
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
                local_time_str = f"{gregorian_date.year}-{gregorian_date.month:02d}-{gregorian_date.day:02d} {now.hour:02d}:{now.minute:02d}"
                from utils.timezone_manager import TimezoneManager
                utc_time = TimezoneManager.local_to_utc(local_time_str, user_timezone)
                return utc_time.strftime("%Y-%m-%d %H:%M")
            else:
                current_day = now.day
                if target_day <= current_day:
                    if now.month == 12:
                        next_month = now.replace(year=now.year + 1, month=1, day=target_day)
                    else:
                        next_month = now.replace(month=now.month + 1, day=target_day)
                else:
                    next_month = now.replace(day=target_day)
                from utils.timezone_manager import TimezoneManager
                utc_time = TimezoneManager.local_to_utc(next_month.strftime("%Y-%m-%d %H:%M"), user_timezone)
                return utc_time.strftime("%Y-%m-%d %H:%M")
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
            data = self.storage.secure_load(user_id)
            lang = data["settings"]["language"]
            rate_limit_msg = self.t(lang, "rate_limit_exceeded")
            await callback.answer(rate_limit_msg, show_alert=True)
        except Exception as e:
            logger.error(f"Error in handle_rate_limit: {e}")
    
    async def handle_message(self, message) -> None:
        return
    
    async def handle_callback(self, callback: CallbackQuery) -> None:
        user_id = callback.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback)
            return
        
        setup_callbacks = ["setup_lang_", "setup_calendar_", "confirm_tz_"]
        is_setup_callback = any(callback.data.startswith(prefix) for prefix in setup_callbacks)
        is_new_user = self.db.is_new_user(user_id)
        
        if is_setup_callback:
            if callback.data.startswith("setup_lang_"):
                await self.handle_setup_language_selection(callback)
                return
            elif callback.data.startswith("setup_calendar_"):
                await self.handle_setup_calendar_selection(callback)
                return
            elif callback.data.startswith("confirm_tz_"):
                await self.handle_timezone_confirmation(callback)
                return
        
        try:
            data = self.storage.secure_load(user_id)
            lang = data["settings"]["language"]
            
            is_new_user_check = self.db.is_new_user(user_id)
            if not is_new_user_check:
                update_sent = await self.update_checker.send_update_notification_if_needed(callback, user_id, lang, self.t)
                if update_sent:
                    await callback.answer()
                    return
            if not self.update_checker.config.force_update_notification:
                self.storage.update_last_activity(user_id)
            
        except ValueError as e:
            logger.warning(f"User validation failed in handle_callback for user {user_id}: {e}")
            await callback.answer(self.storage.get_restart_message(), show_alert=True)
            return
        except PermissionError as e:
            logger.warning(f"Permission denied in handle_callback for user {user_id}: {e}")
            await callback.answer(self.storage.get_restart_message(), show_alert=True)
            return
        except Exception as e:
            logger.error(f"Unexpected error in handle_callback for user {user_id}: {e}")
            await callback.answer()
            return
        
        if not is_setup_callback and not is_new_user and self.db.needs_start_after_restart(user_id):
            await callback.answer(self.t(lang, "update_notification"), show_alert=True)
            return
        
        if callback.data.startswith("lang_"):
            await self.handle_language_selection(callback)
        elif callback.data == "change_lang":
            await self.handle_change_language(callback)
        elif callback.data == "change_tz":
            await self.handle_change_timezone(callback)
        elif callback.data == "cancel_tz":
            await self.handle_timezone_cancel(callback)
        elif callback.data == "change_calendar":
            await self.handle_change_calendar(callback)
        elif callback.data.startswith("calendar_"):
            await self.handle_calendar_selection(callback)
        elif callback.data.startswith(("stop_", "paid_", "taken_")):
            await self.handle_reminder_actions(callback)
        elif callback.data.startswith("delete_confirm_"):
            await self.handle_delete_confirmation(callback)
        elif callback.data.startswith("edit_select_"):
            await self.handle_edit_selection(callback)
        elif callback.data == "exit_edit":
            await self.handle_exit_edit(callback)
        elif callback.data in ["confirm", "cancel"]:
            await self.handle_confirm_cancel(callback)
        else:
            await callback.answer()
            
    async def handle_setup_language_selection(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang_code = callback_query.data.split("_")[2]
            if lang_code in self.locales:
                # Record user start now that they've selected a language
                self.db.record_user_start(user_id)
                data = self.storage.secure_load(user_id)
                data["settings"]["language"] = lang_code
                data["settings"].pop("calendar", None)
                self.storage.save(user_id, data)
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
    @validate_user
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
    @validate_user
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
            lang = self.storage.secure_load(user_id)["settings"]["language"]
            await callback_query.message.edit_text(self.t(lang, "choose_language"), reply_markup=kb)
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_change_language for user {user_id}: {e}")
            await callback_query.answer()
    @validate_user
    async def handle_change_timezone(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.secure_load(user_id)["settings"]["language"]
            self.message_handler.waiting_for_city[user_id] = True
            await callback_query.message.edit_text(self.t(lang, "enter_city_name"))
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_change_timezone for user {user_id}: {e}")
            await callback_query.answer()
    @validate_user
    async def handle_timezone_confirmation(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            timezone = callback_query.data.replace("confirm_tz_", "")
            data = self.storage.secure_load(user_id)
            lang = data["settings"]["language"]
            self.storage.update_setting(user_id, "timezone", timezone)
            is_in_setup = self.db.is_in_setup(user_id, self.storage)
            if is_in_setup:
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
    @validate_user
    async def handle_timezone_cancel(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        try:
            lang = self.storage.secure_load(user_id)["settings"]["language"]
            is_new_user = self.db.is_new_user(user_id)
            if is_new_user:
                await callback_query.message.edit_text(self.t(lang, "timezone_cancelled"))
                self.message_handler.waiting_for_city[user_id] = True
            else:
                await callback_query.message.edit_text(self.t(lang, "timezone_cancelled"))
            
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in handle_timezone_cancel for user {user_id}: {e}")
            await callback_query.answer()
    @validate_user
    async def handle_reminder_actions(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.secure_load(user_id)["settings"]["language"]
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
                        # Get original reminder content
                        original_reminder = self.db.get_reminder_for_log(reminder_id)
                        if original_reminder:
                            original_content = original_reminder[3]  # index 3 is content
                            with self.db.lock:
                                cur = self.db.conn.cursor()
                                cur.execute(
                                    "UPDATE reminders SET status='cancelled' WHERE category='installment_retry' AND content LIKE ?",
                                    (f"%{original_content}%",)
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
    @validate_user
    async def handle_delete_confirmation(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.secure_load(user_id)["settings"]["language"]
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
        try:
            chat = await callback_query.bot.get_chat(user_id)
            user_name = chat.first_name or "Unknown"
            username = chat.username or "Unknown"
        except:
            user_name = "Unknown"
            username = "Unknown"
        
        reminder_content = next((r[2] for r in user_reminders if r[0] == reminder_id), "Unknown")
        
        self.db.update_status(reminder_id, "cancelled")
        self.comp_logger.log_event("reminder_deleted", user_id, user_name, username, reminder_id,
                                 event_data={"content": reminder_content, "method": "user_action"})
        
        await callback_query.message.edit_text(self.t(lang, "reminder_deleted").format(id=reminder_id))
        await callback_query.answer(self.t(lang, "delete_confirmed"))
    @validate_user
    async def handle_edit_selection(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.secure_load(user_id)["settings"]["language"]
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
    @validate_user
    async def handle_confirm_cancel(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            data = self.storage.secure_load(user_id)
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
                try:
                    chat = await callback_query.bot.get_chat(user_id)
                    user_name = chat.first_name or "Unknown"
                    username = chat.username or "Unknown"
                except:
                    user_name = "Unknown"
                    username = "Unknown"
                
                self.db.update_reminder(
                    reminder_id,
                    edit_result.get("category", original["category"]),
                    edit_result.get("content", original["content"]),
                    edit_result.get("time", original["time"]),
                    edit_result.get("timezone", original["timezone"]),
                    edit_result.get("repeat", original["repeat"])
                )
                
                self.comp_logger.log_event("reminder_edited", user_id, user_name, username, reminder_id,
                                         event_data={"old_content": original["content"], 
                                                   "new_content": edit_result.get("content", original["content"]),
                                                   "old_time": original["time"],
                                                   "new_time": edit_result.get("time", original["time"])})
                
                self.session.editing_reminders.pop(user_id, None)
                repeat_value = edit_result.get("repeat", original["repeat"])
                if isinstance(repeat_value, dict):
                    import json
                    repeat_value = json.dumps(repeat_value)
                repeat_pattern = self.repeat_handler.from_json(repeat_value)
                repeat_text = self.repeat_handler.get_display_text(repeat_pattern, lang)
                kb = MenuFactory.create_main_menu(lang, self.message_handler.t, self.admin_handler.is_admin(user_id) if self.admin_handler else False)
                calendar_type = data["settings"].get("calendar", "miladi")
                utc_time = edit_result.get("time", original["time"])
                display_time = TimezoneManager.format_for_display(utc_time, data['settings']['timezone'], calendar_type)
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
                original_message = pending_data.get("original_message", "")
                for reminder in pending_data["reminders"]:
                    reminder_data = {
                        "category": reminder.get("category", self.config.default_category),
                        "content": reminder.get("content", "")[:self.config.max_reminder_length],
                        "time": reminder.get("time"),
                        "timezone": reminder.get("timezone", self.config.default_timezone),
                        "repeat": reminder.get("repeat", self.config.default_repeat)
                    }
                    reminder_data["time"] = reminder_data["time"]
                    meta = None
                    try:
                        meta_data = {}
                        # Add birthday data if applicable
                        if reminder.get("category") == "birthday" and reminder.get("specific_date"):
                            from utils.date_parser import DateParser
                            dp = DateParser()
                            birth_dt = dp.convert_to_gregorian(reminder.get("specific_date"))
                            if birth_dt:
                                meta_data["birthdate_gregorian"] = birth_dt.strftime("%Y-%m-%d")
                        
                        if meta_data:
                            meta = json.dumps(meta_data)
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
                    
                    try:
                        chat = await callback_query.bot.get_chat(user_id)
                        user_name = chat.first_name or "Unknown"
                        username = chat.username or "Unknown"
                    except:
                        user_name = "Unknown"
                        username = "Unknown"
                    
                    self.comp_logger.log_event("reminder_created", user_id, user_name, username, reminder_id,
                                             event_data={"category": reminder_data["category"], "content": reminder_data["content"], 
                                                       "time": reminder_data["time"], "repeat": reminder_data["repeat"]})
                    
                    if self.log_manager:
                        await self.log_manager.send_reminder_log(
                            reminder_id, user_id, reminder_data["category"], 
                            reminder_data["content"], "created", "", 
                            reminder_data["content"]
                        )
                    created_count += 1
                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer(self.t(lang, "multiple_reminders_saved").format(count=created_count))
            else:
                calendar_type = data["settings"].get("calendar", "miladi")
                original_message = pending_data.get("original_message", "")
                reminder_data = {
                    "category": pending_data.get("category", self.config.default_category),
                    "content": pending_data.get("content", "")[:self.config.max_reminder_length],
                    "time": pending_data.get("time"),
                    "timezone": pending_data.get("timezone", self.config.default_timezone),
                    "repeat": pending_data.get("repeat", self.config.default_repeat)
                }
                reminder_data["time"] = reminder_data["time"]
                meta = None
                try:
                    meta_data = {}
                    # Add birthday data if applicable
                    if pending_data.get("category") == "birthday" and pending_data.get("specific_date"):
                        from utils.date_parser import DateParser
                        dp = DateParser()
                        birth_dt = dp.convert_to_gregorian(pending_data.get("specific_date"))
                        if birth_dt:
                            meta_data["birthdate_gregorian"] = birth_dt.strftime("%Y-%m-%d")
                    
                    if meta_data:
                        meta = json.dumps(meta_data)
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
                
                try:
                    chat = await callback_query.bot.get_chat(user_id)
                    user_name = chat.first_name or "Unknown"
                    username = chat.username or "Unknown"
                except:
                    user_name = "Unknown"
                    username = "Unknown"
                
                self.comp_logger.log_event("reminder_created", user_id, user_name, username, reminder_id,
                                         event_data={"category": reminder_data["category"], "content": reminder_data["content"], 
                                                   "time": reminder_data["time"], "repeat": reminder_data["repeat"]})
                
                if self.log_manager:
                    await self.log_manager.send_reminder_log(
                        reminder_id, user_id, reminder_data["category"], 
                        reminder_data["content"], "created", "", 
                        reminder_data["content"]
                    )

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
                        reply_markup=cancel_kb,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                else:
                    await callback_query.message.edit_reply_markup(reply_markup=None)
                    await callback_query.message.answer(self.t(lang, "ask_more"), parse_mode="HTML", disable_web_page_preview=True)
            else:
                await callback_query.message.edit_reply_markup(reply_markup=None)
                await callback_query.message.answer(self.t(lang, "ask_more"), parse_mode="HTML", disable_web_page_preview=True)
        await callback_query.answer()
    @validate_user
    async def handle_exit_edit(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        try:
            data = self.storage.secure_load(user_id)
            lang = data["settings"]["language"]
            self.session.editing_reminders.pop(user_id, None)
            if user_id in self.session.pending:
                self.session.pending.pop(user_id)
            from utils.menu_factory import MenuFactory
            kb = MenuFactory.create_main_menu(lang, self.message_handler.t, self.admin_handler.is_admin(user_id))
            await callback_query.message.answer(self.t(lang, "edit_cancelled"), reply_markup=kb)
        except Exception as e:
            logger.error(f"Error in handle_exit_edit for user {user_id}: {e}")
        await callback_query.answer()
    @validate_user
    async def handle_change_calendar(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            lang = self.storage.secure_load(user_id)["settings"]["language"]
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
    @validate_user
    async def handle_calendar_selection(self, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback_query)
            return
        try:
            calendar_type = callback_query.data.replace("calendar_", "")
            data = self.storage.secure_load(user_id)
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
            data = self.storage.secure_load(user_id)
            lang = data["settings"]["language"]
            
            # Set the calendar type
            self.storage.update_setting(user_id, "calendar", calendar_type)
            
            
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