import unittest
from unittest.mock import Mock, AsyncMock, patch
from message_handlers import ReminderMessageHandler
from config import Config

class TestReminderMessageHandler(unittest.TestCase):
    def setUp(self):
        self.mock_storage = Mock()
        self.mock_db = Mock()
        self.mock_ai = Mock()
        self.mock_repeat_handler = Mock()
        self.mock_config = Mock()
        self.mock_config.max_requests_per_minute = 20
        self.mock_config.max_content_length = 1000
        self.mock_locales = {
            "fa": {"test_key": "test_value_fa"},
            "en": {"test_key": "test_value_en"}
        }
        self.handler = ReminderMessageHandler(
            self.mock_storage, self.mock_db, self.mock_ai, 
            self.mock_repeat_handler, self.mock_locales, Mock(), self.mock_config
        )

    def test_t_function(self):
        result = self.handler.t("fa", "test_key")
        self.assertEqual(result, "test_value_fa")
        
        result = self.handler.t("en", "test_key")
        self.assertEqual(result, "test_value_en")
        
        result = self.handler.t("unknown", "test_key")
        self.assertEqual(result, "test_value_en")

    def test_rate_limit_check(self):
        user_id = 123
        self.handler.user_request_times[user_id] = []
        
        for i in range(self.handler.config.max_requests_per_minute):
            result = self.handler.rate_limit_check(user_id)
            self.assertTrue(result)
        
        result = self.handler.rate_limit_check(user_id)
        self.assertFalse(result)

    def test_validate_user_input(self):
        self.assertTrue(self.handler.validate_user_input("valid text"))
        self.assertFalse(self.handler.validate_user_input(""))
        self.assertFalse(self.handler.validate_user_input(None))
        self.assertFalse(self.handler.validate_user_input("a" * (self.handler.config.max_content_length + 1)))

    def test_sanitize_input(self):
        self.assertEqual(self.handler.sanitize_input("test"), "test")
        self.assertEqual(self.handler.sanitize_input("  test  "), "test")
        self.assertEqual(self.handler.sanitize_input(None), "")
        self.assertEqual(self.handler.sanitize_input("a" * (self.handler.config.max_content_length + 10)), "a" * self.handler.config.max_content_length)

    def test_get_button_action(self):
        self.mock_locales["fa"]["btn_list"] = "لیست"
        self.mock_locales["fa"]["btn_delete"] = "حذف"
        
        result = self.handler.get_button_action("لیست", "fa")
        self.assertEqual(result, "list")
        
        result = self.handler.get_button_action("حذف", "fa")
        self.assertEqual(result, "delete")
        
        result = self.handler.get_button_action("unknown", "fa")
        self.assertIsNone(result)



if __name__ == "__main__":
    unittest.main()
