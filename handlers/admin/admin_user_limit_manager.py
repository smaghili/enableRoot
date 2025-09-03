from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import logging
import json

logger = logging.getLogger(__name__)

class AdminUserLimitManager:
    def __init__(self, storage, config, locales):
        self.storage = storage
        self.config = config
        self.locales = locales
        self.waiting_for_limit = set()

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    async def handle_user_limit(self, message: Message, lang: str):
        current_limit = self.get_current_limit_from_config()
        limit_text = self.t(lang, "admin_current_limit").format(limit=current_limit)
        self.waiting_for_limit.add(message.from_user.id)
        await message.answer(limit_text)

    async def process_limit_change(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            new_limit = int(message.text.strip())
            
            if new_limit < 0:
                await message.answer(self.t(lang, "admin_invalid_limit"))
                return
            
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            config_data["bot"]["max_reminders_per_user"] = new_limit
            
            with open("config/config.json", "w") as f:
                json.dump(config_data, f, indent=2)
            
            self.config.max_reminders_per_user = new_limit
            
            if new_limit == 0:
                await message.answer(self.t(lang, "admin_limit_removed"))
            else:
                await message.answer(self.t(lang, "admin_limit_updated").format(limit=new_limit))
                
        except ValueError:
            await message.answer(self.t(lang, "admin_invalid_limit"))
        except Exception as e:
            logger.error(f"Error changing limit: {e}")
            await message.answer(self.t(lang, "admin_error"))
        finally:
            self.waiting_for_limit.discard(user_id)

    def get_current_limit_from_config(self):
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            return config_data["bot"]["max_reminders_per_user"]
        except Exception:
            return self.config.max_reminders_per_user
