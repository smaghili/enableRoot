from aiogram.types import Message
import logging
import json

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
        stats = self.db.get_admin_stats()
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
            stats['admin_count'] = len(config_data["bot"]["admin_ids"])
        except Exception:
            stats['admin_count'] = 1
        
        user_id = message.from_user.id
        user_reminder_count = self.db.get_user_details(user_id)
        
        stats_text = f"""📊 آمار:

👤 تعداد کاربران ربات : {stats['total_users']} نفر
🖍 تعداد ادمین های ربات :  {stats['admin_count']} نفر

👤 کاربر درخواست کننده:
🆔 ایدی عددی: {user_id}
👤 نام: {message.from_user.first_name or 'نامشخص'}
🆔 یوزرنیم: @{message.from_user.username or 'نامشخص'}
📝 تعداد یادآوری های ثبت شده: {user_reminder_count} عدد

🎂  تولدها
تعداد تولدهای ثبت شده امروز : {stats['birthdays_today']} 
تعداد تولدهای یک هفته اخیر : {stats['birthdays_week']} 
تعداد تولدهای  یک ماه اخیر : {stats['birthdays_month']} 
تعداد کل تولدهای ثبت شده تا امروز  : {stats['total_birthdays']} 

📅 سایر یادآوری ها"""
        for category, cat_stats in stats['category_stats'].items():
            category_display = self.get_category_display_name(category, lang)
            stats_text += f"""

{category_display}
تعداد {category_display} ثبت شده امروز : {cat_stats['today']} 
تعداد {category_display} یک هفته اخیر : {cat_stats['week']} 
تعداد {category_display} یک ماه اخیر : {cat_stats['month']} 
تعداد کل {category_display} ثبت شده تا امروز  : {cat_stats['total']} """
        await message.answer(stats_text)
    
    def get_category_display_name(self, category: str, lang: str) -> str:
        category_mapping = {
            'medicine': '💊 دارو',
            'appointment': '📅 قرار ملاقات',
            'work': '💼 کار',
            'exercise': '🏃‍♂️ ورزش',
            'prayer': '🕌 نماز',
            'shopping': '🛒 خرید',
            'call': '📞 تماس',
            'study': '📚 درس',
            'installment': '💳 قسط',
            'bill': '💰 قبض',
            'general': '⏰ عمومی'
        }
        if lang == 'fa':
            return category_mapping.get(category, category)
        else:
            english_names = {
                'medicine': '💊 Medicine',
                'appointment': '📅 Appointment',
                'work': '💼 Work',
                'exercise': '🏃‍♂️ Exercise',
                'prayer': '🕌 Prayer',
                'shopping': '🛒 Shopping',
                'call': '📞 Call',
                'study': '📚 Study',
                'installment': '💳 Installment',
                'bill': '💰 Bill',
                'general': '⏰ General'
            }
            return english_names.get(category, category)
