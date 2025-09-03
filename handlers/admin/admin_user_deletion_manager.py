from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import logging
import os

logger = logging.getLogger(__name__)

class AdminUserDeletionManager:
    def __init__(self, storage, db, config, locales):
        self.storage = storage
        self.db = db
        self.config = config
        self.locales = locales
        self.waiting_for_delete_user = set()

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

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
