import asyncio
import datetime


class ReminderScheduler:
    def __init__(self, db, json_storage, bot):
        self.db = db
        self.json_storage = json_storage
        self.bot = bot
        self.task = None

    def start(self):
        self.task = asyncio.get_event_loop().create_task(self._loop())

    async def _loop(self):
        while True:
            now = datetime.datetime.utcnow()
            for rid, uid, cat, content, time_str, tz, repeat in self.db.due(now):
                asyncio.create_task(self.bot.send_message(uid, content))
                if repeat == "none":
                    self.db.update_status(rid, "completed")
                else:
                    new_time = self._next_time(time_str, repeat)
                    self.db.update_time(rid, new_time)
            await asyncio.sleep(60)

    def _next_time(self, time_str: str, repeat: str) -> str:
        dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        if repeat == "daily":
            dt += datetime.timedelta(days=1)
        elif repeat == "weekly":
            dt += datetime.timedelta(weeks=1)
        elif repeat == "monthly":
            # approximate: add 30 days
            dt += datetime.timedelta(days=30)
        elif repeat == "yearly":
            dt = dt.replace(year=dt.year + 1)
        return dt.strftime("%Y-%m-%d %H:%M")

    def stop(self):
        if self.task:
            self.task.cancel()
