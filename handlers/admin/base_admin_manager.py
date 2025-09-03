from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from abc import ABC

class BaseAdminManager(ABC):
    def __init__(self, storage, config, locales):
        self.storage = storage
        self.config = config
        self.locales = locales

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    async def return_to_admin_panel(self, message: Message, lang: str):
        keyboard = [
            [KeyboardButton(text=self.t(lang, "admin_add_admin")), KeyboardButton(text=self.t(lang, "admin_remove_admin"))],
            [KeyboardButton(text=self.t(lang, "admin_general_stats")), KeyboardButton(text=self.t(lang, "admin_delete_user"))],
            [KeyboardButton(text=self.t(lang, "admin_broadcast")), KeyboardButton(text=self.t(lang, "admin_private_message"))],
            [KeyboardButton(text=self.t(lang, "admin_user_limit")), KeyboardButton(text=self.t(lang, "admin_forced_join"))],
            [KeyboardButton(text=self.t(lang, "admin_log_channel"))],
            [KeyboardButton(text=self.t(lang, "back"))]
        ]
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(self.t(lang, "admin_panel"), reply_markup=kb)

    def create_cancel_keyboard(self, lang: str) -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton(text=self.t(lang, "cancel_operation"))]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
