import datetime
from typing import Dict, Any, Optional, Tuple
from convertdate import persian, gregorian, islamic
import logging

class DateParser:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def convert_to_gregorian(self, date_data: Dict[str, Any]) -> Optional[datetime.datetime]:
        if not date_data or not isinstance(date_data, dict):
            return None
            
        day = date_data.get("day")
        month = date_data.get("month") 
        year = date_data.get("year")
        calendar_type = date_data.get("calendar")
        if not calendar_type:
            if year and year > 1500:
                calendar_type = "gregorian"
            elif year and year > 1300 and year < 1500:
                calendar_type = "shamsi"
            else:
                calendar_type = "gregorian"
        
        if not all([day, month]):
            return None
            
        try:
            if calendar_type == "shamsi":
                return self._convert_shamsi_to_gregorian(day, month, year)
            elif calendar_type == "hijri":
                return self._convert_hijri_to_gregorian(day, month, year)
            elif calendar_type == "gregorian":
                return self._convert_gregorian(day, month, year)
            else:
                self.logger.warning(f"Unknown calendar type: {calendar_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Date conversion failed: {e}")
            return None
    
    def _convert_shamsi_to_gregorian(self, day: int, month: int, year: Optional[int]) -> Optional[datetime.datetime]:
        try:
            now = datetime.datetime.now()
            current_shamsi = persian.from_gregorian(now.year, now.month, now.day)[0]
            
            if year is None:
                year = current_shamsi
                
            gregorian_date = persian.to_gregorian(year, month, day)
            return datetime.datetime(gregorian_date[0], gregorian_date[1], gregorian_date[2])
            
        except Exception as e:
            self.logger.error(f"Shamsi to Gregorian conversion failed: {e}")
            return None
    
    def _convert_hijri_to_gregorian(self, day: int, month: int, year: Optional[int]) -> Optional[datetime.datetime]:
        try:
            now = datetime.datetime.now()
            current_hijri = islamic.from_gregorian(now.year, now.month, now.day)[0]
            
            if year is None:
                year = current_hijri
                
            gregorian_date = islamic.to_gregorian(year, month, day)
            return datetime.datetime(gregorian_date[0], gregorian_date[1], gregorian_date[2])
            
        except Exception as e:
            self.logger.error(f"Hijri to Gregorian conversion failed: {e}")
            return None
    
    def _convert_gregorian(self, day: int, month: int, year: Optional[int]) -> Optional[datetime.datetime]:
        try:
            if year is None:
                year = datetime.datetime.now().year
                
            return datetime.datetime(year, month, day)
            
        except Exception as e:
            self.logger.error(f"Gregorian date creation failed: {e}")
            return None
    
    def format_for_display(self, dt: datetime.datetime, calendar_type: str) -> str:
        if not dt:
            return ""
            
        try:
            if calendar_type == "shamsi":
                persian_date = persian.from_gregorian(dt.year, dt.month, dt.day)
                return f"{persian_date[0]}/{persian_date[1]:02d}/{persian_date[2]:02d}"
            elif calendar_type == "hijri":
                islamic_date = islamic.from_gregorian(dt.year, dt.month, dt.day)
                return f"{islamic_date[0]}/{islamic_date[1]:02d}/{islamic_date[2]:02d}"
            else:
                return dt.strftime("%Y/%m/%d")
                
        except Exception as e:
            self.logger.error(f"Date formatting failed: {e}")
            return dt.strftime("%Y-%m-%d")
