# 🚀 Quick Start Guide

Get your Tennis Booking Bot running in 5 minutes!

## Step 1: Get a Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow the prompts to create your bot
4. Copy the bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

## Step 2: Install Dependencies

### On Ubuntu/Debian:
```bash
# Run the setup script
./setup.sh
```

### Manual Installation:
```bash
# Install Python packages
pip install -r requirements.txt

# Install Chrome (Ubuntu/Debian)
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable
```

## Step 3: Configure the Bot

Edit `config/config.json`:
```json
{
  "telegram_token": "YOUR_BOT_TOKEN_HERE",
  "headless": true,
  "max_retries": 3
}
```

Or use `.env`:
```bash
cp .env.example .env
nano .env
# Add your TELEGRAM_BOT_TOKEN
```

## Step 4: Run the Bot

```bash
# Development (see output)
python src/telegram_bot.py

# Production (background)
nohup python src/telegram_bot.py > logs/bot.log 2>&1 &
```

## Step 5: Test Your Bot

1. Open Telegram
2. Search for your bot by username
3. Send `/start`
4. Try `/book` to make your first booking!

## 🐳 Docker Quick Start (Recommended)

```bash
# 1. Edit .env with your token
cp .env.example .env
nano .env

# 2. Start with Docker Compose
docker-compose up -d

# 3. Check logs
docker-compose logs -f
```

## Common Commands

```bash
# Start the bot
python src/telegram_bot.py

# View logs
tail -f logs/bot.log

# Stop the bot
pkill -f telegram_bot.py

# Restart with Docker
docker-compose restart
```

## Troubleshooting

### "Bot not responding"
- Check if bot is running: `ps aux | grep telegram_bot`
- Verify token in config.json
- Check logs: `cat logs/bot.log`

### "ChromeDriver error"
- Install Chrome: `google-chrome --version`
- Update ChromeDriver: `pip install --upgrade webdriver-manager`

### "Permission denied"
- Make script executable: `chmod +x setup.sh`
- Check file permissions: `ls -la`

## 📱 Using the Bot

### Make a Booking
1. `/book` - Start booking process
2. Select date from calendar
3. Choose time slot
4. Pick court number
5. Confirm booking

### Quick Booking with Preferences
1. `/preferences` - Set defaults
2. Next time: `/book` → "Use Saved Preferences"

### View History
- `/history` - See all your bookings
- `/status` - Check latest booking

## 🎯 Pro Tips

1. **Set Preferences** - Save time on repeat bookings
2. **Check Screenshots** - Every booking attempt is captured
3. **Enable Notifications** - Get instant updates
4. **Use Docker** - Easier deployment and updates

## Need Help?

- Check `README.md` for detailed documentation
- Review logs in `logs/bot.log`
- Check screenshots in `screenshots/` folder
- Open an issue on GitHub

---

Happy Booking! 🎾
