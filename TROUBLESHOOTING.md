# 🔧 Troubleshooting Guide

Common issues and solutions for the Tennis Court Booking Bot.

## Table of Contents
- [Bot Not Starting](#bot-not-starting)
- [Booking Failures](#booking-failures)
- [Chrome/Selenium Issues](#chromeselenium-issues)
- [Telegram Connection Problems](#telegram-connection-problems)
- [Database Errors](#database-errors)
- [Performance Issues](#performance-issues)

---

## Bot Not Starting

### Error: "No module named 'telegram'"

**Solution:**
```bash
pip install -r requirements.txt
```

### Error: "telegram.error.InvalidToken"

**Cause:** Invalid or missing Telegram bot token

**Solution:**
1. Check `config/config.json` or `.env`
2. Verify token is correct (get from @BotFather)
3. Ensure no extra spaces or quotes

```json
{
  "telegram_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
}
```

### Error: "Permission denied"

**Solution:**
```bash
chmod +x setup.sh
chmod 755 src/*.py
```

---

## Booking Failures

### Error: "TimeoutException"

**Cause:** Page or element took too long to load

**Solutions:**
1. Increase timeouts in config:
```json
{
  "page_timeout": 60,
  "element_timeout": 20
}
```

2. Check internet connection
3. Verify website is accessible

### Error: "NoSuchElementException"

**Cause:** Website layout changed or element not found

**Solutions:**
1. Check screenshots in `screenshots/` folder
2. Website might have changed - selectors may need updating
3. Ensure JavaScript is enabled if needed

### Booking Always Fails

**Debug Steps:**
1. Run in non-headless mode:
```json
{
  "headless": false
}
```

2. Check logs:
```bash
tail -f logs/bot.log
```

3. Review screenshots:
```bash
ls -lt screenshots/ | head -10
```

4. Test website manually in browser

---

## Chrome/Selenium Issues

### Error: "chromedriver executable not found"

**Solution (Ubuntu/Debian):**
```bash
# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f

# ChromeDriver will be auto-managed by webdriver-manager
```

### Error: "Chrome version mismatch"

**Solution:**
```bash
# Update Chrome
sudo apt-get update
sudo apt-get upgrade google-chrome-stable

# Update ChromeDriver
pip install --upgrade webdriver-manager
```

### Error: "Message: session not created"

**Cause:** Chrome/ChromeDriver incompatibility

**Solution:**
```bash
# Check Chrome version
google-chrome --version

# Reinstall Selenium
pip uninstall selenium
pip install selenium==4.16.0
```

### Headless Mode Issues

**Try these Chrome options:**
```python
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--window-size=1920,1080')
```

---

## Telegram Connection Problems

### Bot Not Responding to Commands

**Checklist:**
1. Bot is running: `ps aux | grep telegram_bot`
2. Correct token in config
3. Bot not blocked by user
4. Check logs for errors

**Restart bot:**
```bash
pkill -f telegram_bot.py
python src/telegram_bot.py
```

### Error: "Conflict: terminated by other getUpdates"

**Cause:** Bot running in multiple places

**Solution:**
```bash
# Find all instances
ps aux | grep telegram_bot

# Kill all instances
pkill -f telegram_bot.py

# Start fresh
python src/telegram_bot.py
```

### Messages Not Sending

**Check:**
1. Internet connectivity
2. Telegram API status
3. Bot permissions
4. Rate limiting (too many messages)

---

## Database Errors

### Error: "database is locked"

**Cause:** Multiple processes accessing database

**Solution:**
```bash
# Stop all bot instances
pkill -f telegram_bot.py

# Check for locks
lsof data/bookings.db

# Restart single instance
python src/telegram_bot.py
```

### Corrupted Database

**Recovery:**
```bash
# Backup current database
cp data/bookings.db data/bookings.db.backup

# Try repair (SQLite)
sqlite3 data/bookings.db "PRAGMA integrity_check;"

# If corrupted, restore from backup or start fresh
mv data/bookings.db data/bookings.db.old
# Bot will create new database on restart
```

### Missing Tables

**Solution:**
```bash
# Delete database (will lose history)
rm data/bookings.db

# Restart bot (creates fresh database)
python src/telegram_bot.py
```

---

## Performance Issues

### Bot Running Slow

**Optimizations:**
1. Reduce retry attempts:
```json
{
  "max_retries": 2,
  "retry_delay": 3
}
```

2. Disable unnecessary screenshots:
```json
{
  "screenshot_on_success": true,
  "screenshot_on_failure": false
}
```

3. Clean old data:
```bash
python utils.py cleanup --days 30 --execute
```

### High Memory Usage

**Solutions:**
1. Run in headless mode
2. Limit concurrent operations
3. Restart bot periodically (cron job)

```bash
# Add to crontab for daily restart
0 4 * * * pkill -f telegram_bot.py && cd /path/to/bot && python src/telegram_bot.py &
```

### Screenshots Taking Too Much Space

**Cleanup:**
```bash
# Delete old screenshots
find screenshots/ -name "*.png" -mtime +30 -delete

# Or compress
find screenshots/ -name "*.png" -exec convert {} -quality 50 {} \;
```

---

## Docker Issues

### Container Won't Start

**Check logs:**
```bash
docker-compose logs
```

### Container Exits Immediately

**Debug:**
```bash
docker-compose run --rm tennis-bot bash
```

### Permission Issues in Docker

**Fix volumes:**
```bash
sudo chown -R $USER:$USER data/ screenshots/ logs/
```

---

## Debugging Tips

### Enable Debug Logging

Edit `config/config.json`:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

### Run Test Setup

```bash
python test_setup.py
```

### Check System Health

```bash
python utils.py health
```

### View Recent Bookings

```bash
python utils.py recent --limit 5
```

### Export for Analysis

```bash
python utils.py export --output debug_bookings.csv
```

---

## Still Having Issues?

1. **Check logs:**
   ```bash
   cat logs/bot.log
   ```

2. **Review screenshots:**
   ```bash
   ls -lt screenshots/ | head
   ```

3. **Test components:**
   ```bash
   # Test database
   python -c "from src.database import Database; db = Database(); print('OK')"
   
   # Test Selenium
   python -c "from selenium import webdriver; driver = webdriver.Chrome(); driver.quit(); print('OK')"
   ```

4. **Get help:**
   - Check GitHub Issues
   - Review README.md
   - Contact support

---

## Common Error Codes

| Error | Meaning | Solution |
|-------|---------|----------|
| `InvalidToken` | Wrong bot token | Check config |
| `TimeoutException` | Page load timeout | Increase timeout |
| `NoSuchElementException` | Element not found | Check selectors |
| `WebDriverException` | Chrome/driver issue | Update Chrome |
| `DatabaseError` | Database locked | Stop other instances |

---

## Prevention Tips

✅ **DO:**
- Keep Chrome/ChromeDriver updated
- Monitor logs regularly
- Backup database weekly
- Clean screenshots monthly
- Use Docker for production
- Set up monitoring/alerts

❌ **DON'T:**
- Run multiple bot instances
- Use same token for multiple bots
- Ignore error messages
- Skip backups
- Leave debug mode on in production

---

*Last updated: 2024*
