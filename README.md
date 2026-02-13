# 🎾 Tennis Court Booking Bot

An automated Telegram bot for booking tennis courts at Dubai Parks & Resorts using Selenium WebDriver.

## ✨ Features

- **🤖 Telegram Interface** - Easy-to-use commands and inline keyboards
- **🔄 Smart Retry Logic** - Automatically retries on transient failures
- **⏰ 24/7 Availability** - Cloud deployment for continuous operation
- **📸 Booking History** - Tracks all attempts with screenshots
- **⚙️ User Preferences** - Save preferred dates and times for quick booking
- **📊 Status Tracking** - Monitor booking success/failure in real-time

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Chrome/Chromium browser
- ChromeDriver (automatically managed)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/tennis-booking-bot.git
cd tennis-booking-bot
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up configuration**
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

4. **Configure the bot**

Edit `config/config.json`:
- Add your Telegram bot token
- (Optional) Add website login credentials
- Adjust retry settings and timeouts

### Creating Your Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the instructions
3. Copy the bot token provided
4. Paste it in your `.env` file or `config/config.json`

### Running the Bot

```bash
python src/telegram_bot.py
```

For production deployment:
```bash
nohup python src/telegram_bot.py > logs/bot.log 2>&1 &
```

## 📱 Usage

### Basic Commands

- `/start` - Initialize the bot and register
- `/book` - Start a new court booking
- `/status` - Check current booking status
- `/history` - View your booking history
- `/preferences` - Set default booking preferences
- `/help` - Show available commands

### Booking Process

1. Send `/book` to start
2. Select date from the calendar
3. Choose your preferred time slot
4. Pick a specific court or select "Any Available"
5. Confirm your booking
6. Receive confirmation with screenshot

### Setting Preferences

Save your commonly used settings for faster bookings:

1. Send `/preferences`
2. Set preferred time (e.g., "18:00")
3. Set preferred court (e.g., "Court 1")
4. Next time, use "⚡ Use Saved Preferences" for instant booking

## 🏗️ Project Structure

```
tennis_booking_bot/
├── src/
│   ├── telegram_bot.py      # Main bot logic
│   ├── booking_engine.py    # Selenium automation
│   └── database.py          # SQLite database handler
├── config/
│   └── config.json          # Configuration file
├── screenshots/             # Booking screenshots
├── logs/                    # Application logs
├── data/                    # SQLite database
├── requirements.txt         # Python dependencies
├── .env.example            # Environment template
└── README.md               # This file
```

## 🔧 Configuration

### config.json Parameters

```json
{
  "telegram_token": "YOUR_BOT_TOKEN",
  "headless": true,              // Run browser in headless mode
  "max_retries": 3,             // Number of retry attempts
  "retry_delay": 5,             // Seconds between retries
  "page_timeout": 30,           // Page load timeout
  "element_timeout": 10,        // Element wait timeout
  "auto_login": false,          // Enable automatic login
  "username": "",               // Website username (if auto_login)
  "password": ""                // Website password (if auto_login)
}
```

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t tennis-booking-bot .
```

### Run Container

```bash
docker run -d \
  --name tennis-bot \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/screenshots:/app/screenshots \
  -e TELEGRAM_BOT_TOKEN=your_token \
  tennis-booking-bot
```

### Docker Compose

```yaml
version: '3.8'
services:
  bot:
    build: .
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./screenshots:/app/screenshots
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    restart: unless-stopped
```

## ☁️ Cloud Deployment Options

### AWS EC2

1. Launch EC2 instance (t2.micro or larger)
2. Install dependencies
3. Run bot as systemd service

### Heroku

1. Create new Heroku app
2. Add buildpacks: `heroku/python` and Chrome
3. Deploy using Git

### Google Cloud Platform

1. Create Compute Engine instance
2. Install Chrome and dependencies
3. Run bot with supervisor

### DigitalOcean

1. Create Droplet (Ubuntu 22.04)
2. Install required packages
3. Use PM2 or systemd for process management

## 🛠️ Troubleshooting

### Bot Not Responding

- Check if bot is running: `ps aux | grep telegram_bot`
- Verify Telegram token is correct
- Check logs: `tail -f logs/bot.log`

### Booking Failures

- Ensure ChromeDriver matches Chrome version
- Increase timeouts in config.json
- Check website accessibility
- Review screenshots in `screenshots/` directory

### Database Errors

- Verify database file permissions
- Check disk space
- Reset database: `rm data/bookings.db` (will lose history)

## 📊 Database Schema

### Tables

**users**
- user_id (PRIMARY KEY)
- username
- first_seen
- last_active

**user_preferences**
- user_id (PRIMARY KEY)
- preferred_time
- preferred_court
- preferred_date
- auto_retry
- notifications

**booking_attempts**
- id (PRIMARY KEY)
- user_id
- booking_date
- booking_time
- court_number
- status
- message
- screenshot_path
- retry_count
- created_at
- updated_at

## 🔒 Security Best Practices

1. **Never commit credentials**
   - Use `.env` files
   - Add `.env` to `.gitignore`

2. **Secure your bot token**
   - Keep it private
   - Regenerate if compromised

3. **Database security**
   - Set proper file permissions
   - Regular backups

4. **HTTPS only**
   - Use Telegram's HTTPS webhook
   - Verify SSL certificates

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## ⚠️ Disclaimer

This bot is for educational purposes. Ensure you comply with the website's Terms of Service. Automated booking may violate some websites' policies.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/tennis-booking-bot/issues)
- **Telegram**: Contact bot admin
- **Email**: support@example.com

## 🗺️ Roadmap

- [ ] Multi-language support
- [ ] Recurring bookings
- [ ] Group bookings
- [ ] Payment integration
- [ ] Mobile app integration
- [ ] Advanced analytics dashboard

## 📈 Version History

### v1.0.0 (Current)
- Initial release
- Basic booking functionality
- Telegram integration
- Screenshot capture
- Retry logic

## 🙏 Acknowledgments

- python-telegram-bot library
- Selenium WebDriver
- Dubai Parks & Resorts (booking platform)

---

Made with ❤️ for tennis enthusiasts
