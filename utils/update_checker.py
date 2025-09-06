import datetime
from typing import Optional
from utils.json_storage import JSONStorage
from config.config import Config


class UpdateChecker:
    def __init__(self, storage: JSONStorage, config: Config):
        self.storage = storage
        self.config = config
    
    def should_show_update_notification(self, user_id: int) -> bool:
        if self.config.force_update_notification:
            return True
        if self.storage.is_user_inactive(user_id, self.config.inactive_days_threshold):
            return True
        return False
    
    async def send_update_notification_if_needed(self, message_or_callback, user_id: int, lang: str, t_func) -> bool:
        if not self.should_show_update_notification(user_id):
            return False
        try:
            update_text = t_func(lang, "update_notification")
            if hasattr(message_or_callback, 'answer'):
                await message_or_callback.answer(update_text)
            elif hasattr(message_or_callback, 'message'):
                await message_or_callback.message.answer(update_text)
            self.storage.update_last_activity(user_id)
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending update notification to user {user_id}: {e}")
            return False
