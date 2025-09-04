from typing import Tuple
from .timezone_manager import TimezoneManager

class DisplayHelper:
    def format_reminder_time(self, utc_time: str, timezone: str, calendar_type: str) -> str:
        return TimezoneManager.format_for_display(utc_time, timezone, calendar_type)
    
    def format_reminder_display(self, reminder_tuple: Tuple, calendar_type: str, user_timezone: str = None) -> dict:
        if len(reminder_tuple) < 7:
            return {}
        rid, category, content, utc_time, stored_timezone, repeat, status = reminder_tuple
        display_timezone = user_timezone if user_timezone else stored_timezone
        display_time = self.format_reminder_time(utc_time, display_timezone, calendar_type)
        return {
            'id': rid,
            'category': category,
            'content': content,
            'utc_time': utc_time,
            'display_time': display_time,
            'timezone': display_timezone,
            'repeat': repeat,
            'status': status
        }
