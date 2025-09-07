from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseAdminManager(ABC):
    """Base class for all admin managers with common functionality"""
    
    def __init__(self, storage, config, locales):
        self.storage = storage
        self.config = config
        self.locales = locales
        self.active_operations = set()
    
    def t(self, lang, key, **kwargs):
        """Translation helper"""
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    
    def create_cancel_keyboard(self, lang):
        """Create a keyboard with only cancel button"""
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=self.t(lang, "cancel_operation"))]],
            resize_keyboard=True
        )
    
    def create_admin_keyboard(self, lang):
        """Create admin panel keyboard"""
        from utils.menu_factory import MenuFactory
        return MenuFactory.create_admin_panel(lang, self.t)
    
    async def start_operation(self, message: Message, operation_key: str):
        """Start an admin operation with proper keyboard management"""
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            # Add user to active operations
            self.active_operations.add(user_id)
            
            # Show cancel keyboard
            cancel_kb = self.create_cancel_keyboard(lang)
            
            # Get operation-specific prompt
            prompt = await self.get_operation_prompt(lang, operation_key)
            
            await message.answer(prompt, reply_markup=cancel_kb)
            
        except Exception as e:
            logger.error(f"Error starting operation {operation_key}: {e}")
            await self.handle_error(message, "admin_export_error")
    
    async def complete_operation(self, message: Message, success_message: str, **kwargs):
        """Complete an operation and restore admin keyboard"""
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            # Remove from active operations
            self.active_operations.discard(user_id)
            
            # Restore admin keyboard
            admin_kb = self.create_admin_keyboard(lang)
            
            # Format success message
            formatted_message = self.t(lang, success_message, **kwargs)
            
            await message.answer(formatted_message, reply_markup=admin_kb)
            
        except Exception as e:
            logger.error(f"Error completing operation: {e}")
            await self.handle_error(message, "admin_export_error")
    
    async def handle_error(self, message: Message, error_key: str, **kwargs):
        """Handle errors and restore admin keyboard"""
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            # Remove from active operations
            self.active_operations.discard(user_id)
            
            # Restore admin keyboard
            admin_kb = self.create_admin_keyboard(lang)
            
            # Format error message
            error_message = self.t(lang, error_key, **kwargs)
            
            await message.answer(error_message, reply_markup=admin_kb)
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            await message.answer("❌ Error processing request")
    
    def cancel_operation(self, user_id: int):
        """Cancel an active operation"""
        self.active_operations.discard(user_id)
    
    def is_operation_active(self, user_id: int) -> bool:
        """Check if user has an active operation"""
        return user_id in self.active_operations
    
    @abstractmethod
    async def get_operation_prompt(self, lang: str, operation_key: str) -> str:
        """Get the prompt message for the operation"""
        pass