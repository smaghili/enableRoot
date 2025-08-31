import aiohttp
import json
import datetime
try:
    import jdatetime
except ImportError:  # optional Persian calendar
    jdatetime = None


def _parse_tz(tz: str) -> datetime.timedelta:
    sign = 1 if tz.startswith("+") else -1
    hours, minutes = tz[1:].split(":")
    return datetime.timedelta(hours=sign * int(hours), minutes=sign * int(minutes))


class AIHandler:
    def __init__(self, key: str):
        self.key = key

    def fallback(self, text: str, timezone: str):
        now = datetime.datetime.utcnow() + _parse_tz(timezone)
        # Try to extract time from text
        import re
        time_match = re.search(r'(\d{1,2}):?(\d{2})?', text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            now = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
        return {
            "category": "general",
            "content": text,
            "time": now.strftime("%Y-%m-%d %H:%M"),
            "repeat": "none",
            "timezone": timezone,
        }

    async def parse(self, language: str, timezone: str, text: str):
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        now = datetime.datetime.utcnow() + _parse_tz(timezone)
        g_now = now.strftime("%Y-%m-%d %H:%M")
        p_now = (
            jdatetime.datetime.fromgregorian(datetime=now).strftime("%Y-%m-%d %H:%M")
            if jdatetime
            else "N/A"
        )
        prompt = f"""
You are a Persian/Arabic/Russian/English reminder parser. Current time: {g_now} (Gregorian), {p_now} (Persian), timezone: {timezone}, user language: {language}.

Parse this text: "{text}"

Categories: birthday, medicine, appointment, work, exercise, prayer, shopping, call, study, installment, bill, general

Time formats: YYYY-MM-DD HH:MM
Repeat options: none, daily, weekly, monthly, yearly

Examples:
- "هر روز ساعت 10 قرص" → {{"category": "medicine", "content": "قرص بخورم", "time": "YYYY-MM-DD 10:00", "repeat": "daily"}}
- "28 خرداد تولد مائده" → {{"category": "birthday", "content": "تولد مائده", "time": "YYYY-MM-DD 08:00", "repeat": "yearly"}}
- "هر ماه 15 قسط ماشین" → {{"category": "installment", "content": "قسط ماشین", "time": "YYYY-MM-15 09:00", "repeat": "monthly"}}

Respond ONLY with valid JSON containing: category, content, time, repeat
        """
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a reminder parser that outputs JSON.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                    },
                ) as r:
                    data = await r.json()
                    obj = json.loads(data["choices"][0]["message"]["content"])
                    if not all(k in obj for k in ("category", "content", "time")):
                        raise ValueError("missing keys")
                    obj.setdefault("repeat", "none")
                    obj.setdefault("timezone", timezone)
                    return obj
        except (aiohttp.ClientError, ValueError, KeyError, json.JSONDecodeError) as e:
            print(e)
            return self.fallback(text, timezone)
