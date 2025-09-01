import asyncio
import datetime
import logging
import os
from typing import Optional
from handlers.repeat_handler import RepeatHandler
from config.interfaces import IScheduler, INotificationService
from services.notification_strategies import NotificationContext, NotificationStrategyFactory
from services.reminder_types import ReminderFactory


class ReminderScheduler(IScheduler):
    def __init__(self, db, json_storage, bot, notification_context: Optional[NotificationContext] = None):
        self.db = db
        self.json_storage = json_storage
        self.bot = bot
        self.task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.processing_semaphore = asyncio.Semaphore(30)
        self.logger = logging.getLogger(__name__)
        self.repeat_handler = RepeatHandler()
        self.reminder_factory = ReminderFactory()
        
        # Use dependency injection for notification strategy
        self.notification_context = notification_context or NotificationContext(
            NotificationStrategyFactory.create("standard")
        )
        
        self._load_locales()
        
    def _load_locales(self):
        self.locales = {}
        base_path = os.path.dirname(os.path.dirname(__file__))  # Go up one level from services/
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
                # Check if database connection is still open
                try:
                    with self.db.lock:
                        self.db.conn.execute("SELECT 1")
                except Exception as e:
                    self.logger.error(f"Database connection lost: {e}")
                    break
                    
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
                
                # Handle installment special case
                if cat == "installment":
                    await self._handle_installment_reminder(rid, uid, time_str, repeat)
                elif repeat == "none":
                    self.db.update_status(rid, "completed")
                    self.logger.info(f"Completed one-time reminder {rid} for user {uid}")
                else:
                    # Get timezone for this reminder
                    try:
                        with self.db.lock:
                            cur = self.db.conn.cursor()
                            cur.execute("select timezone from reminders where id=?", (rid,))
                            row = cur.fetchone()
                            cur.close()
                        tz = row[0] if row else "+00:00"
                    except Exception as e:
                        self.logger.error(f"Error getting timezone for reminder {rid}: {e}")
                        tz = "+00:00"
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

    async def _handle_installment_reminder(self, rid, uid, time_str, repeat):
        """Handle special logic for installment reminders - repeat for 3 days if not paid"""
        try:
            # Check how many times this installment has been sent
            with self.db.lock:
                cur = self.db.conn.cursor()
                cur.execute(
                    "select count(*) from reminders where user_id=? and category='installment_retry' and content like ?",
                    (uid, f"%{rid}%")
                )
                retry_count = cur.fetchone()[0] if cur.fetchone() else 0
                cur.close()
            
            if retry_count < 3:
                # Create retry reminder for next day
                dt_local = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                next_day = dt_local + datetime.timedelta(days=1)
                
                # Add retry reminder
                self.db.add(
                    uid,
                    "installment_retry", 
                    f"Retry #{retry_count + 1} for reminder {rid}",
                    next_day.strftime("%Y-%m-%d %H:%M"),
                    "+00:00",  # Will be converted properly
                    '{"type": "none"}'
                )
                self.logger.info(f"Created installment retry {retry_count + 1} for reminder {rid}")
            else:
                # After 3 retries, continue with normal recurring pattern
                if repeat != "none":
                    new_time = self._next_time(time_str, repeat, "+00:00")
                    if new_time:
                        self.db.update_time(rid, new_time)
                        self.logger.info(f"Updated installment reminder {rid} to next cycle: {new_time}")
                    else:
                        self.db.update_status(rid, "cancelled")
                else:
                    self.db.update_status(rid, "completed")
                    
        except Exception as e:
            self.logger.error(f"Error handling installment reminder {rid}: {e}")

    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(3600)
                
                # Check if database connection is still open
                try:
                    with self.db.lock:
                        self.db.conn.execute("SELECT 1")
                except Exception as e:
                    self.logger.error(f"Database connection lost in cleanup: {e}")
                    break
                    
                deleted = self.db.cleanup_old_reminders(30)
                if deleted > 0:
                    self.logger.info(f"Cleaned up {deleted} old reminders")
                    
                stats = self.db.get_stats()
                if stats:
                    self.logger.info(f"Database stats - Total: {stats[0]}, Active: {stats[1]}, Users: {stats[4]}")
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")

    async def _send_reminder(self, rid, uid, category, content, repeat):
        try:
            user_lang = self.json_storage.get_user_language(uid)
            safe_content = str(content)[:500] if content else "No content"
        except Exception as e:
            self.logger.error(f"Error getting user language for {uid}: {e}")
            user_lang = "en"
            safe_content = str(content)[:500] if content else "No content"
        
        # Prepare reminder data for notification strategy
        reminder_data = {
            'id': rid,
            'category': category,
            'content': safe_content,
            'repeat': repeat
        }
        
        # Use notification strategy to send reminder
        success = await self.notification_context.send_notification(
            self.bot, uid, reminder_data, user_lang, self.t
        )
        
        if not success:
            self.logger.error(f"Failed to send reminder {rid} to user {uid}")
            raise Exception(f"Notification failed for reminder {rid}")

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