import unittest
from unittest.mock import patch, AsyncMock
import asyncio
from ai_handler import AIHandler, _parse_tz
import datetime


class TestAIHandler(unittest.TestCase):
    def setUp(self):
        self.ai = AIHandler("test_key")
        
    def test_init_with_invalid_key(self):
        with self.assertRaises(ValueError):
            AIHandler("")
            
    def test_fallback(self):
        result = self.ai.fallback("Take medicine at 10:30", "+03:00")
        self.assertEqual(result["category"], "general")
        self.assertEqual(result["content"], "Take medicine at 10:30")
        self.assertEqual(result["repeat"], "none")
        
    def test_fallback_with_time_extraction(self):
        result = self.ai.fallback("Meeting at 14:30", "+00:00")
        self.assertIn("14:30", result["time"])
        
    def test_fallback_with_invalid_time(self):
        result = self.ai.fallback("Meeting at 25:70", "+00:00")
        self.assertNotIn("25:70", result["time"])
        
    def test_fallback_with_long_text(self):
        long_text = "x" * 1000
        result = self.ai.fallback(long_text, "+00:00")
        self.assertEqual(len(result["content"]), 500)
        
    def test_validate_parsed_object_valid(self):
        obj = {
            "category": "medicine",
            "content": "Take pills",
            "time": "2024-01-01 10:00",
            "repeat": "daily"
        }
        self.assertTrue(self.ai._validate_parsed_object(obj))
        
    def test_validate_parsed_object_invalid_category(self):
        obj = {
            "category": "invalid_category",
            "content": "Take pills",
            "time": "2024-01-01 10:00"
        }
        self.assertTrue(self.ai._validate_parsed_object(obj))
        self.assertEqual(obj["category"], "general")
        
    def test_validate_parsed_object_invalid_time(self):
        obj = {
            "category": "medicine",
            "content": "Take pills",
            "time": "invalid_time"
        }
        self.assertFalse(self.ai._validate_parsed_object(obj))
        
    def test_validate_parsed_object_missing_keys(self):
        obj = {
            "category": "medicine",
            "content": "Take pills"
        }
        self.assertFalse(self.ai._validate_parsed_object(obj))
        
    @patch('aiohttp.ClientSession.post')
    async def test_parse_success(self, mock_post):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"category": "medicine", "content": "Take pills", "time": "2024-01-01 10:00"}'
                }
            }]
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await self.ai.parse("en", "+00:00", "Take pills at 10am")
        self.assertEqual(result["category"], "medicine")
        self.assertEqual(result["content"], "Take pills")
        
    @patch('aiohttp.ClientSession.post')
    async def test_parse_api_error(self, mock_post):
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await self.ai.parse("en", "+00:00", "Take pills")
        self.assertEqual(result["category"], "general")
        
    async def test_parse_invalid_input(self):
        with self.assertRaises(ValueError):
            await self.ai.parse("en", "+00:00", "")
            
    async def test_parse_long_input(self):
        long_text = "x" * 2000
        result = await self.ai.parse("en", "+00:00", long_text)
        self.assertIsInstance(result, dict)


class TestParseTz(unittest.TestCase):
    def test_positive_timezone(self):
        result = _parse_tz("+03:30")
        expected = datetime.timedelta(hours=3, minutes=30)
        self.assertEqual(result, expected)
        
    def test_negative_timezone(self):
        result = _parse_tz("-05:00")
        expected = datetime.timedelta(hours=-5, minutes=0)
        self.assertEqual(result, expected)
        
    def test_invalid_timezone(self):
        result = _parse_tz("invalid")
        self.assertEqual(result, datetime.timedelta(0))
        
    def test_empty_timezone(self):
        result = _parse_tz("")
        self.assertEqual(result, datetime.timedelta(0))
        
    def test_timezone_without_colon(self):
        result = _parse_tz("+0330")
        expected = datetime.timedelta(hours=3, minutes=30)
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
