from functools import wraps
from aiogram.types import Message
import logging

logger = logging.getLogger(__name__)

def admin_operation(operation_name: str, success_message: str = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, message: Message, *args, **kwargs):
            user_id = message.from_user.id
            try:
                result = await func(self, message, *args, **kwargs)
                if result and success_message:
                    await self.complete_operation(message, success_message, **kwargs)
                elif result:
                    data = self.storage.secure_load(user_id)
                    lang = data["settings"]["language"]
                    admin_kb = self.create_admin_keyboard(lang)
                    await message.answer("✅ Operation completed", reply_markup=admin_kb)
                return result
            except Exception as e:
                logger.error(f"Error in {operation_name} for user {user_id}: {e}")
                await self.handle_error(message, "admin_export_error")
                return False
                
        return wrapper
    return decorator

def requires_admin_input(input_type: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, message: Message, *args, **kwargs):
            user_id = message.from_user.id
            if not self.is_operation_active(user_id):
                return False
            try:
                if input_type == 'reminder_id':
                    value = int(message.text.strip())
                elif input_type == 'user_id':
                    value = int(message.text.strip())
                else:
                    value = message.text.strip()
                return await func(self, message, value, *args, **kwargs)
            except ValueError:
                await self.handle_error(message, f"admin_invalid_{input_type}")
                return True
            except Exception as e:
                logger.error(f"Error processing {input_type}: {e}")
                await self.handle_error(message, "admin_export_error")
                return True
                
        return wrapper
    return decorator

def auto_keyboard_management(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            result = await func(self, *args, **kwargs)
            return result
        except Exception as e:
            if hasattr(self, 'handle_error') and len(args) > 0:
                message = args[0] if hasattr(args[0], 'from_user') else None
                if message:
                    await self.handle_error(message, "admin_export_error")
            raise e
    return wrapper
