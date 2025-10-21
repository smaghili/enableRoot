import asyncio
import datetime
import logging
import os
from typing import Optional
from handlers.repeat_handler import RepeatHandler
from config.interfaces import IScheduler, INotificationService
from services.notification_strategies import NotificationContext, NotificationStrategyFactory
from services.reminder_types import ReminderFactory
from utils.comprehensive_logger import ComprehensiveLogger


class ReminderScheduler(IScheduler):
    def __init__(self, db, json_storage, bot, log_manager=None, notification_context: Optional[NotificationContext] = None):
        self.db = db
        self.json_storage = json_storage
        self.bot = bot
        self.task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.processing_semaphore = asyncio.Semaphore(1)
        self.message_queue = asyncio.Queue()
        self.queue_processor_task = None
        self.logger = logging.getLogger(__name__)
        self.repeat_handler = RepeatHandler()
        self.reminder_factory = ReminderFactory()
        self.notification_context = notification_context or NotificationContext(
            NotificationStrategyFactory.create("standard", log_manager=log_manager)
        )
        self.comp_logger = ComprehensiveLogger()
        self._load_locales()
        
    def _load_locales(self):
        self.locales = {}
        base_path = os.path.dirname(os.path.dirname(__file__))
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
        self.queue_processor_task = asyncio.create_task(self._process_message_queue())
        self.task = asyncio.create_task(self._loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _loop(self):
        while True:
            try:
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
    
    async def _process_message_queue(self):
        while True:
            try:
                message_data = await self.message_queue.get()
                await asyncio.sleep(0.02)  # 50 messages per second for bots
                await self._send_queued_message(message_data)
                self.message_queue.task_done()
            except Exception as e:
                self.logger.error(f"Queue error: {e}")
                await asyncio.sleep(5)
    
    async def _send_queued_message(self, message_data):
        try:
            rid = message_data['rid']
            uid = message_data['uid']
            category = message_data['category']
            content = message_data['content']
            repeat = message_data['repeat']
            
            user_name, username = await self._get_user_info(uid)
            self.comp_logger.log_event("reminder_processing_start", uid, user_name, username, rid,
                                     event_data={"category": category, "content": content})
            
            success = await self._send_reminder_direct(rid, uid, category, content, repeat)
            
            if success:
                self.comp_logger.log_event("reminder_sent", uid, user_name, username, rid,
                                         event_data={"category": category, "content": content})
                await self._handle_post_send_logic(rid, uid, category, content, repeat, message_data.get('time_str', ''))
            else:
                self.logger.warning(f"Failed to send queued reminder {rid} to user {uid}")
                
        except Exception as e:
            self.logger.error(f"Error processing queued message for reminder {rid}: {e}")
    
    async def _send_reminder_direct(self, rid, uid, category, content, repeat):
        try:
            user_lang = self.json_storage.get_user_language(uid)
            safe_content = str(content)[:500] if content else "No content"
        except Exception as e:
            self.logger.error(f"Error getting user language for {uid}: {e}")
            user_lang = "en"
            safe_content = str(content)[:500] if content else "No content"
        
        original_message = ""
        try:
            import sqlite3
            ai_db_path = getattr(self.config, 'ai_database_path', "data/ai_logs.db") if hasattr(self, 'config') else "data/ai_logs.db"
            with sqlite3.connect(ai_db_path) as conn:
                cursor = conn.execute(
                    "SELECT original_message FROM ai_logs WHERE parsed_result LIKE ? AND original_message IS NOT NULL ORDER BY timestamp DESC LIMIT 1",
                    (f'%{safe_content}%',)
                )
                result = cursor.fetchone()
                if result and result[0]:
                    original_message = result[0]
        except Exception as e:
            self.logger.error(f"Error getting original message from AI logs for reminder {rid}: {e}")
        
        effective_category = category
        if category == "birthday":
            effective_category = self._get_birthday_notification_type(rid, uid)
            if effective_category is None:
                self.logger.info(f"Birthday notification already sent for this period, skipping reminder {rid}")
                return True
        
        reminder_data = {
            'id': rid,
            'category': effective_category,
            'content': safe_content,
            'repeat': repeat,
            'original_message': original_message
        }
        
        return await self.notification_context.send_notification(
            self.bot, uid, reminder_data, user_lang, self.t
        )
    
    async def _handle_post_send_logic(self, rid, uid, category, content, repeat, time_str):
        try:
            user_name, username = await self._get_user_info(uid)
            
            if category == "installment":
                await self._handle_installment_reminder(rid, uid, time_str, repeat)
            else:
                repeat_pattern = self.repeat_handler.from_json(repeat)
                if repeat_pattern.type == "none":
                    self.db.update_status(rid, "completed")
                    self.comp_logger.log_event("reminder_completed", uid, user_name, username, rid,
                                             event_data={"reason": "one_time_reminder"})
                    self.logger.info(f"Completed one-time reminder {rid} for user {uid}")
                else:
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
                        self.comp_logger.log_event("reminder_rescheduled", uid, user_name, username, rid,
                                                 event_data={"new_time": new_time, "repeat_pattern": repeat})
                        self.logger.info(f"Updated recurring reminder {rid} to {new_time}")
                    else:
                        self.logger.error(f"Failed to calculate next time for reminder {rid}")
                        self.logger.warning(f"Reminder {rid} will remain active for manual review")
        except Exception as e:
            self.logger.error(f"Error in post-send logic for reminder {rid}: {e}")
                
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

    async def _get_user_info(self, user_id):
        try:
            chat = await self.bot.get_chat(user_id)
            user_name = chat.first_name or "Unknown"
            username = chat.username or "Unknown"
            return user_name, username
        except:
            return "Unknown", "Unknown"

    async def _process_reminder(self, rid, uid, cat, content, time_str, repeat):
        try:
            message_data = {
                'rid': rid,
                'uid': uid,
                'category': cat,
                'content': content,
                'repeat': repeat,
                'time_str': time_str
            }
            await self.message_queue.put(message_data)
        except Exception as e:
            self.logger.error(f"Error queuing reminder {rid}: {e}")
            user_name, username = await self._get_user_info(uid)
            self.comp_logger.log_event("reminder_error", uid, user_name, username, rid,
                                     success=False, error_message=str(e))

    async def _handle_installment_reminder(self, rid, uid, time_str, repeat):
        try:
            original_reminder = self.db.get_reminder_for_log(rid)
            if not original_reminder or original_reminder[7] != "active":
                self.logger.info(f"Skipping retry creation for reminder {rid} - already completed/cancelled")
                return
            
            with self.db.lock:
                cur = self.db.conn.cursor()
                cur.execute(
                    "select count(*) from reminders where user_id=? and category='installment_retry' and content like ?",
                    (uid, f"%{rid}%")
                )
                result = cur.fetchone()
                retry_count = result[0] if result else 0
                
                cur.execute("select timezone from reminders where id=?", (rid,))
                tz_row = cur.fetchone()
                tz = tz_row[0] if tz_row else "+00:00"
                cur.close()
            
            if retry_count < 3:
                dt_local = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                next_day = dt_local + datetime.timedelta(days=1)
                user_data = self.json_storage.secure_load(uid)
                user_lang = user_data.get("settings", {}).get("language", "fa")
                original_reminder = self.db.get_reminder_for_log(rid)
                original_content = original_reminder[3] if original_reminder else f'یادآور {rid}'
                
                self.db.add(
                    uid,
                    "installment_retry", 
                    self.t(user_lang, "retry_reminder", count=retry_count + 1, content=original_content),
                    next_day.strftime("%Y-%m-%d %H:%M"),
                    tz,
                    '{"type": "none"}'
                )
                self.db.update_status(rid, "completed")
                self.comp_logger.log_event("reminder_completed", uid, "System", "System", rid,
                                         event_data={"reason": "installment_retry_created", "retry_count": retry_count + 1})
                self.logger.info(f"Created installment retry {retry_count + 1} for reminder {rid} and marked original as completed")
            else:
                if repeat != "none":
                    new_time = self._next_time(time_str, repeat, tz)
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

    
    def _get_birthday_notification_type(self, rid, uid):
        try:
            with self.db.lock:
                cur = self.db.conn.cursor()
                cur.execute("SELECT time, timezone, meta FROM reminders WHERE id=?", (rid,))
                row = cur.fetchone()
                cur.close()
            
            if not row:
                return "birthday"
            
            time_str, timezone, meta = row
            from utils.timezone_manager import TimezoneManager
            birthday_local = TimezoneManager.utc_to_local(time_str, timezone)
            now_local = TimezoneManager.utc_to_local(
                datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), 
                timezone
            )
            
            days_until_birthday = (birthday_local.date() - now_local.date()).days
            
            import json
            meta_data = {}
            if meta:
                try:
                    meta_data = json.loads(meta)
                except:
                    pass
            
            last_sent = meta_data.get('last_birthday_notification')
            current_year = birthday_local.year
            
            if days_until_birthday == 7 and last_sent != f"{current_year}_week":
                meta_data['last_birthday_notification'] = f"{current_year}_week"
                with self.db.lock:
                    cur = self.db.conn.cursor()
                    cur.execute("UPDATE reminders SET meta=? WHERE id=?", (json.dumps(meta_data), rid))
                    self.db.conn.commit()
                    cur.close()
                return "birthday_pre_week"
            elif days_until_birthday == 3 and last_sent != f"{current_year}_three":
                meta_data['last_birthday_notification'] = f"{current_year}_three"
                with self.db.lock:
                    cur = self.db.conn.cursor()
                    cur.execute("UPDATE reminders SET meta=? WHERE id=?", (json.dumps(meta_data), rid))
                    self.db.conn.commit()
                    cur.close()
                return "birthday_pre_three"
            elif days_until_birthday == 0 and last_sent != f"{current_year}_day":
                meta_data['last_birthday_notification'] = f"{current_year}_day"
                with self.db.lock:
                    cur = self.db.conn.cursor()
                    cur.execute("UPDATE reminders SET meta=? WHERE id=?", (json.dumps(meta_data), rid))
                    self.db.conn.commit()
                    cur.close()
                return "birthday"
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error determining birthday notification type for {rid}: {e}")
            return "birthday"

    def _next_time(self, time_str: str, repeat: str, timezone: str = "+00:00") -> Optional[str]:
        try:
            dt_utc = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            from utils.timezone_manager import TimezoneManager
            dt_local = TimezoneManager.utc_to_local(time_str, timezone)
            repeat_pattern = self.repeat_handler.from_json(repeat)
            
            now_utc = datetime.datetime.utcnow()
            now_local = TimezoneManager.utc_to_local(now_utc.strftime("%Y-%m-%d %H:%M"), timezone)
            
            if dt_local > now_local:
                next_dt_utc = TimezoneManager.local_to_utc(dt_local.strftime("%Y-%m-%d %H:%M"), timezone)
                return next_dt_utc.strftime("%Y-%m-%d %H:%M")
            
            next_dt_local = dt_local
            
            if hasattr(repeat_pattern, 'type') and repeat_pattern.type == "interval":
                value = getattr(repeat_pattern, 'value', 0) or getattr(repeat_pattern, 'minutes', 0)
                unit = getattr(repeat_pattern, 'unit', 'minutes')
                
                if (unit == "minutes" or unit == "minute") and value > 0:
                    diff_minutes = int((now_local - dt_local).total_seconds() / 60)
                    periods_passed = (diff_minutes // value) + 1
                    next_dt_local = dt_local + datetime.timedelta(minutes=periods_passed * value)
                else:
                    while next_dt_local <= now_local:
                        next_dt_local = self.repeat_handler.calculate_next_time(next_dt_local, repeat_pattern)
                        if not next_dt_local:
                            return None
            else:
                while next_dt_local <= now_local:
                    next_dt_local = self.repeat_handler.calculate_next_time(next_dt_local, repeat_pattern)
                    if not next_dt_local:
                        return None
            
            if next_dt_local:
                next_dt_utc = TimezoneManager.local_to_utc(next_dt_local.strftime("%Y-%m-%d %H:%M"), timezone)
                return next_dt_utc.strftime("%Y-%m-%d %H:%M")
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
        if self.queue_processor_task and not self.queue_processor_task.done():
            self.queue_processor_task.cancel()