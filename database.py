import sqlite3
import threading
import datetime
import os
from urllib.parse import urlparse


def _parse_tz(tz: str) -> datetime.timedelta:
    sign = 1 if tz.startswith("+") else -1
    hours, minutes = tz[1:].split(":")
    return datetime.timedelta(hours=sign * int(hours), minutes=sign * int(minutes))


class Database:
    def __init__(self, path_or_url: str):
        self.lock = threading.Lock()
        
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
                    status text
                )
                """
            )
            self._create_indexes()
    
    def _create_indexes(self):
        with self.conn:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_user_status ON reminders(user_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_status_time ON reminders(status, time)",
                "CREATE INDEX IF NOT EXISTS idx_user_id ON reminders(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_due_reminders ON reminders(status, time) WHERE status='active'"
            ]
            for index in indexes:
                self.conn.execute(index)

    def add(self, user_id, category, content, time, timezone, repeat, status="active"):
        with self.lock, self.conn:
            dt_local = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M")
            dt_utc = dt_local - _parse_tz(timezone)
            time_utc = dt_utc.strftime("%Y-%m-%d %H:%M")

            cursor = self.conn.execute(
                "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                (user_id, category, content, time_utc, timezone, repeat, status),
            )
            reminder_id = cursor.lastrowid
            if category == "birthday" and repeat == "yearly":
                birthday_8am = dt_local.replace(hour=8, minute=0, second=0, microsecond=0)
                birthday_8am_utc = birthday_8am - _parse_tz(timezone)
                self.conn.execute(
                    "update reminders set time=? where id=?",
                    (birthday_8am_utc.strftime("%Y-%m-%d %H:%M"), reminder_id)
                )
                week_before = dt_local.replace(hour=0, minute=1, second=0, microsecond=0) - datetime.timedelta(days=7)
                week_before_utc = week_before - _parse_tz(timezone)
                self.conn.execute(
                    "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                    (user_id, "birthday_pre_week", content,
                     week_before_utc.strftime("%Y-%m-%d %H:%M"), timezone, "yearly", status),
                )
                three_days_before = dt_local.replace(hour=0, minute=1, second=0, microsecond=0) - datetime.timedelta(days=3)
                three_days_before_utc = three_days_before - _parse_tz(timezone)
                self.conn.execute(
                    "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                    (user_id, "birthday_pre_three", content,
                     three_days_before_utc.strftime("%Y-%m-%d %H:%M"), timezone, "yearly", status),
                )
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

            result = []
            for row in rows:
                rid, cat, content, time_utc, tz, repeat, status_val = row
                try:
                    dt_utc = datetime.datetime.strptime(time_utc, "%Y-%m-%d %H:%M")
                    dt_local = dt_utc + _parse_tz(tz)
                    time_local = dt_local.strftime("%Y-%m-%d %H:%M")
                    result.append((rid, cat, content, time_local, tz, repeat, status_val))
                except (ValueError, TypeError):
                    result.append(row)
            return result

    def update_status(self, reminder_id, status):
        with self.lock, self.conn:
            self.conn.execute("update reminders set status=? where id=?", (status, reminder_id))

    def update_time(self, reminder_id, new_time):
        with self.lock, self.conn:
            cur = self.conn.cursor()
            cur.execute("select timezone from reminders where id=?", (reminder_id,))
            row = cur.fetchone()
            cur.close()

            if row:
                tz = row[0]
                dt_local = datetime.datetime.strptime(new_time, "%Y-%m-%d %H:%M")
                dt_utc = dt_local - _parse_tz(tz)
                time_utc = dt_utc.strftime("%Y-%m-%d %H:%M")
                self.conn.execute("update reminders set time=? where id=?", (time_utc, reminder_id))
            else:
                self.conn.execute("update reminders set time=? where id=?", (new_time, reminder_id))
    
    def update_reminder(self, reminder_id, category, content, time, timezone, repeat):
        with self.lock, self.conn:
            dt_local = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M")
            dt_utc = dt_local - _parse_tz(timezone)
            time_utc = dt_utc.strftime("%Y-%m-%d %H:%M")

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
                        dt_local = dt_utc + _parse_tz(tz)
                        time_local_str = dt_local.strftime("%Y-%m-%d %H:%M")
                        items.append((rid, uid, cat, content, time_local_str, tz, repeat))
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

    def close(self):
        with self.lock:
            self.conn.close()
