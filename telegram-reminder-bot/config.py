import os
from typing import Optional


class Config:
    def __init__(self):
        self.openrouter_key: str = os.getenv("OPENROUTER_KEY", "")
        self.bot_token: str = os.getenv("BOT_TOKEN", "")
        self.database_path: str = "data/reminders.db"
        self.users_path: str = "data/users"
        self.max_requests_per_minute: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "20"))
        self.max_reminders_per_user: int = int(os.getenv("MAX_REMINDERS_PER_USER", "100"))
        self.cleanup_interval_hours: int = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        
    def validate(self) -> bool:
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")
        if not self.openrouter_key:
            raise ValueError("OPENROUTER_KEY environment variable is required")
        return True
