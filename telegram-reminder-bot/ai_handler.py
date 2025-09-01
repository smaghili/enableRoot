import aiohttp
import json
import datetime
import logging
import re
import asyncio
from typing import Dict, Any, Optional


try:
    import jdatetime
except ImportError:
    jdatetime = None


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
    def __init__(self, key: str):
        self.key = key
        self.logger = logging.getLogger(__name__)
        self.session_timeout = aiohttp.ClientTimeout(total=30)

        
        if not key or not isinstance(key, str):
            raise ValueError("Invalid API key provided")
    async def parse(self, language: str, timezone: str, text: str, user_calendar: str = "miladi") -> Dict[str, Any]:
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            raise ValueError("Invalid input text")
            
        if len(text) > 1000:
            text = text[:1000]
            
        try:
            headers = {
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            }
            
            now = datetime.datetime.now()
            g_now = now.strftime("%Y-%m-%d %H:%M")
            p_now = (
                jdatetime.datetime.fromgregorian(datetime=now).strftime("%Y-%m-%d %H:%M")
                if jdatetime
                else "N/A"
            )
        except Exception as e:
            self.logger.error(f"Error preparing parse request: {e}")
            self.logger.error(f"Failed to get valid AI response for: {text}")
            raise Exception("AI parsing failed")
        prompt = f"""
Parse reminders from user text in ANY language/script. Extract multiple reminders if present.

Inputs:
- now="{g_now}"           // Current system time (ISO)
- timezone="{timezone}"   // User timezone (IANA)  
- text="{text}"
- user_calendar="{user_calendar}" // miladi|shamsi|qamari
- shamsi_now="{p_now}"    // Current time in Jalali (if available)

OUTPUT: Strict JSON only:
{{
  "reminders": [
    {{
      "category": "medicine|birthday|appointment|work|exercise|prayer|shopping|call|study|installment|bill|general",
      "content": "clean, corrected title (≤40 chars, in user's language)",
      "time": "YYYY-MM-DD HH:mm",   // ALWAYS Gregorian format
      "repeat": {{ "type": "none|daily|weekly|monthly|yearly|interval", "value": number|null, "unit": "minutes|hours|days|weeks|null" }}
    }}
  ]
}}

CALENDAR CONVERSION RULES:
- CRITICAL: The "time" field must ALWAYS be in Gregorian (miladi) format YYYY-MM-DD HH:mm  
- If user_calendar="shamsi":
  • If text contains Persian month names (مهر، آبان، etc.) → convert shamsi to Gregorian
  • If text is in Persian/Farsi language but no specific month mentioned (e.g., "دهم هر ماه") → interpret day numbers in current shamsi month, then convert to Gregorian
  • Current shamsi date context: shamsi_now shows current shamsi date for reference
- If user_calendar="qamari" and text contains Islamic month names → convert qamari to Gregorian  
- If user_calendar="miladi" or text clearly in English/other non-Persian languages → treat as Gregorian
- Persian months: فروردین=1, اردیبهشت=2, خرداد=3, تیر=4, مرداد=5, شهریور=6, مهر=7, آبان=8, آذر=9, دی=10, بهمن=11, اسفند=12
- Example: user_calendar="shamsi" + Persian text "دهم هر ماه" = 10th of shamsi months, convert each occurrence to Gregorian

RULES:
1. MULTIPLE ITEMS  
   - If text mentions several times or items ("and", "&", "و", "et", "y", "und", …), create separate reminders.  
   - Example: "Monday and Wednesday" → 2 reminders.

2. TIME EXTRACTION  
   - If explicit (e.g., "9 PM", "21:30", "۹ شب", "mercredi 10h") → use it.  
   - If none → fallback to `now`.  
   - Map dayparts across languages: morning → AM, evening/night → PM, "half past" = +30 min, "quarter past" = +15, "quarter to" = −15.  

3. REPEAT LOGIC  
   - "Every day / daily / todos los días / هر روز" → daily.  
   - "Every week / weekly / chaque semaine" → weekly.  
   - "Every Monday" → weekly, anchor Monday.  
   - "Monday and Wednesday" + with "every" → 2 reminders, each weekly.  
   - "Monday and Wednesday" without "every" → 2 reminders, repeat=none.  
   - "Every month day 10" → monthly, anchor day=10.  
   - Interval phrases: "every 8 hours / هر ۸ ساعت / каждые 8 часов" → interval.

4. CONTENT CLEANING  
   - Keep only the object/action: medicine, call, meeting, shopping item, etc.  
   - For medicine: "<form> <name>" (e.g., "قرص کلداستاپ", "pill ibuprofen"). If no name → generic like "قرص / pill".  
   - Remove fillers: maybe / I think / فکر کنم / tal vez / vielleicht / наверное.  
   - Correct spelling and spacing (normalize tokens like "کلد استاپ / کلدیستاپ" → "کلداستاپ").  
   - Do NOT include time words inside content.  
   - Max length ≈40 chars.

5. DEFAULTS  
   - If no time given → use `now` as base.  
   - If only date given without hour/minute → set HH:mm = current local time.  
   - Repeat=none unless explicitly specified by words like "every/daily/weekly/monthly".

STRICT REQUIREMENTS:  
- JSON only, no extra text or markdown.  
- Do not echo full sentences, only normalized concise titles in "content".
- ALWAYS output dates in Gregorian format regardless of input calendar type.
        """
        try:
            async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "gpt-4o",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a reminder parser that outputs JSON.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 500,
                        "temperature": 0.1
                    },
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"API request failed with status {response.status}")
                        raise Exception(f"API failed with status {response.status}")
                        
                    data = await response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        self.logger.error("No choices in API response")
                        raise Exception("No choices in API response")
                        
                    content = data["choices"][0]["message"]["content"].strip()
                    self.logger.info(f"OpenRouter response: {content}")
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    obj = json.loads(content)
                    self.logger.info(f"Parsed JSON: {obj}")
                    # Determine if user explicitly provided a time; used for default time fallback
                    try:
                        import re as _re
                        now_utc = datetime.datetime.utcnow()
                        now_local = now_utc + _parse_tz(timezone)
                        # Heuristic: look for HH:mm (e.g., 10:30), am/pm, or localized hints like 'ساعت 10'
                        time_pattern = _re.compile(r"(\b[01]?\d|2[0-3]):[0-5]\d|\b(am|pm)\b|\bساعت\s*\d{1,2}", _re.IGNORECASE)
                        user_provided_time = bool(time_pattern.search(text))
                    except Exception:
                        user_provided_time = True  # be safe: don't override on detection failure
                    if "reminders" in obj and isinstance(obj["reminders"], list):
                        validated_reminders = []
                        for reminder in obj["reminders"]:
                            if self._validate_parsed_object(reminder):
                                # Fallback: if no explicit time and AI defaulted to 00:00, set to user's current HH:mm
                                try:
                                    if not user_provided_time:
                                        hhmm = reminder["time"][-5:]
                                        if hhmm == "00:00":
                                            reminder["time"] = reminder["time"][:-5] + now_local.strftime("%H:%M")
                                except Exception:
                                    pass
                                reminder.setdefault("timezone", timezone)
                                reminder["content"] = str(reminder["content"])[:500]
                                validated_reminders.append(reminder)
                        
                        if validated_reminders:
                            return {"reminders": validated_reminders, "message": None}
                        else:
                            self.logger.warning("No valid reminders found in AI response")
                            return {"reminders": [], "message": "ai_error"}
                    
                    elif self._validate_parsed_object(obj):
                        obj.setdefault("repeat", "none")
                        # Single reminder path: apply the same fallback for missing time
                        try:
                            if not user_provided_time:
                                hhmm = obj["time"][-5:]
                                if hhmm == "00:00":
                                    obj["time"] = obj["time"][:-5] + now_local.strftime("%H:%M")
                        except Exception:
                            pass
                        obj.setdefault("timezone", timezone)
                        obj["content"] = str(obj["content"])[:500]
                        return {"reminders": [obj], "message": None}
                    
                    else:
                        self.logger.warning(f"Invalid parsed object: {obj}")
                        return {"reminders": [], "message": "ai_error"}
                    
        except (aiohttp.ClientError, ValueError, KeyError, json.JSONDecodeError, asyncio.TimeoutError) as e:
            self.logger.error(f"AI parsing error: {e}")
            self.logger.error(f"Error type: {type(e).__name__}")
            raise Exception(f"AI parsing completely failed: {e}")
            
    def _validate_parsed_object(self, obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
            
        required_keys = ["category", "content", "time"]
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
                # AI returned a dict, validate and keep it
                if obj["repeat"].get("type") == "interval":
                    if not isinstance(obj["repeat"].get("value"), (int, float)) or not obj["repeat"].get("unit"):
                        obj["repeat"] = '{"type": "none"}'
                elif obj["repeat"].get("type") in ["none", "daily", "weekly", "monthly", "yearly"]:
                    pass  # Valid simple type
                else:
                    obj["repeat"] = '{"type": "none"}'
            else:
                obj["repeat"] = '{"type": "none"}'
        else:
            obj["repeat"] = '{"type": "none"}'
        
        # Ensure repeat is always a JSON string
        self._normalize_repeat_field(obj)
            
        try:
            parsed_time = datetime.datetime.strptime(obj["time"], "%Y-%m-%d %H:%M")
            now = datetime.datetime.now()
            if parsed_time < now - datetime.timedelta(minutes=1):
                self.logger.warning(f"Time {obj['time']} is in the past")
        except (ValueError, TypeError):
            return False
            
        return True
    
    def _normalize_repeat_field(self, obj: dict) -> None:
        """Ensure repeat field is always a JSON string"""
        if "repeat" in obj and isinstance(obj["repeat"], dict):
            obj["repeat"] = json.dumps(obj["repeat"])
        
    async def parse_edit(self, current_reminder: dict, edit_text: str, timezone: str) -> Dict[str, Any]:
        """Parse edit request with context of current reminder"""
        try:
            headers = {
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            }
            
            prompt = f"""
EDIT REMINDER ANALYSIS:

Current reminder:
- Content: "{current_reminder['content']}"
- Time: "{current_reminder['time']}"
- Category: "{current_reminder['category']}"
- Repeat: "{current_reminder['repeat']}"

User edit request: "{edit_text}"

TASK: Determine what user wants to change and output the new reminder.

RULES:
1) If user only mentions new content (no time/schedule words), keep original time/repeat
2) If user mentions time/schedule, update accordingly
3) Extract clean content without instruction words
4) Maintain original language style

OUTPUT JSON:
{{
  "content": "cleaned_content_text",
  "time": "YYYY-MM-DD HH:mm",
  "category": "category",
  "repeat": {{"type": "...", "value": null, "unit": null}},
  "changed": ["content"] or ["content", "time", "repeat"]
}}

Return ONLY raw JSON - no markdown, no explanations.
            """
            
            async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "gpt-4o",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an edit analyzer that outputs JSON.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 300,
                        "temperature": 0.1
                    },
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"Edit API request failed with status {response.status}")
                        return None
                        
                    data = await response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        self.logger.error("No choices in edit API response")
                        return None
                        
                    content = data["choices"][0]["message"]["content"].strip()
                    
                    # Clean up response - remove markdown code blocks if present
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    obj = json.loads(content)
                    self.logger.info(f"Edit analysis result: {obj}")
                    
                    # Normalize repeat field
                    self._normalize_repeat_field(obj)
                    
                    return obj
                    
        except Exception as e:
            self.logger.error(f"Edit parsing error: {e}")
            return None

    async def parse_timezone(self, prompt: str) -> Optional[tuple]:
        try:
            async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
                headers = {
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                }
                
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "gpt-4o",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a timezone detector that outputs JSON.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 100,
                        "temperature": 0.1
                    },
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"Timezone API request failed with status {response.status}")
                        return None
                        
                    data = await response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        self.logger.error("No choices in timezone API response")
                        return None
                        
                    content = data["choices"][0]["message"]["content"].strip()
                    self.logger.info(f"Raw timezone response: {content[:200]}")
                    
                    if content.lower() == "null" or not content:
                        self.logger.info("AI returned null or empty response")
                        return None
                    
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
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
