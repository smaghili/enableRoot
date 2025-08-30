import requests,json,datetime,re
class AIHandler:
 def __init__(self,key):
  self.key=key
 def parse(self,language,timezone,text):
  headers={"Authorization":f"Bearer {self.key}","Content-Type":"application/json"}
  prompt=f"language:{language} timezone:{timezone} text:{text}"
  try:
   r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers=headers,json={"model":"gpt-3.5-turbo","messages":[{"role":"system","content":"return json with category content time"},{"role":"user","content":prompt}]})
   obj=json.loads(r.json()["choices"][0]["message"]["content"])
   return obj
  except:
   now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
   return {"category":"general","content":text,"time":now}
