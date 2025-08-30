import sqlite3,threading
class Database:
 def __init__(self,path):
  self.lock=threading.Lock()
  self.path=path
  self.conn=sqlite3.connect(self.path,check_same_thread=False)
  self.cursor=self.conn.cursor()
  self._create_tables()
 def _create_tables(self):
  self.cursor.execute("create table if not exists reminders(id integer primary key,user_id integer,category text,content text,time text,status text)")
  self.conn.commit()
 def add(self,user_id,category,content,time,status="active"):
  with self.lock:
   self.cursor.execute("insert into reminders(user_id,category,content,time,status) values(?,?,?,?,?)",(user_id,category,content,time,status))
   self.conn.commit()
 def list(self,user_id,status="active"):
  with self.lock:
   self.cursor.execute("select id,category,content,time,status from reminders where user_id=? and status=?",(user_id,status))
   return self.cursor.fetchall()
 def update_status(self,reminder_id,status):
  with self.lock:
   self.cursor.execute("update reminders set status=? where id=?",(status,reminder_id))
   self.conn.commit()
 def due(self,now):
  with self.lock:
   self.cursor.execute("select id,user_id,content from reminders where time<=? and status='active'",(now,))
   return self.cursor.fetchall()
