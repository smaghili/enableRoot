import datetime
import json
import logging
from typing import Dict, Any
from utils.date_parser import DateParser

try:
    from convertdate import persian, islamic
except ImportError:
    persian = None
    islamic = None

class TimeCalculator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.date_parser = DateParser()
    
    def parse_time(self, time_str: str) -> tuple:
        if not time_str or time_str is None:
            return None, None
        try:
            hour, minute = map(int, time_str.split(':'))
            return hour, minute
        except:
            return None, None
    
    def _get_target_time(self, time_str: str, now: datetime.datetime) -> tuple:
        if time_str is not None:
            target_hour, target_minute = self.parse_time(time_str)
            if target_hour is not None and target_minute is not None:
                return target_hour, target_minute
        return now.hour, now.minute
    
    def calculate_reminder_time(self, reminder: dict, user_calendar: str, timezone: str) -> str:
        now = datetime.datetime.now()
        
        repeat_data = reminder.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        repeat_type = repeat_data.get("type", "none")
        
        time_str = reminder.get("time")
        target_hour, target_minute = self._get_target_time(time_str, now)
        if repeat_type == "interval":
            start_date = None
            relative_days = reminder.get("relative_days")
            if relative_days is not None:
                start_date = now + datetime.timedelta(days=relative_days)
            else:
                specific_date = reminder.get("specific_date")
                if specific_date and any(specific_date.get(k) is not None for k in ("day", "month", "year")):
                    anchored = self.date_parser.convert_to_gregorian({
                        "day": specific_date.get("day"),
                        "month": specific_date.get("month"),
                        "year": specific_date.get("year"),
                        "calendar": specific_date.get("calendar")
                    })
                    if anchored:
                        start_date = anchored
            return self._calculate_interval_repeat(repeat_data, target_hour, target_minute, now, start_date=start_date)
        
        specific_date = reminder.get("specific_date")
        if specific_date and any(specific_date.get(k) is not None for k in ("day", "month", "year")):
            return self._calculate_specific_date_time(reminder, specific_date, user_calendar, now)
        
        relative_days = reminder.get("relative_days")
        if relative_days is not None:
            return self._calculate_relative_days_time(reminder, relative_days, user_calendar, now)
        
        if reminder.get("today", False) or reminder.get("relative_days") == 0:
            
            target_date = now.replace(hour=target_hour, minute=target_minute)
            if target_date <= now:
                target_date += datetime.timedelta(days=1)
            return target_date.strftime("%Y-%m-%d %H:%M")
        
        if repeat_type == "monthly" and "day" in repeat_data:
            return self._calculate_monthly_repeat(repeat_data, target_hour, target_minute, user_calendar, now)
        elif repeat_type == "weekly" and "weekday" in repeat_data:
            return self._calculate_weekly_repeat(repeat_data, target_hour, target_minute, now)
        
        target_date = now.replace(hour=target_hour, minute=target_minute)
        if target_date <= now:
            target_date += datetime.timedelta(days=1)
        return target_date.strftime("%Y-%m-%d %H:%M")
    
    def _calculate_specific_date_time(self, reminder: dict, specific_date: dict, user_calendar: str, now: datetime.datetime) -> str:
        day = specific_date.get("day")
        month = specific_date.get("month")
        year = specific_date.get("year")
        calendar_type = specific_date.get("calendar")
        if not calendar_type:
            if year and year > 1500:
                calendar_type = "gregorian"
            elif year and year > 1300 and year < 1500:
                calendar_type = "shamsi"
            else:
                calendar_type = "gregorian"
        
        if day and month:
            time_str = reminder.get("time")
            target_hour, target_minute = self._get_target_time(time_str, now)
            date_data = {
                "day": day,
                "month": month,
                "year": (None if reminder.get("category") == "birthday" else year),
                "calendar": calendar_type
            }
            target_date = self.date_parser.convert_to_gregorian(date_data)
            if not target_date:
                return now.replace(hour=target_hour, minute=target_minute).strftime("%Y-%m-%d %H:%M")
            target_date = target_date.replace(hour=target_hour, minute=target_minute)
            if reminder.get("category") == "birthday":
                if target_date < now:
                    target_date = target_date.replace(year=target_date.year + 1)
            return target_date.strftime("%Y-%m-%d %H:%M")
        
        repeat_data = reminder.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        if isinstance(repeat_data, dict) and repeat_data.get("type") == "interval":
            time_str = reminder.get("time")
            target_hour, target_minute = self._get_target_time(time_str, now)
            return self._calculate_interval_repeat(repeat_data, target_hour, target_minute, now)
        
        time_str = reminder.get("time")
        target_hour, target_minute = self._get_target_time(time_str, now)
        target_date = now.replace(hour=target_hour, minute=target_minute)
        if target_date <= now:
            target_date += datetime.timedelta(days=1)
        return target_date.strftime("%Y-%m-%d %H:%M")
    
    def _calculate_relative_days_time(self, reminder: dict, relative_days: int, user_calendar: str, now: datetime.datetime) -> str:
        self.logger.info(f"_calculate_relative_days_time called with relative_days={relative_days}")
        time_str = reminder.get("time")
        target_hour, target_minute = self._get_target_time(time_str, now)
        target_date = now + datetime.timedelta(days=relative_days)
        target_date = target_date.replace(hour=target_hour, minute=target_minute)
        repeat_data = reminder.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        self.logger.info(f"repeat_data after processing: {repeat_data}")
        if isinstance(repeat_data, dict) and repeat_data.get("type") == "interval":
            return self._calculate_interval_repeat(repeat_data, target_hour, target_minute, now, start_date=target_date)
        if target_date < now:
            target_date += datetime.timedelta(days=1)
        return target_date.strftime("%Y-%m-%d %H:%M")
    
    def _calculate_monthly_repeat(self, repeat_data: dict, target_hour: int, target_minute: int, user_calendar: str, now: datetime.datetime) -> str:
        target_day = repeat_data.get("day", now.day)
        current_day = now.day
        if target_day <= current_day:
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=target_day, hour=target_hour, minute=target_minute)
            else:
                next_month = now.replace(month=now.month + 1, day=target_day, hour=target_hour, minute=target_minute)
        else:
            next_month = now.replace(day=target_day, hour=target_hour, minute=target_minute)
        return next_month.strftime("%Y-%m-%d %H:%M")
    
    def _calculate_weekly_repeat(self, repeat_data: dict, target_hour: int, target_minute: int, now: datetime.datetime) -> str:
        weekday_map = {"monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7}
        weekday = repeat_data.get("weekday")
        if isinstance(weekday, str):
            target_weekday = weekday_map.get(weekday.lower(), 1)
        elif isinstance(weekday, int):
            target_weekday = weekday
        else:
            target_weekday = 1
        current_weekday = now.weekday() + 1
        days_ahead = target_weekday - current_weekday
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            if target_hour < now.hour or (target_hour == now.hour and target_minute <= now.minute):
                days_ahead += 7
        next_occurrence = now + datetime.timedelta(days=days_ahead)
        next_occurrence = next_occurrence.replace(hour=target_hour, minute=target_minute)
        return next_occurrence.strftime("%Y-%m-%d %H:%M")
    
    def _calculate_interval_repeat(self, repeat_data: dict, target_hour: int, target_minute: int, now: datetime.datetime, start_date: datetime.datetime = None) -> str:
        value = repeat_data.get("value", 0)
        unit = repeat_data.get("unit", "minutes")
        
        if target_hour is not None and target_minute is not None:
            if start_date is not None:
                start_time = start_date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                self.logger.info(f"Using start_date: {start_date} -> start_time: {start_time}")
            else:
                start_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            if unit == "minutes":
                if start_time <= now:
                    time_diff_minutes = (now - start_time).total_seconds() / 60
                    intervals_passed = int(time_diff_minutes // value)
                    next_time = start_time + datetime.timedelta(minutes=value * (intervals_passed + 1))
                else:
                    next_time = start_time
            elif unit == "hours":
                if start_time <= now:
                    time_diff_hours = (now - start_time).total_seconds() / 3600
                    intervals_passed = int(time_diff_hours // value)
                    next_time = start_time + datetime.timedelta(hours=value * (intervals_passed + 1))
                    self.logger.info(f"Hours calculation: diff={time_diff_hours:.2f}, intervals={intervals_passed}, next={next_time}")
                else:
                    next_time = start_time
            elif unit == "days":
                if start_time <= now:
                    time_diff_days = (now - start_time).days
                    intervals_passed = int(time_diff_days // value)
                    next_time = start_time + datetime.timedelta(days=value * (intervals_passed + 1))
                else:
                    next_time = start_time
            else:
                next_time = start_time + datetime.timedelta(days=1)
            
            return next_time.strftime("%Y-%m-%d %H:%M")
        
        if unit == "minutes":
            next_time = now + datetime.timedelta(minutes=value)
        elif unit == "hours":
            next_time = now + datetime.timedelta(hours=value)
        elif unit == "days":
            next_time = now + datetime.timedelta(days=value)
        else:
            next_time = now
        return next_time.strftime("%Y-%m-%d %H:%M")
