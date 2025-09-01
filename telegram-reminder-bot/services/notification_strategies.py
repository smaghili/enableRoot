from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from services.reminder_types import ReminderFactory


class NotificationStrategy(ABC):
    """Base class for notification strategies"""
    
    @abstractmethod
    async def send_notification(self, bot: Bot, user_id: int, reminder_data: Dict[str, Any], 
                              lang: str, t_func) -> bool:
        """Send notification and return success status"""
        pass


class TelegramNotificationStrategy(NotificationStrategy):
    """Standard Telegram notification strategy"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def send_notification(self, bot: Bot, user_id: int, reminder_data: Dict[str, Any], 
                              lang: str, t_func) -> bool:
        try:
            reminder_id = reminder_data.get('id')
            category = reminder_data.get('category', 'general')
            content = reminder_data.get('content', 'No content')
            
            # Use factory to get reminder type
            reminder_type = ReminderFactory.create(category)
            
            # Format message
            message_text = reminder_type.format_message(content, lang, t_func)
            
            # Create keyboard if needed
            keyboard = reminder_type.create_keyboard(reminder_id, lang, t_func)
            
            # Send message
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard
            )
            
            self.logger.info(f"Sent {category} reminder {reminder_id} to user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send notification to user {user_id}: {e}")
            return False


class SilentNotificationStrategy(NotificationStrategy):
    """Silent notification strategy (for testing or special cases)"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def send_notification(self, bot: Bot, user_id: int, reminder_data: Dict[str, Any], 
                              lang: str, t_func) -> bool:
        try:
            reminder_id = reminder_data.get('id')
            category = reminder_data.get('category', 'general')
            
            self.logger.info(f"Silent notification: {category} reminder {reminder_id} for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Silent notification failed for user {user_id}: {e}")
            return False


class PriorityNotificationStrategy(NotificationStrategy):
    """Priority notification with multiple attempts"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self.base_strategy = TelegramNotificationStrategy()
    
    async def send_notification(self, bot: Bot, user_id: int, reminder_data: Dict[str, Any], 
                              lang: str, t_func) -> bool:
        for attempt in range(self.max_retries):
            try:
                success = await self.base_strategy.send_notification(bot, user_id, reminder_data, lang, t_func)
                if success:
                    return True
                    
                self.logger.warning(f"Notification attempt {attempt + 1} failed for user {user_id}")
                
            except Exception as e:
                self.logger.error(f"Notification attempt {attempt + 1} error for user {user_id}: {e}")
        
        self.logger.error(f"All {self.max_retries} notification attempts failed for user {user_id}")
        return False


class NotificationContext:
    """Context class for notification strategies"""
    
    def __init__(self, strategy: NotificationStrategy):
        self._strategy = strategy
    
    def set_strategy(self, strategy: NotificationStrategy):
        """Change notification strategy at runtime"""
        self._strategy = strategy
    
    async def send_notification(self, bot: Bot, user_id: int, reminder_data: Dict[str, Any], 
                              lang: str, t_func) -> bool:
        """Execute the notification using current strategy"""
        return await self._strategy.send_notification(bot, user_id, reminder_data, lang, t_func)


class NotificationStrategyFactory:
    """Factory for creating notification strategies"""
    
    _strategies = {
        "standard": TelegramNotificationStrategy,
        "silent": SilentNotificationStrategy,
        "priority": PriorityNotificationStrategy,
    }
    
    @classmethod
    def create(cls, strategy_type: str = "standard", **kwargs) -> NotificationStrategy:
        """Create a notification strategy instance"""
        strategy_class = cls._strategies.get(strategy_type, TelegramNotificationStrategy)
        return strategy_class(**kwargs)
    
    @classmethod
    def register_strategy(cls, name: str, strategy_class: type):
        """Register a new notification strategy"""
        if not issubclass(strategy_class, NotificationStrategy):
            raise ValueError("Strategy class must inherit from NotificationStrategy")
        cls._strategies[name] = strategy_class
