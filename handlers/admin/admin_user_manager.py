from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import json

logger = logging.getLogger(__name__)

class AdminUserManager:
    def __init__(self, storage, config, locales):
        self.storage = storage
        self.config = config
        self.locales = locales
        self.waiting_for_admin_id = set()

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
