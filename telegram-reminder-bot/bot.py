from aiogram import Bot,Dispatcher,types
from aiogram.utils import executor
from config import Config
from database import Database
from json_storage import JSONStorage
from ai_handler import AIHandler
from reminder_scheduler import ReminderScheduler
import json,os
config=Config()
bot=Bot(config.bot_token)
dp=Dispatcher(bot)
db=Database(config.database_path)
storage=JSONStorage(config.users_path)
ai=AIHandler(config.openrouter_key)
scheduler=ReminderScheduler(db,storage,bot)
base=os.path.dirname(__file__)
def load_locales():
 l={}
 for f in os.listdir(os.path.join(base,"localization")):
  with open(os.path.join(base,"localization",f)) as d:
   l[f.split(".")[0]]=json.load(d)
 return l
locales=load_locales()
def t(lang,key):
 return locales.get(lang,locales["en"]).get(key,key)
@dp.message_handler(commands=["start"])
async def start_message(message:types.Message):
 user_id=message.from_user.id
 data=storage.load(user_id)
 storage.save(user_id,data)
 await message.answer(t(data["settings"]["language"],"start"))
@dp.message_handler(commands=["lang"])
async def change_lang(message:types.Message):
 parts=message.text.split()
 if len(parts)>1 and parts[1] in locales:
  storage.update_setting(message.from_user.id,"language",parts[1])
  await message.answer(t(parts[1],"saved"))
@dp.message_handler(commands=["tz"])
async def change_tz(message:types.Message):
 parts=message.text.split()
 if len(parts)>1:
  storage.update_setting(message.from_user.id,"timezone",parts[1])
  await message.answer(t(storage.load(message.from_user.id)["settings"]["language"],"saved"))
@dp.message_handler()
async def handle_message(message:types.Message):
 user_id=message.from_user.id
 data=storage.load(user_id)
 try:
  parsed=await ai.parse(data["settings"]["language"],data["settings"]["timezone"],message.text)
 except Exception as e:
  print(e)
  await message.answer("error")
  return
 db.add(user_id,parsed["category"],parsed["content"],parsed["time"])
 storage.add_reminder(user_id,parsed)
 await message.answer(t(data["settings"]["language"],"saved"))
def main():
 scheduler.start()
 executor.start_polling(dp)
 scheduler.stop()
 db.close()
if __name__=="__main__":
 main()
