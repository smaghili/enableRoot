import sqlite3
import threading
import datetime


def _parse_tz(tz: str) -> datetime.timedelta:
    sign = 1 if tz.startswith("+") else -1
    hours, minutes = tz[1:].split(":")
    return datetime.timedelta(hours=sign * int(hours), minutes=sign * int(minutes))


class Database:
    def __init__(self, path: str):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
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
            # Convert local time to UTC for storage
            dt_local = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M")
            dt_utc = dt_local - _parse_tz(timezone)
            time_utc = dt_utc.strftime("%Y-%m-%d %H:%M")

            self.conn.execute(
                "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                (user_id, category, content, time_utc, timezone, repeat, status),
            )
            if category == "birthday" and repeat == "yearly":
                week_before = dt_local - datetime.timedelta(days=7)
                week_before_utc = week_before - _parse_tz(timezone)
                self.conn.execute(
                    "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                    (user_id, "birthday_pre_week", content,
                     week_before_utc.strftime("%Y-%m-%d %H:%M"), timezone, "yearly", status),
                )
                three_days_before = dt_local - datetime.timedelta(days=3)
                three_days_before_utc = three_days_before - _parse_tz(timezone)
                self.conn.execute(
                    "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                    (user_id, "birthday_pre_three", content,
                     three_days_before_utc.strftime("%Y-%m-%d %H:%M"), timezone, "yearly", status),
                )

    def list(self, user_id, status="active"):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "select id,category,content,time,timezone,repeat,status from reminders where user_id=? and status=?",
                (user_id, status),
            )
            rows = cur.fetchall()
            cur.close()

            # Convert UTC times back to local time for display
            result = []
            for row in rows:
                rid, cat, content, time_utc, tz, repeat, status_val = row
                try:
                    dt_utc = datetime.datetime.strptime(time_utc, "%Y-%m-%d %H:%M")
                    dt_local = dt_utc + _parse_tz(tz)
                    time_local = dt_local.strftime("%Y-%m-%d %H:%M")
                    result.append((rid, cat, content, time_local, tz, repeat, status_val))
                except (ValueError, TypeError):
                    # Fallback to UTC time if conversion fails
                    result.append(row)
            return result

    def update_status(self, reminder_id, status):
        with self.lock, self.conn:
            self.conn.execute("update reminders set status=? where id=?", (status, reminder_id))

    def update_time(self, reminder_id, new_time):
        with self.lock, self.conn:
            # Get timezone for this reminder
            cur = self.conn.cursor()
            cur.execute("select timezone from reminders where id=?", (reminder_id,))
            row = cur.fetchone()
            cur.close()

            if row:
                tz = row[0]
                # Convert local time to UTC
                dt_local = datetime.datetime.strptime(new_time, "%Y-%m-%d %H:%M")
                dt_utc = dt_local - _parse_tz(tz)
                time_utc = dt_utc.strftime("%Y-%m-%d %H:%M")
                self.conn.execute("update reminders set time=? where id=?", (time_utc, reminder_id))
            else:
                # Fallback if timezone not found
                self.conn.execute("update reminders set time=? where id=?", (new_time, reminder_id))
    
    def update_reminder(self, reminder_id, category, content, time, timezone, repeat):
        with self.lock, self.conn:
            # Convert local time to UTC
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
                    # Time is already in UTC, no conversion needed
                    dt_utc = datetime.datetime.strptime(time_utc_str, "%Y-%m-%d %H:%M")
                    if dt_utc <= now_utc:
                        # Convert UTC back to local time for display in reminder
                        dt_local = dt_utc + _parse_tz(tz)
                        time_local_str = dt_local.strftime("%Y-%m-%d %H:%M")
                        items.append((rid, uid, cat, content, time_local_str, tz, repeat))
                except (ValueError, TypeError):
                    continue
            cur.close()
            return items

    def cleanup_old_reminders(self, days_old=30):
        with self.lock:
            # Since times are stored in UTC, use UTC cutoff
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
            
            cur.execute("""
                select category, count(*) as count
                from reminders 
                where status != 'cancelled'
                group by category 
                order by count desc 
                limit 1
            """)
            top_category = cur.fetchone()
            
            cur.execute("""
                select user_id, count(*) as count
                from reminders 
                where status != 'cancelled'
                group by user_id 
                order by count desc 
                limit 1
            """)
            top_user = cur.fetchone()
            
            cur.close()
            return {
                'total_users': basic_stats[0],
                'total_reminders': basic_stats[1], 
                'active_reminders': basic_stats[2],
                'top_category': top_category[0] if top_category else None,
                'top_category_count': top_category[1] if top_category else 0,
                'top_user_id': top_user[0] if top_user else None,
                'top_user_count': top_user[1] if top_user else 0
            }

    def close(self):
        with self.lock:
            self.conn.close()
