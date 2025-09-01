# Database Migration Guide

## 🎯 هدف
این پروژه حالا از Database Abstraction Layer پشتیبانی می‌کند که به شما امکان تغییر دیتابیس بدون تغییر کد را می‌دهد.

## 🔧 تنظیمات

### 1. SQLite (پیش‌فرض)
```json
{
  "database": {
    "url": "sqlite:///data/reminders.db"
  }
}
```

### 2. PostgreSQL
```json
{
  "database": {
    "url": "postgresql://username:password@localhost:5432/reminders"
  }
}
```

### 3. MySQL
```json
{
  "database": {
    "url": "mysql://username:password@localhost:3306/reminders"
  }
}
```

## 📦 Dependencies لازم

### برای PostgreSQL:
```bash
pip install sqlalchemy psycopg2-binary
```

### برای MySQL:
```bash
pip install sqlalchemy pymysql
```

## 🚀 نحوه استفاده

1. فایل `config/config.json` را باز کنید
2. `database.url` را تغییر دهید
3. بات را مجدداً راه‌اندازی کنید

**مثال:**
```json
{
  "database": {
    "path": "data/reminders.db",
    "url": "postgresql://myuser:mypass@localhost:5432/telegram_bot"
  }
}
```

## ⚠️ نکات مهم

- فعلاً فقط SQLite پشتیبانی می‌شود
- برای PostgreSQL/MySQL باید SQLAlchemy نصب کنید
- داده‌های موجود به صورت خودکار منتقل نمی‌شوند (migration manual لازم است)

## 🔄 Migration از SQLite به PostgreSQL

اگر می‌خواهید داده‌هایتان را از SQLite به PostgreSQL منتقل کنید:

1. PostgreSQL را راه‌اندازی کنید
2. یک database جدید بسازید
3. `config.json` را تغییر دهید
4. بات را اجرا کنید (جداول خودکار ساخته می‌شوند)
5. داده‌ها را به صورت دستی کپی کنید

## 🎉 مزایا

✅ **تغییر آسان دیتابیس** - فقط یک خط در config
✅ **بدون تغییر کد** - همه چیز مثل قبل کار می‌کند  
✅ **Backward Compatible** - کدهای قدیمی کار می‌کنند
✅ **آماده برای آینده** - راحت قابل گسترش به ORM
