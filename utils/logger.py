import logging
from aiogram import Bot

logger = logging.getLogger(__name__)

class LogManager:
    def __init__(self, bot: Bot, config, storage):
        self.bot = bot
        self.config = config
        self.storage = storage
        self.log_channel_id = config.log_channel_id if hasattr(config, 'log_channel_id') else None

    async def send_reminder_log(self, reminder_id, user_id, category, content, reminder_type="created"):
        if not self.log_channel_id:
            return
        
        try:
            user_data = self.storage.load(user_id)
            user_name = user_data.get("user_info", {}).get("first_name", "نامشخص")
            username = user_data.get("user_info", {}).get("username", "نامشخص")
            language = user_data.get("settings", {}).get("language", "fa")
            calendar = user_data.get("settings", {}).get("calendar", "shamsi")
            timezone = user_data.get("settings", {}).get("timezone", "+03:30")
            
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
            
            log_message = f"""{content}
{emoji} {bot_username}
👤 name: {user_name}
🆔 username: {username_display}
📱 chat_id: {user_id}
🉐 language: {language}
📅 calendar: {calendar}
🕐 timezone: {timezone}
🆔 {bot_username}"""

            await self.bot.send_message(self.log_channel_id, log_message)
            
        except Exception as e:
            logger.error(f"Error sending reminder log: {e}")

    async def send_general_log(self, message_text, user_id=None):
        if not self.log_channel_id:
            return
        
        try:
            await self.bot.send_message(self.log_channel_id, message_text)
        except Exception as e:
            logger.error(f"Error sending general log: {e}")
