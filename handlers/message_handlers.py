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
from utils.timezone_manager import TimezoneManager
from utils.menu_factory import MenuFactory
from utils.update_checker import UpdateChecker
from utils.comprehensive_logger import ComprehensiveLogger
from utils.state_manager import StateManager, StateType

logger = logging.getLogger(__name__)

class ReminderMessageHandler(IMessageHandler):
    def __init__(self, storage, db, ai, repeat_handler, locales, session, config, admin_handler=None):
        self.storage = storage
        self.db = db
        self.ai = ai
        self.repeat_handler = repeat_handler
        self.locales = locales
        self.session = session
        self.config = config
        self.admin_handler = admin_handler
        self.user_request_times = {}
        self.user_message_count = {}
        self.state_manager = StateManager(config.state_timeout_seconds)
        self.date_converter = DateConverter()
        self.update_checker = UpdateChecker(storage, db)
        self.comp_logger = ComprehensiveLogger()
        

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
            data = self.storage.secure_load(user_id)
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
    
    def clear_all_user_states(self, user_id: int) -> None:
        self.state_manager.clear_all_states(user_id)
        if hasattr(self.session, 'editing_reminders'):
            self.session.editing_reminders.pop(user_id, None)

    def get_button_action(self, message_text, user_lang):
        button_mappings = {
            "btn_list": "list",
            "btn_delete": "delete",
            "btn_edit": "edit",
            "btn_new": "new",
            "btn_settings": "settings",
            "btn_stats": "stats",
            "btn_admin": "admin",
            "btn_today": "today"
        }
        admin_button_mappings = {
            "admin_export_logs": "admin_export_logs"
        }
        for key, action in button_mappings.items():
            if message_text == self.t(user_lang, key):
                return action
        for key, action in admin_button_mappings.items():
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
            data = self.storage.secure_load(user_id)
            lang = data["settings"]["language"]
        except ValueError:
            await message.answer(self.storage.get_restart_message())
            return
        except Exception:
            lang = "fa"
            
        try:
            # Check and clear expired states first
            self.state_manager.clear_expired_states(user_id)
            
            update_sent = await self.update_checker.send_update_notification_if_needed(message, user_id, lang, self.t)
            if update_sent:
                return
            
            # Modern state checking with automatic timeout
            if self.state_manager.has_state(user_id, StateType.WAITING_FOR_CITY):
                await self.handle_city_input(message)
                return
            
            
            # Check if admin is waiting for reminder ID
            if self.admin_handler and hasattr(self.admin_handler, 'log_export_manager'):
                if await self.admin_handler.log_export_manager.handle_reminder_id_input(message):
                    return
            if user_id in self.session.editing_reminders:
                if message.text == self.t(lang, "exit_edit"):
                    await self.handle_exit_edit_text(message, lang)
                    return
                else:
                    await self.handle_edit_input(message)
                    return
            
            if self.db.needs_start_after_restart(user_id):
                await message.answer(self.t(lang, "update_notification"))
                return
            
            button_action = self.get_button_action(message.text, lang)
            if button_action:
                # Clear states when user starts new action
                self.clear_all_user_states(user_id)
                
                if button_action == "admin_export_logs":
                    if self.admin_handler and self.admin_handler.is_admin(user_id):
                        await self.admin_handler.handle_admin_button(message)
                        return
                    else:
                        await message.answer(self.t(lang, "access_denied"))
                        return
                await self.handle_button_action(message, button_action, lang)
                return
            
            user_reminders = self.db.list(user_id)
            if self.config.max_reminders_per_user > 0 and len(user_reminders) >= self.config.max_reminders_per_user:
                await message.answer(self.t(lang, "max_reminders_reached").format(max=self.config.max_reminders_per_user))
                return
            logger.info(f"Parsing text for user {user_id}: {message.text}")
            user_calendar = data["settings"].get("calendar", "miladi")
            try:
                chat = await message.bot.get_chat(user_id)
                user_name = chat.first_name or "Unknown"
                username = chat.username or "Unknown"
            except:
                user_name = "Unknown"
                username = "Unknown"
            
            self.comp_logger.log_event("message_received", user_id, user_name, username,
                                     event_data={"message_text": message.text, "language": lang, "calendar": user_calendar})
            
            parsed = await self.ai.parse(lang, data["settings"]["timezone"], message.text, user_calendar, user_id, user_name, username)
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
                await message.answer(error_message, parse_mode="HTML", disable_web_page_preview=True)
                return
                
            parsed["original_message"] = message.text
            self.session.pending[user_id] = parsed
            self.session.pending_cleanup_time[user_id] = datetime.datetime.now() + datetime.timedelta(minutes=10)
            await self.handle_parsed_reminder(message, parsed, lang)
            if not self.update_checker.config.force_update_notification:
                self.storage.update_last_activity(user_id)
        except PermissionError:
            await message.answer(self.storage.get_restart_message())
            return
        except Exception as e:
            logger.error(f"Error in handle_message for user {user_id}: {e}")

    async def handle_callback(self, callback: CallbackQuery) -> None:
        user_id = callback.from_user.id
        if not self.rate_limit_check(user_id):
            await self.handle_rate_limit(callback)
            return
        try:
            data = self.storage.secure_load(user_id)
        except ValueError:
            await message.answer(self.storage.get_restart_message())
            return
        except Exception:
            return
        try:
            lang = data["settings"]["language"]
        except Exception as e:
            logger.error(f"Error in handle_callback for user {user_id}: {e}")
            await callback.answer()
            return
        await callback.answer()

    async def handle_city_input(self, message: Message):
        user_id = message.from_user.id
        if not self.db.is_valid_user(user_id, self.storage):
            await message.answer("لطفا جهت دریافت آپدیت ربات با ارسال دستور /start ربات را مجدد راه اندازی کنید🙏")
            return
        try:
            lang = self.storage.secure_load(user_id)["settings"]["language"]
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
            kb = MenuFactory.create_timezone_confirmation_keyboard(lang, self.t, timezone)
            user_data = self.storage.secure_load(user_id)
            if user_id in self.waiting_for_city and self.db.is_in_setup(user_id, self.storage):
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
            data = self.storage.secure_load(user_id)
        except ValueError:
            await message.answer(self.storage.get_restart_message())
            return
        except Exception:
            return
        try:
            lang = data["settings"]["language"]
            reminder_id = self.session.editing_reminders[user_id] 
            user_reminders = self.db.list(user_id)
            current_reminder = None
            for reminder_tuple in user_reminders:
                rid, cat, content, utc_time, tz, repeat, status = reminder_tuple
                if rid == reminder_id:
                    current_reminder = {
                        "id": rid,
                        "category": cat,
                        "content": content,
                        "time": utc_time,  # Keep UTC time for AI processing
                        "timezone": tz,
                        "repeat": repeat
                    }
                    break
            
            if not current_reminder:
                await message.answer(self.t(lang, "reminder_not_found"))
                self.session.editing_reminders.pop(user_id, None)
                return
            edit_result = await self.ai.parse_edit(current_reminder, message.text, data["settings"]["timezone"], user_id)
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
            
            kb = MenuFactory.create_confirm_cancel_keyboard(lang, self.t)
            
            calendar_type = data["settings"].get("calendar", "miladi")
            utc_time = edit_result.get("time", current_reminder["time"])
            display_time = TimezoneManager.format_for_display(utc_time, data['settings']['timezone'], calendar_type, lang)
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
            kb = MenuFactory.create_main_menu(lang, self.t, self.admin_handler.is_admin(user_id) if self.admin_handler else False)
            
            await message.answer(self.t(lang, "edit_cancelled"), reply_markup=kb)
            
        except Exception as e:
            logger.error(f"Error in handle_exit_edit_text for user {user_id}: {e}")

    async def get_timezone_from_city(self, city_name: str, user_lang: str):
        try:
            prompt = self.ai.prompt_manager.get_prompt_with_params("timezone_detection", city_name=city_name, user_lang=user_lang)
            result = await self.ai.parse_timezone(prompt)
            return result
        except Exception as e:
            logger.error(f"Error getting timezone for {city_name}: {e}")
            return None

    async def handle_parsed_reminder(self, message: Message, parsed: Dict[str, Any], lang: str):
        user_id = message.from_user.id
        if not self.db.is_valid_user(user_id, self.storage):
            await message.answer("لطفا جهت دریافت آپدیت ربات با ارسال دستور /start ربات را مجدد راه اندازی کنید🙏")
            return
        data = self.storage.secure_load(user_id)
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
                display_time = TimezoneManager.format_for_display(reminder['time'], data['settings']['timezone'], calendar_type, lang)
                age_suffix = ""
                try:
                    if reminder.get('category') == 'birthday' and reminder.get('specific_date'):
                        specific_date = reminder.get('specific_date')
                        if specific_date.get('year') is not None:
                            from utils.date_parser import DateParser
                            dp = DateParser()
                            birth_dt = dp.convert_to_gregorian(specific_date)
                            if birth_dt:
                                scheduled_dt = datetime.datetime.strptime(reminder['time'], "%Y-%m-%d %H:%M")
                                age_years = scheduled_dt.year - birth_dt.year - ((scheduled_dt.month, scheduled_dt.day) < (birth_dt.month, birth_dt.day))
                                age_suffix = self.t(lang, "age_suffix", years=age_years)
                except Exception:
                    age_suffix = ""
                summary_lines.append(f"{i}. {reminder['content']} @ {display_time} ({category_text}{age_suffix}) - {repeat_text}")
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
            display_time = TimezoneManager.format_for_display(parsed['time'], data['settings']['timezone'], calendar_type, lang)
            summary_prefix = self.t(lang, 'summary')
            summary = f"{summary_prefix}: {parsed['content']} @ {display_time} ({category_text}) - {repeat_text}"
        kb = MenuFactory.create_confirm_cancel_keyboard(lang, self.t)
        await message.answer(summary, reply_markup=kb)
