import unittest
import os
from unittest.mock import patch
from config import Config


class TestConfig(unittest.TestCase):
    @patch.dict(os.environ, {
        'BOT_TOKEN': 'test_bot_token',
        'OPENROUTER_KEY': 'test_openrouter_key',
        'MAX_REQUESTS_PER_MINUTE': '30',
        'MAX_REMINDERS_PER_USER': '200'
    })
    def test_config_with_env_vars(self):
        config = Config()
        self.assertEqual(config.bot_token, 'test_bot_token')
        self.assertEqual(config.openrouter_key, 'test_openrouter_key')
        self.assertEqual(config.max_requests_per_minute, 30)
        self.assertEqual(config.max_reminders_per_user, 200)
        
    @patch.dict(os.environ, {}, clear=True)
    def test_config_defaults(self):
        config = Config()
        self.assertEqual(config.bot_token, '')
        self.assertEqual(config.openrouter_key, '')
        self.assertEqual(config.max_requests_per_minute, 20)
        self.assertEqual(config.max_reminders_per_user, 100)
        self.assertEqual(config.database_path, 'data/reminders.db')
        self.assertEqual(config.users_path, 'data/users')
        
    @patch.dict(os.environ, {
        'BOT_TOKEN': 'test_token',
        'OPENROUTER_KEY': 'test_key'
    })
    def test_config_validation_success(self):
        config = Config()
        self.assertTrue(config.validate())
        
    @patch.dict(os.environ, {'BOT_TOKEN': ''}, clear=True)
    def test_config_validation_missing_bot_token(self):
        config = Config()
        with self.assertRaises(ValueError) as cm:
            config.validate()
        self.assertIn("BOT_TOKEN", str(cm.exception))
        
    @patch.dict(os.environ, {
        'BOT_TOKEN': 'test_token',
        'OPENROUTER_KEY': ''
    }, clear=True)
    def test_config_validation_missing_openrouter_key(self):
        config = Config()
        with self.assertRaises(ValueError) as cm:
            config.validate()
        self.assertIn("OPENROUTER_KEY", str(cm.exception))


if __name__ == '__main__':
    unittest.main()
