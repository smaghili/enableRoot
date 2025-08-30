import threading,time,datetime
class ReminderScheduler:
 def __init__(self,db,json_storage,bot):
  self.db=db
  self.json_storage=json_storage
  self.bot=bot
 def start(self):
  threading.Thread(target=self._loop,daemon=True).start()
 def _loop(self):
  while True:
   now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
   due=self.db.due(now)
   for rid,uid,content in due:
    self.bot.loop.create_task(self.bot.send_message(uid,content))
    self.db.update_status(rid,"completed")
   time.sleep(60)
