import unittest
import tempfile
import os
import datetime
from database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db = Database(self.temp_db.name)
        
    def tearDown(self):
        self.db.close()
        os.unlink(self.temp_db.name)
        
    def test_add_reminder(self):
        self.db.add(123, "medicine", "Take pills", "2024-01-01 10:00", "+00:00", "daily")
        reminders = self.db.list(123)
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0][2], "Take pills")
        
    def test_list_reminders(self):
        self.db.add(123, "work", "Meeting", "2024-01-01 14:00", "+00:00", "none")
        self.db.add(123, "medicine", "Pills", "2024-01-01 10:00", "+00:00", "daily")
        
        reminders = self.db.list(123)
        self.assertEqual(len(reminders), 2)
        
    def test_update_status(self):
        self.db.add(123, "work", "Meeting", "2024-01-01 14:00", "+00:00", "none")
        reminders = self.db.list(123)
        reminder_id = reminders[0][0]
        
        self.db.update_status(reminder_id, "completed")
        completed_reminders = self.db.list(123, "completed")
        self.assertEqual(len(completed_reminders), 1)
        
    def test_due_reminders(self):
        now = datetime.datetime.utcnow()
        past_time = (now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        future_time = (now + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        
        self.db.add(123, "work", "Past meeting", past_time, "+00:00", "none")
        self.db.add(123, "work", "Future meeting", future_time, "+00:00", "none")
        
        due_reminders = self.db.due(now)
        self.assertEqual(len(due_reminders), 1)
        self.assertEqual(due_reminders[0][3], "Past meeting")
        
    def test_birthday_reminders(self):
        self.db.add(123, "birthday", "John's birthday", "2024-06-15 08:00", "+00:00", "yearly")
        reminders = self.db.list(123)
        self.assertEqual(len(reminders), 3)
        
        categories = [r[1] for r in reminders]
        self.assertIn("birthday", categories)
        self.assertIn("birthday_pre_week", categories)
        self.assertIn("birthday_pre_three", categories)
        
    def test_cleanup_old_reminders(self):
        old_time = (datetime.datetime.utcnow() - datetime.timedelta(days=40)).strftime("%Y-%m-%d %H:%M")
        self.db.add(123, "work", "Old meeting", old_time, "+00:00", "none")
        self.db.update_status(1, "completed")
        
        deleted_count = self.db.cleanup_old_reminders(30)
        self.assertEqual(deleted_count, 1)
        
    def test_get_stats(self):
        self.db.add(123, "work", "Meeting 1", "2024-01-01 14:00", "+00:00", "none")
        self.db.add(456, "medicine", "Pills", "2024-01-01 10:00", "+00:00", "daily")
        
        stats = self.db.get_stats()
        self.assertEqual(stats[0], 2)
        self.assertEqual(stats[1], 2)
        self.assertEqual(stats[4], 2)


if __name__ == '__main__':
    unittest.main()
