from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import logging
import json
from utils.menu_factory import MenuFactory
from .admin_user_manager import AdminUserManager
from .admin_stats_manager import AdminStatsManager
from .admin_broadcast_manager import AdminBroadcastManager
from .admin_user_limit_manager import AdminUserLimitManager
from .admin_forced_join_manager import AdminForcedJoinManager
from .admin_user_deletion_manager import AdminUserDeletionManager
from .admin_log_channel_manager import AdminLogChannelManager

logger = logging.getLogger(__name__)

class AdminHandler:
    def __init__(self, storage, db, bot, config, locales):
        self.storage = storage
        self.db = db
        self.bot = bot
        self.config = config
        self.locales = locales
        
        # Initialize manager classes
        self.user_manager = AdminUserManager(storage, config, locales)
        self.stats_manager = AdminStatsManager(storage, db, config, locales)
        self.broadcast_manager = AdminBroadcastManager(storage, bot, locales, config)
        self.user_limit_manager = AdminUserLimitManager(storage, config, locales)
        self.forced_join_manager = AdminForcedJoinManager(storage, config, locales, bot)
        self.user_deletion_manager = AdminUserDeletionManager(storage, db, config, locales)
        self.log_channel_manager = AdminLogChannelManager(storage, config, locales)

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    def is_admin(self, user_id):
        return user_id in self.config.admin_ids

    async def show_admin_panel(self, message: Message):
        user_id = message.from_user.id
        if not self.is_admin(user_id):
            return
        
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            kb = MenuFactory.create_admin_panel(lang, self.t)
            self.forced_join_manager.in_forced_join_menu.discard(user_id)
            await message.answer(self.t(lang, "admin_panel"), reply_markup=kb)
        except Exception as e:
            logger.error(f"Error in show_admin_panel: {e}")

    async def handle_admin_button(self, message: Message):
        user_id = message.from_user.id
        if not self.is_admin(user_id):
            return
        
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            button_text = message.text
            
            if button_text == self.t(lang, "admin_add_admin"):
                await self.user_manager.handle_add_admin(message, lang)
            elif button_text == self.t(lang, "admin_remove_admin"):
                await self.user_manager.handle_remove_admin(message, lang)
            elif button_text == self.t(lang, "admin_general_stats"):
                await self.stats_manager.handle_general_stats(message, lang)
            elif button_text == self.t(lang, "admin_user_limit"):
                await self.user_limit_manager.handle_user_limit(message, lang)
            elif button_text == self.t(lang, "admin_broadcast"):
                await self.broadcast_manager.handle_broadcast_start(message, lang)
            elif button_text == self.t(lang, "admin_private_message"):
                await self.broadcast_manager.handle_private_message_start(message, lang)
            elif button_text == self.t(lang, "admin_forced_join"):
                await self.forced_join_manager.handle_forced_join_menu(message, lang)
            elif button_text == self.t(lang, "admin_delete_user"):
                await self.user_deletion_manager.handle_delete_user_start(message, lang)
            elif button_text == self.t(lang, "admin_log_channel"):
                await self.log_channel_manager.handle_log_channel_setup(message, lang)
            elif button_text == self.t(lang, "cancel_operation"):
                await self.handle_cancel_operation(message, lang)
            elif button_text == self.t(lang, "back"):
                await self.handle_back_to_main(message, lang)
                
        except Exception as e:
            logger.error(f"Error in handle_admin_button: {e}")

    async def handle_cancel_operation(self, message: Message, lang: str):
        user_id = message.from_user.id
        self.user_manager.waiting_for_admin_id.discard(user_id)
        self.broadcast_manager.waiting_for_broadcast.discard(user_id)
        self.forced_join_manager.waiting_for_channel.discard(user_id)
        self.broadcast_manager.waiting_for_private_user_id.discard(user_id)
        if user_id in self.broadcast_manager.waiting_for_private_message:
            del self.broadcast_manager.waiting_for_private_message[user_id]
        self.user_deletion_manager.waiting_for_delete_user.discard(user_id)
        self.log_channel_manager.waiting_for_log_channel.discard(user_id)
        self.user_limit_manager.waiting_for_limit.discard(user_id)
        self.forced_join_manager.in_forced_join_menu.discard(user_id)
        await self.show_admin_panel(message)

    async def handle_back_to_main(self, message: Message, lang: str):
        from utils.menu_factory import MenuFactory
        kb = MenuFactory.create_main_menu(lang, self.t, self.is_admin(message.from_user.id))
        await message.answer(self.t(lang, "menu"), reply_markup=kb)

    async def handle_admin_message(self, message: Message):
        user_id = message.from_user.id
        if not self.is_admin(user_id):
            return
        
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            if user_id in self.user_manager.waiting_for_admin_id:
                await self.user_manager.process_add_admin(message, lang)
            elif user_id in self.broadcast_manager.waiting_for_broadcast:
                await self.broadcast_manager.process_broadcast(message, lang)
            elif user_id in self.broadcast_manager.waiting_for_private_user_id:
                await self.broadcast_manager.process_private_user_id(message, lang)
            elif user_id in self.broadcast_manager.waiting_for_private_message:
                await self.broadcast_manager.process_private_message(message, lang)
            elif user_id in self.forced_join_manager.waiting_for_channel:
                await self.forced_join_manager.process_add_channel(message, lang)
            elif user_id in self.user_limit_manager.waiting_for_limit:
                await self.user_limit_manager.process_limit_change(message, lang)
            elif user_id in self.user_deletion_manager.waiting_for_delete_user:
                await self.user_deletion_manager.process_delete_user(message, lang)
            elif user_id in self.log_channel_manager.waiting_for_log_channel:
                await self.log_channel_manager.process_log_channel(message, lang)
                
        except Exception as e:
            logger.error(f"Error in handle_admin_message: {e}")

    def is_admin_button(self, message_text: str, lang: str) -> bool:
        admin_buttons = [
            "admin_add_admin", "admin_remove_admin", "admin_general_stats", "admin_user_limit",
            "admin_broadcast", "admin_private_message", "admin_forced_join", "admin_delete_user",
            "admin_log_channel", "back", "cancel_operation"
        ]
        return any(message_text == self.t(lang, btn) for btn in admin_buttons)

    async def handle_forced_join_callback(self, callback: CallbackQuery):
        await self.forced_join_manager.handle_forced_join_callback(callback)

    async def handle_admin_removal_callback(self, callback: CallbackQuery):
        await self.user_manager.handle_admin_removal_callback(callback)

    async def check_user_membership(self, user_id):
        return await self.forced_join_manager.check_user_membership(user_id)

    async def get_join_keyboard(self, lang):
        return await self.forced_join_manager.get_join_keyboard(lang)

