import json
import datetime
import re
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass
import logging


@dataclass
class RepeatPattern:
    type: str
    value: Optional[int] = None
    unit: Optional[str] = None
    time: Optional[str] = None
    day: Optional[int] = None
    weekday: Optional[int] = None


class RepeatHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        

        self.persian_patterns = {
            r'هر\s*دقیقه': ('interval', 'minutes', 1),
            r'هر\s*(\d+)\s*دقیقه': ('interval', 'minutes'),
            r'هر\s*ساعت': ('interval', 'hours', 1),
            r'هر\s*(\d+)\s*ساعت': ('interval', 'hours'),
            r'هر\s*روز|روزانه': ('daily', None),
            r'هر\s*(\d+)\s*روز': ('interval', 'days'),
            r'هر\s*هفته|هفتگی': ('weekly', None),
            r'هر\s*ماه|ماهانه': ('monthly', None),
            r'هر\s*سال|سالانه': ('yearly', None),
        }
        

        self.display_formats = {
            'fa': {
                'none': 'یکبار',
                'daily': 'روزانه',
                'weekly': 'هفتگی', 
                'monthly': 'ماهانه',
                'yearly': 'سالانه',
                'interval_minutes': 'هر {value} دقیقه',
                'interval_hours': 'هر {value} ساعت',
                'interval_days': 'هر {value} روز'
            },
            'en': {
                'none': 'Once',
                'daily': 'Daily',
                'weekly': 'Weekly',
                'monthly': 'Monthly', 
                'yearly': 'Yearly',
                'interval_minutes': 'Every {value} minutes',
                'interval_hours': 'Every {value} hours',
                'interval_days': 'Every {value} days'
            },
            'ar': {
                'none': 'مرة واحدة',
                'daily': 'يوميا',
                'weekly': 'أسبوعيا',
                'monthly': 'شهريا',
                'yearly': 'سنويا',
                'interval_minutes': 'كل {value} دقيقة',
                'interval_hours': 'كل {value} ساعة',
                'interval_days': 'كل {value} يوم'
            },
            'ru': {
                'none': 'Один раз',
                'daily': 'Ежедневно',
                'weekly': 'Еженедельно',
                'monthly': 'Ежемесячно',
                'yearly': 'Ежегодно',
                'interval_minutes': 'Каждые {value} минут',
                'interval_hours': 'Каждые {value} часов',
                'interval_days': 'Каждые {value} дней'
            }
        }

    def parse_from_text(self, text: str, current_time: datetime.datetime) -> RepeatPattern:
        try:
            text = text.strip().lower()
            

            for pattern, pattern_data in self.persian_patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    repeat_type = pattern_data[0]
                    unit = pattern_data[1]
                    
                    if repeat_type == 'interval':
                        if len(pattern_data) == 3:
                            value = pattern_data[2]
                        else:
                            value = int(match.group(1))
                        return RepeatPattern(type='interval', value=value, unit=unit)
                    else:
                        return RepeatPattern(type=repeat_type)
            

            return RepeatPattern(type='none')
            
        except Exception as e:
            self.logger.error(f"Error parsing repeat pattern from text: {e}")
            return RepeatPattern(type='none')

    def to_json(self, pattern: RepeatPattern) -> str:
        try:
            if pattern.type == 'none':
                return json.dumps({"type": "none"})
            elif pattern.type == 'interval':
                return json.dumps({
                    "type": "interval",
                    "value": pattern.value,
                    "unit": pattern.unit
                })
            else:
                return json.dumps({"type": pattern.type})
        except Exception as e:
            self.logger.error(f"Error converting pattern to JSON: {e}")
            return json.dumps({"type": "none"})

    def from_json(self, json_str: str) -> RepeatPattern:
        try:
            if not json_str or json_str.strip() in ['none', 'daily', 'weekly', 'monthly', 'yearly']:
    
                return RepeatPattern(type=json_str.strip() if json_str else 'none')
            
            data = json.loads(json_str)
            if not isinstance(data, dict):
                return RepeatPattern(type='none')
                
            pattern_type = data.get('type', 'none')
            
            if pattern_type == 'interval':
                return RepeatPattern(
                    type='interval',
                    value=data.get('value'),
                    unit=data.get('unit')
                )
            else:
                return RepeatPattern(type=pattern_type)
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"Error parsing JSON repeat pattern: {e}")
            return RepeatPattern(type='none')

    def calculate_next_time(self, current_time: datetime.datetime, pattern: RepeatPattern) -> Optional[datetime.datetime]:
        try:
            if pattern.type == 'none':
                return None
            elif pattern.type == 'interval':
                if pattern.unit == 'minutes':
                    return current_time + datetime.timedelta(minutes=pattern.value)
                elif pattern.unit == 'hours':
                    return current_time + datetime.timedelta(hours=pattern.value)
                elif pattern.unit == 'days':
                    return current_time + datetime.timedelta(days=pattern.value)
            elif pattern.type == 'daily':
                return current_time + datetime.timedelta(days=1)
            elif pattern.type == 'weekly':
                return current_time + datetime.timedelta(weeks=1)
            elif pattern.type == 'monthly':
                if current_time.month == 12:
                    return current_time.replace(year=current_time.year + 1, month=1)
                else:
                    return current_time.replace(month=current_time.month + 1)
            elif pattern.type == 'yearly':
                try:
                    return current_time.replace(year=current_time.year + 1)
                except ValueError:
                    return current_time.replace(year=current_time.year + 1, day=28)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error calculating next time: {e}")
            return None

    def get_display_text(self, pattern: RepeatPattern, language: str = 'fa') -> str:
        try:
            lang_formats = self.display_formats.get(language, self.display_formats['fa'])
            
            if pattern.type == 'none':
                return lang_formats['none']
            elif pattern.type == 'interval':
                key = f"interval_{pattern.unit}"
                if key in lang_formats:
                    return lang_formats[key].format(value=pattern.value)
                else:
                    return f"{pattern.value} {pattern.unit}"
            elif pattern.type in lang_formats:
                return lang_formats[pattern.type]
            else:
                return pattern.type
                
        except Exception as e:
            self.logger.error(f"Error getting display text: {e}")
            return "Unknown"

    def is_valid_pattern(self, pattern: RepeatPattern) -> bool:
        try:
            if pattern.type == 'none':
                return True
            elif pattern.type == 'interval':
                return (pattern.value is not None and 
                       pattern.value > 0 and 
                       pattern.unit in ['minutes', 'hours', 'days'])
            elif pattern.type in ['daily', 'weekly', 'monthly', 'yearly']:
                return True
            else:
                return False
        except Exception:
            return False
