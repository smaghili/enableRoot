import aiohttp
import json
import datetime
import logging
import re
import asyncio
from typing import Dict, Any, Optional
from config.prompt_manager import PromptManager
from .ai.ai_handler import AIHandler

__all__ = ['AIHandler']

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