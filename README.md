# 🎾 Dubai Properties Tennis Court Booking Bot

Automated Telegram bot for booking tennis courts at Dubai Properties communities (Villanova, La Rosa, Amaranta). Features intelligent scheduling, per-user credentials, and automatic midnight bookings for dates beyond the 7-day window.

## ✨ Features

### 🤖 Automated Booking
- One-tap booking through Telegram
- Handles login, court selection, date/time picking, and confirmation automatically
- Real-time status updates during booking process
- Screenshot capture on success/failure

### ⏰ Scheduled Bookings (8+ days ahead)
- **No time travel tricks** — uses proper scheduling
- Schedule bookings for dates 8-21 days in the future
- Bot automatically fires at **00:01 Dubai time** when the 7-day window opens
- APScheduler ensures millisecond-precision firing
- Collision detection prevents double-bookings
- Retry logic with attempt tracking (up to 3 attempts per booking)

### 👥 Multi-User Support
- Each user stores their own Dubai Properties credentials securely
- Per-user booking history and preferences
- Private data isolation

### 📊 Smart Features
- Save favorite times/courts for one-tap rebooking
- View booking history and statistics
- Manage pending scheduled bookings (`/scheduled`)
- Graceful shutdown (waits for running bookings to complete)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Chrome/ChromeDriver (auto-installed in Docker)
- Telegram Bot Token ([get one from @BotFather](https://t.me/botfather))
- Dubai Properties account credentials

### Local Development

1. **Clone and install:**
```bash
git clone <your-repo>
cd tennis_booking_bot
pip install -r requirements.txt
```

2. **Configure:**
```bash
mkdir -p config
cat > config/config.json << 'JSON'
{
  "telegram_token": "YOUR_BOT_TOKEN",
  "username": "",
  "password": "",
  "headless": false,
  "max_retries": 3,
  "retry_delay": 5,
  "page_timeout": 30,
  "element_timeout": 10
}
JSON
```

3. **Run:**
```bash
python src/telegram_bot.py
```

### Docker Deployment

```bash
docker build -t tennis-bot .
docker run -d \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e HEADLESS_MODE="true" \
  tennis-bot
```

### Railway Deployment (Recommended)

1. **Connect your GitHub repo** to Railway
2. **Set environment variables:**
   - `TELEGRAM_BOT_TOKEN` — Your bot token
   - `HEADLESS_MODE` — `true`
   - `MAX_RETRIES` — `3` (optional)

3. **Deploy** — Railway auto-builds from Dockerfile

---

## 📱 Bot Commands

### Setup
- `/start` — Welcome message and setup instructions
- `/login` — Add your Dubai Properties credentials (email + password)
- `/logout` — Remove stored credentials
- `/help` — Show all available commands

### Booking
- `/book` — Start a new booking
  - **Standard (0-7 days):** Books immediately
  - **Scheduled (8+ days):** Fires automatically at midnight when window opens
- `/scheduled` — View and manage pending scheduled bookings
- `/status` — Check latest booking status
- `/history` — View past bookings

### Preferences
- `/preferences` — Set favorite time/court for quick rebooking

---

## 🎯 How Scheduled Bookings Work

### The 7-Day Window Rule
Dubai Properties only allows booking courts **up to 7 days ahead** (today + 6 days). For example:
- **Feb 19:** Can book Feb 19-25
- **Feb 20:** Can book Feb 20-26

### Scheduling Beyond 7 Days

When you schedule a booking for a date 8+ days ahead:

1. **You pick:** Feb 26 at 20:00, La Rosa 4
2. **Bot calculates:** Feb 26 - 6 days = **Feb 20 at 00:01**
3. **Bot schedules** the job in APScheduler (Dubai timezone)
4. **Feb 20 00:01:** Bot wakes up, calendar now shows Feb 20-26
5. **Bot books** normally (no tricks needed — date is available)
6. **You get notified** via Telegram with success/failure message

### Why 00:01 and Not Midnight?
- Ensures the calendar has fully loaded the new day
- Avoids race conditions with other users
- APScheduler precision guarantees exact firing time

### Collision Detection
If the same user/court/time is already being booked (e.g., scheduler restart), only one proceeds. The duplicate is skipped with a warning.

### Retry Logic
Each scheduled booking attempts up to **3 times** with 5-second delays. Attempt count is tracked and shown in `/scheduled`.

---

## 🏗️ Architecture

```
telegram_bot.py      ← User interface (Telegram commands & buttons)
    │
    ├── scheduler.py      ← APScheduler background service
    │       │
    │       └── booking_engine.py  ← Chrome automation (Selenium)
    │
    └── database.py       ← SQLite storage (users, credentials, bookings, scheduled jobs)
```

### Key Technologies
- **python-telegram-bot** — Telegram Bot API wrapper
- **Selenium + ChromeDriver** — Browser automation
- **APScheduler** — Event-driven job scheduling (Dubai timezone)
- **SQLite** — Lightweight database
- **Docker** — Containerized deployment

---

## 🗄️ Database Schema

### `users`
- `user_id` (PK) — Telegram user ID
- `username` — Telegram username
- `first_seen`, `last_active` — Timestamps

### `user_credentials`
- `user_id` (PK) — Foreign key
- `email`, `password` — Dubai Properties login (encrypted in production)

### `booking_attempts`
- Tracks all immediate booking attempts
- Status: `pending`, `success`, `failed`, `error`
- Includes screenshots and retry counts

### `scheduled_bookings` ⭐
- `id` (PK)
- `user_id`, `booking_date`, `booking_time`, `court`
- `fire_at` — ISO datetime when to execute (Dubai timezone)
- `status` — `pending`, `executing`, `success`, `failed`, `cancelled`
- `attempt_count` — How many times this booking has been attempted
- `executed_at`, `message` — Result tracking

### `user_preferences`
- Saved favorite time/court for quick rebooking

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | *required* | Your Telegram bot token |
| `BOOKING_USERNAME` | `""` | Default Dubai Properties email (optional) |
| `BOOKING_PASSWORD` | `""` | Default Dubai Properties password (optional) |
| `HEADLESS_MODE` | `true` | Run Chrome in headless mode |
| `MAX_RETRIES` | `3` | Booking retry attempts |
| `RETRY_DELAY` | `5` | Seconds between retries |
| `PAGE_TIMEOUT` | `30` | Page load timeout (seconds) |
| `ELEMENT_TIMEOUT` | `10` | Element wait timeout (seconds) |

### Timezone
Set to **Asia/Dubai (UTC+4)** in Dockerfile. Scheduler fires at Dubai local time.

---

## 🔒 Security Notes

### Credential Storage
- Stored in SQLite (plaintext in development)
- **Production:** Encrypt passwords before storing (use `cryptography` library)
- Each user's credentials are isolated

### Recommendations
1. Use environment variables for default credentials (not hardcoded)
2. Enable Railway's private networking
3. Encrypt the SQLite database in production
4. Use HTTPS webhooks if deploying with webhooks (not polling)

---

## 🐛 Troubleshooting

### Bot doesn't respond
- Check Railway logs for errors
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure bot is not blocked by user

### Booking fails
- Verify credentials with `/login`
- Check if court is actually available manually
- Review screenshot in booking history
- Check Railway logs for Selenium errors

### Scheduled booking doesn't fire
- Check `/scheduled` to see pending jobs
- Verify Railway container hasn't restarted (jobs reload on restart)
- Check Railway logs at the scheduled fire time
- Ensure timezone is correct (Dubai = UTC+4)

### "ChromeDriver not found"
- In Docker: Auto-installed in Dockerfile
- Locally: `pip install webdriver-manager` handles this

---

## 📈 Roadmap

- [ ] Encrypted credential storage (production-ready)
- [ ] Webhook mode (instead of polling)
- [ ] Multiple court preferences per user
- [ ] Notification 1 hour before booking
- [ ] Analytics dashboard
- [ ] Support for other Dubai Properties amenities (pools, gyms)

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

MIT License - feel free to use this for your community!

---

## 🙏 Credits

Built for Dubai Properties residents who are tired of missing out on court bookings. Special thanks to the Villanova tennis community for testing.

---

## 📞 Support

- **Issues:** Open a GitHub issue
- **Questions:** Create a discussion
- **Telegram:** Contact @YourUsername (if you want to add your contact)

---

**Happy booking! 🎾**
