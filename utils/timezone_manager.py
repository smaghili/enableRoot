import datetime

class TimezoneManager:
    @staticmethod
    def parse_timezone(timezone_str: str) -> datetime.timedelta:
        if not timezone_str:
            return datetime.timedelta(0)
        sign = 1 if timezone_str.startswith("+") else -1
        hours, minutes = timezone_str[1:].split(":")
        return datetime.timedelta(hours=sign * int(hours), minutes=sign * int(minutes))
    
    @classmethod
    def utc_to_local(cls, utc_time_str: str, timezone_str: str) -> datetime.datetime:
        try:
            dt_utc = datetime.datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M")
            tz_offset = cls.parse_timezone(timezone_str)
            return dt_utc + tz_offset
        except (ValueError, TypeError, AttributeError):
            return datetime.datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M")
    
    @classmethod
    def local_to_utc(cls, local_time_str: str, timezone_str: str) -> datetime.datetime:
        try:
            dt_local = datetime.datetime.strptime(local_time_str, "%Y-%m-%d %H:%M")
            tz_offset = cls.parse_timezone(timezone_str)
            return dt_local - tz_offset
        except (ValueError, TypeError, AttributeError):
            return datetime.datetime.strptime(local_time_str, "%Y-%m-%d %H:%M")
    
    @classmethod
    def format_for_display(cls, utc_time_str: str, timezone_str: str, calendar_type: str = "miladi") -> str:
        try:
            dt_local = cls.utc_to_local(utc_time_str, timezone_str)
            local_time_str = dt_local.strftime("%Y-%m-%d %H:%M")
            from .date_converter import DateConverter
            converter = DateConverter()
            return converter.convert_to_user_calendar(local_time_str, calendar_type, None)
        except Exception:
            return utc_time_str
