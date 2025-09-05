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
    
    def _convert_to_utc(self, local_datetime: datetime.datetime) -> str:
        if hasattr(self, '_current_timezone') and self._current_timezone:
            from utils.timezone_manager import TimezoneManager
            utc_datetime = TimezoneManager.local_to_utc(local_datetime.strftime("%Y-%m-%d %H:%M"), self._current_timezone)
            return utc_datetime.strftime("%Y-%m-%d %H:%M")
        return local_datetime.strftime("%Y-%m-%d %H:%M")
    
    def calculate_reminder_time(self, reminder: dict, user_calendar: str, timezone: str) -> str:
        self._current_timezone = timezone
        if timezone:
            from utils.timezone_manager import TimezoneManager
            utc_now = datetime.datetime.utcnow()
            now = TimezoneManager.utc_to_local(utc_now.strftime("%Y-%m-%d %H:%M"), timezone)
            self.logger.info(f"UTC: {utc_now}, Timezone: {timezone}, Local: {now}")
        else:
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
        
        # Handle repeat patterns first (monthly/weekly take priority)
        if repeat_type == "monthly" and "day" in repeat_data:
            return self._calculate_monthly_repeat(repeat_data, target_hour, target_minute, user_calendar, now)
        elif repeat_type == "weekly" and "weekday" in repeat_data:
            return self._calculate_weekly_repeat(repeat_data, target_hour, target_minute, now)
        
        specific_date = reminder.get("specific_date")
        if specific_date and any(specific_date.get(k) is not None for k in ("day", "month", "year")):
            return self._calculate_specific_date_time(reminder, specific_date, user_calendar, now)
        
        relative_minutes = reminder.get("relative_minutes")
        if relative_minutes is not None:
            return self._calculate_relative_minutes_time(reminder, relative_minutes, now)
        
        relative_days = reminder.get("relative_days")
        if relative_days is not None:
            return self._calculate_relative_days_time(reminder, relative_days, user_calendar, now)
        
        if reminder.get("today", False) or reminder.get("relative_days") == 0:
            target_date = now.replace(hour=target_hour, minute=target_minute)
            if target_date <= now:
                target_date += datetime.timedelta(days=1)
            return self._convert_to_utc(target_date)
        
        target_date = now.replace(hour=target_hour, minute=target_minute)
        if target_date <= now:
            target_date += datetime.timedelta(days=1)
        return self._convert_to_utc(target_date)
    
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
            is_recurring_event = reminder.get("category") in ("birthday", "anniversary")
            date_data = {
                "day": day,
                "month": month,
                "year": (None if is_recurring_event else year),
                "calendar": calendar_type
            }
            target_date = self.date_parser.convert_to_gregorian(date_data)
            if not target_date:
                return now.replace(hour=target_hour, minute=target_minute).strftime("%Y-%m-%d %H:%M")
            target_date = target_date.replace(hour=target_hour, minute=target_minute)
            if target_date < now:
                target_date = target_date.replace(year=now.year)
                if target_date <= now:
                    target_date = target_date.replace(year=now.year + 1)
            return self._convert_to_utc(target_date)
        
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
        if relative_days == 0 and time_str:
            try:
                time_parts = time_str.split(":")
                if len(time_parts) == 2:
                    hour, minute = int(time_parts[0]), int(time_parts[1])
                    if hour == 0 and minute > 0:
                        target_date = now + datetime.timedelta(minutes=minute)
                        return self._convert_to_utc(target_date)
            except (ValueError, IndexError):
                pass
        
        target_hour, target_minute = self._get_target_time(time_str, now)
        target_date = now + datetime.timedelta(days=relative_days)
        target_date = target_date.replace(hour=target_hour, minute=target_minute)
        repeat_data = reminder.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        self.logger.info(f"repeat_data after processing: {repeat_data}")
        if isinstance(repeat_data, dict) and repeat_data.get("type") == "interval":
            return self._calculate_interval_repeat(repeat_data, target_hour, target_minute, now, start_date=target_date)
        return self._convert_to_utc(target_date)
    
    def _calculate_relative_minutes_time(self, reminder: dict, relative_minutes: int, now: datetime.datetime) -> str:
        target_date = now + datetime.timedelta(minutes=relative_minutes)
        return self._convert_to_utc(target_date)
    
    def _calculate_monthly_repeat(self, repeat_data: dict, target_hour: int, target_minute: int, user_calendar: str, now: datetime.datetime) -> str:
        target_day = repeat_data.get("day", now.day) 
        if user_calendar == "shamsi":
            return self._calculate_shamsi_monthly_repeat(target_day, target_hour, target_minute, now)
        elif user_calendar == "qamari":
            return self._calculate_qamari_monthly_repeat(target_day, target_hour, target_minute, now)
        return self._calculate_gregorian_monthly_repeat(target_day, target_hour, target_minute, now)
    
    def _calculate_shamsi_monthly_repeat(self, target_day: int, target_hour: int, target_minute: int, now: datetime.datetime) -> str:
        try:
            if persian is None:
                self.logger.warning("Persian calendar not available, falling back to Gregorian")
                return self._calculate_gregorian_monthly_repeat(target_day, target_hour, target_minute, now)
            current_shamsi = persian.from_gregorian(now.year, now.month, now.day)
            shamsi_year, shamsi_month, shamsi_day = current_shamsi
            try:
                if target_day >= shamsi_day:
                    current_month_target = persian.to_gregorian(shamsi_year, shamsi_month, target_day)
                    target_date = datetime.datetime(current_month_target[0], current_month_target[1], current_month_target[2], target_hour, target_minute)
                    if target_date > now:
                        return self._convert_to_utc(target_date)
            except:
                pass
            if shamsi_month == 12:
                next_shamsi_year = shamsi_year + 1
                next_shamsi_month = 1
            else:
                next_shamsi_year = shamsi_year
                next_shamsi_month = shamsi_month + 1
            if next_shamsi_month <= 6:
                max_day = 31
            elif next_shamsi_month <= 11:
                max_day = 30
            else:
                max_day = 29
            actual_day = min(target_day, max_day)
            
            try:
                next_month_target = persian.to_gregorian(next_shamsi_year, next_shamsi_month, actual_day)
                target_date = datetime.datetime(next_month_target[0], next_month_target[1], next_month_target[2], target_hour, target_minute)
                return self._convert_to_utc(target_date)
            except Exception as e:
                self.logger.error(f"Error calculating next Shamsi month: {e}")
                return self._calculate_gregorian_monthly_repeat(target_day, target_hour, target_minute, now)
                
        except Exception as e:
            self.logger.error(f"Error in Shamsi monthly calculation: {e}")
            return self._calculate_gregorian_monthly_repeat(target_day, target_hour, target_minute, now)
    
    def _calculate_gregorian_monthly_repeat(self, target_day: int, target_hour: int, target_minute: int, now: datetime.datetime) -> str:
        try:
            this_month = now.replace(day=target_day, hour=target_hour, minute=target_minute)
            if this_month > now:
                return self._convert_to_utc(this_month)
        except ValueError:
            pass
        
        if now.month == 12:
            try:
                next_month = now.replace(year=now.year + 1, month=1, day=target_day, hour=target_hour, minute=target_minute)
            except ValueError:
                next_month = now.replace(year=now.year + 1, month=1, day=min(target_day, 28), hour=target_hour, minute=target_minute)
        else:
            try:
                next_month = now.replace(month=now.month + 1, day=target_day, hour=target_hour, minute=target_minute)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(now.year, now.month + 1)[1]
                next_month = now.replace(month=now.month + 1, day=min(target_day, last_day), hour=target_hour, minute=target_minute)
        
        return self._convert_to_utc(next_month)
    
    def _calculate_qamari_monthly_repeat(self, target_day: int, target_hour: int, target_minute: int, now: datetime.datetime) -> str:
        try:
            if islamic is None:
                self.logger.warning("Islamic calendar not available, falling back to Gregorian")
                return self._calculate_gregorian_monthly_repeat(target_day, target_hour, target_minute, now)
            
            current_islamic = islamic.from_gregorian(now.year, now.month, now.day)
            islamic_year, islamic_month, islamic_day = current_islamic
            
            try:
                target_islamic_date = islamic.to_gregorian(islamic_year, islamic_month, target_day)
                target_gregorian = datetime.datetime(*target_islamic_date, target_hour, target_minute)
                if target_gregorian > now:
                    return self._convert_to_utc(target_gregorian)
            except (ValueError, OverflowError):
                pass
            
            if islamic_month == 12:
                try:
                    next_month_islamic = islamic.to_gregorian(islamic_year + 1, 1, target_day)
                except (ValueError, OverflowError):
                    next_month_islamic = islamic.to_gregorian(islamic_year + 1, 1, min(target_day, 29))
            else:
                try:
                    next_month_islamic = islamic.to_gregorian(islamic_year, islamic_month + 1, target_day)
                except (ValueError, OverflowError):
                    next_month_islamic = islamic.to_gregorian(islamic_year, islamic_month + 1, min(target_day, 29))
            
            target_gregorian = datetime.datetime(*next_month_islamic, target_hour, target_minute)
            return self._convert_to_utc(target_gregorian)
            
        except Exception as e:
            self.logger.error(f"Error in Qamari monthly calculation: {e}")
            return self._calculate_gregorian_monthly_repeat(target_day, target_hour, target_minute, now)
    
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
        return self._convert_to_utc(next_occurrence)
    
    def _calculate_interval_repeat(self, repeat_data: dict, target_hour: int, target_minute: int, now: datetime.datetime, start_date: datetime.datetime = None) -> str:
        if start_date:
            base_time = start_date.replace(hour=target_hour, minute=target_minute)
        else:
            base_time = now.replace(hour=target_hour, minute=target_minute)
        if base_time <= now and repeat_data.get("type") == "interval":
            value = repeat_data.get("value", 0)
            unit = repeat_data.get("unit", "minutes")
            if unit == "hours" and value > 0:
                diff_hours = int((now - base_time).total_seconds() / 3600)
                periods_passed = (diff_hours // value) + 1
                base_time = base_time + datetime.timedelta(hours=periods_passed * value)
            elif unit == "minutes" and value > 0:
                diff_minutes = int((now - base_time).total_seconds() / 60)
                periods_passed = (diff_minutes // value) + 1
                base_time = base_time + datetime.timedelta(minutes=periods_passed * value)
            elif unit == "days" and value > 0:
                diff_days = (now - base_time).days
                periods_passed = (diff_days // value) + 1
                base_time = base_time + datetime.timedelta(days=periods_passed * value)
        
        return self._convert_to_utc(base_time)
