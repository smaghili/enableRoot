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

    async def send_reminder_log(self, reminder_id, user_id, category, content, reminder_type="created", original_message="", ai_detected_text=""):
        log_channel_id = self._get_current_log_channel()
        if not log_channel_id:
            return
        
        try:
            user_data = self.storage.load(user_id)
            language = user_data.get("settings", {}).get("language", "fa")
            calendar = user_data.get("settings", {}).get("calendar", "shamsi")
            timezone = user_data.get("settings", {}).get("timezone", "+03:30")
            
            try:
                chat = await self.bot.get_chat(user_id)
                user_name = chat.first_name or "نامشخص"
                username = chat.username or "نامشخص"
            except:
                user_name = "نامشخص"
                username = "نامشخص"
            
            username_display = f"@{username}" if username != "نامشخص" else "نامشخص"
            
            category_emojis = {
                'birthday': '🎂',
                'medicine': '💊',
                'appointment': '📅',
                'work': '💼',
                'exercise': '🏃‍♂️',
                'prayer': '🕌',
                'shopping': '🛒',
                'call': '📞',
                'study': '📚',
                'installment': '💳',
                'bill': '💰',
                'general': '⏰'
            }
            
            emoji = category_emojis.get(category, '⏰')
            
            bot_info = await self.bot.get_me()
            bot_username = f"@{bot_info.username}" if bot_info.username else "Bot"
            
            reminder_type_hashtag = f"#{reminder_type}" if reminder_type else ""
            
            # Format the log message with original message, AI detected text, and reminder ID
            log_message_parts = []
            
            if original_message:
                log_message_parts.append(f"📝 original_message: {original_message}")
            
            if ai_detected_text:
                log_message_parts.append(f"🤖 ai_detected: {ai_detected_text}")
            
            log_message_parts.append(f"🆔 reminder_id: {reminder_id}")
            log_message_parts.append("")  # Empty line for separation
            log_message_parts.append(f"{content}")
            log_message_parts.append(f"{emoji} {bot_username}")
            log_message_parts.append(f"👤 name: {user_name}")
            log_message_parts.append(f"🆔 username: {username_display}")
            log_message_parts.append(f"📱 chat_id: {user_id}")
            log_message_parts.append(f"🉐 language: {language}")
            log_message_parts.append(f"📅 calendar: {calendar}")
            log_message_parts.append(f"🕐 timezone: {timezone}")
            log_message_parts.append(f"🆔 {bot_username}")
            log_message_parts.append(f"{reminder_type_hashtag}")
            
            log_message = "\n".join(log_message_parts)

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
