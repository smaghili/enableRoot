import sqlite3
import threading
import datetime
import os
import logging
from urllib.parse import urlparse
from utils.comprehensive_logger import ComprehensiveLogger
from config.config import Config
from utils.timezone_manager import TimezoneManager

logger = logging.getLogger(__name__)




class Database:
    def __init__(self, path_or_url: str):
        self.lock = threading.Lock()
        self.comp_logger = ComprehensiveLogger()
        
        if path_or_url.startswith(('sqlite:///', 'sqlite://')):
            parsed = urlparse(path_or_url)
            if parsed.scheme == 'sqlite':
                db_path = parsed.path.lstrip('/')
            else:
                db_path = path_or_url
        elif '://' in path_or_url:
            raise NotImplementedError(
                f"Database type not supported yet: {path_or_url.split('://')[0]}. "
                "Currently only SQLite is supported. "
                "To add PostgreSQL/MySQL support, install SQLAlchemy: pip install sqlalchemy psycopg2-binary"
            )
        else:
            db_path = path_or_url
        
        if db_path and os.path.dirname(db_path):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self._create_tables()

    def _create_tables(self):
        with self.conn:
            self.conn.execute(
                """
                create table if not exists reminders(
                    id integer primary key,
                    user_id integer,
                    category text,
                    content text,
                    time text,
                    timezone text,
                    repeat text,
                    status text,
                    meta text
                )
                """
            )
            self.conn.execute(
                """
                create table if not exists users(
                    user_id integer primary key,
                    last_start_date text,
                    created_date text
                )
                """
            )
            self.conn.execute(
                """
                create table if not exists app_state(
                    key text primary key,
                    value text
                )
                """
            )
            self._create_indexes()
            try:
                self.conn.execute("ALTER TABLE reminders ADD COLUMN meta text")
            except Exception:
                pass
    
    def _create_indexes(self):
        with self.conn:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_user_status ON reminders(user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_status_time ON reminders(status, time)",
                "CREATE INDEX IF NOT EXISTS idx_user_id ON reminders(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_due_reminders ON reminders(status, time) WHERE status='active'",
                "CREATE INDEX IF NOT EXISTS idx_users_start_date ON users(last_start_date)"
            ]
            for index in indexes:
                self.conn.execute(index)

    def add(self, user_id, category, content, time, timezone, repeat, status="active", meta=None):
        with self.lock, self.conn:
            time_utc = time

            cursor = self.conn.execute(
                "insert into reminders(user_id,category,content,time,timezone,repeat,status,meta) values(?,?,?,?,?,?,?,?)",
                (user_id, category, content, time_utc, timezone, repeat, status, meta),
            )
            reminder_id = cursor.lastrowid
            return reminder_id

    def get_user_details(self, user_id):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                select count(*) from reminders 
                where user_id = ? and status != 'cancelled'
            """, (user_id,))
            reminder_count = cur.fetchone()[0]
            cur.close()
            return reminder_count

    def get_reminder_for_log(self, reminder_id):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                select id, user_id, category, content, time, timezone, repeat, status
                from reminders
                where id = ?
            """, (reminder_id,))
            row = cur.fetchone()
            cur.close()
            return row

    def list(self, user_id, status="active"):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "select id,category,content,time,timezone,repeat,status from reminders where user_id=? and status=?",
                (user_id, status),
            )
            rows = cur.fetchall()
            cur.close()
            return rows

    def get_today_reminders(self, user_id, user_timezone):
        with self.lock:
            cur = self.conn.cursor()
            now_utc = datetime.datetime.utcnow()
            today_local = TimezoneManager.utc_to_local(now_utc.strftime("%Y-%m-%d %H:%M"), user_timezone)
            today_start = today_local.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            today_start_utc = TimezoneManager.local_to_utc(today_start.strftime("%Y-%m-%d %H:%M"), user_timezone)
            today_end_utc = TimezoneManager.local_to_utc(today_end.strftime("%Y-%m-%d %H:%M"), user_timezone)
            cur.execute(
                "select id,category,content,time,timezone,repeat,status from reminders where user_id=? and status=? and time >= ? and time <= ?",
                (user_id, "active", today_start_utc.strftime("%Y-%m-%d %H:%M"), today_end_utc.strftime("%Y-%m-%d %H:%M")),
            )
            rows = cur.fetchall()
            cur.close()
            return rows

    def update_status(self, reminder_id, status):
        with self.lock, self.conn:
            self.conn.execute("update reminders set status=? where id=?", (status, reminder_id))
            self.comp_logger.log_event("database_status_update", 0, "System", "System", reminder_id,
                                     event_data={"new_status": status})

    def update_time(self, reminder_id, new_time):
        with self.lock, self.conn:
            # new_time is already in UTC format from scheduler
            self.conn.execute("update reminders set time=? where id=?", (new_time, reminder_id))
            self.comp_logger.log_event("database_time_update", 0, "System", "System", reminder_id,
                                     event_data={"new_time": new_time})
    
    def update_reminder(self, reminder_id, category, content, time, timezone, repeat):
        with self.lock, self.conn:
            time_utc = time

            self.conn.execute(
                "update reminders set category=?, content=?, time=?, timezone=?, repeat=? where id=?",
                (category, content, time_utc, timezone, repeat, reminder_id)
            )

    def due(self, now_utc: datetime.datetime, limit=1000):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                """select id,user_id,category,content,time,timezone,repeat
                   from reminders
                   where status='active'
                   and datetime(time) <= datetime(?)
                   order by time asc
                   limit ?""",
                (now_utc.strftime("%Y-%m-%d %H:%M"), limit)
            )
            items = []
            for rid, uid, cat, content, time_utc_str, tz, repeat in cur.fetchall():
                try:
                    dt_utc = datetime.datetime.strptime(time_utc_str, "%Y-%m-%d %H:%M")
                    if dt_utc <= now_utc:
                        items.append((rid, uid, cat, content, time_utc_str, tz, repeat))
                except (ValueError, TypeError):
                    continue
            cur.close()
            return items

    def cleanup_old_reminders(self, days_old=30):
        with self.lock:
            cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_old)
            cur = self.conn.cursor()
            cur.execute(
                "delete from reminders where status in ('completed', 'cancelled') and datetime(time) < datetime(?)",
                (cutoff_date.strftime("%Y-%m-%d %H:%M"),)
            )
            deleted_count = cur.rowcount
            self.conn.commit()
            cur.close()
            return deleted_count

    def get_stats(self, user_id=None):
        with self.lock:
            cur = self.conn.cursor()
            if user_id:
                cur.execute("""
                    select 
                        count(*) as total,
                        count(case when status='active' then 1 end) as active,
                        count(case when status='completed' then 1 end) as completed,
                        count(case when status='cancelled' then 1 end) as cancelled,
                        1 as unique_users
                    from reminders
                    where user_id=?
                """, (user_id,))
            else:
                cur.execute("""
                    select 
                        count(*) as total,
                        count(case when status='active' then 1 end) as active,
                        count(case when status='completed' then 1 end) as completed,
                        count(case when status='cancelled' then 1 end) as cancelled,
                        count(distinct user_id) as unique_users
                    from reminders
                """)
            result = cur.fetchone()
            cur.close()
            return {
                'total': result[0],
                'active': result[1],
                'completed': result[2],
                'cancelled': result[3],
                'unique_users': result[4]
            }

    def get_admin_stats(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("""
                select 
                    count(distinct user_id) as total_users,
                    count(*) as total_reminders,
                    count(case when status='active' then 1 end) as active_reminders
                from reminders
            """)
            basic_stats = cur.fetchone()
            admin_count = 1
            cur.execute("""
                select distinct category from reminders 
                where status != 'cancelled' and category != 'birthday_pre_week' and category != 'birthday_pre_three'
                order by category
            """)
            categories = [row[0] for row in cur.fetchall()]
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            month_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            cur.execute("""
                select count(*) from reminders 
                where category = 'birthday' 
                and date(time) = date(?) 
                and status != 'cancelled'
            """, (today,))
            birthdays_today = cur.fetchone()[0]
            cur.execute("""
                select count(*) from reminders 
                where category = 'birthday' 
                and date(time) >= date(?) 
                and date(time) <= date(?) 
                and status != 'cancelled'
            """, (week_ago, today))
            birthdays_week = cur.fetchone()[0]
            cur.execute("""
                select count(*) from reminders 
                where category = 'birthday' 
                and date(time) >= date(?) 
                and date(time) <= date(?) 
                and status != 'cancelled'
            """, (month_ago, today))
            birthdays_month = cur.fetchone()[0]
            cur.execute("""
                select count(*) from reminders 
                where category = 'birthday' 
                and status != 'cancelled'
            """)
            total_birthdays = cur.fetchone()[0]
            category_stats = {}
            for category in categories:
                if category == 'birthday':
                    continue
                cur.execute("""
                    select count(*) from reminders 
                    where category = ? 
                    and date(time) = date(?) 
                    and status != 'cancelled'
                """, (category, today))
                today_count = cur.fetchone()[0]
                cur.execute("""
                    select count(*) from reminders 
                    where category = ? 
                    and date(time) >= date(?) 
                    and date(time) <= date(?) 
                    and status != 'cancelled'
                """, (category, week_ago, today))
                week_count = cur.fetchone()[0]
                cur.execute("""
                    select count(*) from reminders 
                    where category = ? 
                    and date(time) >= date(?) 
                    and date(time) <= date(?) 
                    and status != 'cancelled'
                """, (category, month_ago, today))
                month_count = cur.fetchone()[0]
                cur.execute("""
                    select count(*) from reminders 
                    where category = ? 
                    and status != 'cancelled'
                """, (category,))
                total_count = cur.fetchone()[0]
                category_stats[category] = {
                    'today': today_count,
                    'week': week_count,
                    'month': month_count,
                    'total': total_count
                }
            cur.close()
            return {
                'total_users': basic_stats[0],
                'total_reminders': basic_stats[1], 
                'active_reminders': basic_stats[2],
                'admin_count': admin_count,
                'birthdays_today': birthdays_today,
                'birthdays_week': birthdays_week,
                'birthdays_month': birthdays_month,
                'total_birthdays': total_birthdays,
                'category_stats': category_stats
            }


    def record_user_start(self, user_id):
        with self.lock, self.conn:
            current_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            self.conn.execute(
                "INSERT OR REPLACE INTO users(user_id, last_start_date, created_date) VALUES(?, ?, COALESCE((SELECT created_date FROM users WHERE user_id = ?), ?))",
                (user_id, current_time, user_id, current_time)
            )

    def set_app_restart_time(self):
        with self.lock, self.conn:
            current_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            self.conn.execute(
                "INSERT OR REPLACE INTO app_state(key, value) VALUES(?, ?)",
                ("last_restart", current_time)
            )

    def get_app_restart_time(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT value FROM app_state WHERE key = ?", ("last_restart",))
            result = cur.fetchone()
            cur.close()
            return result[0] if result else None

    def is_new_user(self, user_id):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT last_start_date FROM users WHERE user_id = ?", (user_id,))
            result = cur.fetchone()
            cur.close()
            return result is None
    
    def is_valid_user(self, user_id, storage):
        """
        Check if a user is valid by verifying they exist in database or have valid storage.
        Returns True if user is valid, False otherwise.
        """
        with self.lock:
            cur = self.conn.cursor()
            try:
                cur.execute("SELECT last_start_date FROM users WHERE user_id = ?", (user_id,))
                db_result = cur.fetchone()
                cur.close()
                
                storage_file = storage.file(user_id)
                has_storage = os.path.exists(storage_file)
                is_valid = db_result is not None or (db_result is None and has_storage)
                if not is_valid:
                    logger.warning(f"Invalid user {user_id}: db_exists={db_result is not None}, has_storage={has_storage}")
                
                return is_valid
                
            except Exception as e:
                logger.error(f"Error checking user validity for {user_id}: {e}")
                cur.close()
                storage_file = storage.file(user_id)
                return os.path.exists(storage_file)
    
    def is_in_setup(self, user_id, storage):
        try:
            data = storage.secure_load(user_id)
            settings = data.get("settings", {})
            has_language = settings.get("language")
            has_timezone = settings.get("timezone")
            has_calendar = settings.get("calendar")
            return has_language and has_timezone and not has_calendar
        except:
            return False

    def delete_user(self, user_id):
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self.conn.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))

    def needs_start_after_restart(self, user_id):
        config = Config()
        if not config.force_update_notification:
            return False
            
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT last_start_date FROM users WHERE user_id = ?", (user_id,))
            result = cur.fetchone()
            
            if result is None:
                cur.close()
                return True
            
            user_last_start = result[0]
            if user_last_start is None:
                cur.close()
                return True
            
            cur.execute("SELECT value FROM app_state WHERE key = ?", ("last_restart",))
            restart_result = cur.fetchone()
            cur.close()
            
            if restart_result is None:
                return False
            
            app_restart_time = restart_result[0]
            
            try:
                user_start_dt = datetime.datetime.strptime(user_last_start, "%Y-%m-%d %H:%M")
                app_restart_dt = datetime.datetime.strptime(app_restart_time, "%Y-%m-%d %H:%M")
                return user_start_dt < app_restart_dt
            except (ValueError, TypeError):
                return True

    def close(self):
        with self.lock:
            self.conn.close()
