import aiohttp
import logging
from typing import Optional

class APIClient:
    def __init__(self, key: str, model: str = "gpt-4o"):
        self.key = key
        self.model = model
        self.logger = logging.getLogger(__name__)
        self.session_timeout = aiohttp.ClientTimeout(total=30)
        
        if not key or not isinstance(key, str):
            raise ValueError("Invalid API key provided")
    
    async def make_api_call(self, messages: list, max_tokens: int = 400, temperature: float = 0.1) -> Optional[str]:
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
