import aiohttp
import json
import datetime
import logging
import re
import asyncio
from typing import Dict, Any, Optional
from config.prompt_manager import PromptManager

try:
    from convertdate import persian, islamic
except ImportError:
    persian = None
    islamic = None
def _parse_tz(tz: str) -> datetime.timedelta:
    try:
        if not tz or not isinstance(tz, str):
            return datetime.timedelta(0)
        sign = 1 if tz.startswith("+") else -1
        time_part = tz[1:]
        if ":" in time_part:
            hours, minutes = time_part.split(":")
        else:
            hours = time_part
            minutes = "0"
        hours_int = int(hours)
        minutes_int = int(minutes)
        if not (-12 <= hours_int <= 14) or not (0 <= minutes_int <= 59):
            return datetime.timedelta(0)
        return datetime.timedelta(hours=sign * hours_int, minutes=sign * minutes_int)
    except (ValueError, TypeError, IndexError):
        return datetime.timedelta(0)
class AIHandler:
    def __init__(self, key: str, model: str = "gpt-4o"):
        self.key = key
        self.model = model
        self.logger = logging.getLogger(__name__)
        self.session_timeout = aiohttp.ClientTimeout(total=30)
        self.prompt_manager = PromptManager()
        if not key or not isinstance(key, str):
            raise ValueError("Invalid API key provided")
    
    async def _make_api_call(self, messages: list, max_tokens: int = 400, temperature: float = 0.1):
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        
        async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
            ) as response:
                if response.status != 200:
                    self.logger.error(f"API request failed with status {response.status}")
                    return None
                
                data = await response.json()
                if "choices" not in data or not data["choices"]:
                    self.logger.error("No choices in API response")
                    return None
                
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return content.strip()
    async def parse(self, language: str, timezone: str, text: str, user_calendar: str = "miladi") -> Dict[str, Any]:
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            raise ValueError("Invalid input text")
        if len(text) > 1000:
            text = text[:1000]
        try:
            now = datetime.datetime.now()
            g_now = now.strftime("%Y-%m-%d %H:%M")
            p_now = (
                f"{persian.from_gregorian(now.year, now.month, now.day)[0]}-{persian.from_gregorian(now.year, now.month, now.day)[1]:02d}-{persian.from_gregorian(now.year, now.month, now.day)[2]:02d} {now.hour:02d}:{now.minute:02d}"
                if persian
                else "N/A"
            )
        except Exception as e:
            self.logger.error(f"Error preparing parse request: {e}")
            self.logger.error(f"Failed to get valid AI response for: {text}")
            raise Exception("AI parsing failed")
        prompt = self.prompt_manager.get_prompt_with_params("reminder_parsing", text=text)
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a multilingual reminder pattern parser that outputs JSON.",
                },
                {"role": "user", "content": prompt},
            ]
            
            content = await self._make_api_call(messages, max_tokens=800, temperature=0.1)
            if not content:
                raise Exception("API call failed")
                
            self.logger.info(f"OpenRouter response: {content}")
            try:
                obj = json.loads(content)
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON decode error: {e}")
                if not content.strip().endswith('}'):
                    self.logger.info("Attempting to fix incomplete JSON")
                    content = content.strip()
                    missing_braces = content.count('{') - content.count('}')
                    if missing_braces > 0:
                        content += '}' * missing_braces
                    try:
                        obj = json.loads(content)
                        self.logger.info("Successfully fixed incomplete JSON")
                    except json.JSONDecodeError:
                        raise e
                else:
                    raise e
            self.logger.info(f"Parsed JSON: {obj}")
            if "reminders" in obj and isinstance(obj["reminders"], list):
                validated_reminders = []
                for reminder in obj["reminders"]:
                    if self._validate_parsed_object(reminder):
                        calculated_time = self._calculate_reminder_time(reminder, user_calendar, timezone)
                        if calculated_time.startswith("PAST_DATE_ERROR"):
                            parts = calculated_time.split("|")
                            detected_date = parts[1] if len(parts) > 1 else ""
                            current_date = parts[2] if len(parts) > 2 else ""
                            return {"reminders": [], "message": "past_date_error", "detected_date": detected_date, "current_date": current_date}
                        reminder["time"] = calculated_time
                        reminder.setdefault("timezone", timezone)
                        reminder["content"] = str(reminder["content"])[:40]
                        validated_reminders.append(reminder)
                if validated_reminders:
                    return {"reminders": validated_reminders, "message": None}
                else:
                    self.logger.warning("No valid reminders found in AI response")
                    return {"reminders": [], "message": "ai_error"}
            elif self._validate_parsed_object(obj):
                calculated_time = self._calculate_reminder_time(obj, user_calendar, timezone)
                if calculated_time.startswith("PAST_DATE_ERROR"):
                    parts = calculated_time.split("|")
                    detected_date = parts[1] if len(parts) > 1 else ""
                    current_date = parts[2] if len(parts) > 2 else ""
                    return {"reminders": [], "message": "past_date_error", "detected_date": detected_date, "current_date": current_date}
                obj["time"] = calculated_time
                obj.setdefault("timezone", timezone)
                obj["content"] = str(obj["content"])[:40]
                return {"reminders": [obj], "message": None}
            else:
                self.logger.warning(f"Invalid parsed object: {obj}")
                return {"reminders": [], "message": "ai_error"}
        except (aiohttp.ClientError, ValueError, KeyError, json.JSONDecodeError, asyncio.TimeoutError) as e:
            self.logger.error(f"AI parsing error: {e}")
            self.logger.error(f"Error type: {type(e).__name__}")
            raise Exception(f"AI parsing completely failed: {e}")
    def _parse_time(self, time_str):
        """Parse HH:MM format to hour and minute"""
        if not time_str or time_str is None:
            return None, None
        try:
            hour, minute = map(int, time_str.split(':'))
            return hour, minute
        except:
            return None, None

    def _calculate_reminder_time(self, reminder: dict, user_calendar: str, timezone: str) -> str:
        now = datetime.datetime.now()
        
        specific_date = reminder.get("specific_date")
        if specific_date and isinstance(specific_date, dict):
            day = specific_date.get("day")
            month = specific_date.get("month")
            year = specific_date.get("year")
            if day and month:
                time_str = reminder.get("time")
                if time_str is not None:
                    target_hour, target_minute = self._parse_time(time_str)
                else:
                    target_hour, target_minute = now.hour, now.minute
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
                if target_date < now and reminder.get("category") != "birthday":
                    if user_calendar == "shamsi" and persian:
                        shamsi_target = persian.from_gregorian(target_date.year, target_date.month, target_date.day)
                        shamsi_now = persian.from_gregorian(now.year, now.month, now.day)
                        detected_date_str = f"{shamsi_target[0]}-{shamsi_target[1]:02d}-{shamsi_target[2]:02d} {target_date.hour:02d}:{target_date.minute:02d}"
                        current_date_str = f"{shamsi_now[0]}-{shamsi_now[1]:02d}-{shamsi_now[2]:02d} {now.hour:02d}:{now.minute:02d}"
                    elif user_calendar == "qamari" and islamic:
                        hijri_target = islamic.from_gregorian(target_date.year, target_date.month, target_date.day)
                        hijri_now = islamic.from_gregorian(now.year, now.month, now.day)
                        detected_date_str = f"{hijri_target[0]}-{hijri_target[1]:02d}-{hijri_target[2]:02d} {target_date.hour:02d}:{target_date.minute:02d}"
                        current_date_str = f"{hijri_now[0]}-{hijri_now[1]:02d}-{hijri_now[2]:02d} {now.hour:02d}:{now.minute:02d}"
                    else:
                        detected_date_str = target_date.strftime("%Y-%m-%d %H:%M")
                        current_date_str = now.strftime("%Y-%m-%d %H:%M")
                    return f"PAST_DATE_ERROR|{detected_date_str}|{current_date_str}"
                return target_date.strftime("%Y-%m-%d %H:%M")
        
        relative_days = reminder.get("relative_days")
        if relative_days is not None:
            time_str = reminder.get("time")
            if time_str is not None:
                target_hour, target_minute = self._parse_time(time_str)
            else:
                target_hour = now.hour
                target_minute = now.minute
            target_date = now + datetime.timedelta(days=relative_days)
            target_date = target_date.replace(hour=target_hour, minute=target_minute)
            if target_date < now:
                if user_calendar == "shamsi" and persian:
                    shamsi_target = persian.from_gregorian(target_date.year, target_date.month, target_date.day)
                    shamsi_now = persian.from_gregorian(now.year, now.month, now.day)
                    detected_date_str = f"{shamsi_target[0]}-{shamsi_target[1]:02d}-{shamsi_target[2]:02d} {target_date.hour:02d}:{target_date.minute:02d}"
                    current_date_str = f"{shamsi_now[0]}-{shamsi_now[1]:02d}-{shamsi_now[2]:02d} {now.hour:02d}:{now.minute:02d}"
                elif user_calendar == "qamari" and islamic:
                    hijri_target = islamic.from_gregorian(target_date.year, target_date.month, target_date.day)
                    hijri_now = islamic.from_gregorian(now.year, now.month, now.day)
                    detected_date_str = f"{hijri_target[0]}-{hijri_target[1]:02d}-{hijri_target[2]:02d} {target_date.hour:02d}:{target_date.minute:02d}"
                    current_date_str = f"{hijri_now[0]}-{hijri_now[1]:02d}-{hijri_now[2]:02d} {now.hour:02d}:{now.minute:02d}"
                else:
                    detected_date_str = target_date.strftime("%Y-%m-%d %H:%M")
                    current_date_str = now.strftime("%Y-%m-%d %H:%M")
                return f"PAST_DATE_ERROR|{detected_date_str}|{current_date_str}"
            return target_date.strftime("%Y-%m-%d %H:%M")
        repeat_data = reminder.get("repeat", {})
        if isinstance(repeat_data, str):
            repeat_data = json.loads(repeat_data) if repeat_data.startswith("{") else {"type": repeat_data}
        repeat_type = repeat_data.get("type", "none")
        time_str = reminder.get("time")
        if time_str is not None:
            target_hour, target_minute = self._parse_time(time_str)
        else:
            target_hour = now.hour
            target_minute = now.minute
        if repeat_type == "monthly" and "day" in repeat_data:
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
        elif repeat_type == "weekly" and "weekday" in repeat_data:
            weekday_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
            target_weekday = weekday_map.get(repeat_data["weekday"], 0)
            current_weekday = now.weekday()
            days_ahead = target_weekday - current_weekday
            if days_ahead < 0 or (days_ahead == 0 and target_hour <= now.hour):
                days_ahead += 7
            next_occurrence = now + datetime.timedelta(days=days_ahead)
            next_occurrence = next_occurrence.replace(hour=target_hour, minute=target_minute)
            return next_occurrence.strftime("%Y-%m-%d %H:%M")
        elif repeat_type == "interval":
            if time_str is not None:
                start_time = now.replace(hour=target_hour, minute=target_minute)
                if start_time <= now:
                    start_time += datetime.timedelta(days=1)
                return start_time.strftime("%Y-%m-%d %H:%M")
            value = repeat_data.get("value", 0)
            unit = repeat_data.get("unit", "minutes")
            if unit == "minutes":
                next_time = now + datetime.timedelta(minutes=value)
            elif unit == "hours":
                next_time = now + datetime.timedelta(hours=value)
            elif unit == "days":
                next_time = now + datetime.timedelta(days=value)
            else:
                next_time = now
            return next_time.strftime("%Y-%m-%d %H:%M")
        
        target_date = now.replace(hour=target_hour, minute=target_minute)
        if target_date <= now:
            target_date += datetime.timedelta(days=1)
        return target_date.strftime("%Y-%m-%d %H:%M")
    def _validate_parsed_object(self, obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        required_keys = ["category", "content", "repeat"]
        if not all(k in obj for k in required_keys):
            return False
        valid_categories = [
            "birthday", "medicine", "appointment", "work", "exercise", 
            "prayer", "shopping", "call", "study", "installment", "bill", "general"
        ]
        if obj["category"] not in valid_categories:
            obj["category"] = "general"
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
        return True
    def _normalize_repeat_field(self, obj: dict) -> None:
        if "repeat" in obj and isinstance(obj["repeat"], dict):
            obj["repeat"] = json.dumps(obj["repeat"])
    async def parse_edit(self, current_reminder: dict, edit_text: str, timezone: str) -> Dict[str, Any]:
        try:
            prompt = self.prompt_manager.get_prompt_with_params("edit_reminder", 
                content=current_reminder['content'],
                time=current_reminder['time'],
                category=current_reminder['category'],
                repeat=current_reminder['repeat'],
                edit_text=edit_text
            )
            messages = [
                {
                    "role": "system",
                    "content": "You are an edit analyzer that outputs JSON.",
                },
                {"role": "user", "content": prompt},
            ]
            
            content = await self._make_api_call(messages, max_tokens=300, temperature=0.1)
            if not content:
                return None
            obj = json.loads(content)
            self.logger.info(f"Edit analysis result: {obj}")
            self._normalize_repeat_field(obj)
            return obj
        except Exception as e:
            self.logger.error(f"Edit parsing error: {e}")
            return None
    async def parse_timezone(self, prompt: str) -> Optional[tuple]:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a timezone detector that outputs JSON.",
                },
                {"role": "user", "content": prompt},
            ]
            
            content = await self._make_api_call(messages, max_tokens=100, temperature=0.1)
            if not content:
                return None
                
            self.logger.info(f"Raw timezone response: {content[:200]}")
            if content.lower() == "null" or not content:
                self.logger.info("AI returned null or empty response")
                return None
            if not content:
                self.logger.info("Content empty after cleanup")
                return None
            self.logger.info(f"Cleaned timezone content: {content}")
            obj = json.loads(content)
            if not isinstance(obj, dict) or "city" not in obj or "timezone" not in obj:
                return None
            city = str(obj["city"])[:50]
            timezone = str(obj["timezone"])
            if not self._validate_timezone(timezone):
                return None
            return (city, timezone)
        except (aiohttp.ClientError, ValueError, KeyError, json.JSONDecodeError, asyncio.TimeoutError) as e:
            self.logger.error(f"Timezone parsing error: {e}")
            return None
    def _validate_timezone(self, timezone: str) -> bool:
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