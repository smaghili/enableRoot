import datetime
import json
import os
import logging
from typing import Optional
from utils.json_storage import JSONStorage

logger = logging.getLogger(__name__)

class UpdateChecker:
    def __init__(self, storage: JSONStorage, db=None):
        self.storage = storage
        self.db = db
        self._config_cache = None
    
    @property
    def config(self):
        if self._config_cache is None:
            config_data = self._load_current_config()
            update_settings = config_data.get("bot", {}).get("update_notification", {})
            class ConfigObject:
                def __init__(self, update_settings):
                    self.force_update_notification = update_settings.get("force_update_notification", False)
                    self.force_update_timestamp = update_settings.get("force_update_timestamp", "")
            self._config_cache = ConfigObject(update_settings)
        return self._config_cache
    
    def _get_force_update_notification(self):
        config_data = self._load_current_config()
        update_settings = config_data.get("bot", {}).get("update_notification", {})
        return update_settings.get("force_update_notification", False)

    def _load_current_config(self):
        try:
            with open("config/config.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def should_show_update_notification(self, user_id: int) -> bool:
        import json
        user_file = f"data/users/{user_id}.json"
        
        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        except:
            logger.info(f"User {user_id} file not found, treating as new user")
            return False
        
        needs_start = self.db.needs_start_after_restart(user_id) if hasattr(self, 'db') and self.db else False
        
        if needs_start:
            logger.info(f"User {user_id} is new user, skipping update notification")
            return False
        
        config_data = self._load_current_config()
        update_settings = config_data.get("bot", {}).get("update_notification", {})
        force_update_notification = update_settings.get("force_update_notification", False)
        force_update_timestamp = update_settings.get("force_update_timestamp", "")
        
        logger.info(f"User {user_id} - Force update enabled: {force_update_notification}, Timestamp: {force_update_timestamp}")
        
        if force_update_notification and force_update_timestamp:
            user_last_seen = user_data.get("force_update_seen", "")
            logger.info(f"User {user_id} - DIRECT FILE Last seen: {user_last_seen}, Current: {force_update_timestamp}")
            
            if user_last_seen != force_update_timestamp:
                logger.info(f"User {user_id} needs to restart - timestamps don't match")
                return True
            else:
                logger.info(f"User {user_id} already updated - timestamps match")
        
        inactive_days_threshold = update_settings.get("inactive_days_threshold", 30)
        if self.storage.is_user_inactive(user_id, inactive_days_threshold):
            logger.info(f"User {user_id} is inactive, showing notification")
            return True
        
        logger.info(f"User {user_id} doesn't need notification")
        return False
    
    async def send_update_notification_if_needed(self, message_or_callback, user_id: int, lang: str, t_func) -> bool:
        should_show = self.should_show_update_notification(user_id)
        if not should_show:
            return False
        
        logger.info(f"Sending update notification to user {user_id}")
        
        update_text = t_func(lang, "update_notification")
        if hasattr(message_or_callback, 'answer'):
            await message_or_callback.answer(update_text)
        elif hasattr(message_or_callback, 'message'):
            await message_or_callback.message.answer(update_text)
        
        config_data = self._load_current_config()
        update_settings = config_data.get("bot", {}).get("update_notification", {})
        force_update_notification = update_settings.get("force_update_notification", False)
        
        if not force_update_notification:
            self.storage.update_last_activity(user_id)
            logger.info(f"Updated last activity for user {user_id}")
        
        return True
    
    def mark_user_as_updated(self, user_id: int):
        config_data = self._load_current_config()
        update_settings = config_data.get("bot", {}).get("update_notification", {})
        force_update_notification = update_settings.get("force_update_notification", False)
        force_update_timestamp = update_settings.get("force_update_timestamp", "")
        
        logger.info(f"Marking user {user_id} as updated - Force enabled: {force_update_notification}, Timestamp: {force_update_timestamp}")
        
        if force_update_notification and force_update_timestamp:
            import json
            user_file = f"data/users/{user_id}.json"
            
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
            except:
                user_data = {"user_id": user_id, "settings": {"language": "fa"}}
            
            old_timestamp = user_data.get("force_update_seen", "NOT_SET")
            user_data["force_update_seen"] = force_update_timestamp
            
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
            
            with open(user_file, 'r', encoding='utf-8') as f:
                verify_data = json.load(f)
            new_timestamp = verify_data.get("force_update_seen", "NOT_SAVED")
            
            logger.info(f"User {user_id} DIRECT FILE timestamp update: {old_timestamp} -> {new_timestamp}")
            
            if new_timestamp != force_update_timestamp:
                logger.error(f"DIRECT SAVE FAILED! User {user_id} timestamp not saved correctly")
            else:
                logger.info(f"User {user_id} successfully marked as updated via DIRECT FILE WRITE")
        else:
            logger.warning(f"Cannot mark user {user_id} as updated - Force update disabled or no timestamp")
