import asyncio,datetime
class ReminderScheduler:
 def __init__(self,db,json_storage,bot):
  self.db=db
  self.json_storage=json_storage
  self.bot=bot
  self.task=None
 def start(self):
  self.task=asyncio.get_event_loop().create_task(self._loop())
 async def _loop(self):
  while True:
   now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
   for rid,uid,content in self.db.due(now):
    asyncio.create_task(self.bot.send_message(uid,content))
    self.db.update_status(rid,"completed")
   await asyncio.sleep(60)
 def stop(self):
  if self.task:
   self.task.cancel()
