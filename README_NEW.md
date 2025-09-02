# Telegram Reminder Bot

A robust, multilingual Telegram bot for managing reminders with AI-powered natural language processing, designed for production use with thousands of users.

## Features

### Core Functionality
- **Multilingual Support**: English, Persian (Farsi), Arabic, and Russian
- **AI-Powered Parsing**: Natural language reminder creation using OpenRouter API
- **Smart Categories**: Automatic categorization (medicine, birthday, work, etc.)
- **Recurring Reminders**: Daily, weekly, monthly, and yearly repetitions
- **Birthday Reminders**: Automatic pre-reminders (1 week and 3 days before)
- **Interactive Interface**: Inline keyboards for easy management
- **Timezone Support**: Customizable timezone settings

### Production Ready
- **Optimized SQLite**: WAL mode, proper indexing, connection pooling
- **Rate Limiting**: Configurable request limits per user
- **Input Validation**: Comprehensive sanitization and validation
- **Error Handling**: Robust error handling throughout
- **Logging**: Structured logging with file and console output
- **Security**: File permissions, input sanitization, SQL injection protection
- **Memory Management**: Automatic cleanup of expired sessions
- **Comprehensive Testing**: Unit tests for all components

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd telegram-reminder-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your actual values
```

4. Run the bot:
```bash
python bot.py
```

Or use the provided script:
```bash
chmod +x run.sh
./run.sh
```

## Configuration

### Environment Variables

Required:
- `BOT_TOKEN`: Your Telegram bot token from @BotFather
- `OPENROUTER_KEY`: Your OpenRouter API key for AI processing

Optional:
- `MAX_REQUESTS_PER_MINUTE`: Rate limit per user (default: 20)
- `MAX_REMINDERS_PER_USER`: Maximum reminders per user (default: 100)
- `CLEANUP_INTERVAL_HOURS`: Cleanup interval (default: 24)
- `LOG_LEVEL`: Logging level (default: INFO)

### Database Optimizations

The bot uses SQLite with production-ready optimizations:
- WAL mode for better concurrent access
- Comprehensive indexing for fast queries
- Automatic cleanup of old reminders
- Connection pooling and timeout handling
- Secure file permissions

## Usage

### Basic Commands

- `/start` - Initialize the bot and select language
- `/lang <code>` - Change language (en, fa, ar, ru)
- `/tz <timezone>` - Set timezone (e.g., +03:30)
- `/list` - Show all active reminders
- `/delete <id>` - Delete a specific reminder
- `/menu` - Show interactive menu

### Creating Reminders

Simply send a natural language message:
- "هر روز ساعت 10 قرص" (Take pills daily at 10)
- "28 خرداد تولد مائده" (Maedeh's birthday on 28 Khordad)
- "Every Monday team meeting at 2 PM"
- "Remind me to call mom tomorrow at 6"

### Supported Categories

- 🎂 Birthday
- 💊 Medicine
- 💼 Work
- 📅 Appointment
- 🏃‍♂️ Exercise
- 🕌 Prayer
- 🛒 Shopping
- 📞 Call
- 📚 Study
- 💳 Installment
- 💰 Bill
- ⏰ General

## Architecture

### Core Components

- **bot.py**: Main bot logic with rate limiting and error handling
- **database.py**: Optimized SQLite operations with indexing
- **json_storage.py**: Thread-safe user preferences storage
- **ai_handler.py**: OpenRouter API integration with validation
- **reminder_scheduler.py**: Async background reminder processing
- **config.py**: Configuration management with validation
- **security_utils.py**: Security utilities and file permissions

### Security Features

- **Rate Limiting**: Prevents spam and abuse
- **Input Validation**: Comprehensive sanitization
- **SQL Injection Protection**: Parameterized queries
- **File Security**: Secure permissions and path validation
- **Error Handling**: Prevents information leakage
- **Logging**: Security event logging

### Performance Optimizations

- **Async Processing**: Non-blocking reminder processing
- **Connection Pooling**: Efficient database connections
- **Memory Management**: Automatic cleanup of expired data
- **Batch Processing**: Efficient handling of multiple reminders
- **Caching**: Locale caching for better performance

## Testing

Run the comprehensive test suite:

```bash
python run_tests.py
```

Test coverage includes:
- Database operations
- JSON storage functionality
- AI handler with mocked API calls
- Configuration validation
- Error handling scenarios

## Development

### Adding New Languages

1. Create a new JSON file in `localization/` directory
2. Copy the structure from `en.json`
3. Translate all keys to the target language
4. Add the language code to the language selection menu

### Extending Categories

1. Add new category to the AI prompt in `ai_handler.py`
2. Add emoji mapping in `bot.py`
3. Update localization files with category names
4. Add tests for the new category

### Code Quality

- **Type Hints**: Comprehensive type annotations
- **Error Handling**: Robust exception handling
- **Logging**: Structured logging throughout
- **Documentation**: Inline documentation
- **Testing**: Unit tests for all components

## Deployment

### Production Checklist

- [ ] Set secure environment variables
- [ ] Configure proper file permissions
- [ ] Set up log rotation
- [ ] Configure monitoring
- [ ] Set up backup for database
- [ ] Test rate limiting
- [ ] Verify error handling

### Monitoring

The bot provides comprehensive logging:
- User interactions
- Error conditions
- Performance metrics
- Security events

## Performance

Optimized for thousands of concurrent users:
- **Database**: SQLite with WAL mode and indexing
- **Scheduling**: Efficient reminder checking (30-60 second intervals)
- **Memory**: Automatic cleanup and garbage collection
- **Network**: Connection pooling and timeout handling
- **Rate Limiting**: Configurable per-user limits

## Security

- Environment variables for sensitive data
- Comprehensive input validation and sanitization
- SQL injection protection with parameterized queries
- Rate limiting to prevent abuse
- Secure file permissions (600 for files, 700 for directories)
- Path traversal protection
- Error message sanitization

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue on GitHub or contact the maintainers.

## Changelog

### v2.0.0 (Production Ready)
- Added comprehensive error handling
- Implemented rate limiting
- Added input validation and sanitization
- Enhanced security with file permissions
- Added comprehensive test suite
- Improved logging and monitoring
- Optimized database performance
- Added memory management
- Enhanced AI handler with validation
- Added security utilities

### v1.0.0
- Initial release with multilingual support
- AI-powered natural language processing
- SQLite database with optimizations
- Interactive menu system
- Recurring reminders support
