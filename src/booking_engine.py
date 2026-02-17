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
        
        time_travel_date: if set (YYYY-MM-DD), injects a JS Date override so the
        website thinks today is that date, allowing booking beyond the 7-day limit.
        Uses the EXACT same injection pattern confirmed working in local tests.
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
        
        # Create driver
        try:
            service = Service('/usr/local/bin/chromedriver')
            driver = webdriver.Chrome(service=service, options=chrome_options)
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
        
        driver.set_page_load_timeout(self.page_timeout)
        
        # ── Hide webdriver flag ────────────────────────────────
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        
        # ── Time travel injection ──────────────────────────────
        # Uses EXACT same pattern as the local test that confirmed it works.
        # Must be injected here (before any driver.get()) so it runs before
        # the React calendar initialises on first page load.
        if time_travel_date:
            from datetime import datetime as _dt
            ts_ms = int(_dt.strptime(time_travel_date, "%Y-%m-%d").timestamp() * 1000)
            
            time_script = f"""
(function() {{
    const _Date = window.Date;
    const _fakeNow = {ts_ms};

    function PatchedDate(...args) {{
        if (!(this instanceof PatchedDate)) {{
            return new PatchedDate(...args);
        }}
        if (args.length === 0) {{
            return new _Date(_fakeNow);
        }}
        return new _Date(...args);
    }}

    PatchedDate.now        = () => _fakeNow;
    PatchedDate.parse      = _Date.parse.bind(_Date);
    PatchedDate.UTC        = _Date.UTC.bind(_Date);
    PatchedDate.prototype  = _Date.prototype;

    Object.defineProperty(window, 'Date', {{
        value:        PatchedDate,
        writable:     true,
        configurable: true,
    }});

    console.log('[TimeTravel] active - new Date():', new window.Date().toISOString());
}})();
"""
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                                   {'source': time_script})
            logger.info(f"🎯 Time override injected → browser will think today is {time_travel_date}")
        
        return driver
    
    async def book_court(
        self,
        date: str,
        time: str,
        court: Optional[str] = None,
        user_id: int = None,
        booking_id: int = None,
        enable_time_travel: bool = False
    ) -> Dict:
        """
        Execute the booking process with retry logic and availability checking
        
        Args:
            date: Booking date (YYYY-MM-DD)
            time: Booking time (HH:MM) in 24-hour format
            court: Court name (user-friendly)
            user_id: Telegram user ID for updates
            booking_id: Database booking ID
            enable_time_travel: If True, manipulate browser time for advanced booking
        
        Returns:
            Dict with booking result and details
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
                
                # Calculate time travel settings BEFORE creating driver
                time_travel_date = None
                if enable_time_travel:
                    from datetime import datetime, timedelta
                    target_dt = datetime.strptime(date, "%Y-%m-%d")
                    today = datetime.now().date()
                    days_until = (target_dt.date() - today).days
                    
                    if days_until > 7:
                        # Calculate how many days to shift browser time
                        time_shift_days = days_until - 7
                        fake_today = today + timedelta(days=time_shift_days)
                        time_travel_date = fake_today.strftime("%Y-%m-%d")
                        
                        logger.info(f"🎯 Target date {date} is {days_until} days away")
                        logger.info(f"🎯 Will shift browser time +{time_shift_days} days to {time_travel_date}")
                        self._send_telegram_update(f"🎯 Advanced booking: +{time_shift_days} days")
                
                # Create driver (will inject time override if time_travel_date is set)
                driver = self._create_driver(time_travel_date=time_travel_date)
                wait = WebDriverWait(driver, self.element_timeout)
                
                # Execute booking flow
                await self._handle_initial_page_load(driver, wait)
                await self._handle_login(driver, wait)
                await self._navigate_to_booking(driver, wait)
                await self._select_court(driver, wait, court)
                
                # Check date availability
                available_dates = await self._get_available_dates(driver, wait)
                result['available_dates'] = available_dates
                
                # Select date
                date_selected = await self._select_date(driver, wait, date, available_dates)
                if not date_selected:
                    result['message'] = f"❌ Date {date} is not available"
                    self._send_telegram_update(result['message'])
                    
                    if available_dates:
                        dates_str = ", ".join(available_dates[:5])
                        result['message'] += f"\n📅 Available dates: {dates_str}"
                        self._send_telegram_update(f"📅 Available: {dates_str}")
                    
                    return result
                
                # Check time availability
                available_times = await self._get_available_times(driver, wait)
                result['available_times'] = available_times
                
                # Select time
                time_selected = await self._select_time(driver, wait, time, available_times)
                if not time_selected:
                    result['message'] = f"❌ Time {time} is not available on {date}"
                    self._send_telegram_update(result['message'])
                    
                    if available_times:
                        times_str = ", ".join(available_times[:5])
                        result['message'] += f"\n⏰ Available times: {times_str}"
                        self._send_telegram_update(f"⏰ Available: {times_str}")
                    
                    return result
                
                # Confirm booking
                await self._confirm_booking(driver, wait)
                
                # Get booking reference
                reference = await self._get_booking_reference(driver, wait)
                
                # Success!
                screenshot_path = await self._save_screenshot(driver, "booking_success")
                
                result.update({
                    'success': True,
                    'message': f"✅ Booking confirmed!\n📅 {date}\n⏰ {time}\n🎾 {court}",
                    'screenshot': screenshot_path,
                    'reference': reference
                })
                
                logger.info(f"Booking successful: {reference}")
                self._send_telegram_update(result['message'])
                
                if reference:
                    self._send_telegram_update(f"🎫 Reference: {reference}")
                
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
            
            # Handle notification popup if it appears
            try:
                later_button = driver.find_element(
                    By.ID,
                    "onesignal-slidedown-cancel-button"
                )
                if later_button.is_displayed():
                    later_button.click()
                    logger.info("Notification popup dismissed")
                    await asyncio.sleep(1)
            except:
                logger.debug("No notification popup or already dismissed")
            
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
        """Get list of available dates from calendar"""
        logger.info("Checking available dates...")
        
        try:
            # Wait for calendar to load
            wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    ".MuiDayCalendar-root"
                ))
            )
            
            # Get all available (not disabled) date buttons
            available_date_elements = driver.find_elements(
                By.CSS_SELECTOR,
                "button[role='gridcell']:not([disabled])"
            )
            
            available_dates = []
            for date_elem in available_date_elements:
                day_number = date_elem.text
                if day_number.isdigit():
                    # You could enhance this to return full dates
                    available_dates.append(day_number)
            
            logger.info(f"Found {len(available_dates)} available dates")
            return available_dates
            
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
        Select date on calendar
        
        Args:
            target_date: Date in YYYY-MM-DD format
            available_dates: List of available day numbers
        
        Returns:
            True if date selected successfully
        """
        logger.info(f"Selecting date: {target_date}")
        self._send_telegram_update(f"📅 Selecting {target_date}...")
        
        try:
            # Parse target date
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            day_number = str(target_dt.day)
            
            # Check if date is available
            if day_number not in available_dates:
                logger.warning(f"Date {target_date} (day {day_number}) not available")
                return False
            
            # Find and click the date button
            date_xpath = f"//button[@role='gridcell' and not(@disabled) and text()='{day_number}']"
            
            date_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, date_xpath))
            )
            
            driver.execute_script("arguments[0].scrollIntoView(true);", date_button)
            await asyncio.sleep(0.5)
            
            try:
                date_button.click()
            except:
                driver.execute_script("arguments[0].click();", date_button)
            
            logger.info(f"Date selected: {target_date}")
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"Date selection failed: {e}")
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
            # Click Continue after time selection - THIS COMPLETES THE BOOKING
            continue_button = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(., 'Continue') and not(contains(@class, 'disabled'))]"
                ))
            )
            
            driver.execute_script("arguments[0].scrollIntoView(true);", continue_button)
            await asyncio.sleep(0.5)
            
            continue_button.click()
            logger.info("✅ Booking confirmed! Continue button clicked.")
            
            # Wait for confirmation page to load
            await asyncio.sleep(5)
            
            # Take final confirmation screenshot
            logger.info("Capturing confirmation screenshot...")
            
            # Booking is now complete!
            
        except Exception as e:
            logger.error(f"Confirmation error: {e}")
            raise
    
    async def _get_booking_reference(self, driver: webdriver.Chrome, wait: WebDriverWait) -> Optional[str]:
        """Extract booking reference number from confirmation page"""
        try:
            # TODO: Add selector for booking reference once discovered
            # This is a placeholder
            logger.info("Looking for booking reference...")
            return None
            
        except Exception as e:
            logger.debug(f"Could not extract booking reference: {e}")
            return None
    
    async def _save_screenshot(self, driver: webdriver.Chrome, name: str) -> str:
        """Save screenshot with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        
        driver.save_screenshot(str(filepath))
        logger.info(f"Screenshot saved: {filepath}")
        
        return str(filepath)
