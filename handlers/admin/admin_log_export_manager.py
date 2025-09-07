from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
import logging
import os
import datetime
import sqlite3
import json
from utils.comprehensive_logger import ComprehensiveLogger
from utils.ai_database import AIDatabase
from .base_admin_manager import BaseAdminManager
from utils.admin_decorators import requires_admin_input

logger = logging.getLogger(__name__)

class AdminLogExportManager(BaseAdminManager):
    def __init__(self, storage, config, locales, bot):
        super().__init__(storage, config, locales)
        self.bot = bot
        self.comp_logger = ComprehensiveLogger()
    
    async def get_operation_prompt(self, lang: str, operation_key: str) -> str:
        return self.t(lang, "admin_reminder_id_prompt")
    
    async def handle_log_export_request(self, message: Message):
        await self.start_operation(message, "log_export")
    
    @requires_admin_input('reminder_id')
    async def handle_reminder_id_input(self, message: Message, reminder_id: int = None):
        if reminder_id is None:
            return False
        await self.process_reminder_export(message, reminder_id)
        return True
    
    async def process_reminder_export(self, message: Message, reminder_id: int):
        user_id = message.from_user.id
        data = self.storage.load(user_id)
        lang = data["settings"]["language"]
        
        # Get comprehensive logs for this reminder
        logs = self.get_reminder_logs(reminder_id)
        
        if not logs:
            await self.handle_error(message, "admin_no_logs_found", reminder_id=reminder_id)
            return False

        log_file = self.create_reminder_log_file(reminder_id, logs)
        if not os.path.exists(log_file):
            return False
            
        file_size = os.path.getsize(log_file)
        if file_size > 50 * 1024 * 1024:
            os.remove(log_file)
            await self.handle_error(message, "admin_export_too_large")
            return False
        
        # Send the file
        document = FSInputFile(log_file)
        await self.bot.send_document(
            user_id,
            document,
            caption=self.t(lang, "admin_reminder_log_caption", 
                         reminder_id=reminder_id, 
                         size=file_size // 1024)
        )
        
        # Clean up and complete operation with reminder_id
        os.remove(log_file)
        await self.complete_operation(message, "admin_reminder_log_success", reminder_id=reminder_id)
    
    def get_reminder_logs(self, reminder_id: int):
        logs = []
        original_message_from_db = ""
        try:
            # Get reminder content first
            with sqlite3.connect(self.config.database_path if hasattr(self.config, 'database_path') else "data/reminders.db") as conn:
                cursor = conn.execute("SELECT content FROM reminders WHERE id = ?", (reminder_id,))
                result = cursor.fetchone()
                reminder_content = result[0] if result else ""
            
            # Search AI logs for the creation message
            if reminder_content:
                ai_db_path = self.config.ai_database_path if hasattr(self.config, 'ai_database_path') else "data/ai_logs.db"
                with sqlite3.connect(ai_db_path) as conn:
                    cursor = conn.execute(
                        "SELECT original_message FROM ai_logs WHERE parsed_result LIKE ? AND original_message IS NOT NULL ORDER BY timestamp DESC LIMIT 1",
                        (f'%{reminder_content}%',)
                    )
                    result = cursor.fetchone()
                    if result and result[0]:
                        original_message_from_db = result[0]
        except Exception as e:
            logger.error(f"Error getting original message: {e}")
        
        # Get comprehensive logs
        comp_logger = ComprehensiveLogger()
        with sqlite3.connect(comp_logger.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM reminder_logs WHERE reminder_id = ? ORDER BY timestamp ASC", 
                (reminder_id,)
            )
            comp_logs = cursor.fetchall()
            for log in comp_logs:
                logs.append({
                    'type': 'comprehensive',
                    'id': log[0],
                    'reminder_id': log[1],
                    'user_id': log[2],
                    'user_name': log[3],
                    'user_username': log[4],
                    'event_type': log[5],
                    'event_data': log[6],
                    'timestamp': log[7],
                    'success': log[8],
                    'error_message': log[9],
                    'additional_info': log[10],
                    'original_message_from_db': original_message_from_db
                })
        
        # Get AI logs
        try:
            ai_db = AIDatabase(self.config.ai_database_path if hasattr(self.config, 'ai_database_path') else "data/ai_logs.db")
            with sqlite3.connect(ai_db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM ai_logs WHERE original_message LIKE ? OR parsed_result LIKE ? ORDER BY timestamp ASC",
                    (f'%{reminder_id}%', f'%{reminder_id}%')
                )
            ai_logs = cursor.fetchall()
            for log in ai_logs:
                logs.append({
                    'type': 'ai',
                    'id': log[0],
                    'user_id': log[1],
                    'timestamp': log[2],
                    'original_message': log[3],
                    'ai_response': log[4],
                    'parsed_result': log[5],
                    'success': log[6],
                    'error_message': log[7],
                    'processing_time': log[8]
                })
        except Exception as e:
            pass
        
        logs.sort(key=lambda x: x['timestamp'])
        return logs
    
    def create_reminder_log_file(self, reminder_id: int, logs: list):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"data/reminder_logs_{reminder_id}_{timestamp}.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(f"=== COMPLETE LOGS FOR REMINDER ID: {reminder_id} ===\n")
            f.write(f"Generated at: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Total log entries: {len(logs)}\n")     
            original_msg = ""
            if logs and logs[0].get('original_message_from_db'):
                original_msg = logs[0]['original_message_from_db']
                f.write(f"📝 ORIGINAL USER MESSAGE: {original_msg}\n")
            f.write("\n")

            for i, log in enumerate(logs, 1):
                f.write(f"--- LOG ENTRY #{i} ---\n")
                f.write(f"Type: {log['type'].upper()}\n")
                f.write(f"Timestamp: {log['timestamp']}\n")
                
                if log['type'] == 'comprehensive':
                    f.write(f"Event Type: {log['event_type']}\n")
                    f.write(f"User ID: {log['user_id']}\n")
                    f.write(f"User Name: {log['user_name']}\n")
                    f.write(f"Username: @{log['user_username']}\n")
                    f.write(f"Reminder ID: {log['reminder_id']}\n")
                    f.write(f"Success: {log['success']}\n")
                    f.write(f"Error: {log['error_message'] or 'None'}\n")
                    f.write(f"Event Data: {log['event_data'] or 'None'}\n")
                    if log['additional_info']:
                        f.write(f"📝 {log['additional_info']}\n")
                    else:
                        f.write(f"Additional Info: None\n")
                    
                elif log['type'] == 'ai':
                    f.write(f"User ID: {log['user_id']}\n")
                    f.write(f"Original Message: {log['original_message']}\n")
                    f.write(f"AI Response: {log['ai_response']}\n")
                    f.write(f"Parsed Result: {log['parsed_result']}\n")
                    f.write(f"Success: {log['success']}\n")
                    f.write(f"Error: {log['error_message'] or 'None'}\n")
                    f.write(f"Processing Time: {log['processing_time']}s\n")
                
                f.write("\n" + "="*50 + "\n\n")
        
        return file_name
