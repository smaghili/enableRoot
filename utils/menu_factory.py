from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Union, Dict, Any

class MenuFactory:
    """Factory class for creating consistent menus across the application"""
    
    @staticmethod
    def create_main_menu(lang: str, t_func, is_admin: bool = False) -> ReplyKeyboardMarkup:
        """Create main menu keyboard"""
        keyboard = [
            [KeyboardButton(text=t_func(lang, "btn_new"))],
            [KeyboardButton(text=t_func(lang, "btn_delete")), KeyboardButton(text=t_func(lang, "btn_edit"))],
            [KeyboardButton(text=t_func(lang, "btn_list"))],
            [KeyboardButton(text=t_func(lang, "btn_settings")), KeyboardButton(text=t_func(lang, "btn_stats"))]
        ]
        if is_admin:
            keyboard.append([KeyboardButton(text=t_func(lang, "btn_admin"))])
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    @staticmethod
    def create_admin_panel(lang: str, t_func) -> ReplyKeyboardMarkup:
        """Create admin panel keyboard"""
        keyboard = [
            [KeyboardButton(text=t_func(lang, "admin_add_admin")), KeyboardButton(text=t_func(lang, "admin_remove_admin"))],
            [KeyboardButton(text=t_func(lang, "admin_general_stats")), KeyboardButton(text=t_func(lang, "admin_delete_user"))],
            [KeyboardButton(text=t_func(lang, "admin_broadcast")), KeyboardButton(text=t_func(lang, "admin_private_message"))],
            [KeyboardButton(text=t_func(lang, "admin_user_limit")), KeyboardButton(text=t_func(lang, "admin_forced_join"))],
            [KeyboardButton(text=t_func(lang, "admin_log_channel"))],
            [KeyboardButton(text=t_func(lang, "back"))]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    @staticmethod
    def create_cancel_keyboard(lang: str, t_func) -> ReplyKeyboardMarkup:
        """Create cancel operation keyboard"""
        keyboard = [[KeyboardButton(text=t_func(lang, "cancel_operation"))]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    @staticmethod
    def create_settings_keyboard(lang: str, t_func) -> InlineKeyboardMarkup:
        """Create settings inline keyboard"""
        keyboard = [
            [InlineKeyboardButton(text=t_func(lang, "change_language"), callback_data="change_lang")],
            [InlineKeyboardButton(text=t_func(lang, "change_timezone"), callback_data="change_tz")],
            [InlineKeyboardButton(text=t_func(lang, "change_calendar"), callback_data="change_calendar")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def create_confirm_cancel_keyboard(lang: str, t_func) -> InlineKeyboardMarkup:
        """Create confirm/cancel inline keyboard"""
        keyboard = [
            [InlineKeyboardButton(text=t_func(lang, "confirm"), callback_data="confirm")],
            [InlineKeyboardButton(text=t_func(lang, "cancel"), callback_data="cancel")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def create_language_selection_keyboard() -> InlineKeyboardMarkup:
        """Create language selection keyboard"""
        keyboard = [
            [InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="setup_lang_fa")],
            [InlineKeyboardButton(text="🇺🇸 English", callback_data="setup_lang_en")],
            [InlineKeyboardButton(text="🇸🇦 العربية", callback_data="setup_lang_ar")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setup_lang_ru")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    @staticmethod
    def create_timezone_confirmation_keyboard(lang: str, t_func, timezone: str) -> InlineKeyboardMarkup:
        """Create timezone confirmation keyboard"""
        keyboard = [
            [InlineKeyboardButton(text=t_func(lang, "yes"), callback_data=f"confirm_tz_{timezone}")],
            [InlineKeyboardButton(text=t_func(lang, "no"), callback_data="cancel_tz")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
