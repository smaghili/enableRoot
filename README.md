# 🤖 Telegram Reminder Bot

ربات تلگرامی هوشمند برای مدیریت یادآوری‌ها با پشتیبانی از زبان فارسی و تاریخ شمسی

## ✨ ویژگی‌ها

- 🧠 **پردازش هوشمند متن** با OpenRouter AI
- 🌍 **چندزبانه**: فارسی، انگلیسی، عربی، روسی
- 📅 **تاریخ شمسی** و میلادی
- 🕐 **تایم‌زون** قابل تنظیم
- 💊 **انواع یادآوری**: دارو، تولد، قسط، کار، ورزش و...
- 🔄 **تکرار**: روزانه، هفتگی، ماهانه، سالانه
- 📱 **منوهای تعاملی** و دکمه‌های هوشمند
- ⚙️ **سیستم تنظیمات پیشرفته** با فایل JSON

## 🚀 نصب و راه‌اندازی

### روش آسان (توصیه شده):
```bash
# اجرای اسکریپت نصب
./install.sh
```

اسکریپت نصب به صورت خودکار:
- Python و dependencies را نصب می‌کند
- توکن‌های مورد نیاز را از شما می‌گیرد
- فایل `config.json` را با تنظیمات پیش‌فرض ایجاد می‌کند
- پوشه‌های داده را ایجاد می‌کند
- سرویس systemd را (اختیاری) تنظیم می‌کند

### روش دستی:

#### 1. نصب dependencies:
```bash
pip install -r requirements.txt
```

#### 2. تنظیم فایل config.json:
```bash
# کپی کردن فایل نمونه
cp config.json.example config.json

# ویرایش فایل با توکن‌های واقعی
nano config.json
```

#### 3. اجرای ربات:
```bash
python bot.py
```

## 📝 نحوه استفاده

### دستورات:
- `/start` - شروع و انتخاب زبان
- `/menu` - نمایش منوی اصلی  
- `/list` - لیست یادآوری‌ها
- `/lang fa` - تغییر زبان به فارسی
- `/tz +03:30` - تنظیم تایم‌زون ایران
- `/delete 123` - حذف یادآوری با شناسه 123

### مثال‌های یادآوری:
```
هر روز ساعت 10 قرص بخورم
28 خرداد 1372 تولد مائده است هر سال یادآوری کن  
هر ماه روز 15 باید قسط ماشین بدم
فردا ساعت 3 جلسه کاری دارم
```

## ⚙️ تنظیمات

### فایل config.json:
```json
{
  "bot": {
    "token": "YOUR_BOT_TOKEN_HERE",
    "max_requests_per_minute": 20,
    "max_reminders_per_user": 100
  },
  "ai": {
    "openrouter_key": "YOUR_OPENROUTER_API_KEY_HERE",
    "model": "gpt-4o",
    "max_tokens": 500,
    "temperature": 0.1
  },
  "database": {
    "path": "data/reminders.db",
    "timeout": 30.0
  },
  "storage": {
    "users_path": "data/users",
    "backup_enabled": true
  },
  "security": {
    "max_content_length": 1000,
    "enable_rate_limiting": true
  }
}
```

### تنظیمات قابل تغییر:
- **Rate Limiting**: تعداد درخواست‌های مجاز در دقیقه
- **AI Model**: مدل هوش مصنوعی مورد استفاده
- **Database**: مسیر و تنظیمات پایگاه داده
- **Security**: محدودیت‌های امنیتی
- **Notifications**: استراتژی ارسال اعلان‌ها

## 🏗 ساختار پروژه

```
telegram-reminder-bot/
├── bot.py                 # ربات اصلی تلگرام
├── config.py              # مدیریت تنظیمات
├── config.json.example    # نمونه فایل تنظیمات
├── config.json            # فایل تنظیمات (ایجاد شده توسط install.sh)
├── constants.py            # ثابت‌های برنامه
├── ai_handler.py          # پردازش AI
├── database.py            # مدیریت دیتابیس
├── json_storage.py        # ذخیره‌سازی JSON
├── reminder_scheduler.py  # زمان‌بندی یادآوری‌ها
├── message_handlers.py    # پردازش پیام‌ها
├── callback_handlers.py   # پردازش دکمه‌ها
├── repeat_handler.py      # مدیریت تکرارها
├── install.sh             # اسکریپت نصب خودکار
├── requirements.txt       # وابستگی‌های Python
├── localization/          # فایل‌های ترجمه
│   ├── fa.json           # فارسی
│   ├── en.json           # انگلیسی
│   ├── ar.json           # عربی
│   └── ru.json           # روسی
└── data/                 # داده‌های کاربران
    ├── reminders.db      # پایگاه داده
    └── users/            # فایل‌های JSON کاربران
```

## 🔑 دریافت توکن‌ها

### توکن ربات تلگرام:
1. به [@BotFather](https://t.me/BotFather) در تلگرام پیام دهید
2. دستور `/newbot` را ارسال کنید
3. نام و username برای ربات انتخاب کنید
4. توکن دریافتی را کپی کنید

### کلید API OpenRouter:
1. به [OpenRouter.ai](https://openrouter.ai) بروید
2. ثبت نام کنید یا وارد شوید
3. به بخش API Keys بروید
4. یک کلید جدید ایجاد کنید
5. کلید را کپی کنید

## 🧪 تست

```bash
# اجرای تمام تست‌ها
python run_tests.py

# تست تنظیمات
python test_config.py

# تست handlers
python test_message_handlers.py
```

## 📊 نظارت و لاگ‌ها

### مشاهده لاگ‌ها:
```bash
tail -f bot.log
```

### بررسی وضعیت:
```bash
# اگر با systemd نصب شده
sudo systemctl status telegram-reminder-bot

# بررسی فایل‌های داده
ls -la data/
```

## 🔧 عیب‌یابی

### مشکلات رایج:
1. **خطای توکن**: توکن ربات یا OpenRouter را بررسی کنید
2. **خطای دیتابیس**: مجوزهای پوشه `data/` را بررسی کنید
3. **خطای import**: `pip install -r requirements.txt` را اجرا کنید

### لاگ‌های مفید:
```bash
# لاگ‌های خطا
grep ERROR bot.log

# لاگ‌های مربوط به کاربر خاص
grep "user_id: 123456" bot.log
```

## 🤝 مشارکت

برای مشارکت در توسعه:
1. Fork کنید
2. Branch جدید ایجاد کنید
3. تغییرات را commit کنید
4. Pull Request ارسال کنید

## 📄 لایسنس

این پروژه تحت لایسنس MIT منتشر شده است.

---

**نکته**: فایل `config.json` حاوی اطلاعات حساس است. آن را در git commit نکنید!