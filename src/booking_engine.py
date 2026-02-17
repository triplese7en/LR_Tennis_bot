"""
Booking Engine — Selenium browser automation for Dubai Properties court booking.
Handles login, court selection, date/time selection, and confirmation.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


class BookingEngine:
    """Selenium-based booking automation for eservices.dp.ae/amenity-booking"""

    # Maps user-friendly court names → exact website text
    COURT_MAP = {
        "Amaranta B":     "Tennis Court Amaranta B",
        "Amaranta 3":     "Tennis Court  Amaranta 3",   # two spaces — site quirk
        "La Rosa 4":      "Tennis Court - La Rosa 4",
        "Paddle Court 1": "Paddle Tennis Court 1 - Villanova (La Violeta 2)",
        "Paddle Court 2": "Paddle Tennis Court 2 - Villanova (La Violeta 2)",
    }

    def __init__(
        self,
        config: Dict,
        telegram_callback=None,
        user_credentials: Dict = None,
    ):
        self.config            = config
        self.user_credentials  = user_credentials
        self.telegram_callback = telegram_callback
        self.base_url          = "https://eservices.dp.ae/amenity-booking"
        self.screenshot_dir    = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)

        self.max_retries     = config.get('max_retries',     3)
        self.retry_delay     = config.get('retry_delay',     5)
        self.page_timeout    = config.get('page_timeout',    30)
        self.element_timeout = config.get('element_timeout', 10)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _send_telegram_update(self, message: str):
        if self.telegram_callback:
            try:
                asyncio.create_task(self.telegram_callback(message))
            except Exception:
                pass

    def _create_driver(self) -> webdriver.Chrome:
        """Create a headless Chrome WebDriver."""
        opts = Options()
        if self.config.get('headless', True):
            opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_argument('--disable-notifications')
        opts.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation":   2,
        })
        opts.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option('useAutomationExtension', False)

        try:
            driver = webdriver.Chrome(
                service=Service('/usr/local/bin/chromedriver'), options=opts
            )
            logger.info("Using system ChromeDriver")
        except Exception:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()), options=opts
                )
                logger.info("Using webdriver-manager ChromeDriver")
            except Exception as e:
                logger.error(f"ChromeDriver init failed: {e}")
                raise

        driver.set_page_load_timeout(self.page_timeout)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        return driver

    async def _save_screenshot(self, driver: webdriver.Chrome, name: str) -> str:
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.screenshot_dir / f"{name}_{ts}.png"
        driver.save_screenshot(str(filepath))
        logger.info(f"Screenshot saved: {filepath}")
        return str(filepath)

    # ── Public API ────────────────────────────────────────────────────────────

    async def book_court(
        self,
        date:  str,
        time:  str,
        court: Optional[str] = None,
        user_id:    int = None,
        booking_id: int = None,
        enable_time_travel: bool = False,   # unused, kept for API compatibility
    ) -> Dict:
        """
        Book a court.  Retries up to max_retries times.
        date  : YYYY-MM-DD
        time  : HH:MM  (24-hour)
        court : friendly name from COURT_MAP, or None for any
        """
        result = {
            'success': False, 'message': '',
            'screenshot': None, 'reference': None,
            'available_times': [], 'available_dates': [],
        }

        for attempt in range(1, self.max_retries + 1):
            driver = None
            try:
                logger.info(f"Booking attempt {attempt}/{self.max_retries}")
                self._send_telegram_update(f"🔄 Attempt {attempt}/{self.max_retries}…")

                driver = self._create_driver()
                wait   = WebDriverWait(driver, self.element_timeout)

                await self._load_site(driver, wait)
                await self._login(driver, wait)
                await self._navigate_to_booking(driver, wait)
                await self._select_court(driver, wait, court)

                available_dates = await self._get_available_dates(driver, wait)
                result['available_dates'] = available_dates
                logger.info(f"📅 Calendar shows: {available_dates}")

                date_selected = await self._select_date(driver, wait, date)
                if not date_selected:
                    raise Exception(f"Could not select date {date} on calendar")

                available_times = await self._get_available_times(driver, wait)
                result['available_times'] = available_times
                if not available_times:
                    raise Exception(f"No time slots loaded after selecting {date}")

                time_selected = await self._select_time(driver, wait, time, available_times)
                if not time_selected:
                    msg = (
                        f"❌ {time} not available on {date}\n"
                        f"⏰ Available: {', '.join(available_times[:5])}"
                    )
                    result['message'] = msg
                    self._send_telegram_update(msg)
                    return result   # Don't retry — time genuinely unavailable

                await self._confirm_booking(driver, wait)

                screenshot = await self._save_screenshot(driver, "booking_success")
                result.update({
                    'success':    True,
                    'message':    (
                        f"🎉 Booking confirmed!\n"
                        f"📅 {date}  ⏰ {time}  🎾 {court}\n\n"
                        f"📧 Check your email for confirmation."
                    ),
                    'screenshot': screenshot,
                })
                logger.info(f"✅ Booking successful: {date} {time} {court}")
                self._send_telegram_update(result['message'])
                return result

            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                if driver:
                    result['screenshot'] = await self._save_screenshot(
                        driver, f"error_attempt_{attempt}"
                    )
                if attempt < self.max_retries:
                    self._send_telegram_update(
                        f"⚠️ Attempt {attempt} failed, retrying in {self.retry_delay}s…"
                    )
                    await asyncio.sleep(self.retry_delay)
                else:
                    result['message'] = f"❌ Booking failed after {self.max_retries} attempts: {e}"
                    self._send_telegram_update(result['message'])
            finally:
                if driver:
                    driver.quit()

        return result

    # ── Booking steps ─────────────────────────────────────────────────────────

    async def _load_site(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Load the site and accept Terms & Conditions if shown."""
        logger.info("Loading booking website…")
        driver.get(self.base_url)
        await asyncio.sleep(5)
        try:
            cb = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                ".terms-and-condition_checkbox__osgE4 input[type='checkbox']"
            )))
            if not cb.is_selected():
                cb.click()
                await asyncio.sleep(0.5)
            wait.until(EC.element_to_be_clickable((
                By.CLASS_NAME, "terms-and-condition_updateButton__pqUFT"
            ))).click()
            logger.info("Terms accepted")
            await asyncio.sleep(2)
        except Exception:
            logger.debug("Terms screen not shown")

    async def _login(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Log in with saved credentials."""
        creds    = self.user_credentials or {}
        username = creds.get('email')    or self.config.get('username')
        password = creds.get('password') or self.config.get('password')

        if not (username and password):
            logger.info("No credentials — skipping login")
            return

        logger.info("Logging in…")
        self._send_telegram_update("🔐 Logging in…")

        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(), 'Login')]"
        ))).click()
        await asyncio.sleep(1)

        wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(text(), 'Password')]"
        ))).click()
        await asyncio.sleep(0.5)

        field = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "emailField")))
        field.clear()
        field.send_keys(username)

        pw = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pw.clear()
        pw.send_keys(password)

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        logger.info("Login submitted…")
        await asyncio.sleep(5)

        # Dismiss notification popup — try several selectors, move on if none appear
        for selector, by in [
            ("onesignal-slidedown-cancel-button",    By.ID),
            ("onesignal-slidedown-allow-button",      By.ID),
            ("[id*='onesignal'][id*='cancel']",       By.CSS_SELECTOR),
            ("//button[contains(text(),'Later')]",     By.XPATH),
            ("//button[contains(text(),'No Thanks')]", By.XPATH),
        ]:
            try:
                WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((by, selector))
                ).click()
                logger.info("Notification popup dismissed")
                await asyncio.sleep(1)
                break
            except Exception:
                continue

        logger.info("Login successful")
        self._send_telegram_update("✅ Logged in")

    async def _navigate_to_booking(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Click through to the court selection screen."""
        logger.info("Navigating to booking…")
        self._send_telegram_update("📍 Navigating…")
        await asyncio.sleep(5)

        btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//div[contains(text(), 'Book Amenities')]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        await asyncio.sleep(0.5)
        try:
            btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", btn)
        logger.info("Clicked 'Book Amenities'")
        await asyncio.sleep(3)

        wait.until(EC.element_to_be_clickable((
            By.CLASS_NAME, "booking-list_BookBtn__YqvHo"
        ))).click()
        logger.info("Clicked 'Book an Amenity'")
        await asyncio.sleep(2)

    async def _select_court(self, driver: webdriver.Chrome, wait: WebDriverWait, court: str):
        """Select a court by name and click Continue."""
        logger.info(f"Selecting court: {court}")
        self._send_telegram_update(f"🎾 Selecting {court}…")

        full_name   = self.COURT_MAP.get(court, court)
        court_xpath = (
            f"//div[contains(text(), '{full_name}')]"
            f"/ancestor::div[contains(@class, 'select-amenity_amenityBox')]"
        )
        court_box = wait.until(EC.presence_of_element_located((By.XPATH, court_xpath)))
        driver.execute_script("arguments[0].scrollIntoView(true);", court_box)
        await asyncio.sleep(0.5)

        radio = court_box.find_element(
            By.XPATH, ".//div[contains(@class, 'select-amenity_cursor')]"
        )
        try:
            radio.click()
        except Exception:
            driver.execute_script("arguments[0].click();", radio)
        await asyncio.sleep(2)

        # Verify selection (SVG checkmark)
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((
                By.XPATH,
                f"//div[contains(text(), '{full_name}')]"
                f"/ancestor::div[contains(@class, 'select-amenity_amenityBox')]//svg"
            )))
            logger.info("Court selection verified")
        except Exception:
            logger.warning("Court selection SVG not found — continuing anyway")

        cont = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(., 'Continue') and not(contains(@class, 'disabled'))]"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", cont)
        await asyncio.sleep(0.5)
        try:
            cont.click()
        except Exception:
            driver.execute_script("arguments[0].click();", cont)
        logger.info("Clicked Continue after court selection")
        await asyncio.sleep(3)

    async def _get_available_dates(
        self, driver: webdriver.Chrome, wait: WebDriverWait
    ) -> List[str]:
        """Return list of enabled day numbers shown on the calendar."""
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".MuiDayCalendar-root")))
            elems = driver.find_elements(
                By.CSS_SELECTOR, "button[role='gridcell']:not([disabled])"
            )
            return [e.text for e in elems if e.text.isdigit()]
        except Exception as e:
            logger.error(f"Could not read calendar: {e}")
            return []

    async def _select_date(
        self, driver: webdriver.Chrome, wait: WebDriverWait, target_date: str
    ) -> bool:
        """
        Select a date on the MUI calendar.
        Navigates to the correct month, tries a normal click,
        then falls back to DOM unlock + React event dispatch.
        """
        logger.info(f"Selecting date: {target_date}")
        self._send_telegram_update(f"📅 Selecting {target_date}…")

        try:
            target_dt  = datetime.strptime(target_date, "%Y-%m-%d")
            day_number = str(target_dt.day)
            today      = datetime.now()

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".MuiDayCalendar-root")))
            await asyncio.sleep(1)

            # Navigate forward if target is in a future month
            months_ahead = (
                (target_dt.year  - today.year)  * 12
                + (target_dt.month - today.month)
            )
            for _ in range(months_ahead):
                try:
                    nxt = wait.until(EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        "button[aria-label='Go to next month'], "
                        "button.MuiPickersArrowSwitcher-button:last-of-type, "
                        "button[title='Next month']"
                    )))
                    nxt.click()
                    await asyncio.sleep(1)
                    logger.info("Navigated to next month")
                except Exception as e:
                    logger.warning(f"Could not advance month: {e}")
                    break

            # Normal click (date is enabled)
            try:
                btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((
                    By.XPATH,
                    f"//button[@role='gridcell' and not(@disabled) "
                    f"and normalize-space(text())='{day_number}']"
                )))
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                btn.click()
                logger.info(f"✅ Date {target_date} clicked (enabled)")
                await asyncio.sleep(2)
                return True
            except Exception:
                logger.info(f"Day {day_number} disabled — trying DOM unlock")

            # DOM unlock + React synthetic events
            clicked = driver.execute_script(f"""
                var target = null;
                document.querySelectorAll('button[role="gridcell"]').forEach(function(b) {{
                    if (b.textContent.trim() === '{day_number}') {{
                        b.removeAttribute('disabled');
                        b.classList.remove('Mui-disabled');
                        b.style.opacity       = '1';
                        b.style.pointerEvents = 'auto';
                        target = b;
                    }}
                }});
                if (!target) return false;
                var opts = {{bubbles: true, cancelable: true, view: window, buttons: 1}};
                target.dispatchEvent(new MouseEvent('mousedown', opts));
                target.dispatchEvent(new MouseEvent('mouseup',   opts));
                target.dispatchEvent(new MouseEvent('click',     opts));
                return true;
            """)

            if not clicked:
                logger.error(f"Day {day_number} not found on calendar")
                return False

            logger.info(f"🔓 DOM unlock dispatched for day {day_number}")
            await asyncio.sleep(3)
            return True

        except Exception as e:
            logger.error(f"Date selection failed: {e}")
            return False

    async def _get_available_times(
        self, driver: webdriver.Chrome, wait: WebDriverWait
    ) -> List[str]:
        """Return available time slot strings after a date is selected."""
        logger.info("Checking time slots…")
        try:
            await asyncio.sleep(2)
            elems = wait.until(EC.presence_of_all_elements_located((
                By.CSS_SELECTOR, ".select-dates_timeSlots__GuHwQ"
            )))
            slots = [e.text for e in elems if e.text]
            logger.info(f"Found {len(slots)} time slots")
            return slots
        except Exception as e:
            logger.error(f"Could not read time slots: {e}")
            return []

    def _to_website_time(self, time_24h: str) -> str:
        """Convert '20:00' → '08:00 PM - 09:00 PM' (website display format)."""
        try:
            hour = int(time_24h.split(':')[0])
            if hour < 12:
                sh, eh = hour, hour + 1
                sp = ep = "AM"
                if eh == 12:
                    ep = "PM"
            else:
                sh = 12 if hour == 12 else hour - 12
                eh = 1  if hour == 23 else ((hour + 1 - 12) if hour >= 12 else hour + 1)
                sp = "PM"
                ep = "PM" if hour < 23 else "AM"
            return f"{sh:02d}:00 {sp} - {eh:02d}:00 {ep}"
        except Exception as e:
            logger.error(f"Time conversion error: {e}")
            return time_24h

    async def _select_time(
        self,
        driver: webdriver.Chrome,
        wait:   WebDriverWait,
        target_time: str,
        available_times: List[str],
    ) -> bool:
        """Click the matching time slot."""
        website_time = self._to_website_time(target_time)
        logger.info(f"Selecting time: {target_time} → {website_time}")
        self._send_telegram_update(f"⏰ Selecting {target_time}…")

        if website_time not in available_times:
            logger.warning(f"{website_time} not in available list")
            return False

        try:
            slot = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                f"//div[contains(@class, 'select-dates_timeSlots') and text()='{website_time}']"
            )))
            driver.execute_script("arguments[0].scrollIntoView(true);", slot)
            await asyncio.sleep(0.5)
            try:
                slot.click()
            except Exception:
                driver.execute_script("arguments[0].click();", slot)
            logger.info(f"Time selected: {website_time}")
            await asyncio.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Time selection failed: {e}")
            return False

    async def _confirm_booking(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """Click the final Continue button to complete the booking."""
        logger.info("Confirming booking…")
        self._send_telegram_update("✅ Confirming booking…")
        await asyncio.sleep(1)

        btn = None
        for sel in [
            "//button[contains(., 'Continue') and not(@disabled) and not(contains(@class, 'disabled'))]",
            "//button[contains(., 'Continue') and not(@disabled)]",
            "//button[contains(., 'Continue') and not(contains(@class, 'disabled'))]",
        ]:
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                break
            except Exception:
                continue

        if not btn:
            raise Exception("Continue button not found after time selection")

        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        await asyncio.sleep(0.5)
        try:
            btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", btn)

        logger.info("✅ Continue clicked — booking complete")
        await asyncio.sleep(5)
