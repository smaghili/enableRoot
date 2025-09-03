from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import logging

logger = logging.getLogger(__name__)

class AdminBroadcastManager:
    def __init__(self, storage, bot, locales):
        self.storage = storage
        self.bot = bot
        self.locales = locales
        self.waiting_for_broadcast = set()
        self.waiting_for_private_message = {}
        self.waiting_for_private_user_id = set()

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    async def handle_broadcast_start(self, message: Message, lang: str):
        self.waiting_for_broadcast.add(message.from_user.id)
        
        kb = self.create_cancel_keyboard(lang)
        await message.answer(self.t(lang, "admin_enter_broadcast"), reply_markup=kb)

    async def handle_private_message_start(self, message: Message, lang: str):
        self.waiting_for_private_user_id.add(message.from_user.id)
        
        kb = self.create_cancel_keyboard(lang)
        await message.answer(self.t(lang, "admin_enter_user_id_private"), reply_markup=kb)

    async def process_broadcast(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            broadcast_text = message.text
            users = self.storage.get_all_users()
            success_count = 0
            
            for user_data in users:
                try:
                    await self.bot.send_message(user_data["user_id"], broadcast_text)
                    success_count += 1
                except Exception:
                    pass
            
            await message.answer(self.t(lang, "admin_broadcast_sent").format(count=success_count))
            self.waiting_for_broadcast.discard(user_id)
            await self.return_to_admin_panel(message, lang)
            
        except Exception as e:
            logger.error(f"Error in broadcast: {e}")
            await message.answer(self.t(lang, "admin_error"))
            self.waiting_for_broadcast.discard(user_id)
            await self.return_to_admin_panel(message, lang)

    async def process_private_user_id(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            target_user_id = int(message.text.strip())
            self.waiting_for_private_user_id.discard(user_id)
            self.waiting_for_private_message[user_id] = target_user_id
            
            kb = self.create_cancel_keyboard(lang)
            await message.answer(self.t(lang, "admin_enter_private_message"), reply_markup=kb)
        except ValueError:
            await message.answer(self.t(lang, "admin_invalid_id"))

    async def process_private_message(self, message: Message, lang: str):
        user_id = message.from_user.id
        # User already provided target ID, now sending the message
        target_user_id = self.waiting_for_private_message[user_id]
        try:
            await self.bot.send_message(target_user_id, message.text)
            await message.answer(self.t(lang, "admin_private_sent"))
            del self.waiting_for_private_message[user_id]
            await self.return_to_admin_panel(message, lang)
        except Exception as e:
            logger.error(f"Error sending private message: {e}")
            await message.answer(self.t(lang, "admin_error"))
            del self.waiting_for_private_message[user_id]
            await self.return_to_admin_panel(message, lang)
