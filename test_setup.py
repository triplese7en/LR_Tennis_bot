#!/usr/bin/env python3
"""
Test script to verify bot setup and functionality
"""

import sys
import json
from pathlib import Path

print("🧪 Tennis Booking Bot - Setup Test")
print("=" * 50)
print()

# Test 1: Python version
print("Test 1: Python Version")
version = sys.version_info
if version.major == 3 and version.minor >= 8:
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
else:
    print(f"❌ Python version too old: {version.major}.{version.minor}")
    sys.exit(1)
print()

# Test 2: Required modules
print("Test 2: Required Modules")
modules = {
    'telegram': 'python-telegram-bot',
    'selenium': 'selenium',
}

missing = []
for module, package in modules.items():
    try:
        __import__(module)
        print(f"✅ {package}")
    except ImportError:
        print(f"❌ {package} - Not installed")
        missing.append(package)

if missing:
    print(f"\n❌ Missing packages. Install with:")
    print(f"   pip install {' '.join(missing)}")
    sys.exit(1)
print()

# Test 3: Directory structure
print("Test 3: Directory Structure")
required_dirs = ['logs', 'screenshots', 'data', 'config', 'src']
for dir_name in required_dirs:
    dir_path = Path(dir_name)
    if dir_path.exists():
        print(f"✅ {dir_name}/")
    else:
        print(f"❌ {dir_name}/ - Creating...")
        dir_path.mkdir(exist_ok=True)
print()

# Test 4: Configuration file
print("Test 4: Configuration")
config_path = Path('config/config.json')
if config_path.exists():
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        if config.get('telegram_token') == 'YOUR_TELEGRAM_BOT_TOKEN':
            print("⚠️  config.json exists but token not configured")
            print("   Please add your Telegram bot token")
        else:
            print("✅ config.json configured")
    except json.JSONDecodeError:
        print("❌ config.json is invalid JSON")
else:
    print("⚠️  config.json not found")
    print("   Copy config.json.example to config.json and configure it")
print()

# Test 5: Source files
print("Test 5: Source Files")
source_files = [
    'src/telegram_bot.py',
    'src/booking_engine.py',
    'src/database.py'
]

for file_path in source_files:
    if Path(file_path).exists():
        print(f"✅ {file_path}")
    else:
        print(f"❌ {file_path} - Missing!")
print()

# Test 6: Chrome/ChromeDriver
print("Test 6: Browser (Chrome)")
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    print("   Attempting to start Chrome...")
    driver = webdriver.Chrome(options=options)
    driver.quit()
    print("✅ Chrome and ChromeDriver working")
except Exception as e:
    print(f"❌ Chrome/ChromeDriver error: {e}")
    print("   Install Chrome and ensure ChromeDriver is accessible")
print()

# Test 7: Database
print("Test 7: Database")
try:
    sys.path.insert(0, 'src')
    from database import Database
    
    db = Database('data/test.db')
    print("✅ Database module working")
    
    # Cleanup test database
    Path('data/test.db').unlink(missing_ok=True)
except Exception as e:
    print(f"❌ Database error: {e}")
print()

# Summary
print("=" * 50)
print("📋 Test Summary")
print("=" * 50)
print()
print("If all tests passed ✅, you're ready to run the bot!")
print()
print("Next steps:")
print("1. Add your Telegram bot token to config/config.json")
print("2. Run: python src/telegram_bot.py")
print("3. Open Telegram and message your bot!")
print()
print("For help, check README.md or QUICKSTART.md")
print()
