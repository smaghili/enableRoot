import json
import re
import logging
from typing import Any

class ReminderValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_parsed_object(self, obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        
        required_keys = ["category", "content", "repeat"]
        if not all(k in obj for k in required_keys):
            return False
        
        valid_categories = [
            "birthday", "anniversary", "medicine", "appointment", "work", "exercise", 
            "prayer", "shopping", "call", "study", "installment", "bill", "general"
        ]
        
        if obj.get("category") not in valid_categories:
            obj["category"] = "general"
        
        self._normalize_repeat_field(obj)
        return True
    
    def _normalize_repeat_field(self, obj: dict) -> None:
        if "repeat" in obj and isinstance(obj["repeat"], dict):
            obj["repeat"] = json.dumps(obj["repeat"])
    
    def normalize_repeat_field(self, obj: dict) -> None:
        if "repeat" in obj:
            if isinstance(obj["repeat"], str):
                if obj["repeat"] in ["none", "daily", "weekly", "monthly", "yearly"]:
                    obj["repeat"] = f'{{"type": "{obj["repeat"]}"}}'
                elif re.match(r'^every_\d+_(hours|minutes|days|weeks)$', obj["repeat"]):
                    match = re.match(r'^every_(\d+)_(hours|minutes|days|weeks)$', obj["repeat"])
                    if match:
                        value = int(match.group(1))
                        unit = match.group(2)
                        obj["repeat"] = f'{{"type": "interval", "value": {value}, "unit": "{unit}"}}'
                else:
                    obj["repeat"] = '{"type": "none"}'
            elif isinstance(obj["repeat"], dict):
                if obj["repeat"].get("type") == "interval":
                    if not isinstance(obj["repeat"].get("value"), (int, float)) or not obj["repeat"].get("unit"):
                        obj["repeat"] = '{"type": "none"}'
                elif obj["repeat"].get("type") in ["none", "daily", "weekly", "monthly", "yearly"]:
                    pass
                else:
                    obj["repeat"] = '{"type": "none"}'
            else:
                obj["repeat"] = '{"type": "none"}'
        else:
            obj["repeat"] = '{"type": "none"}'
        
        self._normalize_repeat_field(obj)
