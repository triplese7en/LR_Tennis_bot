# 🎾 Tennis Court Booking Bot

Automated tennis court booking system for Dubai Properties via Telegram.

## ✨ Features

- 🤖 **Fully Automated Booking** - Book courts with a few taps
- 👥 **Multi-User Support** - Each user has their own credentials
- 💾 **Smart Preferences** - Save favorite court and time
- 📊 **Booking History** - Track all your bookings
- ⏰ **Real-Time Updates** - See booking progress live
- 📸 **Screenshot Capture** - Get confirmation screenshots
- 🔄 **Auto-Retry Logic** - Handles failures automatically
- 🎯 **Smart Availability** - Shows available times/dates

## 🚀 Quick Start

### For Users

1. **Find the bot** on Telegram
2. Send `/start`
3. Use `/login` to add your Dubai Properties credentials
4. Use `/book` to start booking!

### Commands

```
/start       - Welcome message
/login       - Set up your credentials
/book        - Start booking process
/status      - Check recent booking
/history     - View booking history
/preferences - Save favorite court/time
/logout      - Remove your credentials
/help        - Show all commands
```

## 📱 How to Use

### First Time Setup

1. **Start the bot:**
   ```
   /start
   ```

2. **Add your credentials:**
   ```
   /login
   ```
   - Enter your Dubai Properties email
   - Enter your Dubai Properties password
   - Credentials stored securely per user

3. **You're ready!**
   ```
   /book
   ```

### Making a Booking

1. **Start booking:**
   ```
   /book
   ```

2. **Select date:**
   - Choose from next 7 days for standard booking
   - Available immediately

3. **Select time:**
   - Choose your preferred time slot
   - See available times in real-time

4. **Select court:**
   - Amaranta B
   - Amaranta 3
   - La Rosa 4
   - Paddle Court 1
   - Paddle Court 2

5. **Confirm:**
   - Review your booking
   - Click "✅ Confirm"
   - Watch real-time progress!

6. **Done!**
   - Screenshot sent to Telegram
   - Email confirmation from Dubai Properties

## ⚙️ Advanced Features

### Saved Preferences

Speed up booking by saving your favorites:

```
/preferences
→ Set preferred time
→ Set preferred court
```

Then when booking, click "⚡ Use Saved Preferences"!

### Booking History

View your past bookings:

```
/history
```

Shows:
- Date & time
- Court
- Status (success/failed)
- Screenshots

## 🔐 Security & Privacy

- ✅ **Per-User Credentials** - Each user has own login
- ✅ **Secure Storage** - Credentials stored in database
- ✅ **No Sharing** - Your data never mixed with others
- ✅ **Easy Logout** - Remove credentials anytime with `/logout`

## 📊 Booking Status

During booking, you'll see real-time updates:

```
🔄 Attempt 1/3...
🔐 Logging in...
✅ Logged in
📍 Navigating to booking...
🎾 Selecting La Rosa 4...
📅 Selecting 2026-02-16...
⏰ Selecting 20:00...
✅ Confirming booking...
🎉 Booking Successful!
```

## 🆘 Troubleshooting

### "No credentials found"
```
→ Use /login to add your credentials
```

### "Time not available"
```
→ Bot shows available times
→ Try different time or date
```

### "Date not available"
```
→ Bot shows available dates
→ Try different date
```

### "Booking failed"
```
→ Bot automatically retries (3 attempts)
→ Check screenshot for details
→ Try again later
```

## 💡 Tips

1. **Set Preferences** - Saves time on every booking
2. **Book Early** - Popular times fill up fast
3. **Check Availability** - Bot shows what's available
4. **Use Screenshots** - Keep for your records
5. **Email Confirmation** - Always sent by Dubai Properties

## 🔄 Updates

The bot is continuously improved with:
- Bug fixes
- New features
- Performance improvements

No action needed - updates deploy automatically!

## 📞 Support

If you have issues:

1. Try `/help` for command reference
2. Check `/status` for booking status
3. Use `/logout` and `/login` to reset credentials
4. Restart with `/start`

## ⚡ Performance

- **Booking Speed**: 30-60 seconds average
- **Success Rate**: High for available slots
- **Availability Check**: Real-time
- **Retry Logic**: 3 automatic attempts

## 🎯 Best Practices

### For Best Results:

1. **Login Once** - Credentials saved permanently
2. **Set Preferences** - One-time setup
3. **Book in Advance** - Don't wait until last minute
4. **Flexible Times** - Have backup times ready
5. **Check History** - Track your bookings

### Booking Strategy:

- 🌅 Early morning slots (8-10 AM) - Less competition
- 🌆 Evening slots (6-8 PM) - Popular, book early
- 📅 Weekday bookings - More availability
- 🎯 Book early - Best selection

## 📈 Statistics

Your personal stats available via:
```
/history
```

Shows:
- Total bookings
- Success rate
- Recent bookings

## 🔒 Data Privacy

- Credentials stored locally in bot database
- Never shared with third parties
- Can be deleted anytime with `/logout`
- Booking history kept for your reference only

## 📄 License

This bot is for personal use with Dubai Properties tennis court booking system.

---

**Version:** 2.0  
**Last Updated:** February 2026  
**Status:** ✅ Fully Operational

Enjoy your tennis! 🎾
