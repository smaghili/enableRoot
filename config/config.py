import os
import json
from typing import Optional

class Config:
    def __init__(self):
        self.config_data = self._load_config()
        self.bot_token: str = self.config_data.get("bot", {}).get("token", "")
        self.openrouter_key: str = self.config_data.get("ai", {}).get("openrouter_key", "")
        self.database_path: str = self.config_data.get("database", {}).get("path", "data/reminders.db")
        self.database_url: str = self.config_data.get("database", {}).get("url", f"sqlite:///{self.database_path}")
        self.users_path: str = self.config_data.get("storage", {}).get("users_path", "data/users")
        self.max_requests_per_minute: int = self.config_data.get("bot", {}).get("max_requests_per_minute", 20)
        self.rate_limit_window: int = self.config_data.get("bot", {}).get("rate_limit_window", 60)
        self.max_reminders_per_user: int = self.config_data.get("bot", {}).get("max_reminders_per_user", 100)
        self.cleanup_interval_hours: int = self.config_data.get("storage", {}).get("backup_interval_hours", 24)
        self.log_level: str = self.config_data.get("bot", {}).get("log_level", "INFO")
        self.ai_model: str = self.config_data.get("ai", {}).get("model", "gpt-4o")
        self.ai_max_tokens: int = self.config_data.get("ai", {}).get("max_tokens", 500)
        self.ai_temperature: float = self.config_data.get("ai", {}).get("temperature", 0.1)
        self.ai_timeout: float = self.config_data.get("ai", {}).get("timeout", 30.0)
        self.max_content_length: int = self.config_data.get("security", {}).get("max_content_length", 1000)
        self.enable_rate_limiting: bool = self.config_data.get("security", {}).get("enable_rate_limiting", True)
        self.enable_input_validation: bool = self.config_data.get("security", {}).get("enable_input_validation", True)
        self.notification_strategy: str = self.config_data.get("notification", {}).get("strategy", "standard")
        self.notification_max_retries: int = self.config_data.get("notification", {}).get("max_retries", 3)
        self.notification_retry_delay: float = self.config_data.get("notification", {}).get("retry_delay", 1.0)
        constants = self.config_data.get("constants", {})
        self.max_reminder_length: int = constants.get("max_reminder_length", 500)
        self.max_city_length: int = constants.get("max_city_length", 50)
        self.session_timeout: int = constants.get("session_timeout", 600)
        self.max_button_length: int = constants.get("max_button_length", 20)
        self.default_language: str = constants.get("default_language", "fa")
        self.default_timezone: str = constants.get("default_timezone", "+03:30")
        self.default_category: str = constants.get("default_category", "general")
        self.default_repeat: str = constants.get("default_repeat", '{"type": "none"}')
        self.emoji_mapping: dict = constants.get("emoji_mapping", {
            "birthday": "🎂", "medicine": "💊", "installment": "💳",
            "work": "💼", "appointment": "📅", "exercise": "🏃‍♂️",
            "prayer": "🕌", "shopping": "🛒", "call": "📞",
            "study": "📚", "bill": "💰", "general": "⏰"
        })
        self.detailed_prompt_count: int = constants.get("detailed_prompt_count", 5)
        self.admin_ids: list = self.config_data.get("bot", {}).get("admin_ids", [])
        self.log_channel_id: Optional[int] = self.config_data.get("bot", {}).get("log_channel_id")
        self.forced_join: dict = self.config_data.get("bot", {}).get("forced_join", {"enabled": False, "channels": []})
        update_settings = self.config_data.get("bot", {}).get("update_notification", {})
        self.inactive_days_threshold: int = update_settings.get("inactive_days_threshold", 30)
        self.force_update_notification: bool = update_settings.get("force_update_notification", False)
        self.force_update_timestamp: str = update_settings.get("force_update_timestamp", "")
        ai_logging_settings = self.config_data.get("bot", {}).get("ai_logging", {})
        self.ai_logging_enabled: bool = ai_logging_settings.get("enabled", True)
        self.ai_database_path: str = ai_logging_settings.get("database_path", "data/ai_logs.db")
        self.ai_cleanup_days: int = ai_logging_settings.get("cleanup_days", 30)

    def reload_config(self):
        self.config_data = self._load_config()
        self.log_channel_id = self.config_data.get("bot", {}).get("log_channel_id")
        self.admin_ids = self.config_data.get("bot", {}).get("admin_ids", [])
        update_settings = self.config_data.get("bot", {}).get("update_notification", {})
        self.force_update_notification = update_settings.get("force_update_notification", False)
        self.force_update_timestamp = update_settings.get("force_update_timestamp", "")
        
    def update_force_update_notification(self, value: bool):
        self.force_update_notification = value
        self._ensure_bot_config_structure()
        self.config_data["bot"]["update_notification"]["force_update_notification"] = value
        
        if value:
            import datetime
            new_timestamp = datetime.datetime.now().isoformat()
            self.force_update_timestamp = new_timestamp
            self.config_data["bot"]["update_notification"]["force_update_timestamp"] = new_timestamp
        else:
            self.force_update_timestamp = ""
            self.config_data["bot"]["update_notification"]["force_update_timestamp"] = ""
        
        self._save_config()
    
    def set_restart_timestamp(self):
        import datetime
        new_timestamp = datetime.datetime.now().isoformat()
        self.force_update_timestamp = new_timestamp
        self._ensure_bot_config_structure()
        self.config_data["bot"]["update_notification"]["force_update_timestamp"] = new_timestamp
        self._save_config()
    
    def _ensure_bot_config_structure(self):
        if "bot" not in self.config_data:
            self.config_data["bot"] = {}
        if "update_notification" not in self.config_data["bot"]:
            self.config_data["bot"]["update_notification"] = {}
    
    def _reset_all_users_force_update_status(self):
        users_dir = "data/users/"
        if not os.path.exists(users_dir):
            return
            
        for filename in os.listdir(users_dir):
            if not filename.endswith('.json'):
                continue
                
            user_file = os.path.join(users_dir, filename)
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                
                if 'force_update_seen' in user_data:
                    user_data['force_update_seen'] = False
                    with open(user_file, 'w', encoding='utf-8') as f:
                        json.dump(user_data, f, ensure_ascii=False, indent=2)
                        
            except (json.JSONDecodeError, IOError, PermissionError) as e:
                print(f"Could not reset force_update_seen for {filename}: {e}")
                continue
    
        
    def _save_config(self):
        config_file = "config/config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Could not save {config_file}: {e}")
        
    def _load_config(self) -> dict:
        config_file = "config/config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load {config_file}: {e}")
                return {}
        else:
            print(f"Warning: {config_file} not found")
            return {}
        
    def validate(self) -> bool:
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is required in config.json")
        if not self.openrouter_key:
            raise ValueError("OPENROUTER_KEY is required in config.json")
        return True
