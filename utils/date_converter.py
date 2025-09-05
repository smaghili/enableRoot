import datetime
from convertdate import persian, gregorian, islamic
from typing import Optional
from .date_parser import DateParser
from .persian_numbers import PersianNumbers

class DateConverter:
    def __init__(self):
        self.date_parser = DateParser()
    
    def convert_to_user_calendar(self, local_datetime_str: str, calendar_type: str, timezone: str = None, language: str = "en") -> str:
        try:
            dt_local = datetime.datetime.strptime(local_datetime_str, "%Y-%m-%d %H:%M")
            
            if calendar_type == "shamsi":
                date_part = self.date_parser.format_for_display(dt_local, "shamsi")
                result = f"{date_part} {dt_local.hour:02d}:{dt_local.minute:02d}"
                if language == "fa":
                    result = PersianNumbers.to_persian(result)
                return result
            elif calendar_type in ["qamari", "hijri"]:
                date_part = self.date_parser.format_for_display(dt_local, "hijri")
                result = f"{date_part} {dt_local.hour:02d}:{dt_local.minute:02d}"
                if language == "fa":
                    result = PersianNumbers.to_persian(result)
                return result
            else:
                result = dt_local.strftime("%Y/%m/%d %H:%M")
                if language == "fa":
                    result = PersianNumbers.to_persian(result)
                return result
        except Exception:
            return local_datetime_str

    @staticmethod
    def _to_shamsi(dt: datetime.datetime) -> str:
        try:
            persian_date = persian.from_gregorian(dt.year, dt.month, dt.day)
            return f"{persian_date[0]}/{persian_date[1]:02d}/{persian_date[2]:02d} {dt.hour:02d}:{dt.minute:02d}"
        except Exception:
            return dt.strftime("%Y/%m/%d %H:%M")

    @staticmethod
    def _to_qamari(dt: datetime.datetime) -> str:
        try:
            islamic_date = islamic.from_gregorian(dt.year, dt.month, dt.day)
            return f"{islamic_date[0]}/{islamic_date[1]:02d}/{islamic_date[2]:02d} {dt.hour:02d}:{dt.minute:02d}"
        except Exception:
            return dt.strftime("%Y/%m/%d %H:%M")
