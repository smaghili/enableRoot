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
                await self._send_reminder(rid, uid, cat, content, repeat)
                if repeat == "none":
                    self.db.update_status(rid, "completed")
                else:
                    new_time = self._next_time(time_str, repeat)
                    self.db.update_time(rid, new_time)
            await asyncio.sleep(60)

    async def _send_reminder(self, rid, uid, category, content, repeat):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        if category == "birthday":
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("اینو دیگه یادآوری نکن ❌", 
                                      callback_data=f"stop_{rid}"))
            await self.bot.send_message(uid, f"🎂 {content}", reply_markup=kb)
            
        elif category == "installment":
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("پرداخت شد ✅", 
                                      callback_data=f"paid_{rid}"))
            kb.add(InlineKeyboardButton("دیگه یادآوری نکن ❌", 
                                      callback_data=f"stop_{rid}"))
            await self.bot.send_message(uid, f"💳 {content}", reply_markup=kb)
            
            # If not paid, schedule follow-up reminders for next 3 days
            if repeat != "none":
                for day in [1, 2, 3]:
                    follow_up_time = (datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M") + 
                                    datetime.timedelta(days=day)).strftime("%Y-%m-%d %H:%M")
                    self.db.add(uid, "installment_followup", f"⚠️ یادآوری قسط: {content}", 
                              follow_up_time, tz, "none")
            
        elif category == "medicine":
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("خوردم ✅", 
                                      callback_data=f"taken_{rid}"))
            await self.bot.send_message(uid, f"💊 {content}", reply_markup=kb)
            
        else:
            await self.bot.send_message(uid, f"⏰ {content}")

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
