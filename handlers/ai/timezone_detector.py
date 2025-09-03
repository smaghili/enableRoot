import logging
from typing import Optional

class TimezoneDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_timezone(self, timezone: str) -> bool:
        try:
            if not timezone or not isinstance(timezone, str):
                return False
            if not (timezone.startswith("+") or timezone.startswith("-")):
                return False
            if ":" not in timezone:
                return False
            sign = timezone[0]
            time_part = timezone[1:]
            hours, minutes = time_part.split(":")
            hours_int = int(hours)
            minutes_int = int(minutes)
            if not (-12 <= hours_int <= 14):
                return False
            if not (0 <= minutes_int <= 59):
                return False
            return True
        except (ValueError, TypeError, IndexError):
            return False
