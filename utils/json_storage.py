import json
import os
import threading
import datetime
from typing import Dict, Any


class JSONStorage:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.db = None
    
    def set_db(self, db):
        self.db = db
    
    def secure_load(self, user_id: int) -> Dict[str, Any]:
        """
        Securely load user data after validating user exists.
        Raises ValueError if user is invalid (deleted or unauthorized).
        """
        if self.db and not self.db.is_valid_user(user_id, self):
            raise ValueError("Invalid user - deleted or unauthorized")
        return self.load(user_id)
    
    def get_restart_message(self, lang: str = "fa") -> str:
        messages = {
            "fa": "لطفا جهت دریافت آپدیت ربات با ارسال دستور /start ربات را مجدد راه اندازی کنید🙏",
            "en": "Please restart the bot by sending /start command to receive updates🙏",
            "ar": "يرجى إعادة تشغيل البوت بإرسال الأمر /start لتلقي التحديثات🙏",
            "ru": "Пожалуйста, перезапустите бота, отправив команду /start для получения обновлений🙏"
        }
        return messages.get(lang, messages["fa"])
        os.makedirs(self.path, exist_ok=True)
        
    def file(self, user_id: int) -> str:
        return os.path.join(self.path, f"{user_id}.json")
        
    def load(self, user_id: int) -> Dict[str, Any]:
        """
        Load user data from storage file.
        Creates default data if file doesn't exist.
        Raises PermissionError if user is not valid.
        """
        with self.lock:
            # Security check: prevent deleted users from creating files
            if self.db and not self.db.is_valid_user(user_id, self):
                raise PermissionError(f"Access denied for user {user_id}")
            p = self.file(user_id)
            default_data = {
                "user_id": user_id,
                "reminders": {"active": [], "completed": [], "cancelled": []},
                "settings": {"language": "fa", "timezone": "+03:30", "calendar": "shamsi", "reminder_creation_count": 0},
                "activity": {"last_activity": datetime.datetime.now().isoformat()}
            }
            
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "settings" in data:
                            return data
                        else:
                            raise json.JSONDecodeError("Invalid data structure", "", 0)
                except (json.JSONDecodeError, IOError):
                    with open(p, "w", encoding='utf-8') as w:
                        json.dump(default_data, w, ensure_ascii=False, indent=2)
                    return default_data
            else:
                with open(p, "w", encoding='utf-8') as w:
                    json.dump(default_data, w, ensure_ascii=False, indent=2)
                    
            return default_data
            
    def save(self, user_id: int, data: Dict[str, Any]) -> None:
        with self.lock:
            try:
                with open(self.file(user_id), "w", encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except IOError as e:
                raise Exception(f"Failed to save user data: {e}")
                
    def update_setting(self, user_id: int, key: str, value: Any) -> None:
        if not key or not isinstance(key, str):
            raise ValueError("Invalid setting key")
            
        data = self.load(user_id)
        if "settings" not in data:
            data["settings"] = {}
        data["settings"][key] = value
        self.save(user_id, data)
        
    def add_reminder(self, user_id: int, reminder: Dict[str, Any]) -> None:
        if not isinstance(reminder, dict):
            raise ValueError("Invalid reminder data")
            
        data = self.load(user_id)
        if "reminders" not in data:
            data["reminders"] = {"active": [], "completed": [], "cancelled": []}
        data["reminders"]["active"].append(reminder)
        self.save(user_id, data)
        
    def get_user_language(self, user_id: int) -> str:
        try:
            data = self.load(user_id)
            return data.get("settings", {}).get("language", "en")
        except Exception:
            return "en"
            
    def get_text(self, lang: str, key: str, **kwargs) -> str:
        import os
        base_path = os.path.dirname(__file__)
        locale_file = os.path.join(base_path, "localization", f"{lang}.json")
        
        try:
            with open(locale_file, 'r', encoding='utf-8') as f:
                locales = json.load(f)
                text = locales.get(key, key)
                if kwargs:
                    return text.format(**kwargs)
                return text
        except (FileNotFoundError, json.JSONDecodeError):
            return key
            
    def increment_reminder_creation_count(self, user_id: int) -> int:
        data = self.load(user_id)
        if "settings" not in data:
            data["settings"] = {}
        current_count = data["settings"].get("reminder_creation_count", 0)
        new_count = current_count + 1
        data["settings"]["reminder_creation_count"] = new_count
        self.save(user_id, data)
        return new_count
    
    def get_reminder_creation_count(self, user_id: int) -> int:
        data = self.load(user_id)
        return data.get("settings", {}).get("reminder_creation_count", 0)

    def get_all_users(self):
        users = []
        for filename in os.listdir(self.path):
            if filename.endswith('.json'):
                try:
                    user_id = int(filename[:-5])
                    data = self.load(user_id)
                    users.append(data)
                except (ValueError, Exception):
                    continue
        return users
    
    def update_last_activity(self, user_id: int) -> None:
        data = self.load(user_id)
        if "activity" not in data:
            data["activity"] = {}
        data["activity"]["last_activity"] = datetime.datetime.now().isoformat()
        self.save(user_id, data)
    
    def get_last_activity(self, user_id: int) -> datetime.datetime:
        data = self.load(user_id)
        activity_data = data.get("activity", {})
        last_activity_str = activity_data.get("last_activity")
        
        if last_activity_str:
            try:
                return datetime.datetime.fromisoformat(last_activity_str)
            except ValueError:
                pass
        return datetime.datetime.now()
    
    def is_user_inactive(self, user_id: int, days_threshold: int) -> bool:
        last_activity = self.get_last_activity(user_id)
        days_since_activity = (datetime.datetime.now() - last_activity).days
        return days_since_activity > days_threshold