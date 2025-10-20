from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from services.reminder_types import ReminderFactory
from utils.comprehensive_logger import ComprehensiveLogger


class NotificationStrategy(ABC):
    """Base class for notification strategies"""
    
    @abstractmethod
    async def send_notification(self, bot: Bot, user_id: int, reminder_data: Dict[str, Any], 
                              lang: str, t_func) -> bool:
        """Send notification and return success status"""
        pass


class TelegramNotificationStrategy(NotificationStrategy):
    """Standard Telegram notification strategy"""
    
    def __init__(self, log_manager=None):
        self.logger = logging.getLogger(__name__)
        self.log_manager = log_manager
        self.comp_logger = ComprehensiveLogger()
    
    async def send_notification(self, bot: Bot, user_id: int, reminder_data: Dict[str, Any], 
                              lang: str, t_func) -> bool:
        reminder_id = reminder_data.get('id')
        category = reminder_data.get('category', 'general')
        content = reminder_data.get('content', 'No content')
        
        try:
            reminder_type = ReminderFactory.create(category)   
            message_text = reminder_type.format_message(content, lang, t_func)
            keyboard = reminder_type.create_keyboard(reminder_id, lang, t_func)      
            await bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=keyboard
            )
            
            self.logger.info(f"Sent {category} reminder {reminder_id} to user {user_id}")
            
            if self.log_manager:
                await self.log_manager.send_reminder_log(
                    reminder_id, user_id, category, message_text, "sent", 
                    "", 
                    content
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send notification to user {user_id}: {e}")
            if "Too Many Requests" in str(e) or "Flood control exceeded" in str(e):
                import re
                import asyncio
                retry_match = re.search(r'retry after (\d+)', str(e))
                if retry_match:
                    retry_seconds = int(retry_match.group(1))
                    self.logger.info(f"Rate limited, will retry after {retry_seconds} seconds")
                    await asyncio.sleep(retry_seconds + 1)
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=message_text,
                            reply_markup=keyboard
                        )
                        self.logger.info(f"Successfully sent {category} reminder {reminder_id} after retry")
                        
                        if self.log_manager:
                            await self.log_manager.send_reminder_log(
                                reminder_id, user_id, category, message_text, "sent", 
                                "", 
                                content
                            )
                        return True
                    except Exception as retry_error:
                        self.logger.error(f"Retry also failed for user {user_id}: {retry_error}")
            
            try:
                chat = await bot.get_chat(user_id)
                user_name = chat.first_name or "Unknown"
                username = chat.username or "Unknown"
            except:
                user_name = "Unknown"
                username = "Unknown"
            
            self.comp_logger.log_event("notification_send_error", user_id, user_name, username, 
                                     reminder_id, success=False, error_message=str(e),
                                     event_data={"category": category, "content": content})
            
            if self.log_manager:
                try:
                    reminder_type = ReminderFactory.create(category)
                    formatted_message = reminder_type.format_message(content, lang, t_func)
                    await self.log_manager.send_reminder_log(
                        reminder_id, user_id, category, formatted_message, "failed", 
                        "", 
                        content
                    )
                except Exception as log_error:
                    self.logger.error(f"Failed to format message for log: {log_error}")
                    await self.log_manager.send_reminder_log(
                        reminder_id, user_id, category, content, "failed", 
                        "", 
                        content
                    )
            
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
