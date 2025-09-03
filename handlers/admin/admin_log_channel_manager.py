from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import logging
import json

logger = logging.getLogger(__name__)

class AdminLogChannelManager:
    def __init__(self, storage, config, locales):
        self.storage = storage
        self.config = config
        self.locales = locales
        self.waiting_for_log_channel = set()

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    async def handle_log_channel_setup(self, message: Message, lang: str):
        current_log_channel = self.get_current_log_channel()
        if current_log_channel:
            status_text = self.t(lang, "admin_log_channel_current").format(channel=current_log_channel)
        else:
            status_text = self.t(lang, "admin_log_channel_not_set")
        
        self.waiting_for_log_channel.add(message.from_user.id)
        keyboard = [[KeyboardButton(text=self.t(lang, "cancel_operation"))]]
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(self.t(lang, "admin_log_channel_setup").format(status=status_text), reply_markup=kb)

    def get_current_log_channel(self):
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            return config_data["bot"].get("log_channel_id")
        except Exception:
            return None

    async def process_log_channel(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            log_channel_id = int(message.text.strip())
            
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            config_data["bot"]["log_channel_id"] = log_channel_id
            
            with open("config/config.json", "w") as f:
                json.dump(config_data, f, indent=2)
            
            await message.answer(self.t(lang, "admin_log_channel_set").format(channel=log_channel_id))
            
        except ValueError:
            await message.answer(self.t(lang, "admin_invalid_id"))
        except Exception as e:
            logger.error(f"Error setting log channel: {e}")
            await message.answer(self.t(lang, "admin_error"))
        finally:
            self.waiting_for_log_channel.discard(user_id)
