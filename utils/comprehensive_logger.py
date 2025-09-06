import sqlite3
import datetime
import threading
import logging
import json
from typing import Optional, Dict, Any, List

class ComprehensiveLogger:
    def __init__(self, db_path: str = "data/comprehensive_logs.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminder_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reminder_id INTEGER,
                    user_id INTEGER NOT NULL,
                    user_name TEXT,
                    user_username TEXT,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    timestamp TEXT NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT,
                    additional_info TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reminder_id ON reminder_logs(reminder_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON reminder_logs(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON reminder_logs(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON reminder_logs(timestamp)")
    
    def log_event(self, event_type: str, user_id: int, user_name: str = None, 
                  user_username: str = None, reminder_id: int = None, 
                  event_data: Dict[str, Any] = None, success: bool = True, 
                  error_message: str = None, additional_info: str = None):
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO reminder_logs (
                            reminder_id, user_id, user_name, user_username, event_type,
                            event_data, timestamp, success, error_message, additional_info
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        reminder_id,
                        user_id,
                        user_name[:100] if user_name else None,
                        user_username[:50] if user_username else None,
                        event_type,
                        json.dumps(event_data, ensure_ascii=False)[:2000] if event_data else None,
                        datetime.datetime.now().isoformat(),
                        success,
                        error_message[:500] if error_message else None,
                        additional_info[:500] if additional_info else None
                    ))
            except Exception as e:
                self.logger.error(f"Failed to log event {event_type}: {e}")
    
    def get_reminder_logs(self, reminder_id: int) -> List[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""
                SELECT timestamp, event_type, user_name, user_username, event_data, 
                       success, error_message, additional_info
                FROM reminder_logs 
                WHERE reminder_id = ?
                ORDER BY timestamp ASC
            """, (reminder_id,)).fetchall()
    
    def get_user_logs(self, user_id: int, limit: int = 100) -> List[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""
                SELECT timestamp, event_type, reminder_id, event_data, success, error_message
                FROM reminder_logs 
                WHERE user_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit)).fetchall()
    
    def get_all_logs(self, limit: int = 1000) -> List[tuple]:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""
                SELECT id, reminder_id, user_id, user_name, user_username, event_type,
                       event_data, timestamp, success, error_message, additional_info
                FROM reminder_logs 
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()
    
    def export_logs_to_text(self, output_file: str = None) -> str:
        if not output_file:
            output_file = f"data/logs_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        logs = self.get_all_logs(10000)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=== COMPREHENSIVE REMINDER LOGS ===\n")
            f.write(f"Generated: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Total Records: {len(logs)}\n")
            f.write("="*50 + "\n\n")
            
            for log in logs:
                log_id, reminder_id, user_id, user_name, user_username, event_type, event_data, timestamp, success, error_message, additional_info = log
                
                f.write(f"Log ID: {log_id}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Event Type: {event_type}\n")
                f.write(f"User ID: {user_id}\n")
                f.write(f"User Name: {user_name or 'N/A'}\n")
                f.write(f"Username: @{user_username or 'N/A'}\n")
                f.write(f"Reminder ID: {reminder_id or 'N/A'}\n")
                f.write(f"Success: {'✅' if success else '❌'}\n")
                
                if event_data:
                    f.write(f"Event Data: {event_data}\n")
                
                if error_message:
                    f.write(f"Error: {error_message}\n")
                
                if additional_info:
                    f.write(f"Additional Info: {additional_info}\n")
                
                f.write("-" * 30 + "\n\n")
        
        return output_file
    
    def cleanup_old_logs(self, days: int = 90):
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("DELETE FROM reminder_logs WHERE timestamp < ?", (cutoff_date,))
            return result.rowcount
