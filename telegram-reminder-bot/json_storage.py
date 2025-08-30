import json,os
class JSONStorage:
 def __init__(self,path):
  self.path=path
  os.makedirs(self.path,exist_ok=True)
 def file(self,user_id):
  return os.path.join(self.path,f"{user_id}.json")
 def load(self,user_id):
  p=self.file(user_id)
  d={"user_id":user_id,"reminders":{"active":[],"completed":[],"cancelled":[]},"settings":{"language":"en","timezone":"+00:00"}}
  if os.path.exists(p):
   with open(p) as f:
    try:
     return json.load(f)
    except json.JSONDecodeError:
     with open(p,"w") as w:
      json.dump(d,w)
     return d
  return d
 def save(self,user_id,data):
  with open(self.file(user_id),"w") as f:
   json.dump(data,f)
 def update_setting(self,user_id,key,value):
  data=self.load(user_id)
  data["settings"][key]=value
  self.save(user_id,data)
 def add_reminder(self,user_id,reminder):
  data=self.load(user_id)
  data["reminders"]["active"].append(reminder)
  self.save(user_id,data)
