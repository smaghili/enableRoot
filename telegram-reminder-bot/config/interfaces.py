from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime


class IReminderParser(ABC):
    """Interface for parsing reminder text"""
    
    @abstractmethod
    async def parse(self, language: str, timezone: str, text: str) -> Dict[str, Any]:
        """Parse reminder text and return structured data"""
        pass
    
    @abstractmethod
    async def parse_edit(self, current_reminder: Dict[str, Any], edit_text: str, timezone: str) -> Dict[str, Any]:
        """Parse edit request for existing reminder"""
        pass
    
    @abstractmethod
    def fallback(self, text: str, timezone: str) -> Dict[str, Any]:
        """Fallback parsing when AI fails"""
        pass


class IReminderStorage(ABC):
    """Interface for reminder storage operations"""
    
    @abstractmethod
    def add(self, user_id: int, category: str, content: str, time: str, timezone: str, repeat: str, status: str = "active") -> int:
        """Add new reminder and return its ID"""
        pass
    
    @abstractmethod
    def list(self, user_id: int, status: str = "active") -> List[Tuple]:
        """List reminders for user"""
        pass
    
    @abstractmethod
    def update_status(self, reminder_id: int, status: str) -> bool:
        """Update reminder status"""
        pass
    
    @abstractmethod
    def update_time(self, reminder_id: int, new_time: str) -> bool:
        """Update reminder time"""
        pass
    
    @abstractmethod
    def update_reminder(self, reminder_id: int, category: str, content: str, time: str, timezone: str, repeat: str) -> bool:
        """Update entire reminder"""
        pass
    
    @abstractmethod
    def due(self, now_utc: datetime, limit: int = 1000) -> List[Tuple]:
        """Get due reminders"""
        pass
    
    @abstractmethod
    def get_stats(self, user_id: Optional[int] = None) -> Tuple:
        """Get reminder statistics"""
        pass
    
    @abstractmethod
    def cleanup_old_reminders(self, days_old: int = 30) -> int:
        """Cleanup old reminders"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close storage connection"""
        pass


class IUserStorage(ABC):
    """Interface for user data storage"""
    
    @abstractmethod
    def load(self, user_id: int) -> Dict[str, Any]:
        """Load user data"""
        pass
    
    @abstractmethod
    def save(self, user_id: int, data: Dict[str, Any]) -> None:
        """Save user data"""
        pass
    
    @abstractmethod
    def update_setting(self, user_id: int, key: str, value: Any) -> None:
        """Update specific user setting"""
        pass
    
    @abstractmethod
    def add_reminder(self, user_id: int, reminder: Dict[str, Any]) -> None:
        """Add reminder to user data"""
        pass
    
    @abstractmethod
    def get_user_language(self, user_id: int) -> str:
        """Get user's preferred language"""
        pass


class IRepeatHandler(ABC):
    """Interface for handling reminder repetition patterns"""
    
    @abstractmethod
    def parse_from_text(self, text: str, base_time: datetime) -> Dict[str, Any]:
        """Parse repeat pattern from text"""
        pass
    
    @abstractmethod
    def to_json(self, pattern: Dict[str, Any]) -> str:
        """Convert pattern to JSON string"""
        pass
    
    @abstractmethod
    def from_json(self, json_str: str) -> Dict[str, Any]:
        """Parse pattern from JSON string"""
        pass
    
    @abstractmethod
    def get_display_text(self, pattern: Dict[str, Any], lang: str) -> str:
        """Get human-readable display text"""
        pass
    
    @abstractmethod
    def calculate_next_time(self, current_time: datetime, pattern: Dict[str, Any]) -> Optional[datetime]:
        """Calculate next occurrence time"""
        pass


class IMessageHandler(ABC):
    """Interface for handling messages and callbacks"""
    
    @abstractmethod
    async def handle_message(self, message) -> None:
        """Handle incoming message"""
        pass
    
    @abstractmethod
    async def handle_callback(self, callback) -> None:
        """Handle callback query"""
        pass
    
    @abstractmethod
    def rate_limit_check(self, user_id: int) -> bool:
        """Check if user is within rate limits"""
        pass
    
    @abstractmethod
    async def handle_rate_limit(self, message_or_callback) -> None:
        """Handle rate limit exceeded"""
        pass


class IScheduler(ABC):
    """Interface for reminder scheduling"""
    
    @abstractmethod
    def start(self) -> None:
        """Start the scheduler"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the scheduler"""
        pass


class INotificationService(ABC):
    """Interface for notification services"""
    
    @abstractmethod
    async def send_notification(self, user_id: int, reminder_data: Dict[str, Any], lang: str) -> bool:
        """Send notification to user"""
        pass


class ILocalizationService(ABC):
    """Interface for localization services"""
    
    @abstractmethod
    def get_text(self, lang: str, key: str, **kwargs) -> str:
        """Get localized text"""
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        pass


class IConfigurationService(ABC):
    """Interface for configuration management"""
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        pass
    
    @abstractmethod
    def update_config(self, key: str, value: Any) -> None:
        """Update configuration value"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate current configuration"""
        pass


class ISecurityService(ABC):
    """Interface for security services"""
    
    @abstractmethod
    def sanitize_input(self, text: str) -> str:
        """Sanitize user input"""
        pass
    
    @abstractmethod
    def validate_user_input(self, text: str) -> bool:
        """Validate user input"""
        pass
    
    @abstractmethod
    def create_secure_directory(self, path: str) -> None:
        """Create directory with secure permissions"""
        pass
    
    @abstractmethod
    def secure_file_permissions(self, file_path: str) -> None:
        """Set secure file permissions"""
        pass
