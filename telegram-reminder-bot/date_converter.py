import datetime
from convertdate import persian, gregorian, islamic
from typing import Optional

class DateConverter:
    @staticmethod
    def convert_to_user_calendar(date_str: str, calendar_type: str) -> str:
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M")
            if calendar_type == "shamsi":
                return DateConverter._to_shamsi(dt)
            elif calendar_type == "qamari":
                return DateConverter._to_qamari(dt)
            else:
                return date_str
        except Exception:
            return date_str

    @staticmethod
    def _to_shamsi(dt: datetime.datetime) -> str:
        try:
            persian_date = persian.from_gregorian(dt.year, dt.month, dt.day)
            return f"{persian_date[0]}-{persian_date[1]:02d}-{persian_date[2]:02d} {dt.hour:02d}:{dt.minute:02d}"
        except Exception:
            return dt.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _to_qamari(dt: datetime.datetime) -> str:
        try:
            islamic_date = islamic.from_gregorian(dt.year, dt.month, dt.day)
            return f"{islamic_date[0]}-{islamic_date[1]:02d}-{islamic_date[2]:02d} {dt.hour:02d}:{dt.minute:02d}"
        except Exception:
            return dt.strftime("%Y-%m-%d %H:%M")
