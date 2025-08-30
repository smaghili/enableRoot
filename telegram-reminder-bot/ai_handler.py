import aiohttp,json,datetime
class AIHandler:
 def __init__(self,key):
  self.key=key
 def fallback(self,text):
  now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
  return {"category":"general","content":text,"time":now}
 async def parse(self,language,timezone,text):
  headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  prompt=f"language:{language} timezone:{timezone} text:{text}"
  try:
   async with aiohttp.ClientSession() as s:
    async with s.post("https://openrouter.ai/api/v1/chat/completions",headers=headers,json={"model":"gpt-3.5-turbo","messages":[{"role":"system","content":"return json with category content time"},{"role":"user","content":prompt}]}) as r:
     obj=json.loads((await r.json())["choices"][0]["message"]["content"])
     return obj
  except aiohttp.ClientError as e:
   print(e)
   return self.fallback(text)
  except json.JSONDecodeError as e:
   print(e)
   return self.fallback(text)
