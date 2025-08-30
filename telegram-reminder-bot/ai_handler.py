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
        prompt = (
            f"current_gregorian:{g_now} current_persian:{p_now} timezone:{timezone} "
            f"language:{language} text:{text}. "
            "Categories: birthday, medicine, appointment, work, exercise, prayer, shopping, call, study, installment, bill, general. "
            "Respond in JSON with keys category, content, time, repeat."
        )
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
