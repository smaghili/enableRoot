import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional
from config.prompt_manager import PromptManager
from .api_client import APIClient
from .time_calculator import TimeCalculator
from .reminder_validator import ReminderValidator
from .timezone_detector import TimezoneDetector
from utils.ai_database import AIDatabase
from utils.comprehensive_logger import ComprehensiveLogger

class AIHandler:
    def __init__(self, key: str, model: str = "gpt-4o", config=None, storage=None):
        self.key = key
        self.model = model
        self.storage = storage
        self.logger = logging.getLogger(__name__)
        self.prompt_manager = PromptManager()
        self.api_client = APIClient(key, model)
        self.time_calculator = TimeCalculator()
        self.reminder_validator = ReminderValidator()
        self.timezone_detector = TimezoneDetector()
        if config and config.ai_logging_enabled:
            self.ai_database = AIDatabase(config.ai_database_path)
        else:
            self.ai_database = None
        self.comp_logger = ComprehensiveLogger()
    
    async def parse(self, language: str, timezone: str, text: str, user_calendar: str = "miladi", user_id: int = None, user_name: str = None, user_username: str = None) -> Dict[str, Any]:
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            raise ValueError("Invalid input text")
        
        if len(text) > 1000:
            text = text[:1000]
        start_time = time.time()
        ai_response = None
        if user_id:
            self.comp_logger.log_event("ai_parse_start", user_id, user_name, user_username, 
                                     event_data={"original_message": text, "language": language, "calendar": user_calendar})
        try:
            prompt = self.prompt_manager.get_prompt_with_params("reminder_parsing", text=text)
            messages = [
                {
                    "role": "system",
                    "content": "You are a multilingual reminder pattern parser that outputs JSON.",
                },
                {"role": "user", "content": prompt},
            ]
            
            ai_response = await self.api_client.make_api_call(messages, max_tokens=800, temperature=0.1)
            if not ai_response:
                raise Exception("API call failed")
            
            if not ai_response.strip().startswith('{'):
                self.logger.error(f"AI returned non-JSON response: {ai_response}")
                raise Exception(f"AI returned invalid format: {ai_response[:100]}")
            
            try:
                obj = json.loads(ai_response)
                self.logger.info(f"Parsed object type: {type(obj)}")
                self.logger.info(f"Parsed object keys: {list(obj.keys()) if isinstance(obj, dict) else 'Not a dict'}")
            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON decode error: {e}")
                if not ai_response.strip().endswith('}'):
                    ai_response = ai_response.strip()
                    missing_braces = ai_response.count('{') - ai_response.count('}')
                    if missing_braces > 0:
                        ai_response += '}' * missing_braces
                    try:
                        obj = json.loads(ai_response)
                    except json.JSONDecodeError:
                        if user_id and self.ai_database:
                            self.ai_database.log_interaction(user_id, text, ai_response, None, False, str(e), time.time() - start_time)
                        raise e
                else:
                    if user_id and self.ai_database:
                        self.ai_database.log_interaction(user_id, text, ai_response, None, False, str(e), time.time() - start_time)
                    raise e
            
            self.logger.info(f"Parsed JSON: {obj}")
            
            if "reminders" in obj and isinstance(obj.get("reminders"), list):
                result = self._process_reminders_list(obj.get("reminders", []), user_calendar, timezone)
            else:
                result = self._process_single_reminder(obj, user_calendar, timezone)
            
            if user_id and self.ai_database:
                self.ai_database.log_interaction(user_id, text, ai_response, str(result), True, None, time.time() - start_time)
            if user_id:
                self.comp_logger.log_event("ai_parse_success", user_id, user_name, user_username,
                                         event_data={"parsed_reminders": len(result.get("reminders", [])), "processing_time": time.time() - start_time})
            return result
                
        except Exception as e:
            if user_id and self.ai_database:
                self.ai_database.log_interaction(user_id, text, ai_response, None, False, str(e), time.time() - start_time)
            if user_id:
                self.comp_logger.log_event("ai_parse_error", user_id, user_name, user_username,
                                         success=False, error_message=str(e), 
                                         event_data={"processing_time": time.time() - start_time})
            raise Exception(f"AI parsing completely failed: {e}")
    
    def _process_reminders_list(self, reminders: list, user_calendar: str, timezone: str) -> Dict[str, Any]:
        validated_reminders = []
        first_error_info = None
        
        for reminder in reminders:
            if self.reminder_validator.validate_parsed_object(reminder):
                calculated_time = self.time_calculator.calculate_reminder_time(reminder, user_calendar, timezone)
                
                if calculated_time and calculated_time.startswith("PAST_DATE_ERROR"):
                    if first_error_info is None:
                        parts = calculated_time.split("|")
                        first_error_info = {
                            "detected_date": parts[1] if len(parts) > 1 else "",
                            "current_date": parts[2] if len(parts) > 2 else ""
                        }
                    continue
                
                reminder["time"] = calculated_time
                reminder.setdefault("timezone", timezone)
                reminder["content"] = str(reminder["content"])[:40]
                self.logger.info(f"Calculated time for reminder: {calculated_time}")
                validated_reminders.append(reminder)
        
        if validated_reminders:
            return {"reminders": validated_reminders, "message": None}
        elif first_error_info:
            return {
                "reminders": [], 
                "message": "past_date_error", 
                "detected_date": first_error_info.get("detected_date", ""), 
                "current_date": first_error_info.get("current_date", "")
            }
        else:
            self.logger.warning("No valid reminders found in AI response")
            return {"reminders": [], "message": "ai_error"}
    
    def _process_single_reminder(self, reminder: Dict, user_calendar: str, timezone: str) -> Dict[str, Any]:
        if self.reminder_validator.validate_parsed_object(reminder):
            calculated_time = self.time_calculator.calculate_reminder_time(reminder, user_calendar, timezone)
            
            if calculated_time and calculated_time.startswith("PAST_DATE_ERROR"):
                parts = calculated_time.split("|")
                detected_date = parts[1] if len(parts) > 1 else ""
                current_date = parts[2] if len(parts) > 2 else ""
                return {
                    "reminders": [], 
                    "message": "past_date_error", 
                    "detected_date": detected_date, 
                    "current_date": current_date
                }
            
            reminder["time"] = calculated_time
            reminder.setdefault("timezone", timezone)
            reminder["content"] = str(reminder["content"])[:40]
            self.logger.info(f"Calculated time for single reminder: {calculated_time}")
            return {"reminders": [reminder], "message": None}
        else:
            self.logger.warning(f"Invalid parsed object: {reminder}")
            return {"reminders": [], "message": "ai_error"}
    
    async def parse_edit(self, current_reminder: dict, edit_text: str, timezone: str, user_id: int = None) -> Dict[str, Any]:
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
            
            content = await self.api_client.make_api_call(messages, max_tokens=300, temperature=0.1)
            if not content:
                return None
            
            obj = json.loads(content)
            self.logger.info(f"Edit analysis result: {obj}")
            self.reminder_validator.normalize_repeat_field(obj)
            
            if obj.get('time') and ':' in obj.get('time', ''):
                user_data = self.storage.secure_load(user_id) if user_id else {}
                user_calendar = user_data.get("settings", {}).get("calendar", "miladi")
                calculated_time = self.time_calculator.calculate_reminder_time(obj, user_calendar, timezone)
                if calculated_time:
                    obj["time"] = calculated_time
                    obj.pop('specific_date', None)
            
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
            
            content = await self.api_client.make_api_call(messages, max_tokens=100, temperature=0.1)
            if not content:
                return None
            
            self.logger.info(f"Raw timezone response: {content[:200]}")
            if content.lower() == "null" or not content:
                self.logger.info("AI returned null or empty response")
                return None
            
            self.logger.info(f"Cleaned timezone content: {content}")
            obj = json.loads(content)
            
            if not isinstance(obj, dict) or "city" not in obj or "timezone" not in obj:
                return None
            
            city = str(obj.get("city", ""))[:50]
            timezone = str(obj.get("timezone", ""))
            
            if not self.timezone_detector.validate_timezone(timezone):
                return None
            
            return (city, timezone)
            
        except (ValueError, KeyError, json.JSONDecodeError, asyncio.TimeoutError) as e:
            self.logger.error(f"Timezone parsing error: {e}")
            return None
