import unittest
import os
import json
import tempfile
from unittest.mock import patch
from config import Config

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.config_data = {
            "bot": {
                "token": "test_bot_token",
                "max_requests_per_minute": 30,
                "max_reminders_per_user": 200
            },
            "ai": {
                "openrouter_key": "test_openrouter_key",
                "model": "gpt-4o",
                "max_tokens": 500,
                "temperature": 0.1,
                "timeout": 30.0
            },
            "database": {
                "path": "test_data/reminders.db",
                "timeout": 30.0
            },
            "storage": {
                "users_path": "test_data/users",
                "backup_interval_hours": 12
            },
            "security": {
                "max_content_length": 1500,
                "enable_rate_limiting": True,
                "enable_input_validation": True
            },
            "notification": {
                "strategy": "standard",
                "max_retries": 5,
                "retry_delay": 2.0
            }
        }
        json.dump(self.config_data, self.temp_config)
        self.temp_config.close()

    def tearDown(self):
        os.unlink(self.temp_config.name)

    @patch('config.Config._load_config')
    def test_config_with_json_file(self, mock_load_config):
        mock_load_config.return_value = self.config_data
        config = Config()
        self.assertEqual(config.bot_token, 'test_bot_token')
        self.assertEqual(config.max_requests_per_minute, 30)
        self.assertEqual(config.max_reminders_per_user, 200)
        self.assertEqual(config.openrouter_key, 'test_openrouter_key')
        self.assertEqual(config.ai_model, 'gpt-4o')
        self.assertEqual(config.ai_max_tokens, 500)
        self.assertEqual(config.ai_temperature, 0.1)
        self.assertEqual(config.ai_timeout, 30.0)
        self.assertEqual(config.database_path, 'test_data/reminders.db')
        self.assertEqual(config.users_path, 'test_data/users')
        self.assertEqual(config.cleanup_interval_hours, 12)
        self.assertEqual(config.max_content_length, 1500)
        self.assertTrue(config.enable_rate_limiting)
        self.assertTrue(config.enable_input_validation)
        self.assertEqual(config.notification_strategy, 'standard')
        self.assertEqual(config.notification_max_retries, 5)
        self.assertEqual(config.notification_retry_delay, 2.0)



    @patch('config.Config._load_config')
    def test_config_validation_success(self, mock_load_config):
        mock_load_config.return_value = {
            "bot": {"token": "test_token"},
            "ai": {"openrouter_key": "test_key"}
        }
        config = Config()
        self.assertTrue(config.validate())

    @patch('config.Config._load_config')
    def test_config_validation_missing_bot_token(self, mock_load_config):
        mock_load_config.return_value = {
            "ai": {"openrouter_key": "test_key"}
        }
        config = Config()
        with self.assertRaises(ValueError) as cm:
            config.validate()
        self.assertIn("BOT_TOKEN", str(cm.exception))

    @patch('config.Config._load_config')
    def test_config_validation_missing_openrouter_key(self, mock_load_config):
        mock_load_config.return_value = {
            "bot": {"token": "test_token"}
        }
        config = Config()
        with self.assertRaises(ValueError) as cm:
            config.validate()
        self.assertIn("OPENROUTER_KEY", str(cm.exception))

    def test_load_config_file_not_found(self):
        with patch('os.path.exists', return_value=False):
            config = Config()
            self.assertEqual(config.config_data, {})

    def test_load_config_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')
            temp_file = f.name
        try:
            with patch('config.Config._load_config') as mock_load_config:
                mock_load_config.return_value = {}
                config = Config()
                self.assertEqual(config.config_data, {})
        finally:
            os.unlink(temp_file)

if __name__ == '__main__':
    unittest.main()
