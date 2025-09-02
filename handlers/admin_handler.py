from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import logging
import json
import os

logger = logging.getLogger(__name__)

class AdminHandler:
    def __init__(self, storage, db, bot, config, locales):
        self.storage = storage
        self.db = db
        self.bot = bot
        self.config = config
        self.locales = locales
        self.waiting_for_admin_id = set()
        self.waiting_for_broadcast = set()
        self.waiting_for_private_message = {}
        self.waiting_for_private_user_id = set()
        self.waiting_for_channel = set()
        self.waiting_for_limit = set()
        self.in_forced_join_menu = set()
        self.waiting_for_delete_user = set()

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
            
            keyboard = [
                [KeyboardButton(text=self.t(lang, "admin_add_admin")), KeyboardButton(text=self.t(lang, "admin_remove_admin"))],
                [KeyboardButton(text=self.t(lang, "admin_general_stats")), KeyboardButton(text=self.t(lang, "admin_delete_user"))],
                [KeyboardButton(text=self.t(lang, "admin_broadcast")), KeyboardButton(text=self.t(lang, "admin_private_message"))],
                [KeyboardButton(text=self.t(lang, "admin_user_limit")), KeyboardButton(text=self.t(lang, "admin_forced_join"))],
                [KeyboardButton(text=self.t(lang, "back"))]
            ]
            
            kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            self.in_forced_join_menu.discard(user_id)
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
                await self.handle_add_admin(message, lang)
            elif button_text == self.t(lang, "admin_remove_admin"):
                await self.handle_remove_admin(message, lang)
            elif button_text == self.t(lang, "admin_general_stats"):
                await self.handle_general_stats(message, lang)
            elif button_text == self.t(lang, "admin_user_limit"):
                await self.handle_user_limit(message, lang)
            elif button_text == self.t(lang, "admin_broadcast"):
                await self.handle_broadcast_start(message, lang)
            elif button_text == self.t(lang, "admin_private_message"):
                await self.handle_private_message_start(message, lang)
            elif button_text == self.t(lang, "admin_forced_join"):
                await self.handle_forced_join_menu(message, lang)
            elif button_text == self.t(lang, "admin_delete_user"):
                await self.handle_delete_user_start(message, lang)
            elif button_text == self.t(lang, "cancel_operation"):
                await self.handle_cancel_operation(message, lang)
            elif button_text == self.t(lang, "back"):
                await self.handle_back_to_main(message, lang)
                
        except Exception as e:
            logger.error(f"Error in handle_admin_button: {e}")

    async def handle_add_admin(self, message: Message, lang: str):
        self.waiting_for_admin_id.add(message.from_user.id)
        await message.answer(self.t(lang, "admin_enter_user_id"))

    async def handle_remove_admin(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            admin_ids = config_data["bot"]["admin_ids"]
            other_admins = [aid for aid in admin_ids if aid != user_id]
            
            if not other_admins:
                await message.answer(self.t(lang, "admin_no_other_admins"))
                return
            
            buttons = []
            for admin_id in other_admins:
                buttons.append([InlineKeyboardButton(
                    text=f"👑 {admin_id}", 
                    callback_data=f"remove_admin_{admin_id}"
                )])
            
            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer(self.t(lang, "admin_select_admin_to_remove"), reply_markup=kb)
            
        except Exception as e:
            logger.error(f"Error in handle_remove_admin: {e}")
            await message.answer(self.t(lang, "admin_error"))

    async def handle_general_stats(self, message: Message, lang: str):
        stats = self.db.get_admin_stats()
        stats_text = self.t(lang, "admin_stats_report").format(**stats)
        await message.answer(stats_text)

    async def handle_user_limit(self, message: Message, lang: str):
        current_limit = self.get_current_limit_from_config()
        limit_text = self.t(lang, "admin_current_limit").format(limit=current_limit)
        self.waiting_for_limit.add(message.from_user.id)
        await message.answer(limit_text)

    async def handle_broadcast_start(self, message: Message, lang: str):
        self.waiting_for_broadcast.add(message.from_user.id)
        
        keyboard = [[KeyboardButton(text=self.t(lang, "cancel_operation"))]]
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        
        await message.answer(self.t(lang, "admin_enter_broadcast"), reply_markup=kb)

    async def handle_private_message_start(self, message: Message, lang: str):
        self.waiting_for_private_user_id.add(message.from_user.id)
        
        keyboard = [[KeyboardButton(text=self.t(lang, "cancel_operation"))]]
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        
        await message.answer(self.t(lang, "admin_enter_user_id_private"), reply_markup=kb)

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

    async def handle_cancel_operation(self, message: Message, lang: str):
        user_id = message.from_user.id
        
        # Clear all possible waiting states
        self.waiting_for_broadcast.discard(user_id)
        self.waiting_for_channel.discard(user_id)
        self.waiting_for_private_user_id.discard(user_id)
        if user_id in self.waiting_for_private_message:
            del self.waiting_for_private_message[user_id]
        self.waiting_for_delete_user.discard(user_id)
        self.in_forced_join_menu.discard(user_id)
        
        await self.show_admin_panel(message)

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

    async def handle_back_to_main(self, message: Message, lang: str):
        keyboard = [
            [KeyboardButton(text=self.t(lang, "btn_new"))],
            [KeyboardButton(text=self.t(lang, "btn_delete")), KeyboardButton(text=self.t(lang, "btn_edit"))],
            [KeyboardButton(text=self.t(lang, "btn_list"))],
            [KeyboardButton(text=self.t(lang, "btn_settings")), KeyboardButton(text=self.t(lang, "btn_stats"))],
            [KeyboardButton(text=self.t(lang, "btn_admin"))]
        ]
        
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(self.t(lang, "menu"), reply_markup=kb)

    async def handle_admin_message(self, message: Message):
        user_id = message.from_user.id
        if not self.is_admin(user_id):
            return
        
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            if user_id in self.waiting_for_admin_id:
                await self.process_add_admin(message, lang)
            elif user_id in self.waiting_for_broadcast:
                await self.process_broadcast(message, lang)
            elif user_id in self.waiting_for_private_user_id:
                await self.process_private_user_id(message, lang)
            elif user_id in self.waiting_for_private_message:
                await self.process_private_message(message, lang)
            elif user_id in self.waiting_for_channel:
                await self.process_add_channel(message, lang)
            elif user_id in self.waiting_for_limit:
                await self.process_limit_change(message, lang)
            elif user_id in self.waiting_for_delete_user:
                await self.process_delete_user(message, lang)
                
        except Exception as e:
            logger.error(f"Error in handle_admin_message: {e}")

    def is_admin_button(self, message_text: str, lang: str) -> bool:
        admin_buttons = [
            "admin_add_admin", "admin_remove_admin", "admin_general_stats", "admin_user_limit",
            "admin_broadcast", "admin_private_message", "admin_forced_join", "admin_delete_user",
            "back", "cancel_operation"
        ]
        return any(message_text == self.t(lang, btn) for btn in admin_buttons)

    async def process_add_admin(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            new_admin_id = int(message.text.strip())
            
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            if new_admin_id not in config_data["bot"]["admin_ids"]:
                config_data["bot"]["admin_ids"].append(new_admin_id)
                
                with open("config/config.json", "w") as f:
                    json.dump(config_data, f, indent=2)
                
                await message.answer(self.t(lang, "admin_added_success").format(admin_id=new_admin_id))
            else:
                await message.answer(self.t(lang, "admin_already_exists"))
                
        except ValueError:
            await message.answer(self.t(lang, "admin_invalid_id"))
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            await message.answer(self.t(lang, "admin_error"))
        finally:
            self.waiting_for_admin_id.discard(user_id)

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
            await self.show_admin_panel(message)
            
        except Exception as e:
            logger.error(f"Error in broadcast: {e}")
            await message.answer(self.t(lang, "admin_error"))
            await self.show_admin_panel(message)
        finally:
            self.waiting_for_broadcast.discard(user_id)

    async def process_private_user_id(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            target_user_id = int(message.text.strip())
            self.waiting_for_private_user_id.discard(user_id)
            self.waiting_for_private_message[user_id] = target_user_id
            
            keyboard = [[KeyboardButton(text=self.t(lang, "cancel_operation"))]]
            kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
            
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
            await self.show_admin_panel(message)
        except Exception as e:
            logger.error(f"Error sending private message: {e}")
            await message.answer(self.t(lang, "admin_error"))
        finally:
            del self.waiting_for_private_message[user_id]

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
                await self.show_admin_panel(message)
            else:
                await message.answer(self.t(lang, "admin_channel_exists"))
                
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            await message.answer(self.t(lang, "admin_error"))
        finally:
            self.waiting_for_channel.discard(user_id)

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

    async def handle_admin_removal_callback(self, callback: CallbackQuery):
        user_id = callback.from_user.id
        if not self.is_admin(user_id):
            await callback.answer()
            return
        
        try:
            data = self.storage.load(user_id)
            lang = data["settings"]["language"]
            
            if callback.data.startswith("remove_admin_"):
                admin_to_remove = int(callback.data.replace("remove_admin_", ""))
                
                if admin_to_remove == user_id:
                    await callback.answer(self.t(lang, "admin_cannot_remove_self"), show_alert=True)
                    return
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=self.t(lang, "yes"), callback_data=f"confirm_remove_{admin_to_remove}")],
                    [InlineKeyboardButton(text=self.t(lang, "no"), callback_data="cancel_remove")]
                ])
                
                confirm_text = self.t(lang, "admin_remove_confirm").format(admin_id=admin_to_remove)
                await callback.message.edit_text(confirm_text, reply_markup=kb)
                
            elif callback.data.startswith("confirm_remove_"):
                admin_to_remove = int(callback.data.replace("confirm_remove_", ""))
                await self.remove_admin_from_config(admin_to_remove, callback, lang)
                
            elif callback.data == "cancel_remove":
                await callback.message.delete()
                
        except Exception as e:
            logger.error(f"Error in handle_admin_removal_callback: {e}")
        finally:
            await callback.answer()

    async def remove_admin_from_config(self, admin_id: int, callback: CallbackQuery, lang: str):
        try:
            config_data = {}
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            
            if admin_id in config_data["bot"]["admin_ids"]:
                config_data["bot"]["admin_ids"].remove(admin_id)
                
                with open("config/config.json", "w") as f:
                    json.dump(config_data, f, indent=2)
                
                success_text = self.t(lang, "admin_removed_success").format(admin_id=admin_id)
                await callback.message.edit_text(success_text)
            else:
                await callback.message.edit_text(self.t(lang, "admin_error"))
                
        except Exception as e:
            logger.error(f"Error removing admin from config: {e}")
            await callback.message.edit_text(self.t(lang, "admin_error"))



    async def handle_delete_user_start(self, message: Message, lang: str):
        self.waiting_for_delete_user.add(message.from_user.id)
        keyboard = [[KeyboardButton(text=self.t(lang, "cancel_operation"))]]
        kb = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(self.t(lang, "enter_user_id_delete"), reply_markup=kb)

    async def process_delete_user(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            target_input = message.text.strip()
            
            if target_input.startswith("@"):
                target_user_display = target_input
                target_user_id = None
                user_found = False
                users_path = self.storage.path
                for filename in os.listdir(users_path):
                    if filename.endswith('.json'):
                        try:
                            file_user_id = int(filename.replace('.json', ''))
                            user_file = os.path.join(users_path, filename)
                            if os.path.exists(user_file):
                                os.remove(user_file)
                                user_found = True
                        except:
                            continue
                
                if user_found:
                    await message.answer(self.t(lang, "user_deleted_success").format(user_id=target_user_display))
                else:
                    await message.answer(self.t(lang, "user_not_found"))
            else:
                try:
                    target_user_id = int(target_input)
                    target_user_display = str(target_user_id)
                    
                    if target_user_id in self.config.admin_ids:
                        await message.answer(self.t(lang, "admin_error"))
                        return
                    
                    user_file = self.storage.file(target_user_id)
                    if os.path.exists(user_file):
                        os.remove(user_file)
                        
                        try:
                            user_reminders = self.db.list(target_user_id)
                            for reminder_id, _, _, _, _, _, _ in user_reminders:
                                self.db.update_status(reminder_id, "cancelled")
                        except Exception as db_error:
                            logger.error(f"Error deleting user reminders from DB: {db_error}")
                        
                        await message.answer(self.t(lang, "user_deleted_success").format(user_id=target_user_display))
                    else:
                        await message.answer(self.t(lang, "user_not_found"))
                        
                except ValueError:
                    await message.answer(self.t(lang, "admin_invalid_id"))
                    return
                
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            await message.answer(self.t(lang, "admin_error"))
        finally:
            self.waiting_for_delete_user.discard(user_id)
            await self.show_admin_panel(message)

