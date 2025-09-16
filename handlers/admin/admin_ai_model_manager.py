from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import json
from .base_admin_manager import BaseAdminManager
from utils.menu_factory import MenuFactory

logger = logging.getLogger(__name__)

class AdminAIModelManager(BaseAdminManager):
    def __init__(self, storage, config, locales):
        super().__init__(storage, config, locales)
        self.waiting_for_model_confirmation = {}
        
        self.available_models = [
            "gpt-4o",
            "gpt-4o-mini", 
            "gpt-3.5-turbo",
            "gemini-2.0-flash-exp:free",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "claude-sonnet-4",
            "claude-3.5-sonnet",
            "deepseek-r1:free"
        ]

    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    async def handle_ai_model_menu(self, message: Message, lang: str):
        current_model = self.config.ai_model
        
        buttons = []
        for model in self.available_models:
            emoji = "✅" if model == current_model else "🔘"
            button_text = f"{emoji} {model}"
            buttons.append([InlineKeyboardButton(
                text=button_text, 
                callback_data=f"select_model_{model}"
            )])
        
        buttons.append([InlineKeyboardButton(
            text=self.t(lang, "cancel_operation"), 
            callback_data="cancel_model_change"
        )])
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(
            self.t(lang, "admin_ai_model_menu").format(current=current_model),
            reply_markup=kb
        )

    async def handle_model_selection_callback(self, callback, lang: str):
        user_id = callback.from_user.id
        data = callback.data
        
        if data == "cancel_model_change":
            await callback.message.delete()
            kb = MenuFactory.create_admin_panel(lang, self.t)
            await callback.message.answer(self.t(lang, "admin_panel"), reply_markup=kb)
            await callback.answer(self.t(lang, "operation_cancelled"))
            return
            
        if data.startswith("select_model_"):
            selected_model = data.replace("select_model_", "")
            current_model = self.config.ai_model
            
            if selected_model == current_model:
                await callback.answer(
                    self.t(lang, "admin_model_already_selected").format(model=selected_model),
                    show_alert=True
                )
                return
                
            if selected_model in self.available_models:
                self.waiting_for_model_confirmation[user_id] = selected_model
                
                buttons = [
                    [InlineKeyboardButton(text="✅ " + self.t(lang, "confirm"), callback_data=f"confirm_model_{selected_model}")],
                    [InlineKeyboardButton(text=self.t(lang, "cancel"), callback_data="cancel_model_confirmation")]
                ]
                
                kb = InlineKeyboardMarkup(inline_keyboard=buttons)
                
                await callback.message.edit_text(
                    self.t(lang, "admin_model_change_warning").format(
                        current=current_model,
                        new=selected_model
                    ),
                    reply_markup=kb
                )
                await callback.answer()

    async def handle_model_confirmation(self, callback, lang: str):
        user_id = callback.from_user.id
        data = callback.data
        
        if data == "cancel_model_confirmation":
            self.waiting_for_model_confirmation.pop(user_id, None)
            await callback.message.edit_text(self.t(lang, "operation_cancelled"))
            kb = MenuFactory.create_admin_panel(lang, self.t)
            await callback.message.answer(self.t(lang, "admin_panel"), reply_markup=kb)
            await callback.answer()
            return
            
        if data.startswith("confirm_model_"):
            selected_model = data.replace("confirm_model_", "")
            stored_model = self.waiting_for_model_confirmation.get(user_id)
            
            if selected_model == stored_model and selected_model in self.available_models:
                success = self._update_ai_model(selected_model)
                
                if success:
                    await callback.message.edit_text(
                        self.t(lang, "admin_model_updated").format(model=selected_model)
                    )
                    
                    kb = MenuFactory.create_admin_panel(lang, self.t)
                    await callback.message.answer(self.t(lang, "admin_panel"), reply_markup=kb)
                    
                else:
                    await callback.message.edit_text(self.t(lang, "admin_model_update_error"))
                    
                self.waiting_for_model_confirmation.pop(user_id, None)
                await callback.answer()

    def _update_ai_model(self, new_model: str) -> bool:
        try:
            config_file = "config/config.json"
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if "ai" not in config_data:
                config_data["ai"] = {}
            
            config_data["ai"]["model"] = new_model
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            self.config.ai_model = new_model
            
            return True
        except Exception as e:
            logger.error(f"Error updating AI model in config: {e}")
            return False

    def cancel_operation(self, user_id: int):
        self.waiting_for_model_confirmation.pop(user_id, None)

    def is_operation_active(self, user_id: int) -> bool:
        return user_id in self.waiting_for_model_confirmation

    async def get_operation_prompt(self, lang: str, operation_key: str) -> str:
        current_model = self.config.ai_model
        return self.t(lang, "admin_ai_model_menu").format(current=current_model)
