# 🔧 Troubleshooting Guide

Complete solutions for common issues with the Tennis Court Booking Bot.

---

## 📋 Quick Diagnosis

### Problem Categories

1. **Login Issues** - Can't add credentials
2. **Booking Failures** - Booking doesn't complete
3. **Availability Issues** - No times/dates shown
4. **Bot Not Responding** - Commands don't work
5. **Screenshot Issues** - No confirmation image
6. **Performance Issues** - Bot is slow

---

## 🔐 Login Issues

### Issue 1: "No credentials found"

**Symptoms:**
```
User sends /book
Bot says: "⚠️ No Login Credentials Found"
```

**Solution:**
```
1. Send: /login
2. Enter your Dubai Properties email
3. Enter your Dubai Properties password
4. Wait for confirmation
5. Try /book again
```

**Prevention:**
- Always use `/login` before first booking
- Credentials are saved permanently

---

### Issue 2: Login fails during booking

**Symptoms:**
```
Bot shows: "🔐 Logging in..."
Then: "❌ Login error"
```

**Possible Causes:**
1. Wrong email or password
2. Dubai Properties account locked
3. Website is down

**Solutions:**

**A) Reset Credentials:**
```
1. /logout
2. /login
3. Double-check email/password
4. Try again
```

**B) Check Dubai Properties Account:**
```
1. Visit https://eservices.dp.ae
2. Try logging in manually
3. Reset password if needed
4. Then update bot credentials
```

**C) Wait and Retry:**
```
Website might be temporarily down
Wait 10-15 minutes
Try /book again
```

---

### Issue 3: "Credentials already saved"

**Symptoms:**
```
User sends /login
Bot says: "You already have credentials"
```

**Solution (To Update):**
```
1. Send: /logout
2. Wait for confirmation
3. Send: /login
4. Enter new credentials
```

**Note:** This is expected behavior to prevent accidental overwrites

---

## 📅 Booking Failures

### Issue 4: "Booking failed after 3 attempts"

**Symptoms:**
```
Bot tries 3 times, all fail
Error message or screenshot shown
```

**Common Causes & Solutions:**

**A) Date/Time Not Available:**
```
Solution: Choose different time or date
Bot should show available options
```

**B) Court Not Available:**
```
Solution: Select different court
All 5 courts might be booked
```

**C) Website Issue:**
```
Solution: Wait 10-15 minutes
Try again
Check Dubai Properties status
```

**D) Login Problem:**
```
Solution: /logout then /login
Re-enter credentials
```

---

### Issue 5: "Time not available" error

**Symptoms:**
```
Bot shows: "❌ Time 20:00 is not available"
Bot lists available times
```

**This is NORMAL behavior!**

**Solution:**
```
1. Look at available times shown
2. Choose one of those
3. Try booking again
```

**Why This Happens:**
- Someone else booked that time
- Time already taken
- Not a bug - real availability check

**Prevention:**
- Book earlier in the day
- Have backup times ready
- Use less popular times

---

### Issue 6: "Date not available" error

**Symptoms:**
```
Bot shows: "❌ Date 2026-02-20 is not available"
Bot lists available dates
```

**Solution:**
```
1. Choose from available dates shown
2. Try different date
```

**Common Reasons:**
- Date fully booked (all times taken)
- Too far in advance (>7 days standard)
- Holiday/maintenance closure

---

## 🤖 Bot Not Responding

### Issue 7: Bot doesn't reply to commands

**Symptoms:**
```
User sends /start, /book, etc.
No response from bot
```

**Solutions:**

**A) Restart Conversation:**
```
1. Send: /start
2. Wait 5-10 seconds
3. Try command again
```

**B) Check Bot Status:**
```
1. Is bot online? (Green dot)
2. Send simple message: "hello"
3. If no response, wait 5 minutes
```

**C) Check Telegram:**
```
1. Close and reopen Telegram
2. Check internet connection
3. Try on different device
```

---

### Issue 8: Bot stops mid-booking

**Symptoms:**
```
Bot shows: "🔐 Logging in..."
Then stops, no more updates
```

**Solution:**
```
1. Wait 2-3 minutes (might be slow)
2. If still stuck, send /cancel
3. Try /book again
4. If persists, contact admin
```

**Prevention:**
- Don't spam commands
- Wait for each step to complete
- Good internet connection

---

## 📊 Availability Issues

### Issue 9: No available times shown

**Symptoms:**
```
Select date
No time options appear
Or very few times
```

**Reasons:**
```
1. Date is heavily booked
2. Only morning/evening slots left
3. All courts taken for that time
```

**Solutions:**
```
1. Try different date
2. Try earlier date
3. Try weekday instead of weekend
4. Book earlier in the day
```

---

### Issue 10: No dates shown / Only today available

**Symptoms:**
```
Only 1-2 dates appear
Expected 7 days
```

**Possible Causes:**
1. System restricting bookings
2. Most dates fully booked
3. Display issue

**Solution:**
```
1. Try /cancel then /book
2. Restart with /start
3. Try tomorrow (new dates open)
```

---

## 📸 Screenshot Issues

### Issue 11: No screenshot received

**Symptoms:**
```
Booking completes
No image sent
```

**This might be normal:**
- Screenshot sent with email confirmation
- Check your Telegram for image
- Look in bot chat history

**If truly missing:**
```
1. Check /history for booking
2. Email confirmation still sent
3. Screenshot optional, email is primary
```

---

### Issue 12: Screenshot shows error page

**Symptoms:**
```
Image received but shows error
```

**Action:**
```
1. Read error message in image
2. Usually indicates booking failed
3. Try booking again
4. Use different time/date
```

---

## ⚡ Performance Issues

### Issue 13: Booking takes too long

**Symptoms:**
```
Booking runs over 2 minutes
Still processing...
```

**Normal Duration:**
- 30-60 seconds average
- Up to 90 seconds acceptable
- Over 2 minutes = issue

**If Too Slow:**
```
1. Wait it out (might complete)
2. If over 3 minutes, send /cancel
3. Try again
4. Check your internet speed
```

---

### Issue 14: Bot is laggy / slow to respond

**Symptoms:**
```
Commands take 10-20 seconds to respond
Buttons don't work immediately
```

**Solutions:**
```
1. Close and reopen Telegram
2. Check internet connection
3. Try on WiFi vs mobile data
4. Wait for off-peak hours
```

---

## 🔄 Command Issues

### Issue 15: /preferences not saving

**Symptoms:**
```
Set preferences
Next time they're gone
```

**Solution:**
```
1. Set preferences one at a time
2. Wait for confirmation after each
3. Don't exit Telegram immediately
4. Test with /preferences to view
```

---

### Issue 16: /history shows no bookings

**Symptoms:**
```
Made bookings but history empty
```

**Possible Reasons:**
1. Bookings failed (not completed)
2. Different account
3. After /logout (data cleared)

**Check:**
```
1. Look for email confirmations
2. Check Dubai Properties website
3. Email = real booking
4. No email = booking failed
```

---

## 🆘 Emergency Procedures

### Can't access bot at all

```
1. Check bot username (correct bot?)
2. Search in Telegram
3. Ask bot owner for link
4. Try t.me/YourBotUsername
```

---

### Urgent booking needed

```
If bot is down:
1. Go to https://eservices.dp.ae
2. Book manually
3. Report bot issue to admin
```

---

### Booked wrong time/date

```
Bot cannot cancel bookings
To cancel:
1. Go to Dubai Properties website
2. Login with your credentials
3. Find booking in "My Bookings"
4. Cancel from there
```

---

## 💡 Prevention Tips

### Avoid Issues Before They Happen

**1. Set up correctly first time:**
```
✅ Use /login with correct credentials
✅ Test with one booking
✅ Set preferences
✅ Save bot to favorites
```

**2. Best booking practices:**
```
✅ Book during off-peak hours
✅ Have backup times ready
✅ Book in advance (not last minute)
✅ Check /status after booking
```

**3. Maintenance:**
```
✅ Update credentials if password changes
✅ Check /history regularly
✅ Use /logout if switching accounts
✅ Keep Telegram updated
```

---

## 📞 When to Contact Support

Contact bot admin if:

1. **Bot completely unresponsive** (>10 minutes)
2. **All bookings fail** (tried 5+ times)
3. **Login works but booking always fails**
4. **Error messages you don't understand**
5. **Bot charges you but no booking**

**Before contacting:**
- Try troubleshooting steps above
- Note exact error messages
- Take screenshots
- Record what time it happened

---

## 🔍 Advanced Diagnostics

### How to report issues effectively

Include these details:

```
1. Command used: /book
2. What happened: Bot stopped at "Logging in"
3. Error message: [exact text or screenshot]
4. When: Date and time
5. Steps tried: Restarted, tried again, etc.
6. Telegram version: [if relevant]
```

---

## ✅ Issue Resolution Checklist

For any issue, try in order:

- [ ] Send /start to restart
- [ ] Check internet connection
- [ ] Try command again
- [ ] Check /help for correct usage
- [ ] Read error message carefully
- [ ] Try /logout and /login if credential issue
- [ ] Wait 10 minutes and retry
- [ ] Check this troubleshooting guide
- [ ] Contact support if persists

---

## 🎯 Common Error Messages Explained

### "No credentials found"
```
Meaning: Haven't done /login yet
Fix: /login and enter credentials
```

### "Time not available"
```
Meaning: That time is booked by someone else
Fix: Choose different time from list
```

### "Booking failed after 3 attempts"
```
Meaning: Something wrong with booking process
Fix: Check error details, try again later
```

### "Login error"
```
Meaning: Can't log into Dubai Properties account
Fix: Check credentials, reset if needed
```

### "ChromeDriver error"
```
Meaning: Technical issue (admin should fix)
Fix: Report to admin, try again in 30 min
```

---

## 📊 Success Rate Expectations

### Normal Performance:

```
✅ Login Success: 95%+
✅ Availability Check: 100%
✅ Booking (when available): 90%+
✅ Overall Success: 85%+
```

### If your success rate is lower:
- Check your internet
- Verify credentials
- Try less popular times
- Book earlier in day

---

## 🔄 System Status

### Is the bot working?

**Check these indicators:**

```
✅ Bot responds to /start
✅ /login accepts credentials
✅ /book shows date options
✅ Real-time updates appear
✅ Screenshots sent
✅ Email confirmations received
```

**If ANY of these fail consistently:**
- System might be down
- Wait 30 minutes
- Report to admin

---

## 📚 Additional Resources

- **README.md** - Full feature documentation
- **QUICKSTART.md** - Setup guide
- `/help` - In-bot command reference
- Dubai Properties: https://eservices.dp.ae

---

**Still having issues?**

Try the bot's `/help` command or contact the bot administrator with specific details about your problem.

**Remember:** Most issues resolve with a simple restart (/start) or credential reset (/logout → /login)!

🎾 Happy booking!
