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
        self.conn = sqlite3.connect(path, check_same_thread=False)
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

    def add(self, user_id, category, content, time, timezone, repeat, status="active"):
        with self.lock, self.conn:
            self.conn.execute(
                "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                (user_id, category, content, time, timezone, repeat, status),
            )
            
            # For birthdays, add pre-reminders
            if category == "birthday" and repeat == "yearly":
                dt = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M")
                
                # 1 week before
                week_before = dt - datetime.timedelta(days=7)
                self.conn.execute(
                    "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                    (user_id, "birthday_pre", f"📅 1 هفته تا {content}", 
                     week_before.strftime("%Y-%m-%d %H:%M"), timezone, "yearly", status),
                )
                
                # 3 days before  
                three_days_before = dt - datetime.timedelta(days=3)
                self.conn.execute(
                    "insert into reminders(user_id,category,content,time,timezone,repeat,status) values(?,?,?,?,?,?,?)",
                    (user_id, "birthday_pre", f"📅 3 روز تا {content}", 
                     three_days_before.strftime("%Y-%m-%d %H:%M"), timezone, "yearly", status),
                )

    def list(self, user_id, status="active"):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "select id,category,content,time,timezone,repeat,status from reminders where user_id=? and status=?",
                (user_id, status),
            )
            r = cur.fetchall()
            cur.close()
            return r

    def update_status(self, reminder_id, status):
        with self.lock, self.conn:
            self.conn.execute("update reminders set status=? where id=?", (status, reminder_id))

    def update_time(self, reminder_id, new_time):
        with self.lock, self.conn:
            self.conn.execute("update reminders set time=? where id=?", (new_time, reminder_id))

    def due(self, now_utc: datetime.datetime):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "select id,user_id,category,content,time,timezone,repeat from reminders where status='active'",
            )
            items = []
            for rid, uid, cat, content, time_str, tz, repeat in cur.fetchall():
                dt_local = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                dt_utc = dt_local - _parse_tz(tz)
                if dt_utc <= now_utc:
                    items.append((rid, uid, cat, content, time_str, tz, repeat))
            cur.close()
            return items

    def close(self):
        with self.lock:
            self.conn.close()
