from aiogram.types import Message
import logging
import json
from .base_admin_manager import BaseAdminManager

logger = logging.getLogger(__name__)

class AdminLogChannelManager(BaseAdminManager):
    def __init__(self, storage, config, locales):
        super().__init__(storage, config, locales)
        self.waiting_for_log_channel = set()

    async def handle_log_channel_setup(self, message: Message, lang: str):
        current_log_channel = self.get_current_log_channel()
        if current_log_channel:
            status_text = self.t(lang, "admin_log_channel_current").format(channel=current_log_channel)
        else:
            status_text = self.t(lang, "admin_log_channel_not_set")
        
        self.waiting_for_log_channel.add(message.from_user.id)
        kb = self.create_cancel_keyboard(lang)
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
            self.waiting_for_log_channel.discard(user_id)
            await self.return_to_admin_panel(message, lang)
            
        except ValueError:
            await message.answer(self.t(lang, "admin_invalid_id"))
        except Exception as e:
            logger.error(f"Error setting log channel: {e}")
            await message.answer(self.t(lang, "admin_error"))
            self.waiting_for_log_channel.discard(user_id)
            await self.return_to_admin_panel(message, lang)
