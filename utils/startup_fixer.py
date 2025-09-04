import datetime
import json
import logging
from database import Database
from utils.timezone_manager import TimezoneManager
from handlers.repeat_handler import RepeatHandler
from utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class StartupFixer:
    def __init__(self, database: Database, storage: JSONStorage):
        self.db = database
        self.storage = storage
        self.repeat_handler = RepeatHandler()

    def fix_all_overdue_reminders(self) -> int:
        now_utc = datetime.datetime.utcnow()
        fixed_count = 0
        try:
            with self.db.lock:
                cur = self.db.conn.cursor()
                cur.execute(
                    """
                    SELECT id, time, timezone, repeat
                    FROM reminders
                    WHERE status = 'active'
                    """
                )
                reminders = cur.fetchall()
                cur.close()
            for reminder_id, time_str, timezone, repeat_json in reminders:
                try:
                    if self._fix_single_reminder(reminder_id, time_str, timezone, repeat_json, now_utc):
                        fixed_count += 1
                except Exception:
                    continue
            return fixed_count
        except Exception:
            return 0

    def _fix_single_reminder(self, reminder_id: int, time_str: str, timezone: str, repeat_json: str, now_utc: datetime.datetime) -> bool:
        try:
            reminder_utc = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            if reminder_utc > now_utc:
                return False
            try:
                repeat_dict = json.loads(repeat_json) if repeat_json else {"type": "none"}
            except Exception:
                repeat_dict = {"type": "none"}
            if repeat_dict.get("type") in (None, "none"):
                with self.db.lock:
                    self.db.conn.execute("update reminders set status='cancelled' where id=?", (reminder_id,))
                    self.db.conn.commit()
                return True
            dt_local = TimezoneManager.utc_to_local(time_str, timezone)
            now_local = TimezoneManager.utc_to_local(now_utc.strftime("%Y-%m-%d %H:%M"), timezone)
            repeat_pattern = self.repeat_handler.from_json(repeat_json)
            next_dt_local = self._calculate_next_time(dt_local, now_local, repeat_pattern)
            if next_dt_local and next_dt_local > now_local:
                next_dt_utc = TimezoneManager.local_to_utc(next_dt_local.strftime("%Y-%m-%d %H:%M"), timezone)
                next_time_str = next_dt_utc.strftime("%Y-%m-%d %H:%M")
                self.db.update_time(reminder_id, next_time_str)
                return True
        except Exception:
            return False
        return False

    def _calculate_next_time(self, dt_local: datetime.datetime, now_local: datetime.datetime, repeat_pattern) -> datetime.datetime:
        if getattr(repeat_pattern, "type", None) == "interval":
            value = getattr(repeat_pattern, "value", 0) or getattr(repeat_pattern, "minutes", 0)
            unit = getattr(repeat_pattern, "unit", "minutes")
            if (unit == "minutes" or unit == "minute") and value > 0:
                diff_minutes = int((now_local - dt_local).total_seconds() / 60)
                periods_passed = (diff_minutes // value) + 1
                return dt_local + datetime.timedelta(minutes=periods_passed * value)
        next_dt_local = dt_local
        while next_dt_local <= now_local:
            prev = next_dt_local
            next_dt_local = self.repeat_handler.calculate_next_time(prev, repeat_pattern)
            if not next_dt_local or next_dt_local <= prev:
                return None
        return next_dt_local
