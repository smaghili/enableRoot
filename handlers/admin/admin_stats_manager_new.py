from aiogram.types import Message
import logging

logger = logging.getLogger(__name__)

class AdminStatsManager:
    def __init__(self, storage, db, config, locales):
        self.storage = storage
        self.db = db
        self.config = config
        self.locales = locales
    
    def t(self, lang, key, **kwargs):
        text = self.locales.get(lang, self.locales["en"]).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text
    
    async def handle_general_stats(self, message: Message, lang: str):
        user_id = message.from_user.id
        try:
            stats = self.get_comprehensive_stats()
            user_reminder_count = self.get_user_reminder_count(user_id)
            
            stats_text = self.t(lang, "admin_stats_report", 
                              total_users=stats['total_users'],
                              admin_count=stats['admin_count'],
                              user_id=user_id,
                              user_name=message.from_user.first_name or 'Unknown',
                              username=message.from_user.username or 'Unknown',
                              user_reminder_count=user_reminder_count,
                              birthdays_today=stats['birthdays_today'],
                              birthdays_week=stats['birthdays_week'],
                              birthdays_month=stats['birthdays_month'],
                              total_birthdays=stats['total_birthdays'],
                              other_today=stats['other_today'],
                              other_week=stats['other_week'],
                              other_month=stats['other_month'],
                              total_other=stats['total_other'])
            
            await message.answer(stats_text)
            
        except Exception as e:
            logger.error(f"Error in handle_general_stats: {e}")
            await message.answer(self.t(lang, "admin_error"))
    
    def get_comprehensive_stats(self):
        users = self.storage.get_all_users()
        total_users = len(users)
        admin_count = len([uid for uid in self.config.admin_ids if uid])
        
        all_reminders = []
        for user_data in users:
            user_id = user_data.get("user_id")
            if user_id:
                user_reminders = self.db.list(user_id)
                all_reminders.extend(user_reminders)
        
        import datetime
        today = datetime.date.today()
        week_ago = today - datetime.timedelta(days=7)
        month_ago = today - datetime.timedelta(days=30)
        
        birthdays_today = 0
        birthdays_week = 0
        birthdays_month = 0
        total_birthdays = 0
        other_today = 0
        other_week = 0
        other_month = 0
        total_other = 0
        
        for reminder in all_reminders:
            try:
                reminder_date = datetime.datetime.strptime(reminder[3], "%Y-%m-%d %H:%M").date()
                category = reminder[1]
                
                if category == "birthday":
                    total_birthdays += 1
                    if reminder_date == today:
                        birthdays_today += 1
                    if reminder_date >= week_ago:
                        birthdays_week += 1
                    if reminder_date >= month_ago:
                        birthdays_month += 1
                else:
                    total_other += 1
                    if reminder_date == today:
                        other_today += 1
                    if reminder_date >= week_ago:
                        other_week += 1
                    if reminder_date >= month_ago:
                        other_month += 1
            except:
                continue
        
        return {
            'total_users': total_users,
            'admin_count': admin_count,
            'birthdays_today': birthdays_today,
            'birthdays_week': birthdays_week,
            'birthdays_month': birthdays_month,
            'total_birthdays': total_birthdays,
            'other_today': other_today,
            'other_week': other_week,
            'other_month': other_month,
            'total_other': total_other
        }
    
    def get_user_reminder_count(self, user_id):
        try:
            user_reminders = self.db.list(user_id)
            return len(user_reminders)
        except:
            return 0
