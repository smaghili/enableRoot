from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from abc import ABC
from utils.menu_factory import MenuFactory

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
        kb = MenuFactory.create_admin_panel(lang, self.t)
        await message.answer(self.t(lang, "admin_panel"), reply_markup=kb)

    def create_cancel_keyboard(self, lang: str) -> ReplyKeyboardMarkup:
        return MenuFactory.create_cancel_keyboard(lang, self.t)
