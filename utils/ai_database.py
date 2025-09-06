import sqlite3
import datetime
import threading
import logging

class AIDatabase:
    def __init__(self, db_path: str = "data/ai_logs.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    original_message TEXT,
                    ai_response TEXT,
                    parsed_result TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    processing_time REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_time ON ai_logs(user_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_success ON ai_logs(success)")
    
    def log_interaction(self, user_id: int, original_message: str, ai_response: str = None, 
                       parsed_result: str = None, success: bool = True, error_message: str = None, 
                       processing_time: float = None):
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO ai_logs (user_id, timestamp, original_message, ai_response, 
                                           parsed_result, success, error_message, processing_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user_id,
                        datetime.datetime.now().isoformat(),
                        original_message[:500] if original_message else None,
                        ai_response[:2000] if ai_response else None,
                        parsed_result[:1000] if parsed_result else None,
                        success,
                        error_message[:500] if error_message else None,
                        processing_time
                    ))
            except Exception as e:
                self.logger.error(f"Failed to log AI interaction: {e}")
    
    def get_user_logs(self, user_id: int, limit: int = 20):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""
                SELECT timestamp, original_message, ai_response, parsed_result, 
                       success, error_message, processing_time
                FROM ai_logs WHERE user_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit)).fetchall()
    
    def get_error_logs(self, user_id: int = None, limit: int = 50):
        query = """
            SELECT user_id, timestamp, original_message, error_message
            FROM ai_logs WHERE success = 0
        """
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(query, params).fetchall()
    
    def cleanup_old_logs(self, days: int = 30):
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("DELETE FROM ai_logs WHERE timestamp < ?", (cutoff_date,))
            return result.rowcount
