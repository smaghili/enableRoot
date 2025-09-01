import json
import os
import threading
from typing import Dict, Any


class JSONStorage:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        os.makedirs(self.path, exist_ok=True)
        
    def file(self, user_id: int) -> str:
        return os.path.join(self.path, f"{user_id}.json")
        
    def load(self, user_id: int) -> Dict[str, Any]:
        with self.lock:
            p = self.file(user_id)
            default_data = {
                "user_id": user_id,
                "reminders": {"active": [], "completed": [], "cancelled": []},
                "settings": {"language": "fa", "timezone": "+03:30", "setup_complete": False}
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