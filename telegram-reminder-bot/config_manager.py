from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Database configuration"""
    path: str = "data/reminders.db"
    timeout: float = 30.0
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    cache_size: int = 10000
    temp_store: str = "MEMORY"
    
    def validate(self) -> bool:
        """Validate database configuration"""
        if not self.path:
            raise ValueError("Database path cannot be empty")
        if self.timeout <= 0:
            raise ValueError("Database timeout must be positive")
        return True


@dataclass
class BotConfig:
    """Bot configuration"""
    token: str = ""
    name: str = "Smart Reminder Bot"
    description: str = "AI-powered reminder bot"
    max_requests_per_minute: int = 20
    rate_limit_window: int = 60
    max_reminders_per_user: int = 100
    
    def validate(self) -> bool:
        """Validate bot configuration"""
        if not self.token:
            raise ValueError("Bot token is required")
        if self.max_requests_per_minute <= 0:
            raise ValueError("Max requests per minute must be positive")
        return True


@dataclass
class AIConfig:
    """AI configuration"""
    openrouter_key: str = ""
    model: str = "gpt-4o"
    max_tokens: int = 500
    temperature: float = 0.1
    timeout: float = 30.0
    
    def validate(self) -> bool:
        """Validate AI configuration"""
        if not self.openrouter_key:
            raise ValueError("OpenRouter API key is required")
        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return True


@dataclass
class StorageConfig:
    """Storage configuration"""
    users_path: str = "data/users"
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    cleanup_old_backups: bool = True
    max_backup_files: int = 7
    
    def validate(self) -> bool:
        """Validate storage configuration"""
        if not self.users_path:
            raise ValueError("Users path cannot be empty")
        if self.backup_interval_hours <= 0:
            raise ValueError("Backup interval must be positive")
        return True


@dataclass
class SecurityConfig:
    """Security configuration"""
    file_permissions: str = "0o600"
    directory_permissions: str = "0o700"
    enable_rate_limiting: bool = True
    enable_input_validation: bool = True
    max_content_length: int = 1000
    
    def validate(self) -> bool:
        """Validate security configuration"""
        if self.max_content_length <= 0:
            raise ValueError("Max content length must be positive")
        return True


@dataclass
class NotificationConfig:
    """Notification configuration"""
    strategy: str = "standard"
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_silent_mode: bool = False
    
    def validate(self) -> bool:
        """Validate notification configuration"""
        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")
        if self.retry_delay < 0:
            raise ValueError("Retry delay cannot be negative")
        return True


@dataclass
class AppConfig:
    """Main application configuration"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    bot: BotConfig = field(default_factory=BotConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    
    def validate(self) -> bool:
        """Validate all configurations"""
        return (
            self.database.validate() and
            self.bot.validate() and
            self.ai.validate() and
            self.storage.validate() and
            self.security.validate() and
            self.notification.validate()
        )


class ConfigLoader(ABC):
    """Abstract configuration loader"""
    
    @abstractmethod
    def load(self) -> Dict[str, Any]:
        pass


class EnvironmentConfigLoader(ConfigLoader):
    """Load configuration from environment variables"""
    
    def load(self) -> Dict[str, Any]:
        return {
            "bot": {
                "token": os.getenv("BOT_TOKEN", ""),
                "max_requests_per_minute": int(os.getenv("MAX_REQUESTS_PER_MINUTE", "20")),
            },
            "ai": {
                "openrouter_key": os.getenv("OPENROUTER_KEY", ""),
                "model": os.getenv("AI_MODEL", "gpt-4o"),
                "temperature": float(os.getenv("AI_TEMPERATURE", "0.1")),
            },
            "database": {
                "path": os.getenv("DATABASE_PATH", "data/reminders.db"),
                "timeout": float(os.getenv("DATABASE_TIMEOUT", "30.0")),
            },
            "storage": {
                "users_path": os.getenv("USERS_PATH", "data/users"),
                "backup_enabled": os.getenv("BACKUP_ENABLED", "true").lower() == "true",
            },
            "notification": {
                "strategy": os.getenv("NOTIFICATION_STRATEGY", "standard"),
                "max_retries": int(os.getenv("NOTIFICATION_MAX_RETRIES", "3")),
            }
        }


class FileConfigLoader(ConfigLoader):
    """Load configuration from JSON file"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
    
    def load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to load config from {self.config_path}: {e}")
            return {}


class ConfigManager:
    """Centralized configuration manager"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.loaders = [
            EnvironmentConfigLoader(),
        ]
        
        if config_file:
            self.loaders.append(FileConfigLoader(config_file))
        
        self._config: Optional[AppConfig] = None
    
    def load_config(self) -> AppConfig:
        """Load and merge configuration from all sources"""
        merged_config = {}
        
        # Load from all sources and merge
        for loader in self.loaders:
            try:
                config_data = loader.load()
                self._deep_merge(merged_config, config_data)
            except Exception as e:
                self.logger.error(f"Failed to load config from {loader.__class__.__name__}: {e}")
        
        # Create AppConfig with merged data
        self._config = self._create_app_config(merged_config)
        
        # Validate configuration
        self._config.validate()
        
        self.logger.info("Configuration loaded and validated successfully")
        return self._config
    
    def get_config(self) -> AppConfig:
        """Get current configuration"""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge two dictionaries"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def _create_app_config(self, config_data: Dict[str, Any]) -> AppConfig:
        """Create AppConfig from dictionary data"""
        app_config = AppConfig()
        
        # Update database config
        if "database" in config_data:
            for key, value in config_data["database"].items():
                if hasattr(app_config.database, key):
                    setattr(app_config.database, key, value)
        
        # Update bot config
        if "bot" in config_data:
            for key, value in config_data["bot"].items():
                if hasattr(app_config.bot, key):
                    setattr(app_config.bot, key, value)
        
        # Update AI config
        if "ai" in config_data:
            for key, value in config_data["ai"].items():
                if hasattr(app_config.ai, key):
                    setattr(app_config.ai, key, value)
        
        # Update storage config
        if "storage" in config_data:
            for key, value in config_data["storage"].items():
                if hasattr(app_config.storage, key):
                    setattr(app_config.storage, key, value)
        
        # Update security config
        if "security" in config_data:
            for key, value in config_data["security"].items():
                if hasattr(app_config.security, key):
                    setattr(app_config.security, key, value)
        
        # Update notification config
        if "notification" in config_data:
            for key, value in config_data["notification"].items():
                if hasattr(app_config.notification, key):
                    setattr(app_config.notification, key, value)
        
        return app_config
    
    def save_config(self, config_path: str):
        """Save current configuration to file"""
        if self._config is None:
            raise ValueError("No configuration loaded")
        
        config_dict = {
            "database": {
                "path": self._config.database.path,
                "timeout": self._config.database.timeout,
                "journal_mode": self._config.database.journal_mode,
                "synchronous": self._config.database.synchronous,
                "cache_size": self._config.database.cache_size,
                "temp_store": self._config.database.temp_store,
            },
            "bot": {
                "token": self._config.bot.token,
                "name": self._config.bot.name,
                "description": self._config.bot.description,
                "max_requests_per_minute": self._config.bot.max_requests_per_minute,
                "rate_limit_window": self._config.bot.rate_limit_window,
                "max_reminders_per_user": self._config.bot.max_reminders_per_user,
            },
            "ai": {
                "openrouter_key": self._config.ai.openrouter_key,
                "model": self._config.ai.model,
                "max_tokens": self._config.ai.max_tokens,
                "temperature": self._config.ai.temperature,
                "timeout": self._config.ai.timeout,
            },
            "storage": {
                "users_path": self._config.storage.users_path,
                "backup_enabled": self._config.storage.backup_enabled,
                "backup_interval_hours": self._config.storage.backup_interval_hours,
                "cleanup_old_backups": self._config.storage.cleanup_old_backups,
                "max_backup_files": self._config.storage.max_backup_files,
            },
            "security": {
                "file_permissions": self._config.security.file_permissions,
                "directory_permissions": self._config.security.directory_permissions,
                "enable_rate_limiting": self._config.security.enable_rate_limiting,
                "enable_input_validation": self._config.security.enable_input_validation,
                "max_content_length": self._config.security.max_content_length,
            },
            "notification": {
                "strategy": self._config.notification.strategy,
                "max_retries": self._config.notification.max_retries,
                "retry_delay": self._config.notification.retry_delay,
                "enable_silent_mode": self._config.notification.enable_silent_mode,
            }
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Configuration saved to {config_path}")
        except IOError as e:
            self.logger.error(f"Failed to save config to {config_path}: {e}")
            raise


# Global configuration manager instance
config_manager = ConfigManager()
