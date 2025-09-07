from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseAdminManager(ABC):    
    def __init__(self, storage, config, locales):
        self.storage = storage
        self.config = config
        self.locales = locales
        self.active_operations = set()
    
    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    
    def create_cancel_keyboard(self, lang):
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=self.t(lang, "cancel_operation"))]],
            resize_keyboard=True
        )
    
    def create_admin_keyboard(self, lang):
        from utils.menu_factory import MenuFactory
        return MenuFactory.create_admin_panel(lang, self.t)
    
    async def start_operation(self, message: Message, operation_key: str):
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            self.active_operations.add(user_id)
            cancel_kb = self.create_cancel_keyboard(lang)
            prompt = await self.get_operation_prompt(lang, operation_key)
            
            await message.answer(prompt, reply_markup=cancel_kb)
            
        except Exception as e:
            logger.error(f"Error starting operation {operation_key}: {e}")
            await self.handle_error(message, "admin_export_error")
    
    async def complete_operation(self, message: Message, success_message: str, **kwargs):
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            self.active_operations.discard(user_id)
            admin_kb = self.create_admin_keyboard(lang)
            formatted_message = self.t(lang, success_message, **kwargs)
            
            await message.answer(formatted_message, reply_markup=admin_kb)
            
        except Exception as e:
            logger.error(f"Error completing operation: {e}")
            await self.handle_error(message, "admin_export_error")
    
    async def handle_error(self, message: Message, error_key: str, **kwargs):
        user_id = message.from_user.id
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]  
            self.active_operations.discard(user_id)
            admin_kb = self.create_admin_keyboard(lang)
            error_message = self.t(lang, error_key, **kwargs)
            await message.answer(error_message, reply_markup=admin_kb)
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            await message.answer("❌ Error processing request")
    
    def cancel_operation(self, user_id: int):
        self.active_operations.discard(user_id)
    
    def is_operation_active(self, user_id: int) -> bool:
        return user_id in self.active_operations
    
    async def return_to_admin_panel(self, message: Message, lang: str):
        admin_kb = self.create_admin_keyboard(lang)
        await message.answer(self.t(lang, "admin_panel"), reply_markup=admin_kb)
    
    @abstractmethod
    async def get_operation_prompt(self, lang: str, operation_key: str) -> str:
        pass