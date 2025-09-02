from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class ReminderType(ABC):
    """Base class for all reminder types"""
    
    @abstractmethod
    def get_emoji(self) -> str:
        pass
    
    @abstractmethod
    def get_category_name(self) -> str:
        pass
    
    @abstractmethod
    def create_keyboard(self, reminder_id: int, lang: str, t_func) -> Optional[InlineKeyboardMarkup]:
        pass
    
    @abstractmethod
    def format_message(self, content: str, lang: str, t_func) -> str:
        pass
    
    @abstractmethod
    def validate_content(self, content: str) -> bool:
        pass


class MedicineReminder(ReminderType):
    def get_emoji(self) -> str:
        return "💊"
    
    def get_category_name(self) -> str:
        return "medicine"
    
    def create_keyboard(self, reminder_id: int, lang: str, t_func) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t_func(lang, "medicine_taken"), 
                                callback_data=f"taken_{reminder_id}")]
        ])
    
    def format_message(self, content: str, lang: str, t_func) -> str:
        return f"💊 {content}"
    
    def validate_content(self, content: str) -> bool:
        return len(content.strip()) > 0 and len(content) <= 100


class BirthdayReminder(ReminderType):
    def get_emoji(self) -> str:
        return "🎂"
    
    def get_category_name(self) -> str:
        return "birthday"
    
    def create_keyboard(self, reminder_id: int, lang: str, t_func) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t_func(lang, "installment_stop_reminder"), 
                                callback_data=f"stop_{reminder_id}")]
        ])
    
    def format_message(self, content: str, lang: str, t_func) -> str:
        return f"🎂 {content}"
    
    def validate_content(self, content: str) -> bool:
        return len(content.strip()) > 0


class InstallmentReminder(ReminderType):
    def get_emoji(self) -> str:
        return "💳"
    
    def get_category_name(self) -> str:
        return "installment"
    
    def create_keyboard(self, reminder_id: int, lang: str, t_func) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t_func(lang, "installment_paid"), 
                                callback_data=f"paid_{reminder_id}")],
            [InlineKeyboardButton(text=t_func(lang, "installment_stop_reminder"), 
                                callback_data=f"stop_{reminder_id}")]
        ])
    
    def format_message(self, content: str, lang: str, t_func) -> str:
        return f"💳 {content}"
    
    def validate_content(self, content: str) -> bool:
        return len(content.strip()) > 0


class WorkReminder(ReminderType):
    def get_emoji(self) -> str:
        return "💼"
    
    def get_category_name(self) -> str:
        return "work"
    
    def create_keyboard(self, reminder_id: int, lang: str, t_func) -> Optional[InlineKeyboardMarkup]:
        return None  # No special buttons for work reminders
    
    def format_message(self, content: str, lang: str, t_func) -> str:
        return f"💼 {content}"
    
    def validate_content(self, content: str) -> bool:
        return len(content.strip()) > 0


class GeneralReminder(ReminderType):
    def get_emoji(self) -> str:
        return "⏰"
    
    def get_category_name(self) -> str:
        return "general"
    
    def create_keyboard(self, reminder_id: int, lang: str, t_func) -> Optional[InlineKeyboardMarkup]:
        return None
    
    def format_message(self, content: str, lang: str, t_func) -> str:
        return f"⏰ {content}"
    
    def validate_content(self, content: str) -> bool:
        return len(content.strip()) > 0


class InstallmentRetryReminder(ReminderType):
    def get_emoji(self) -> str:
        return "💳⚠️"
    
    def get_category_name(self) -> str:
        return "installment_retry"
    
    def create_keyboard(self, reminder_id: int, lang: str, t_func) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t_func(lang, "installment_paid"), 
                                callback_data=f"paid_{reminder_id}")],
            [InlineKeyboardButton(text=t_func(lang, "installment_stop_reminder"), 
                                callback_data=f"stop_{reminder_id}")]
        ])
    
    def format_message(self, content: str, lang: str, t_func) -> str:
        return f"💳⚠️ {t_func(lang, 'installment_reminder_retry')}: {content}"
    
    def validate_content(self, content: str) -> bool:
        return len(content.strip()) > 0


class ReminderFactory:
    """Factory for creating reminder type instances"""
    
    _reminder_types = {
        "medicine": MedicineReminder,
        "birthday": BirthdayReminder,
        "installment": InstallmentReminder,
        "installment_retry": InstallmentRetryReminder,
        "work": WorkReminder,
        "general": GeneralReminder,
        "appointment": WorkReminder,  # Reuse work reminder
        "exercise": WorkReminder,
        "prayer": WorkReminder,
        "shopping": WorkReminder,
        "call": WorkReminder,
        "study": WorkReminder,
        "bill": InstallmentReminder,  # Reuse installment reminder
    }
    
    @classmethod
    def create(cls, category: str) -> ReminderType:
        """Create a reminder type instance"""
        reminder_class = cls._reminder_types.get(category, GeneralReminder)
        return reminder_class()
    
    @classmethod
    def get_available_types(cls) -> Dict[str, str]:
        """Get all available reminder types with their emojis"""
        return {
            category: cls.create(category).get_emoji() 
            for category in cls._reminder_types.keys()
        }
    
    @classmethod
    def register_type(cls, category: str, reminder_class: type):
        """Register a new reminder type (Open/Closed Principle)"""
        if not issubclass(reminder_class, ReminderType):
            raise ValueError("Reminder class must inherit from ReminderType")
        cls._reminder_types[category] = reminder_class
