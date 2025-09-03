import datetime
import json
import logging
from typing import Dict, Any

try:
    from convertdate import persian, islamic
except ImportError:
    persian = None
    islamic = None

class TimeCalculator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
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
        
        specific_date = reminder.get("specific_date")
        if specific_date and isinstance(specific_date, dict):
            return self._calculate_specific_date_time(reminder, specific_date, user_calendar, now)
        
        relative_days = reminder.get("relative_days")
        if relative_days is not None:
            return self._calculate_relative_days_time(reminder, relative_days, user_calendar, now)
        
        repeat_data = reminder.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        
        repeat_type = repeat_data.get("type", "none")
        time_str = reminder.get("time")
        if repeat_type == "interval" and time_str is None:
            return self._calculate_interval_repeat(repeat_data, None, None, now)
        
        target_hour, target_minute = self._get_target_time(time_str, now)
        if reminder.get("today", False) or reminder.get("relative_days") == 0:
            # If it's today and has interval repeat, use interval logic instead of error
            if repeat_type == "interval":
                return self._calculate_interval_repeat(repeat_data, target_hour, target_minute, now)
            
            target_date = now.replace(hour=target_hour, minute=target_minute)
            if target_date <= now:
                # Never show PAST_DATE_ERROR for interval repeats or birthdays
                target_date += datetime.timedelta(days=1)
            return target_date.strftime("%Y-%m-%d %H:%M")
        
        if repeat_type == "monthly" and "day" in repeat_data:
            return self._calculate_monthly_repeat(repeat_data, target_hour, target_minute, user_calendar, now)
        elif repeat_type == "weekly" and "weekday" in repeat_data:
            return self._calculate_weekly_repeat(repeat_data, target_hour, target_minute, now)
        elif repeat_type == "interval":
            return self._calculate_interval_repeat(repeat_data, target_hour, target_minute, now)
        
        target_date = now.replace(hour=target_hour, minute=target_minute)
        if target_date <= now:
            target_date += datetime.timedelta(days=1)
        return target_date.strftime("%Y-%m-%d %H:%M")
    
    def _calculate_specific_date_time(self, reminder: dict, specific_date: dict, user_calendar: str, now: datetime.datetime) -> str:
        day = specific_date.get("day")
        month = specific_date.get("month")
        year = specific_date.get("year")
        if day and month:
            time_str = reminder.get("time")
            target_hour, target_minute = self._get_target_time(time_str, now)
            
            if reminder.get("category") == "birthday" and year:
                if user_calendar == "shamsi" and persian:
                    current_shamsi = persian.from_gregorian(now.year, now.month, now.day)
                    current_year = current_shamsi[0]
                    try:
                        gregorian_date = persian.to_gregorian(current_year, month, day)
                        target_date = datetime.datetime(gregorian_date[0], gregorian_date[1], gregorian_date[2], target_hour, target_minute)
                        if target_date < now:
                            gregorian_date = persian.to_gregorian(current_year + 1, month, day)
                            target_date = datetime.datetime(gregorian_date[0], gregorian_date[1], gregorian_date[2], target_hour, target_minute)
                    except Exception:
                        return now.replace(hour=target_hour, minute=target_minute).strftime("%Y-%m-%d %H:%M")
                else:
                    try:
                        target_date = datetime.datetime(now.year, month, day, target_hour, target_minute)
                        if target_date < now:
                            target_date = datetime.datetime(now.year + 1, month, day, target_hour, target_minute)
                    except Exception:
                        return now.replace(hour=target_hour, minute=target_minute).strftime("%Y-%m-%d %H:%M")
            else:
                if user_calendar == "shamsi" and persian and year:
                    try:
                        gregorian_date = persian.to_gregorian(year, month, day)
                        target_date = datetime.datetime(gregorian_date[0], gregorian_date[1], gregorian_date[2], target_hour, target_minute)
                    except Exception:
                        return now.replace(hour=target_hour, minute=target_minute).strftime("%Y-%m-%d %H:%M")
                elif year:
                    try:
                        target_date = datetime.datetime(year, month, day, target_hour, target_minute)
                    except Exception:
                        return now.replace(hour=target_hour, minute=target_minute).strftime("%Y-%m-%d %H:%M")
                else:
                    try:
                        target_date = datetime.datetime(now.year, month, day, target_hour, target_minute)
                    except Exception:
                        return now.replace(hour=target_hour, minute=target_minute).strftime("%Y-%m-%d %H:%M")
            
            # Never show PAST_DATE_ERROR for interval repeats or birthdays
            # For past dates, just move to next occurrence
            return target_date.strftime("%Y-%m-%d %H:%M")
        
        # If day or month is None, check if this has interval repeat
        repeat_data = reminder.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        if isinstance(repeat_data, dict) and repeat_data.get("type") == "interval":
            time_str = reminder.get("time")
            target_hour, target_minute = self._get_target_time(time_str, now)
            return self._calculate_interval_repeat(repeat_data, target_hour, target_minute, now)
        
        # Otherwise use default logic
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
        target_day = repeat_data["day"]
        if user_calendar == "shamsi" and persian:
            shamsi_now = persian.from_gregorian(now.year, now.month, now.day)
            current_day = shamsi_now[2]
            if target_day <= current_day:
                if shamsi_now[1] == 12:
                    gregorian_date = persian.to_gregorian(shamsi_now[0] + 1, 1, target_day)
                else:
                    gregorian_date = persian.to_gregorian(shamsi_now[0], shamsi_now[1] + 1, target_day)
            else:
                gregorian_date = persian.to_gregorian(shamsi_now[0], shamsi_now[1], target_day)
            target_date = datetime.datetime(gregorian_date[0], gregorian_date[1], gregorian_date[2], target_hour, target_minute)
            return target_date.strftime("%Y-%m-%d %H:%M")
        else:
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
        weekday_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        weekday = repeat_data["weekday"]
        
        # Handle both string names and numeric values
        if isinstance(weekday, str):
            target_weekday = weekday_map.get(weekday, 0)
        elif isinstance(weekday, int):
            target_weekday = weekday
        else:
            target_weekday = 0
        current_weekday = now.weekday()
        days_ahead = target_weekday - current_weekday
        self.logger.info(f"Weekly calc: target={target_weekday}, current={current_weekday}, days_ahead={days_ahead}")
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            # Same day - check if time has passed
            if target_hour < now.hour or (target_hour == now.hour and target_minute <= now.minute):
                days_ahead += 7
                
        next_occurrence = now + datetime.timedelta(days=days_ahead)
        next_occurrence = next_occurrence.replace(hour=target_hour, minute=target_minute)
        return next_occurrence.strftime("%Y-%m-%d %H:%M")
    
    def _calculate_interval_repeat(self, repeat_data: dict, target_hour: int, target_minute: int, now: datetime.datetime, start_date: datetime.datetime = None) -> str:
        value = repeat_data.get("value", 0)
        unit = repeat_data.get("unit", "minutes")
        
        if target_hour is not None and target_minute is not None:
            # Use provided start_date or default to today
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
