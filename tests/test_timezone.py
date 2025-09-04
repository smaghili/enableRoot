import unittest
from unittest.mock import patch, AsyncMock
import asyncio
from handlers.ai.ai_handler import AIHandler


class TestTimezoneHandler(unittest.TestCase):
    def setUp(self):
        self.ai = AIHandler("test_key")
        
    def test_validate_timezone_valid(self):
        self.assertTrue(self.ai._validate_timezone("+03:30"))
        self.assertTrue(self.ai._validate_timezone("-05:00"))
        self.assertTrue(self.ai._validate_timezone("+00:00"))
        self.assertTrue(self.ai._validate_timezone("+14:00"))
        self.assertTrue(self.ai._validate_timezone("-12:00"))
        
    def test_validate_timezone_invalid(self):
        self.assertFalse(self.ai._validate_timezone("invalid"))
        self.assertFalse(self.ai._validate_timezone("03:30"))
        self.assertFalse(self.ai._validate_timezone("+25:00"))
        self.assertFalse(self.ai._validate_timezone("+03:70"))
        self.assertFalse(self.ai._validate_timezone(""))
        self.assertFalse(self.ai._validate_timezone(None))
        
    @patch('aiohttp.ClientSession.post')
    async def test_parse_timezone_success(self, mock_post):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"city": "Tehran", "timezone": "+03:30"}'
                }
            }]
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await self.ai.parse_timezone("Tehran")
        self.assertEqual(result, ("Tehran", "+03:30"))
        
    @patch('aiohttp.ClientSession.post')
    async def test_parse_timezone_not_found(self, mock_post):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": 'null'
                }
            }]
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await self.ai.parse_timezone("InvalidCity")
        self.assertIsNone(result)
        
    @patch('aiohttp.ClientSession.post')
    async def test_parse_timezone_api_error(self, mock_post):
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await self.ai.parse_timezone("Tehran")
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
