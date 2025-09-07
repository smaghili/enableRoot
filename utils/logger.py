import logging
import json
from aiogram import Bot

logger = logging.getLogger(__name__)

class LogManager:
    def __init__(self, bot: Bot, config, storage):
        self.bot = bot
        self.config = config
        self.storage = storage
        self.log_channel_id = config.log_channel_id if hasattr(config, 'log_channel_id') else None

    def _get_current_log_channel(self):
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            return config_data.get("bot", {}).get("log_channel_id")
        except Exception:
            return self.config.log_channel_id if hasattr(self.config, 'log_channel_id') else None
    
    def _get_original_message_from_ai_logs(self, content):
        try:
            import sqlite3
            ai_db_path = getattr(self.config, 'ai_database_path', "data/ai_logs.db")
            with sqlite3.connect(ai_db_path) as conn:
                cursor = conn.execute(
                    "SELECT original_message FROM ai_logs WHERE parsed_result LIKE ? AND original_message IS NOT NULL ORDER BY timestamp DESC LIMIT 1",
                    (f'%{content}%',)
                )
                result = cursor.fetchone()
                if result and result[0]:
                    return result[0]
        except Exception as e:
            logger.error(f"Error getting original message from AI logs: {e}")
        return ""

    def _get_category_emoji(self, category):
        emojis = {
            'birthday': '🎂', 'medicine': '💊', 'appointment': '📅', 'work': '💼',
            'exercise': '🏃‍♂️', 'prayer': '🕌', 'shopping': '🛒', 'call': '📞',
            'study': '📚', 'installment': '💳', 'bill': '💰', 'general': '⏰'
        }
        return emojis.get(category, '⏰')
    
    async def _get_user_info(self, user_id):
        """Get user information"""
        user_data = self.storage.secure_load(user_id)
        settings = user_data.get("settings", {})
        
        try:
            chat = await self.bot.get_chat(user_id)
            user_name = chat.first_name or "Unknown"
            username = chat.username or "Unknown"
        except:
            user_name = "Unknown"
            username = "Unknown"
        
        return {
            'name': user_name,
            'username': f"@{username}" if username != "Unknown" else "Unknown",
            'language': settings.get("language", "fa"),
            'calendar': settings.get("calendar", "shamsi"),
            'timezone': settings.get("timezone", "+03:30")
        }
    
    def _build_log_message(self, reminder_id, user_info, category, content, reminder_type, original_message, ai_detected_text, bot_username):
        parts = []
        if original_message:
            parts.append(f"📝 original_message: {original_message}")
        if ai_detected_text:
            parts.append(f"🤖 ai_detected: {ai_detected_text}")
        parts.extend([
            f"🆔 reminder_id: {reminder_id}",
            "",
            content,
            f"{self._get_category_emoji(category)} {bot_username}",
            f"👤 name: {user_info['name']}",
            f"🆔 username: {user_info['username']}",
            f"📱 chat_id: {user_info.get('user_id', '')}",
            f"🉐 language: {user_info['language']}",
            f"📅 calendar: {user_info['calendar']}",
            f"🕐 timezone: {user_info['timezone']}",
            f"🆔 {bot_username}",
            f"#{reminder_type}" if reminder_type else ""
        ])
        return "\n".join(parts)

    async def send_reminder_log(self, reminder_id, user_id, category, content, reminder_type="created", original_message="", ai_detected_text=""):
        log_channel_id = self._get_current_log_channel()
        if not log_channel_id:
            return
            
        if not original_message:
            original_message = self._get_original_message_from_ai_logs(content)
        
        try:
            user_info = await self._get_user_info(user_id)
            user_info['user_id'] = user_id
            
            bot_info = await self.bot.get_me()
            bot_username = f"@{bot_info.username}" if bot_info.username else "Bot"
            
            log_message = self._build_log_message(
                reminder_id, user_info, category, content, 
                reminder_type, original_message, ai_detected_text, bot_username
            )

            await self.bot.send_message(log_channel_id, log_message)
            
        except Exception as e:
            logger.error(f"Error sending reminder log: {e}")

    async def send_general_log(self, message_text, user_id=None):
        log_channel_id = self._get_current_log_channel()
        if not log_channel_id:
            return
        
        try:
            await self.bot.send_message(log_channel_id, message_text)
        except Exception as e:
            logger.error(f"Error sending general log: {e}")
