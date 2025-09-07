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
        os.makedirs(self.path, exist_ok=True)
    
    def set_db(self, db):
        self.db = db
    
    def secure_load(self, user_id: int) -> Dict[str, Any]:
        if self.db and not self.db.is_valid_user(user_id, self):
            raise ValueError("Invalid user - deleted or unauthorized")
        return self.load(user_id)
    
    def get_restart_message(self, lang: str = "fa") -> str:
        # Use localization system instead of hard-coded messages
        from config.localization_manager import LocalizationManager
        loc_manager = LocalizationManager()
        return loc_manager.get_text(lang, "update_notification")
    
    def file(self, user_id: int) -> str:
        return os.path.join(self.path, f"{user_id}.json")
        
    def load(self, user_id: int) -> Dict[str, Any]:
        with self.lock:
            if self.db and not self.db.is_valid_user(user_id, self):
                raise PermissionError(f"Access denied for user {user_id}")
                
            p = self.file(user_id)
            default_data = self._get_default_data(user_id)
            
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "settings" in data:
                            return data
                        else:
                            raise json.JSONDecodeError("Invalid data structure", "", 0)
                except (json.JSONDecodeError, IOError):
                    self._save_file(p, default_data)
                    return default_data
            else:
                self._save_file(p, default_data)
                    
            return default_data
    
    def _get_default_data(self, user_id: int) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "reminders": {"active": [], "completed": [], "cancelled": []},
            "settings": {"language": "fa", "timezone": "+03:30", "calendar": "shamsi", "reminder_creation_count": 0},
            "activity": {"last_activity": datetime.datetime.now().isoformat()}
        }
    
    def _save_file(self, path: str, data: Dict[str, Any]) -> None:
        with open(path, "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def save(self, user_id: int, data: Dict[str, Any]) -> None:
        with self.lock:
            try:
                self._save_file(self.file(user_id), data)
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