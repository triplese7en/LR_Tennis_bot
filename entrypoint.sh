#!/bin/sh
# Generate config.json from Railway environment variables, then start the bot.
set -e

python - << PYEOF
import json, os, sys

token = os.getenv('TELEGRAM_BOT_TOKEN', '')
if not token:
    print('ERROR: TELEGRAM_BOT_TOKEN is not set', flush=True)
    sys.exit(1)

config = {
    'telegram_token':  token,
    'username':        os.getenv('BOOKING_USERNAME', ''),
    'password':        os.getenv('BOOKING_PASSWORD', ''),
    'headless':        os.getenv('HEADLESS_MODE',  'true').lower() == 'true',
    'max_retries':     int(os.getenv('MAX_RETRIES',     '3')),
    'retry_delay':     int(os.getenv('RETRY_DELAY',     '5')),
    'page_timeout':    int(os.getenv('PAGE_TIMEOUT',    '30')),
    'element_timeout': int(os.getenv('ELEMENT_TIMEOUT', '10')),
}

with open('/app/config/config.json', 'w') as f:
    json.dump(config, f, indent=2)

print('✅ config.json generated', flush=True)
PYEOF

exec python src/telegram_bot.py
