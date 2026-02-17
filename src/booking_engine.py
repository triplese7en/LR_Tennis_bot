"""
Booking Engine using Selenium WebDriver
Handles all browser automation for tennis court booking
UPDATED with all discovered selectors and smart availability checking
"""

import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class BookingEngine:
    """Selenium-based booking automation engine with smart availability checking"""
    
    # Court name mapping (user-friendly name → actual website text)
    COURT_MAP = {
        "Amaranta B": "Tennis Court Amaranta B",
        "Amaranta 3": "Tennis Court  Amaranta 3",  # Note: two spaces!
        "La Rosa 4": "Tennis Court - La Rosa 4",
        "Paddle Court 1": "Paddle Tennis Court 1 - Villanova (La Violeta 2)",
        "Paddle Court 2": "Paddle Tennis Court 2 - Villanova (La Violeta 2)"
    }
    
    def __init__(self, config: Dict, telegram_callback=None, user_credentials: Dict = None):
        self.config = config
        self.user_credentials = user_credentials  # Per-user credentials
        self.base_url = "https://eservices.dp.ae/amenity-booking"
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        
        # Callback for sending Telegram messages
        self.telegram_callback = telegram_callback
        
        # Retry configuration
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 5)
        
        # Timeout configuration
        self.page_timeout = config.get('page_timeout', 30)
        self.element_timeout = config.get('element_timeout', 10)
    
    def _send_telegram_update(self, message: str):
        """Send update to user via Telegram if callback is provided"""
        if self.telegram_callback:
            try:
                asyncio.create_task(self.telegram_callback(message))
            except:
                logger.debug(f"Could not send Telegram update: {message}")
    
    def _create_driver(self, time_travel_date: str = None) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver.

        time_travel_date: YYYY-MM-DD. When set, Chrome is launched with libfaketime
        via LD_PRELOAD so the *entire process* (not just JS) sees the fake date.
        This is equivalent to changing the system date on your phone — the most
        reliable way to trick a client-side date check.
        """
        chrome_options = Options()

        if self.config.get('headless', True):
            chrome_options.add_argument('--headless=new')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 2
        })
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # ── libfaketime: spoof system clock for entire Chrome process ──────────
        # Sets os.environ directly before spawning Chrome so the child process
        # inherits LD_PRELOAD. This is equivalent to changing your phone's date.
        faketime_applied = False
        original_env     = {}

        if time_travel_date:
            import os, glob

            # Find libfaketime .so
            faketime_lib = None
            try:
                with open('/faketime_lib_path.txt') as f:
                    p = f.read().strip()
                    if p and os.path.exists(p):
                        faketime_lib = p
            except Exception:
                pass

            if not faketime_lib:
                for pattern in [
                    '/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so*',
                    '/usr/lib/faketime/libfaketime.so*',
                    '/usr/lib/libfaketime*.so*',
                    '/usr/local/lib/libfaketime*.so*',
                ]:
                    hits = glob.glob(pattern)
                    if hits:
                        faketime_lib = hits[0]
                        break

            if faketime_lib:
                fake_time_str = f"@{time_travel_date} 08:00:00"
                # Save originals so we can restore after driver is created
                for key in ('LD_PRELOAD', 'FAKETIME', 'FAKETIME_NO_CACHE'):
                    original_env[key] = os.environ.get(key)
                os.environ['LD_PRELOAD']         = faketime_lib
                os.environ['FAKETIME']           = fake_time_str
                os.environ['FAKETIME_NO_CACHE']  = '1'
                faketime_applied = True
                logger.info(f"🎯 libfaketime active: FAKETIME={fake_time_str}  LIB={faketime_lib}")
            else:
                logger.warning("⚠️  libfaketime .so not found — JS override only")

        # ── Create driver ─────────────────────────────────────────────────────
        try:
            service = Service('/usr/local/bin/chromedriver')
            driver  = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("Using system ChromeDriver")
        except Exception:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options
                )
                logger.info("Using webdriver-manager ChromeDriver")
            except Exception as e:
                logger.error(f"ChromeDriver init failed: {e}")
                raise
        finally:
            # Restore env immediately — Chrome is already spawned, it has its copy
            if faketime_applied:
                import os
                for key, val in original_env.items():
                    if val is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = val
                logger.info("🔁 os.environ restored after Chrome spawn")

        driver.set_page_load_timeout(self.page_timeout)

        # Hide webdriver flag
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        # Also inject JS Date override as belt-and-suspenders
        # (works on Mac/visible Chrome; libfaketime covers headless Linux)
        if time_travel_date:
            import os as _os
            from datetime import datetime as _dt
            ts_ms = int(_dt.strptime(time_travel_date, "%Y-%m-%d").timestamp() * 1000)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': f"""
(function() {{
    const _D = window.Date, _t = {ts_ms};
    function FD(...a) {{
        if (!(this instanceof FD)) return new FD(...a);
        return a.length ? new _D(...a) : new _D(_t);
    }}
    FD.now = () => _t;  FD.parse = _D.parse.bind(_D);
    FD.UTC  = _D.UTC.bind(_D);  FD.prototype = _D.prototype;
    Object.defineProperty(window, 'Date', {{value: FD, writable: true, configurable: true}});
    console.log('[TimeTravel] date override active:', new FD().toISOString());
}})();
"""})
            logger.info(f"🎯 JS Date override also injected for {time_travel_date}")

        return driver
    
    async def book_court(
        self,
        date: str,
        time: str,
        court: Optional[str] = None,
        user_id: int = None,
        booking_id: int = None,
        enable_time_travel: bool = False  # kept for API compatibility, no longer used
    ) -> Dict:
        """
        Execute the booking process with retry logic and availability checking.

        Advanced dates (>7 days) are handled directly by _select_date via
        calendar navigation + DOM unlock - no JS Date override needed.
        """
        driver = None
        result = {
            'success': False,
            'message': '',
            'screenshot': None,
            'reference': None,
            'available_times': [],
            'available_dates': []
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Booking attempt {attempt}/{self.max_retries}")
                self._send_telegram_update(f"🔄 Attempt {attempt}/{self.max_retries}...")

                # Calculate time travel shift BEFORE creating driver
                time_travel_date = None
                target_dt  = datetime.strptime(date, "%Y-%m-%d")
                today_dt   = datetime.now()
                days_ahead = (target_dt.date() - today_dt.date()).days

                if days_ahead > 7:
                    # Shift browser clock so target date falls within the 7-day window.
                    # Shift = days_ahead - 6  (not -7) so target lands ON the last
                    # enabled day rather than one past it.
                    time_shift    = days_ahead - 6
                    fake_today    = today_dt.date() + __import__('datetime').timedelta(days=time_shift)
                    time_travel_date = fake_today.strftime("%Y-%m-%d")
                    logger.info(
                        f"🎯 Advanced booking: {days_ahead}d ahead → "
                        f"shifting browser +{time_shift}d to {time_travel_date}"
                    )
                    self._send_telegram_update(f"🎯 Advanced booking: +{time_shift} days")

                driver = self._create_driver(time_travel_date=time_travel_date)
                wait   = WebDriverWait(driver, self.element_timeout)
                
                # Execute booking flow
                await self._handle_initial_page_load(driver, wait)
                await self._handle_login(driver, wait)
                await self._navigate_to_booking(driver, wait)
                await self._select_court(driver, wait, court)

                # ── Date selection ─────────────────────────────────
                # With libfaketime the target date is now enabled normally.
                # DOM unlock is kept as a safety net only.
                available_dates = await self._get_available_dates(driver, wait)
                result['available_dates'] = available_dates
                logger.info(f"📅 Calendar shows available days: {available_dates}")

                target_day = str(datetime.strptime(date, "%Y-%m-%d").day)
                logger.info(f"📅 Looking for day {target_day} (target {date})")

                if target_day in available_dates:
                    date_selected = await self._select_date(driver, wait, date, available_dates)
                else:
                    # libfaketime shifted calendar but day still shows as disabled
                    # → DOM unlock as last resort
                    logger.warning(f"⚠️  Day {target_day} not enabled — trying DOM unlock")
                    self._send_telegram_update("⚠️ Using DOM unlock fallback...")
                    date_selected = await self._select_date_dom_unlock(driver, wait, date)

                if not date_selected:
                    raise Exception(f"Could not select date {date} on calendar")

                # ── Time selection ─────────────────────────────────
                available_times = await self._get_available_times(driver, wait)
                result['available_times'] = available_times

                if not available_times:
                    raise Exception(f"No time slots loaded after selecting {date}")

                time_selected = await self._select_time(driver, wait, time, available_times)
                if not time_selected:
                    times_str = "\n".join(f"  {t}" for t in available_times[:5])
                    msg = f"❌ Time {time} not available on {date}\n⏰ Available:\n{times_str}"
                    result['message'] = msg
                    self._send_telegram_update(msg)
                    return result   # No point retrying same unavailable time

                # ── Confirm ────────────────────────────────────────
                await self._confirm_booking(driver, wait)

                screenshot_path = await self._save_screenshot(driver, "booking_success")
                result.update({
                    'success':    True,
                    'message':    (f"🎉 Booking confirmed!\n"
                                   f"📅 {date}\n⏰ {time}\n🎾 {court}\n\n"
                                   f"📧 Check your email for confirmation."),
                    'screenshot': screenshot_path,
                    'reference':  None
                })
                logger.info(f"✅ Booking successful: {date} {time} {court}")
                self._send_telegram_update(result['message'])
                return result
                
            except Exception as e:
                logger.error(f"Booking attempt {attempt} failed: {e}")
                
                if driver:
                    screenshot_path = await self._save_screenshot(driver, f"error_attempt_{attempt}")
                    result['screenshot'] = screenshot_path
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    self._send_telegram_update(f"⚠️ Attempt failed, retrying in {self.retry_delay}s...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    result['message'] = f"❌ Booking failed after {self.max_retries} attempts: {str(e)}"
                    self._send_telegram_update(result['message'])
            
            finally:
                if driver:
                    driver.quit()
        
        return result
    
    async def _handle_initial_page_load(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Handle initial page load and terms & conditions"""
        logger.info("Loading booking website...")
        driver.get(self.base_url)
        
        # Wait for page to fully load
        await asyncio.sleep(5)
        
        try:
            # Accept Terms & Conditions
            terms_checkbox = wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    ".terms-and-condition_checkbox__osgE4 input[type='checkbox']"
                ))
            )
            
            if not terms_checkbox.is_selected():
                terms_checkbox.click()
                logger.info("Terms & Conditions accepted")
                await asyncio.sleep(0.5)
            
            # Click Continue
            continue_button = wait.until(
                EC.element_to_be_clickable((
                    By.CLASS_NAME,
                    "terms-and-condition_updateButton__pqUFT"
                ))
            )
            continue_button.click()
            logger.info("Clicked Continue after terms")
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.debug(f"Terms already accepted or not required: {e}")
    
    async def _handle_login(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Handle login process"""
        
        # Use user-specific credentials if provided, otherwise fall back to config
        if self.user_credentials:
            username = self.user_credentials.get('email')
            password = self.user_credentials.get('password')
        else:
            username = self.config.get('username')
            password = self.config.get('password')
        
        if not (username and password):
            logger.info("No credentials provided, skipping auto-login")
            return True
        
        try:
            logger.info("Attempting automatic login...")
            self._send_telegram_update("🔐 Logging in...")
            
            # Click Login button
            login_button = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(text(), 'Login')]"
                ))
            )
            login_button.click()
            await asyncio.sleep(1)
            
            # Select Password tab
            password_tab = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(text(), 'Password')]"
                ))
            )
            password_tab.click()
            await asyncio.sleep(0.5)
            
            # Enter email
            email_field = wait.until(
                EC.presence_of_element_located((
                    By.CLASS_NAME,
                    "emailField"
                ))
            )
            email_field.clear()
            email_field.send_keys(username)
            
            # Enter password
            password_field = driver.find_element(
                By.CSS_SELECTOR,
                "input[type='password']"
            )
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit
            submit_button = driver.find_element(
                By.CSS_SELECTOR,
                "button[type='submit']"
            )
            submit_button.click()
            
            logger.info("Login submitted, waiting for completion...")
            await asyncio.sleep(5)
            
            # Dismiss notification popup - try multiple selectors with short timeout
            for selector, by in [
                ("onesignal-slidedown-cancel-button",   By.ID),
                ("onesignal-slidedown-allow-button",    By.ID),
                ("[id*='onesignal'][id*='cancel']",     By.CSS_SELECTOR),
                ("[id*='onesignal'][id*='allow']",      By.CSS_SELECTOR),
                ("//button[contains(text(),'Later')]",  By.XPATH),
                ("//button[contains(text(),'No Thanks')]", By.XPATH),
                ("//button[contains(text(),'Cancel')]", By.XPATH),
            ]:
                try:
                    btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    btn.click()
                    logger.info(f"Notification popup dismissed via: {selector}")
                    await asyncio.sleep(1)
                    break
                except Exception:
                    continue
            
            logger.info("Login successful")
            self._send_telegram_update("✅ Logged in")
            return True
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise
    
    async def _navigate_to_booking(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Navigate to booking page"""
        logger.info("Navigating to booking page...")
        self._send_telegram_update("📍 Navigating to booking...")
        
        # Wait for dashboard to load
        await asyncio.sleep(5)
        
        # Click "Book Amenities"
        book_amenities = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[contains(text(), 'Book Amenities')]"
            ))
        )
        
        driver.execute_script("arguments[0].scrollIntoView(true);", book_amenities)
        await asyncio.sleep(0.5)
        
        try:
            book_amenities.click()
        except:
            driver.execute_script("arguments[0].click();", book_amenities)
        
        logger.info("Clicked 'Book Amenities'")
        await asyncio.sleep(3)
        
        # Click "Book an Amenity"
        book_amenity = wait.until(
            EC.element_to_be_clickable((
                By.CLASS_NAME,
                "booking-list_BookBtn__YqvHo"
            ))
        )
        book_amenity.click()
        
        logger.info("Clicked 'Book an Amenity'")
        await asyncio.sleep(2)
    
    async def _select_court(self, driver: webdriver.Chrome, wait: WebDriverWait, court: str):
        """Select specific court by name"""
        logger.info(f"Selecting court: {court}")
        self._send_telegram_update(f"🎾 Selecting {court}...")
        
        # Map user-friendly name to actual website text
        court_full_name = self.COURT_MAP.get(court, court)
        
        # Find the court container
        court_xpath = f"//div[contains(text(), '{court_full_name}')]/ancestor::div[contains(@class, 'select-amenity_amenityBox')]"
        
        court_box = wait.until(
            EC.presence_of_element_located((By.XPATH, court_xpath))
        )
        
        # Scroll into view
        driver.execute_script("arguments[0].scrollIntoView(true);", court_box)
        await asyncio.sleep(0.5)
        
        # Click the radio button directly
        radio_button = court_box.find_element(
            By.XPATH,
            ".//div[contains(@class, 'select-amenity_cursor')]"
        )
        
        try:
            radio_button.click()
        except:
            driver.execute_script("arguments[0].click();", radio_button)
        
        logger.info(f"Court selected: {court}")
        await asyncio.sleep(2)
        
        # Verify selection
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    f"//div[contains(text(), '{court_full_name}')]/ancestor::div[contains(@class, 'select-amenity_amenityBox')]//svg"
                ))
            )
            logger.info("Court selection verified")
        except:
            logger.warning("Could not verify court selection, but continuing...")
        
        # Click Continue
        continue_button = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(., 'Continue') and not(contains(@class, 'disabled'))]"
            ))
        )
        continue_button.click()
        
        logger.info("Clicked Continue after court selection")
        await asyncio.sleep(3)
    
    async def _get_available_dates(self, driver: webdriver.Chrome, wait: WebDriverWait) -> List[str]:
        """Get list of available dates from calendar (current visible month only)"""
        logger.info("Checking available dates...")
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".MuiDayCalendar-root")))
            available = driver.find_elements(
                By.CSS_SELECTOR, "button[role='gridcell']:not([disabled])"
            )
            dates = [e.text for e in available if e.text.isdigit()]
            logger.info(f"Calendar shows available days: {dates}")
            return dates
        except Exception as e:
            logger.error(f"Could not get available dates: {e}")
            return []

    async def _select_date(
        self,
        driver: webdriver.Chrome,
        wait: WebDriverWait,
        target_date: str,
        available_dates: List[str]
    ) -> bool:
        """
        Select a date on the calendar.

        For dates within the normal 7-day window: click directly.
        For advanced dates (>7 days): navigate to the correct month using
        the calendar's own next-month arrow, then DOM-unlock the disabled
        button and force-click it. This is 100% client-side and does not
        depend on any JS Date override.
        """
        logger.info(f"Selecting date: {target_date}")
        self._send_telegram_update(f"📅 Selecting {target_date}...")

        try:
            target_dt  = datetime.strptime(target_date, "%Y-%m-%d")
            day_number = str(target_dt.day)
            today      = datetime.now()
            days_ahead = (target_dt.date() - today.date()).days

            # ── Wait for calendar ────────────────────────────────
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".MuiDayCalendar-root")))
            await asyncio.sleep(1)

            # ── If target month ≠ current month, navigate forward ─
            current_month = today.month
            target_month  = target_dt.month
            target_year   = target_dt.year

            months_to_advance = (
                (target_year - today.year) * 12 + (target_month - current_month)
            )

            if months_to_advance > 0:
                logger.info(f"📅 Navigating {months_to_advance} month(s) forward on calendar")
                for _ in range(months_to_advance):
                    try:
                        # MUI calendar next-month button (right arrow)
                        next_btn = wait.until(EC.element_to_be_clickable((
                            By.CSS_SELECTOR,
                            "button[aria-label='Go to next month'], "
                            "button.MuiPickersArrowSwitcher-button:last-of-type, "
                            "button[title='Next month']"
                        )))
                        next_btn.click()
                        await asyncio.sleep(1)
                        logger.info("Clicked next-month arrow")
                    except Exception as e:
                        logger.warning(f"Could not click next-month arrow: {e}")
                        break

            # ── Try normal click first (date might be enabled) ────
            normal_xpath = (
                f"//button[@role='gridcell' and not(@disabled) "
                f"and normalize-space(text())='{day_number}']"
            )
            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, normal_xpath))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                btn.click()
                logger.info(f"✅ Date {target_date} clicked normally")
                await asyncio.sleep(2)
                return True
            except Exception:
                logger.info(f"Day {day_number} is disabled - attempting DOM unlock")

            # ── DOM unlock: remove disabled, force-click ──────────
            unlocked = driver.execute_script(f"""
                var buttons = document.querySelectorAll('button[role="gridcell"]');
                var found   = null;
                buttons.forEach(function(btn) {{
                    if (btn.textContent.trim() === '{day_number}') {{
                        btn.removeAttribute('disabled');
                        btn.classList.remove('Mui-disabled');
                        btn.style.opacity        = '1';
                        btn.style.pointerEvents  = 'auto';
                        found = btn;
                    }}
                }});
                if (found) {{ found.click(); return true; }}
                return false;
            """)

            if unlocked:
                logger.info(f"✅ Date {target_date} selected via DOM unlock")
                await asyncio.sleep(2)
                return True

            logger.error(f"Day {day_number} not found on calendar at all")
            return False

        except Exception as e:
            logger.error(f"Date selection failed: {e}")
            return False


    async def _select_date_dom_unlock(
        self,
        driver: webdriver.Chrome,
        wait: WebDriverWait,
        target_date: str
    ) -> bool:
        """
        Advanced booking: select a date beyond the normal 7-day limit.

        Strategy (no JS Date override needed):
          1. Wait for calendar to appear.
          2. Navigate to the correct month using the MUI next-month arrow.
          3. Try a normal click first (date might already be enabled on some courts).
          4. If the button is disabled, remove the disabled attribute and force-click.
          5. Verify the selection was accepted by waiting for time slots to appear.
        """
        logger.info(f"🎯 DOM unlock: targeting {target_date}")

        try:
            target_dt  = datetime.strptime(target_date, "%Y-%m-%d")
            day_number = str(target_dt.day)
            today      = datetime.now()

            # ── Wait for calendar ──────────────────────────────────
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".MuiDayCalendar-root")
            ))
            await asyncio.sleep(1)

            # ── Navigate to correct month ──────────────────────────
            months_ahead = (
                (target_dt.year - today.year) * 12
                + (target_dt.month - today.month)
            )
            for i in range(months_ahead):
                try:
                    next_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((
                            By.CSS_SELECTOR,
                            "button[aria-label='Go to next month'],"
                            "button.MuiPickersArrowSwitcher-button:last-of-type,"
                            "button[title='Next month']"
                        ))
                    )
                    next_btn.click()
                    await asyncio.sleep(1)
                    logger.info(f"📅 Navigated to next month ({i+1}/{months_ahead})")
                except Exception as e:
                    logger.warning(f"Could not click next-month arrow: {e}")

            # ── Try normal click (date may already be enabled) ─────
            normal_xpath = (
                f"//button[@role='gridcell' and not(@disabled)"
                f" and normalize-space(text())='{day_number}']"
            )
            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, normal_xpath))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                btn.click()
                logger.info(f"✅ Day {day_number} clicked normally (already enabled)")
                await asyncio.sleep(2)
                return True
            except Exception:
                logger.info(f"Day {day_number} is disabled — attempting DOM unlock")

            # ── DOM unlock: strip disabled and fire React synthetic event ──────
            clicked = driver.execute_script(f"""
                var buttons = document.querySelectorAll('button[role="gridcell"]');
                var target  = null;
                buttons.forEach(function(b) {{
                    if (b.textContent.trim() === '{day_number}') {{
                        b.removeAttribute('disabled');
                        b.classList.remove('Mui-disabled');
                        b.style.opacity       = '1';
                        b.style.pointerEvents = 'auto';
                        target = b;
                    }}
                }});
                if (!target) return false;
                
                // React ignores native .click() on controlled components.
                // We must dispatch a real MouseEvent that bubbles through React's
                // synthetic event system.
                var opts = {{
                    bubbles:    true,
                    cancelable: true,
                    view:       window,
                    buttons:    1
                }};
                target.dispatchEvent(new MouseEvent('mousedown', opts));
                target.dispatchEvent(new MouseEvent('mouseup',   opts));
                target.dispatchEvent(new MouseEvent('click',     opts));
                return true;
            """)

            if not clicked:
                logger.error(f"Day {day_number} not found on calendar page")
                return False

            logger.info(f"🔓 DOM unlock + React event dispatched — day {day_number}")
            await asyncio.sleep(4)   # Give React time to re-render time slots

            # ── Verify: time slots should appear if click worked ───
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".select-dates_timeSlots__GuHwQ")
                    )
                )
                logger.info(f"✅ Time slots appeared — date {target_date} accepted!")
                return True
            except Exception:
                logger.warning(
                    "No time slots appeared after DOM unlock click. "
                    "The server may have rejected the out-of-range date."
                )
                return False

        except Exception as e:
            logger.error(f"_select_date_dom_unlock failed: {e}")
            return False

    async def _get_available_times(self, driver: webdriver.Chrome, wait: WebDriverWait) -> List[str]:
        """Get list of available time slots"""
        logger.info("Checking available time slots...")
        
        try:
            # Wait for time slots to load
            await asyncio.sleep(2)
            
            time_slot_elements = wait.until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    ".select-dates_timeSlots__GuHwQ"
                ))
            )
            
            available_times = []
            for slot in time_slot_elements:
                slot_text = slot.text
                if slot_text:
                    available_times.append(slot_text)
            
            logger.info(f"Found {len(available_times)} available time slots")
            return available_times
            
        except Exception as e:
            logger.error(f"Could not get available times: {e}")
            return []
    
    def _convert_time_to_website_format(self, time_24h: str) -> str:
        """Convert 24-hour time (HH:MM) to website format"""
        try:
            hour = int(time_24h.split(':')[0])
            
            if hour < 12:
                start_hour = hour
                end_hour = hour + 1
                start_period = end_period = "AM"
                if end_hour == 12:
                    end_period = "PM"
            else:
                start_hour = 12 if hour == 12 else hour - 12
                end_hour = 1 if hour == 23 else ((hour + 1) - 12 if hour >= 12 else hour + 1)
                start_period = "PM"
                end_period = "PM" if hour < 23 else "AM"
            
            return f"{start_hour:02d}:00 {start_period} - {end_hour:02d}:00 {end_period}"
            
        except Exception as e:
            logger.error(f"Time conversion error: {e}")
            return time_24h
    
    async def _select_time(
        self,
        driver: webdriver.Chrome,
        wait: WebDriverWait,
        target_time: str,
        available_times: List[str]
    ) -> bool:
        """
        Select time slot
        
        Args:
            target_time: Time in HH:MM format (24-hour)
            available_times: List of available time slot strings
        
        Returns:
            True if time selected successfully
        """
        logger.info(f"Selecting time: {target_time}")
        self._send_telegram_update(f"⏰ Selecting {target_time}...")
        
        try:
            # Convert to website format
            website_time = self._convert_time_to_website_format(target_time)
            logger.info(f"Converted time: {website_time}")
            
            # Check if time is available
            if website_time not in available_times:
                logger.warning(f"Time {website_time} not available")
                return False
            
            # Find and click the time slot
            time_xpath = f"//div[contains(@class, 'select-dates_timeSlots') and text()='{website_time}']"
            
            time_slot = wait.until(
                EC.element_to_be_clickable((By.XPATH, time_xpath))
            )
            
            driver.execute_script("arguments[0].scrollIntoView(true);", time_slot)
            await asyncio.sleep(0.5)
            
            try:
                time_slot.click()
            except:
                driver.execute_script("arguments[0].click();", time_slot)
            
            logger.info(f"Time selected: {website_time}")
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Time selection failed: {e}")
            return False
    
    async def _confirm_booking(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Click final Continue button - this completes the booking"""
        logger.info("Confirming booking...")
        self._send_telegram_update("✅ Confirming booking...")
        
        try:
            continue_button = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(., 'Continue') and not(contains(@class, 'disabled'))]"
                ))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", continue_button)
            await asyncio.sleep(0.5)
            continue_button.click()
            logger.info("✅ Continue clicked - booking complete")
            await asyncio.sleep(5)   # Wait for confirmation page
            
        except Exception as e:
            logger.error(f"Confirmation error: {e}")
            raise
    
    async def _save_screenshot(self, driver: webdriver.Chrome, name: str) -> str:
        """Save screenshot with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        driver.save_screenshot(str(filepath))
        logger.info(f"Screenshot saved: {filepath}")
        
        return str(filepath)
