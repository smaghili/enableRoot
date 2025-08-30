import os
class Config:
 def __init__(self):
  self.openrouter_key=os.getenv("OPENROUTER_KEY","")
  self.bot_token=os.getenv("BOT_TOKEN","")
  self.database_path="data/reminders.db"
  self.users_path="data/users"
