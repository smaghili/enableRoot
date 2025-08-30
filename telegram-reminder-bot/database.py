import sqlite3,threading
class Database:
 def __init__(self,path):
  self.lock=threading.Lock()
  self.conn=sqlite3.connect(path,check_same_thread=False)
  self._create_tables()
 def _create_tables(self):
  with self.conn:
   self.conn.execute("create table if not exists reminders(id integer primary key,user_id integer,category text,content text,time text,status text)")
 def add(self,user_id,category,content,time,status="active"):
  with self.lock,self.conn:
   self.conn.execute("insert into reminders(user_id,category,content,time,status) values(?,?,?,?,?)",(user_id,category,content,time,status))
 def list(self,user_id,status="active"):
  with self.lock:
   cur=self.conn.cursor()
   cur.execute("select id,category,content,time,status from reminders where user_id=? and status=?",(user_id,status))
   r=cur.fetchall()
   cur.close()
   return r
 def update_status(self,reminder_id,status):
  with self.lock,self.conn:
   self.conn.execute("update reminders set status=? where id=?",(status,reminder_id))
 def due(self,now):
  with self.lock:
   cur=self.conn.cursor()
   cur.execute("select id,user_id,content from reminders where time<=? and status='active'",(now,))
   r=cur.fetchall()
   cur.close()
   return r
 def close(self):
  with self.lock:
   self.conn.close()
