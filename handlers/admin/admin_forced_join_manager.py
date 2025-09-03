from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import logging
import json

logger = logging.getLogger(__name__)

class AdminForcedJoinManager:
    def __init__(self, storage, config, locales, bot):
        self.storage = storage
        self.config = config
        self.locales = locales
        self.bot = bot
        self.waiting_for_channel = set()
        self.in_forced_join_menu = set()

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    async def handle_forced_join_menu(self, message: Message, lang: str):
        await self.show_forced_join_inline_menu(message, lang)

    async def show_forced_join_inline_menu(self, message: Message, lang: str):
        current_status = self.get_forced_join_status_from_config()
        status_icon = "✅" if current_status else "❌"
        status_text = self.t(lang, "status_enabled") if current_status else self.t(lang, "status_disabled")
        
        keyboard = [
            [InlineKeyboardButton(
                text=self.t(lang, 'admin_forced_join_toggle'),
                callback_data="forced_join_toggle"
            )],
            [InlineKeyboardButton(
                text=self.t(lang, 'admin_forced_join_add'),
                callback_data="forced_join_add"
            )],
            [InlineKeyboardButton(
                text=self.t(lang, 'admin_forced_join_list'),
                callback_data="forced_join_list"
            )]
        ]
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        text = self.t(lang, "admin_forced_join_status").format(status=f"{status_icon} {status_text}")
        self.in_forced_join_menu.add(message.from_user.id)
        await message.answer(text, reply_markup=kb)

    async def handle_forced_join_toggle(self, message: Message, lang: str):
        try:
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            config_data["bot"]["forced_join"]["enabled"] = not config_data["bot"]["forced_join"]["enabled"]
            
            with open("config/config.json", "w") as f:
                json.dump(config_data, f, indent=2)
            
            status = "enabled" if config_data["bot"]["forced_join"]["enabled"] else "disabled"
            await message.answer(
                self.t(lang, "admin_forced_join_toggled").format(status=self.t(lang, f"status_{status}"))
            )
        except Exception as e:
            logger.error(f"Error toggling forced join: {e}")

    async def handle_forced_join_add(self, message: Message, lang: str):
        self.waiting_for_channel.add(message.from_user.id)
        await message.answer(self.t(lang, "admin_enter_channel"))

    async def handle_forced_join_list(self, message: Message, lang: str):
        channels = self.config.forced_join.get("channels", [])
        
        if channels:
            channels_text = "\n".join([f"• {channel}" for channel in channels])
            text = self.t(lang, "admin_channels_list").format(channels=channels_text)
        else:
            text = self.t(lang, "admin_no_channels")
        
        await message.answer(text)

    async def process_add_channel(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            channel_input = message.text.strip()
            if channel_input.startswith("https://t.me/"):
                channel = "@" + channel_input.replace("https://t.me/", "")
            elif channel_input.startswith("t.me/"):
                channel = "@" + channel_input.replace("t.me/", "")
            elif channel_input.startswith("@"):
                channel = channel_input
            else:
                channel = "@" + channel_input
            
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            if channel not in config_data["bot"]["forced_join"]["channels"]:
                config_data["bot"]["forced_join"]["channels"].append(channel)
                
                with open("config/config.json", "w") as f:
                    json.dump(config_data, f, indent=2)
                
                await message.answer(self.t(lang, "admin_channel_added").format(channel=channel))
            else:
                await message.answer(self.t(lang, "admin_channel_exists"))
                
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            await message.answer(self.t(lang, "admin_error"))
        finally:
            self.waiting_for_channel.discard(user_id)

    def get_forced_join_status_from_config(self):
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            return config_data["bot"]["forced_join"]["enabled"]
        except Exception:
            return self.config.forced_join.get("enabled", False)

    async def check_user_membership(self, user_id):
        if not self.config.forced_join.get("enabled", False):
            return True
        
        channels = self.config.forced_join.get("channels", [])
        if not channels:
            return True
        
        for channel in channels:
            try:
                member = await self.bot.get_chat_member(channel, user_id)
                valid_statuses = ["member", "administrator", "creator"]
                if member.status not in valid_statuses:
                    return False
            except Exception as e:
                if "member list is inaccessible" in str(e):
                    continue
                return False
        
        return True

    async def get_join_keyboard(self, lang):
        channels = self.config.forced_join.get("channels", [])
        buttons = []
        
        for channel in channels:
            channel_name = channel.replace("@", "")
            buttons.append([InlineKeyboardButton(
                text=f"📢 {channel_name}", 
                url=f"https://t.me/{channel_name}"
            )])
        
        buttons.append([InlineKeyboardButton(
            text=self.t(lang, "check_membership"), 
            callback_data="check_membership"
        )])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def handle_forced_join_callback(self, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not self.is_admin(user_id):
            await callback.answer()
            return

        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]

            if callback.data == "forced_join_toggle":
                await self.handle_forced_join_toggle_inline(callback, lang)
            elif callback.data == "forced_join_add":
                await self.handle_forced_join_add_inline(callback, lang)
            elif callback.data == "forced_join_list":
                await self.handle_forced_join_list_inline(callback, lang)
            elif callback.data.startswith("delete_channel_"):
                channel_name = "@" + callback.data.replace("delete_channel_", "")
                await self.show_delete_channel_confirmation(callback, lang, channel_name)
            elif callback.data.startswith("confirm_delete_channel_"):
                channel_name = "@" + callback.data.replace("confirm_delete_channel_", "")
                await self.delete_channel_confirmed(callback, lang, channel_name)
            elif callback.data.startswith("cancel_delete_channel"):
                await self.handle_forced_join_list_inline(callback, lang)
            elif callback.data == "back_to_forced_join":
                await self.back_to_forced_join_menu(callback, lang)

        except Exception as e:
            logger.error(f"Error in handle_forced_join_callback: {e}")
            await callback.answer()

    async def handle_forced_join_toggle_inline(self, callback: CallbackQuery, lang: str):
        try:
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            current_status = config_data["bot"]["forced_join"]["enabled"]
            new_status = not current_status
            config_data["bot"]["forced_join"]["enabled"] = new_status
            
            with open("config/config.json", "w") as f:
                json.dump(config_data, f, indent=2)
            
            self.config.forced_join["enabled"] = new_status
            
            await callback.answer(self.t(lang, "admin_forced_join_toggled"))
            
            await self.update_forced_join_inline_menu(callback.message, lang)
            
        except Exception as e:
            logger.error(f"Error toggling forced join: {e}")
            await callback.answer(self.t(lang, "admin_error"))

    async def handle_forced_join_add_inline(self, callback: CallbackQuery, lang: str):
        user_id = callback.from_user.id
        self.waiting_for_channel.add(user_id)
        self.in_forced_join_menu.discard(user_id)
        
        keyboard = [[KeyboardButton(text=self.t(lang, "cancel_operation"))]]
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        
        await callback.message.answer(self.t(lang, "admin_enter_channel"), reply_markup=kb)
        await callback.answer()

    async def handle_forced_join_list_inline(self, callback: CallbackQuery, lang: str):
        try:
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            channels = config_data["bot"]["forced_join"]["channels"]
            
            if channels:
                text = self.t(lang, "admin_channels_delete_instruction")
                keyboard = []
                
                for channel in channels:
                    keyboard.append([InlineKeyboardButton(
                        text=f"🗑️ {channel}",
                        callback_data=f"delete_channel_{channel[1:]}"  # Remove @ from channel name
                    )])
                
                keyboard.append([InlineKeyboardButton(
                    text=self.t(lang, 'back'),
                    callback_data="back_to_forced_join"
                )])
                
                kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
                await callback.message.edit_text(text, reply_markup=kb)
            else:
                text = self.t(lang, "admin_no_channels")
                keyboard = [[InlineKeyboardButton(
                    text=self.t(lang, 'back'),
                    callback_data="back_to_forced_join"
                )]]
                kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
                await callback.message.edit_text(text, reply_markup=kb)
            
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Error showing channel list: {e}")
            await callback.answer(self.t(lang, "admin_error"))

    async def show_delete_channel_confirmation(self, callback: CallbackQuery, lang: str, channel_name: str):
        try:
            text = self.t(lang, "admin_delete_channel_confirm").format(channel=channel_name)
            
            keyboard = [
                [InlineKeyboardButton(
                    text=self.t(lang, "yes"),
                    callback_data=f"confirm_delete_channel_{channel_name[1:]}"  # Remove @
                )],
                [InlineKeyboardButton(
                    text=self.t(lang, "no"),
                    callback_data="cancel_delete_channel"
                )]
            ]
            
            kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.edit_text(text, reply_markup=kb)
            await callback.answer()
            
        except Exception as e:
            logger.error(f"Error showing delete confirmation: {e}")
            await callback.answer(self.t(lang, "admin_error"))

    async def delete_channel_confirmed(self, callback: CallbackQuery, lang: str, channel_name: str):
        try:
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            if channel_name in config_data["bot"]["forced_join"]["channels"]:
                config_data["bot"]["forced_join"]["channels"].remove(channel_name)
                
                with open("config/config.json", "w") as f:
                    json.dump(config_data, f, indent=2)
                
                await callback.answer(self.t(lang, "admin_channel_deleted").format(channel=channel_name))
                await self.handle_forced_join_list_inline(callback, lang)
            else:
                await callback.answer(self.t(lang, "admin_error"))
                
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            await callback.answer(self.t(lang, "admin_error"))

    async def back_to_forced_join_menu(self, callback: CallbackQuery, lang: str):
        try:
            await self.update_forced_join_inline_menu(callback.message, lang)
            await callback.answer()
        except Exception as e:
            logger.error(f"Error going back to forced join menu: {e}")
            await callback.answer(self.t(lang, "admin_error"))

    async def update_forced_join_inline_menu(self, message: Message, lang: str):
        current_status = self.get_forced_join_status_from_config()
        status_icon = "✅" if current_status else "❌"
        status_text = self.t(lang, "status_enabled") if current_status else self.t(lang, "status_disabled")
        
        keyboard = [
            [InlineKeyboardButton(
                text=self.t(lang, 'admin_forced_join_toggle'),
                callback_data="forced_join_toggle"
            )],
            [InlineKeyboardButton(
                text=self.t(lang, 'admin_forced_join_add'),
                callback_data="forced_join_add"
            )],
            [InlineKeyboardButton(
                text=self.t(lang, 'admin_forced_join_list'),
                callback_data="forced_join_list"
            )]
        ]
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        text = self.t(lang, "admin_forced_join_status").format(status=f"{status_icon} {status_text}")
        
        try:
            await message.edit_text(text, reply_markup=kb)
        except Exception:
            await message.answer(text, reply_markup=kb)

    def is_admin(self, user_id):
        return user_id in self.config.admin_ids
