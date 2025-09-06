from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import os
from utils.comprehensive_logger import ComprehensiveLogger

logger = logging.getLogger(__name__)

class AdminLogExportManager:
    def __init__(self, storage, config, locales, bot):
        self.storage = storage
        self.config = config
        self.locales = locales
        self.bot = bot
        self.comp_logger = ComprehensiveLogger()
        self.waiting_for_reminder_id = set()
    
    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    
    async def handle_log_export_request(self, message: Message):
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            # Ask for reminder ID
            self.waiting_for_reminder_id.add(user_id)
            await message.answer(
                self.t(lang, "admin_reminder_id_prompt")
            )
                
        except Exception as e:
            logger.error(f"Error in log export request: {e}")
            try:
                data = self.storage.load(user_id)
                lang = data["settings"]["language"]
                await message.answer(
                    self.t(lang, "admin_export_error")
                )
            except:
                await message.answer("❌ Error processing request")
    
    async def handle_reminder_id_input(self, message: Message):
        user_id = message.from_user.id
        if user_id not in self.waiting_for_reminder_id:
            return False
            
        try:
            reminder_id = int(message.text.strip())
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            # Get comprehensive logs for this reminder
            logs = self.get_reminder_logs(reminder_id)
            
            if not logs:
                await message.answer(
                    self.t(lang, "admin_no_logs_found", reminder_id=reminder_id)
                )
                self.waiting_for_reminder_id.discard(user_id)
                return True
            
            # Create log file
            log_file = self.create_reminder_log_file(reminder_id, logs)
            
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                if file_size > 50 * 1024 * 1024:
                    await message.answer(
                        self.t(lang, "admin_export_too_large")
                    )
                    os.remove(log_file)
                    return True
                
                with open(log_file, 'rb') as f:
                    await self.bot.send_document(
                        user_id,
                        f,
                        caption=self.t(lang, "admin_reminder_log_caption", 
                                     reminder_id=reminder_id, 
                                     size=file_size // 1024)
                    )
                
                os.remove(log_file)
                await message.answer(
                    self.t(lang, "admin_reminder_log_success", reminder_id=reminder_id)
                )
            else:
                await message.answer(
                    self.t(lang, "admin_export_error")
                )
                
        except ValueError:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            await message.answer(
                self.t(lang, "admin_invalid_reminder_id")
            )
        except Exception as e:
            logger.error(f"Error processing reminder ID: {e}")
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            await message.answer(
                self.t(lang, "admin_export_error")
            )
        finally:
            self.waiting_for_reminder_id.discard(user_id)
            
        return True
    
    def get_reminder_logs(self, reminder_id: int):
        """Get all logs related to a specific reminder"""
        import sqlite3
        from utils.comprehensive_logger import ComprehensiveLogger
        from utils.ai_database import AIDatabase
        
        logs = []
        
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
                    'additional_info': log[10]
                })
        
        # Get AI logs
        ai_db = AIDatabase()
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
        
        return logs
    
    def create_reminder_log_file(self, reminder_id: int, logs: list):
        """Create a detailed log file for a specific reminder"""
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"data/reminder_logs_{reminder_id}_{timestamp}.txt"
        
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(f"=== COMPLETE LOGS FOR REMINDER ID: {reminder_id} ===\n")
            f.write(f"Generated at: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Total log entries: {len(logs)}\n\n")
            
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
                    f.write(f"Additional Info: {log['additional_info'] or 'None'}\n")
                    
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
