import aiohttp
import json
import datetime
import logging
import re
import asyncio
from typing import Dict, Any, Optional
from repeat_handler import RepeatHandler

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
        self.repeat_handler = RepeatHandler()
        
        if not key or not isinstance(key, str):
            raise ValueError("Invalid API key provided")

    def fallback(self, text: str, timezone: str) -> Dict[str, Any]:
        try:
            now = datetime.datetime.now()
            reminder_time = now

            repeat_pattern = self.repeat_handler.parse_from_text(text, now)
            self.logger.info(f"Fallback - repeat pattern: {repeat_pattern}")

            reminder_time = self._calculate_smart_time(text, now, repeat_pattern)
            category = self._detect_category(text)
            safe_text = str(text)[:500] if text else "Reminder"

            result = {
                "category": category,
                "content": safe_text,
                "time": reminder_time.strftime("%Y-%m-%d %H:%M"),
                "repeat": self.repeat_handler.to_json(repeat_pattern),
                "timezone": timezone,
            }

            self.logger.info(f"Fallback result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error in fallback parsing: {e}")
            now = datetime.datetime.now()
            return {
                "category": "general",
                "content": "Reminder",
                "time": now.strftime("%Y-%m-%d %H:%M"),
                "repeat": '{"type": "none"}',
                "timezone": timezone,
            }

    def _detect_category(self, text: str) -> str:
        text_lower = text.lower()
        
        category_patterns = {
            "medicine": [r'قرص', r'دارو', r'دوا', r'medicine', r'pill', r'medication'],
            "birthday": [r'تولد', r'birthday', r'عيد ميلاد'],
            "installment": [r'قسط', r'installment', r'قرض'],
            "work": [r'کار', r'work', r'جلسه', r'meeting', r'عمل'],
            "exercise": [r'ورزش', r'exercise', r'تمرين'],
            "prayer": [r'نماز', r'prayer', r'صلاة'],
            "shopping": [r'خرید', r'shopping', r'تسوق'],
            "call": [r'تماس', r'call', r'اتصال'],
            "study": [r'درس', r'study', r'دراسة'],
            "bill": [r'قبض', r'bill', r'فاتورة'],
            "appointment": [r'قرار', r'appointment', r'موعد']
        }
        
        for category, patterns in category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return category
        
        return "general"

    def _calculate_smart_time(self, text: str, now: datetime.datetime, repeat_pattern) -> datetime.datetime:
        if repeat_pattern.type == 'interval':
            if repeat_pattern.unit == 'minutes':
                return now + datetime.timedelta(minutes=repeat_pattern.value)
            elif repeat_pattern.unit == 'hours':
                return now + datetime.timedelta(hours=repeat_pattern.value)
            elif repeat_pattern.unit == 'days':
                return now + datetime.timedelta(days=repeat_pattern.value)
        return now

    async def parse(self, language: str, timezone: str, text: str) -> Dict[str, Any]:
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
            return self.fallback(text, timezone)
        prompt = f"""
Parse a reminder from user text in ANY language.

now="{g_now}"           // ISO, e.g. 2025-08-31T03:20:00
timezone="{timezone}"   // IANA, e.g. Europe/Amsterdam
text="{text}"

OUTPUT: Return ONLY valid JSON:
{{
  "reminders": [
    {{
      "category": "medicine|birthday|appointment|work|exercise|prayer|shopping|call|study|installment|bill|general",
      "content": "string (keep user's language)",
      "time": "YYYY-MM-DD HH:mm",   // 24h, localized to timezone
      "repeat": {{ "type": "none|daily|weekly|monthly|yearly|interval", "value": number|null, "unit": "minutes|hours|days|weeks|null" }}
    }}
  ]
}}

ANALYSIS STEPS:
1) COUNT DETECTION: Look for quantity indicators in ANY language (numbers, words like "three/سه/ثلاثة/три")
2) ITEM ENUMERATION: Identify each distinct item mentioned:
   - Sequence patterns: "first...second...third" or "یکی...یکی...دیگری" or "الأول...الثاني...الثالث"
   - Even if some are described in past tense, they are still separate items needing reminders
3) TIME EXTRACTION: Extract ALL time references mentioned:
   - Past times + repeat pattern = future reminders starting from those times
   - Relative times: "last night/دیشب/البارحة" = previous day
   - Time formats: "1 midnight/1 نصف شب/1 منتصف الليل" = 01:00 next day
4) REPEAT APPLICATION: If repeat mentioned, apply to ALL items identified in step 2
5) FUTURE CALCULATION: For past times with repeat, calculate next occurrence

CRITICAL RULES:
- If text says "N items" (like "سه تا قرص/three pills/ثلاث حبوب"), create exactly N reminders
- Past tense + repeat pattern = create future reminder from that time
- "midnight/نصف شب/منتصف الليل" = 01:00 next day
- Always match the count: if "three" mentioned, output exactly 3 reminders
- INCLUDE ALL ITEMS: Even past actions with times are items needing future reminders

EXAMPLE LOGIC:
"I have 3 pills. One I took last night at 7, one at 8, another at 1 midnight. Every 8 hours remind me"
→ 3 reminders: next 7:00, next 8:00, next 1:00 (all with 8-hour repeat)

OUTPUT FORMAT: Always use "reminders" array. Return ONLY raw JSON - no markdown, no explanations.
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
                        return self.fallback(text, timezone)
                        
                    data = await response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        self.logger.error("No choices in API response")
                        return self.fallback(text, timezone)
                        
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
                    if "reminders" in obj and isinstance(obj["reminders"], list):
                        validated_reminders = []
                        for reminder in obj["reminders"]:
                            if self._validate_parsed_object(reminder):
                                reminder.setdefault("timezone", timezone)
                                reminder["content"] = str(reminder["content"])[:500]
                                if isinstance(reminder.get("repeat"), dict):
                                    reminder["repeat"] = json.dumps(reminder["repeat"])
                                validated_reminders.append(reminder)
                        
                        if validated_reminders:
                            return {"reminders": validated_reminders}
                        else:
                            self.logger.warning("No valid reminders found, using fallback")
                            return self.fallback(text, timezone)
                    
                    elif self._validate_parsed_object(obj):
                        obj.setdefault("repeat", "none")
                        obj.setdefault("timezone", timezone)
                        obj["content"] = str(obj["content"])[:500]
                        if isinstance(obj.get("repeat"), dict):
                            obj["repeat"] = json.dumps(obj["repeat"])
                        return obj
                    
                    else:
                        self.logger.warning(f"Invalid parsed object: {obj}, using fallback")
                        return self.fallback(text, timezone)
                    
        except (aiohttp.ClientError, ValueError, KeyError, json.JSONDecodeError, asyncio.TimeoutError) as e:
            self.logger.error(f"AI parsing error: {e}")
            self.logger.info(f"Using fallback for text: {text}")
            return self.fallback(text, timezone)
            
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
                elif re.match(r'^every_\d+_hours$', obj["repeat"]):

                    match = re.match(r'^every_(\d+)_hours$', obj["repeat"])
                    if match:
                        hours = int(match.group(1))
                        obj["repeat"] = f'{{"type": "interval", "value": {hours}, "unit": "hours"}}'
                else:
                    obj["repeat"] = '{"type": "none"}'
            elif isinstance(obj["repeat"], dict):

                repeat_pattern = self.repeat_handler.from_json(json.dumps(obj["repeat"]))
                if not self.repeat_handler.is_valid_pattern(repeat_pattern):
                    obj["repeat"] = '{"type": "none"}'
                else:
                    obj["repeat"] = json.dumps(obj["repeat"])
            else:
                obj["repeat"] = '{"type": "none"}'
        else:
            obj["repeat"] = '{"type": "none"}'
            
        try:
            parsed_time = datetime.datetime.strptime(obj["time"], "%Y-%m-%d %H:%M")
            now = datetime.datetime.now()
            if parsed_time < now - datetime.timedelta(minutes=1):
                self.logger.warning(f"Time {obj['time']} is in the past")
        except (ValueError, TypeError):
            return False
            
        return True
        
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
                    
                    # Convert repeat object to JSON string if needed
                    if isinstance(obj.get("repeat"), dict):
                        obj["repeat"] = json.dumps(obj["repeat"])
                    
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
