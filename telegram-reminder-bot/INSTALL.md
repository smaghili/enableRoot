# 🚀 راهنمای نصب ربات تلگرام یادآوری

## 📋 پیش‌نیازها

- **سیستم عامل**: Linux, macOS, یا Windows (با WSL)
- **Python**: نسخه 3.7 یا بالاتر
- **اتصال اینترنت**: برای دانلود کتابخانه‌ها
- **توکن ربات تلگرام**: از [@BotFather](https://t.me/BotFather)
- **کلید API OpenRouter**: از [OpenRouter.ai](https://openrouter.ai)

## ⚡ نصب سریع (توصیه شده)

### 1. دانلود پروژه
```bash
git clone <repository-url>
cd telegram-reminder-bot
```

### 2. اجرای اسکریپت نصب
```bash
./install.sh
```

اسکریپت نصب به طور خودکار:
- ✅ Python و pip را نصب می‌کند (در صورت نیاز)
- ✅ محیط مجازی (virtual environment) ایجاد می‌کند
- ✅ تمام کتابخانه‌های مورد نیاز را نصب می‌کند
- ✅ توکن‌ها و تنظیمات را از شما می‌گیرد
- ✅ فایل `.env` را ایجاد می‌کند
- ✅ پوشه‌های داده را با مجوزهای امن ایجاد می‌کند
- ✅ نصب را تست می‌کند
- ✅ سرویس systemd ایجاد می‌کند (اختیاری)

### 3. اجرای ربات
```bash
./run.sh
```

یا:
```bash
source venv/bin/activate
python bot.py
```

## 🔧 نصب دستی

اگر ترجیح می‌دهید نصب دستی انجام دهید:

### 1. نصب Python و pip
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip

# macOS
brew install python3
```

### 2. ایجاد محیط مجازی
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. نصب کتابخانه‌ها
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. تنظیم متغیرهای محیطی
```bash
cp .env.example .env
nano .env
```

فایل `.env` را با اطلاعات خود پر کنید:
```env
BOT_TOKEN=your_telegram_bot_token_here
OPENROUTER_KEY=your_openrouter_api_key_here
MAX_REQUESTS_PER_MINUTE=20
MAX_REMINDERS_PER_USER=100
CLEANUP_INTERVAL_HOURS=24
LOG_LEVEL=INFO
```

### 5. ایجاد پوشه‌های داده
```bash
mkdir -p data/users
chmod 700 data data/users
```

### 6. اجرای ربات
```bash
python bot.py
```

## 🔑 دریافت توکن‌ها

### توکن ربات تلگرام
1. به [@BotFather](https://t.me/BotFather) در تلگرام پیام دهید
2. دستور `/newbot` را ارسال کنید
3. نام و username برای ربات انتخاب کنید
4. توکن دریافتی را کپی کنید

### کلید API OpenRouter
1. به [OpenRouter.ai](https://openrouter.ai) بروید
2. ثبت نام کنید یا وارد شوید
3. به بخش API Keys بروید
4. یک کلید جدید ایجاد کنید
5. کلید را کپی کنید

## 🔧 تنظیمات اختیاری

### متغیرهای محیطی قابل تنظیم:

| متغیر | پیش‌فرض | توضیح |
|-------|---------|--------|
| `MAX_REQUESTS_PER_MINUTE` | 20 | حداکثر درخواست در دقیقه برای هر کاربر |
| `MAX_REMINDERS_PER_USER` | 100 | حداکثر یادآوری برای هر کاربر |
| `CLEANUP_INTERVAL_HOURS` | 24 | فاصله پاکسازی به ساعت |
| `LOG_LEVEL` | INFO | سطح لاگ (DEBUG/INFO/WARNING/ERROR) |

### سرویس Systemd (Linux)

برای اجرای خودکار ربات:
```bash
sudo systemctl start telegram-reminder-bot
sudo systemctl enable telegram-reminder-bot
sudo systemctl status telegram-reminder-bot
```

## 🧪 تست نصب

```bash
source venv/bin/activate
python run_tests.py
```

## 📊 نظارت و لاگ‌ها

### مشاهده لاگ‌ها
```bash
tail -f bot.log
```

### بررسی وضعیت سرویس
```bash
sudo systemctl status telegram-reminder-bot
```

### مشاهده لاگ‌های سرویس
```bash
sudo journalctl -u telegram-reminder-bot -f
```

## 🔄 بروزرسانی

```bash
git pull
./install.sh
```

## 🗑️ حذف نصب

```bash
./uninstall.sh
```

## ❗ عیب‌یابی

### مشکلات رایج:

#### 1. خطای "Permission denied"
```bash
chmod +x install.sh
chmod +x run.sh
```

#### 2. خطای "Python not found"
```bash
# نصب Python
sudo apt-get install python3 python3-pip
```

#### 3. خطای "Module not found"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

#### 4. خطای "Bot token invalid"
- توکن را از @BotFather دوباره دریافت کنید
- مطمئن شوید فاصله اضافی وجود ندارد

#### 5. خطای "OpenRouter API"
- کلید API را بررسی کنید
- اعتبار حساب OpenRouter را چک کنید

### لاگ‌های مفید:
```bash
# لاگ‌های ربات
tail -f bot.log

# لاگ‌های سیستم
sudo journalctl -u telegram-reminder-bot -f

# بررسی پردازه‌ها
ps aux | grep python
```

## 📞 پشتیبانی

اگر مشکلی داشتید:
1. ابتدا لاگ‌ها را بررسی کنید
2. مطمئن شوید تمام پیش‌نیازها نصب است
3. تست‌ها را اجرا کنید
4. در صورت نیاز، issue جدید ایجاد کنید

## 🎉 تبریک!

ربات شما آماده استفاده است! 🤖

برای شروع، ربات را در تلگرام پیدا کنید و دستور `/start` را ارسال کنید.
