import asyncio
import datetime
import logging
import os
from typing import Optional
from repeat_handler import RepeatHandler


class ReminderScheduler:
    def __init__(self, db, json_storage, bot):
        self.db = db
        self.json_storage = json_storage
        self.bot = bot
        self.task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.processing_semaphore = asyncio.Semaphore(30)
        self.logger = logging.getLogger(__name__)
        self.repeat_handler = RepeatHandler()
        self._load_locales()
        
    def _load_locales(self):
        self.locales = {}
        base_path = os.path.dirname(__file__)
        locale_dir = os.path.join(base_path, "localization")
        
        if os.path.exists(locale_dir):
            for filename in os.listdir(locale_dir):
                if filename.endswith('.json'):
                    lang_code = filename.split('.')[0]
                    try:
                        import json
                        with open(os.path.join(locale_dir, filename), 'r', encoding='utf-8') as f:
                            self.locales[lang_code] = json.load(f)
                    except (json.JSONDecodeError, IOError) as e:
                        self.logger.error(f"Failed to load locale {filename}: {e}")
                        
    def t(self, lang: str, key: str, **kwargs) -> str:
        text = self.locales.get(lang, self.locales.get('en', {})).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                return text
        return text

    def start(self):
        self.task = asyncio.get_event_loop().create_task(self._loop())
        self.cleanup_task = asyncio.get_event_loop().create_task(self._cleanup_loop())

    async def _loop(self):
        while True:
            try:
                now = datetime.datetime.utcnow()
                due_reminders = self.db.due(now, limit=500)
                
                if due_reminders:
                    self.logger.info(f"Processing {len(due_reminders)} due reminders")
                    tasks = []
                    for rid, uid, cat, content, time_str, tz, repeat in due_reminders:
                        if self._validate_reminder_data(rid, uid, cat, content, time_str, repeat):
                            task = self._process_reminder(rid, uid, cat, content, time_str, repeat)
                            tasks.append(task)
                    
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for i, result in enumerate(results):
                            if isinstance(result, Exception):
                                self.logger.error(f"Task {i} failed: {result}")
                
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)
                
    def _validate_reminder_data(self, rid, uid, cat, content, time_str, repeat) -> bool:
        if not all([rid, uid, cat, content, time_str, repeat]):
            self.logger.warning(f"Invalid reminder data: {rid}, {uid}, {cat}, {content}, {time_str}, {repeat}")
            return False
        if not isinstance(rid, int) or not isinstance(uid, int):
            self.logger.warning(f"Invalid ID types: rid={type(rid)}, uid={type(uid)}")
            return False
        if len(str(content)) > 1000:
            self.logger.warning(f"Content too long for reminder {rid}")
            return False
        return True

    async def _process_reminder(self, rid, uid, cat, content, time_str, repeat):
        async with self.processing_semaphore:
            try:
                await self._send_reminder(rid, uid, cat, content, repeat)
                if repeat == "none":
                    self.db.update_status(rid, "completed")
                    self.logger.info(f"Completed one-time reminder {rid} for user {uid}")
                else:
                    # Get timezone for this reminder
                    cur = self.db.conn.cursor()
                    cur.execute("select timezone from reminders where id=?", (rid,))
                    row = cur.fetchone()
                    cur.close()

                    tz = row[0] if row else "+00:00"
                    new_time = self._next_time(time_str, repeat, tz)
                    if new_time:
                        self.db.update_time(rid, new_time)
                        self.logger.info(f"Updated recurring reminder {rid} to {new_time}")
                    else:
                        self.logger.error(f"Failed to calculate next time for reminder {rid}")
                        self.db.update_status(rid, "cancelled")
            except Exception as e:
                self.logger.error(f"Error processing reminder {rid}: {e}")
                try:
                    self.db.update_status(rid, "cancelled")
                except Exception as db_error:
                    self.logger.error(f"Failed to cancel reminder {rid}: {db_error}")

    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(3600)
                deleted = self.db.cleanup_old_reminders(30)
                if deleted > 0:
                    self.logger.info(f"Cleaned up {deleted} old reminders")
                    
                stats = self.db.get_stats()
                if stats:
                    self.logger.info(f"Database stats - Total: {stats[0]}, Active: {stats[1]}, Users: {stats[4]}")
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")

    async def _send_reminder(self, rid, uid, category, content, repeat):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        try:
            user_lang = self.json_storage.get_user_language(uid)
            safe_content = str(content)[:500] if content else "No content"
        except Exception as e:
            self.logger.error(f"Error getting user language for {uid}: {e}")
            user_lang = "en"
            safe_content = str(content)[:500] if content else "No content"
        
        try:
            if category == "birthday":
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(self.t(user_lang, "reminder_stopped"), 
                                          callback_data=f"stop_{rid}"))
                await self.bot.send_message(uid, f"🎂 {safe_content}", reply_markup=kb)
            
            elif category == "birthday_pre_week":
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(self.t(user_lang, "reminder_stopped"), 
                                          callback_data=f"stop_{rid}"))
                message_text = self.t(user_lang, "birthday_week_before", content=safe_content)
                await self.bot.send_message(uid, message_text, reply_markup=kb)
            
            elif category == "birthday_pre_three":
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(self.t(user_lang, "reminder_stopped"), 
                                          callback_data=f"stop_{rid}"))
                message_text = self.t(user_lang, "birthday_three_days_before", content=safe_content)
                await self.bot.send_message(uid, message_text, reply_markup=kb)
            
            elif category == "installment":
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(self.t(user_lang, "payment_recorded"), 
                                          callback_data=f"paid_{rid}"))
                kb.add(InlineKeyboardButton(self.t(user_lang, "reminder_stopped"), 
                                          callback_data=f"stop_{rid}"))
                await self.bot.send_message(uid, f"💳 {safe_content}", reply_markup=kb)
            
            elif category == "installment_followup":
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(self.t(user_lang, "payment_recorded"), 
                                          callback_data=f"paid_{rid}"))
                kb.add(InlineKeyboardButton(self.t(user_lang, "reminder_stopped"), 
                                          callback_data=f"stop_{rid}"))
                message_text = self.t(user_lang, "installment_reminder", content=safe_content)
                await self.bot.send_message(uid, message_text, reply_markup=kb)
            
            elif category == "medicine":
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(self.t(user_lang, "medicine_taken"), 
                                          callback_data=f"taken_{rid}"))
                await self.bot.send_message(uid, f"💊 {safe_content}", reply_markup=kb)
            
            else:
                await self.bot.send_message(uid, f"⏰ {safe_content}")
                
        except Exception as e:
            self.logger.error(f"Error sending reminder {rid} to user {uid}: {e}")
            raise

    def _next_time(self, time_str: str, repeat: str, timezone: str = "+00:00") -> Optional[str]:
        try:
            # time_str is already in local time (converted from UTC in due() method)
            dt_local = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")

            repeat_pattern = self.repeat_handler.from_json(repeat)
            next_dt_local = self.repeat_handler.calculate_next_time(dt_local, repeat_pattern)

            if next_dt_local:
                return next_dt_local.strftime("%Y-%m-%d %H:%M")
            else:
                return None

        except (ValueError, TypeError) as e:
            self.logger.error(f"Error calculating next time for {time_str}, {repeat}: {e}")
            return None

    def stop(self):
        self.logger.info("Stopping reminder scheduler")
        if self.task and not self.task.done():
            self.task.cancel()
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()