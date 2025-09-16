from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
import logging
import os
import tempfile
from pathlib import Path
from .base_admin_manager import BaseAdminManager
from utils.menu_factory import MenuFactory

logger = logging.getLogger(__name__)

class AdminPromptManager(BaseAdminManager):
    def __init__(self, storage, config, locales, bot=None):
        super().__init__(storage, config, locales)
        self.bot = bot
        self.waiting_for_prompt_edit = set()
        self.current_prompt_type = {}
        self.prompts_dir = Path("config/prompts")
        
        self.prompt_files = {
            "add": "reminder_parsing.txt",
            "edit": "edit_reminder.txt", 
            "timezone": "timezone_detection.txt"
        }

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    async def handle_prompt_edit_menu(self, message: Message, lang: str):
        buttons = [
            [InlineKeyboardButton(text=self.t(lang, "prompt_add_reminder"), callback_data="edit_prompt_add")],
            [InlineKeyboardButton(text=self.t(lang, "prompt_edit_reminder"), callback_data="edit_prompt_edit")],
            [InlineKeyboardButton(text=self.t(lang, "prompt_timezone_detection"), callback_data="edit_prompt_timezone")],
            [InlineKeyboardButton(text=self.t(lang, "cancel_operation"), callback_data="cancel_prompt_edit")]
        ]
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(self.t(lang, "admin_prompt_edit_menu"), reply_markup=kb)

    async def handle_prompt_edit_callback(self, callback, lang: str):
        user_id = callback.from_user.id
        data = callback.data
        
        if data == "cancel_prompt_edit":
            await callback.message.delete()
            kb = MenuFactory.create_admin_panel(lang, self.t)
            await callback.message.answer(self.t(lang, "admin_panel"), reply_markup=kb)
            await callback.answer(self.t(lang, "operation_cancelled"))
            return
            
        prompt_type = data.replace("edit_prompt_", "")
        if prompt_type in self.prompt_files:
            current_prompt = self._get_current_prompt(prompt_type)
            
            self.current_prompt_type[user_id] = prompt_type
            self.waiting_for_prompt_edit.add(user_id)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(current_prompt)
                temp_filename = temp_file.name
            
            try:
                await callback.message.delete()
                await callback.message.answer_document(
                    document=FSInputFile(temp_filename, filename=f"{prompt_type}_prompt.txt"),
                    caption=self.t(lang, "admin_current_prompt_file").format(
                        type=self._get_prompt_type_name(prompt_type, lang)
                    )
                )
            finally:
                os.unlink(temp_filename)
            
            cancel_kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=self.t(lang, "cancel_operation"))]],
                resize_keyboard=True
            )
            await callback.message.answer(self.t(lang, "admin_enter_new_prompt"), reply_markup=cancel_kb)
            await callback.answer()

    async def process_prompt_edit(self, message: Message, lang: str):
        user_id = message.from_user.id
        
        if user_id not in self.waiting_for_prompt_edit:
            return
            
        if message.text and message.text == self.t(lang, "cancel_operation"):
            self._cleanup_user_state(user_id)
            kb = MenuFactory.create_admin_panel(lang, self.t)
            await message.answer(self.t(lang, "operation_cancelled"), reply_markup=kb)
            return
            
        if not message.document or not message.document.file_name.endswith('.txt'):
            await message.answer(self.t(lang, "admin_invalid_prompt"))
            return
            
        prompt_type = self.current_prompt_type.get(user_id)
        if not prompt_type:
            await message.answer(self.t(lang, "admin_invalid_prompt"))
            return
            
        try:
            file = await self.bot.get_file(message.document.file_id)
            file_content = await self.bot.download_file(file.file_path)
            new_prompt = file_content.read().decode('utf-8').strip()
        except Exception as e:
            logger.error(f"Error reading uploaded file: {e}")
            await message.answer(self.t(lang, "admin_prompt_update_error"))
            return
            
        if not new_prompt:
            await message.answer(self.t(lang, "admin_invalid_prompt"))
            return
            
        buttons = [
            [InlineKeyboardButton(text="✅ " + self.t(lang, "confirm"), callback_data=f"confirm_prompt_{prompt_type}")],
            [InlineKeyboardButton(text=self.t(lang, "cancel"), callback_data="cancel_prompt_change")]
        ]
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        self.pending_prompts = getattr(self, 'pending_prompts', {})
        self.pending_prompts[user_id] = new_prompt
        
        await message.answer(
            self.t(lang, "admin_prompt_change_warning").format(
                type=self._get_prompt_type_name(prompt_type, lang)
            ),
            reply_markup=kb
        )

    async def handle_prompt_confirmation(self, callback, lang: str):
        user_id = callback.from_user.id
        data = callback.data
        
        if data == "cancel_prompt_change":
            self._cleanup_user_state(user_id)
            await callback.message.edit_text(self.t(lang, "operation_cancelled"))
            kb = MenuFactory.create_admin_panel(lang, self.t)
            await callback.message.answer(self.t(lang, "admin_panel"), reply_markup=kb)
            await callback.answer()
            return
            
        if data.startswith("confirm_prompt_"):
            prompt_type = data.replace("confirm_prompt_", "")
            new_prompt = getattr(self, 'pending_prompts', {}).get(user_id)
            
            if new_prompt and prompt_type in self.prompt_files:
                success = self._save_prompt(prompt_type, new_prompt)
                
                if success:
                    await callback.message.edit_text(
                        self.t(lang, "admin_prompt_updated").format(
                            type=self._get_prompt_type_name(prompt_type, lang)
                        )
                    )
                    
                    kb = MenuFactory.create_admin_panel(lang, self.t)
                    await callback.message.answer(self.t(lang, "admin_panel"), reply_markup=kb)
                else:
                    await callback.message.edit_text(self.t(lang, "admin_prompt_update_error"))
                    
                self._cleanup_user_state(user_id)
                await callback.answer()

    def _get_current_prompt(self, prompt_type: str) -> str:
        prompt_file = self.prompts_dir / self.prompt_files[prompt_type]
        try:
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            return "Prompt not found"
        except Exception as e:
            logger.error(f"Error reading prompt file {prompt_file}: {e}")
            return "Error reading prompt"

    def _save_prompt(self, prompt_type: str, new_prompt: str) -> bool:
        prompt_file = self.prompts_dir / self.prompt_files[prompt_type]
        try:
            self.prompts_dir.mkdir(exist_ok=True)
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(new_prompt)
            return True
        except Exception as e:
            logger.error(f"Error saving prompt file {prompt_file}: {e}")
            return False

    def _get_prompt_type_name(self, prompt_type: str, lang: str) -> str:
        type_keys = {
            "add": "prompt_add_reminder",
            "edit": "prompt_edit_reminder", 
            "timezone": "prompt_timezone_detection"
        }
        key = type_keys.get(prompt_type, "")
        if key:
            return self.t(lang, key).split(" ", 1)[-1] if " " in self.t(lang, key) else self.t(lang, key)
        return prompt_type

    def _cleanup_user_state(self, user_id: int):
        self.waiting_for_prompt_edit.discard(user_id)
        self.current_prompt_type.pop(user_id, None)
        if hasattr(self, 'pending_prompts'):
            self.pending_prompts.pop(user_id, None)

    def cancel_operation(self, user_id: int):
        self._cleanup_user_state(user_id)

    def is_operation_active(self, user_id: int) -> bool:
        return user_id in self.waiting_for_prompt_edit

    async def get_operation_prompt(self, lang: str, operation_key: str) -> str:
        return self.t(lang, "admin_enter_new_prompt")
