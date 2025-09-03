from aiogram.types import Message
import logging
import os
from .base_admin_manager import BaseAdminManager

logger = logging.getLogger(__name__)

class AdminUserDeletionManager(BaseAdminManager):
    def __init__(self, storage, db, config, locales):
        super().__init__(storage, config, locales)
        self.db = db
        self.waiting_for_delete_user = set()

    async def handle_delete_user_start(self, message: Message, lang: str):
        self.waiting_for_delete_user.add(message.from_user.id)
        kb = self.create_cancel_keyboard(lang)
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
                        self.waiting_for_delete_user.discard(user_id)
                        await self.return_to_admin_panel(message, lang)
                    else:
                        await message.answer(self.t(lang, "user_not_found"))
                        self.waiting_for_delete_user.discard(user_id)
                        await self.return_to_admin_panel(message, lang)
                        
                except ValueError:
                    await message.answer(self.t(lang, "admin_invalid_id"))
                
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            await message.answer(self.t(lang, "admin_error"))
            self.waiting_for_delete_user.discard(user_id)
            await self.return_to_admin_panel(message, lang)
