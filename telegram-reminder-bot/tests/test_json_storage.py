import unittest
import tempfile
import shutil
import os
from json_storage import JSONStorage


class TestJSONStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = JSONStorage(self.temp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_load_new_user(self):
        data = self.storage.load(123)
        self.assertEqual(data["user_id"], 123)
        self.assertIn("settings", data)
        self.assertIn("reminders", data)
        
    def test_save_and_load(self):
        data = self.storage.load(123)
        data["test_field"] = "test_value"
        self.storage.save(123, data)
        
        loaded_data = self.storage.load(123)
        self.assertEqual(loaded_data["test_field"], "test_value")
        
    def test_update_setting(self):
        self.storage.update_setting(123, "language", "fa")
        data = self.storage.load(123)
        self.assertEqual(data["settings"]["language"], "fa")
        
    def test_add_reminder(self):
        reminder = {
            "category": "medicine",
            "content": "Take pills",
            "time": "2024-01-01 10:00",
            "repeat": "daily"
        }
        self.storage.add_reminder(123, reminder)
        
        data = self.storage.load(123)
        self.assertEqual(len(data["reminders"]["active"]), 1)
        self.assertEqual(data["reminders"]["active"][0]["content"], "Take pills")
        
    def test_get_user_language(self):
        self.storage.update_setting(123, "language", "fa")
        lang = self.storage.get_user_language(123)
        self.assertEqual(lang, "fa")
        
    def test_get_user_language_default(self):
        lang = self.storage.get_user_language(999)
        self.assertEqual(lang, "en")
        
    def test_invalid_reminder_data(self):
        with self.assertRaises(ValueError):
            self.storage.add_reminder(123, "invalid_data")
            
    def test_invalid_setting_key(self):
        with self.assertRaises(ValueError):
            self.storage.update_setting(123, "", "value")
            
    def test_corrupted_json_recovery(self):
        user_file = self.storage.file(123)
        with open(user_file, 'w') as f:
            f.write("invalid json content")
            
        data = self.storage.load(123)
        self.assertEqual(data["user_id"], 123)
        self.assertIn("settings", data)


if __name__ == '__main__':
    unittest.main()
