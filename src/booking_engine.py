"""
Booking Engine using Selenium WebDriver
Handles all browser automation for tennis court booking
"""

import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, Optional
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

logger = logging.getLogger(__name__)


class BookingEngine:
    """Selenium-based booking automation engine"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.base_url = "https://eservices.dp.ae/amenity-booking"
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        
        # Retry configuration
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 5)
        
        # Timeout configuration
        self.page_timeout = config.get('page_timeout', 30)
        self.element_timeout = config.get('element_timeout', 10)
    
    def _create_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver"""
        chrome_options = Options()
        
        # Headless mode for cloud deployment
        if self.config.get('headless', True):
            chrome_options.add_argument('--headless=new')
        
        # Additional options for stability
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # User agent to avoid detection
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Disable automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Create driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(self.page_timeout)
        
        # Execute CDP commands to further hide automation
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        return driver
    
    async def book_court(
        self,
        date: str,
        time: str,
        court: Optional[str] = None,
        user_id: int = None,
        booking_id: int = None
    ) -> Dict:
        """
        Execute the booking process with retry logic
        
        Args:
            date: Booking date (YYYY-MM-DD)
            time: Booking time (HH:MM)
            court: Court number or 'any'
            user_id: Telegram user ID
            booking_id: Database booking ID
        
        Returns:
            Dict with success status, message, and screenshot path
        """
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                logger.info(f"Booking attempt {retry_count + 1}/{self.max_retries}")
                result = await self._execute_booking(date, time, court, user_id, booking_id)
                
                if result['success']:
                    return result
                
                # If booking failed but no exception, retry
                last_error = result.get('error', 'Unknown error')
                logger.warning(f"Booking failed: {last_error}")
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Booking attempt {retry_count + 1} failed: {e}", exc_info=True)
            
            retry_count += 1
            
            if retry_count < self.max_retries:
                logger.info(f"Retrying in {self.retry_delay} seconds...")
                await asyncio.sleep(self.retry_delay)
        
        # All retries exhausted
        return {
            'success': False,
            'error': f"Failed after {self.max_retries} attempts. Last error: {last_error}",
            'retry_count': retry_count
        }
    
    async def _execute_booking(
        self,
        date: str,
        time: str,
        court: Optional[str],
        user_id: int,
        booking_id: int
    ) -> Dict:
        """Execute a single booking attempt"""
        driver = None
        screenshot_path = None
        
        try:
            driver = self._create_driver()
            wait = WebDriverWait(driver, self.element_timeout)
            
            logger.info(f"Navigating to booking page: {self.base_url}")
            driver.get(self.base_url)
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Step 1: Login or proceed as guest
            if not await self._handle_login(driver, wait):
                raise Exception("Login failed")
            
            # Step 2: Navigate to tennis courts
            if not await self._navigate_to_tennis(driver, wait):
                raise Exception("Failed to navigate to tennis courts")
            
            # Step 3: Select date
            if not await self._select_date(driver, wait, date):
                raise Exception(f"Failed to select date: {date}")
            
            # Step 4: Select time slot
            if not await self._select_time(driver, wait, time):
                raise Exception(f"Failed to select time: {time}")
            
            # Step 5: Select court
            if not await self._select_court(driver, wait, court):
                raise Exception(f"Failed to select court: {court}")
            
            # Step 6: Confirm booking
            if not await self._confirm_booking(driver, wait):
                raise Exception("Failed to confirm booking")
            
            # Step 7: Get booking confirmation
            booking_ref = await self._get_booking_reference(driver, wait)
            
            # Take success screenshot
            screenshot_path = self._save_screenshot(
                driver,
                f"success_{user_id}_{booking_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            logger.info(f"Booking successful! Reference: {booking_ref}")
            
            return {
                'success': True,
                'message': 'Booking completed successfully',
                'booking_reference': booking_ref,
                'court': court,
                'screenshot': screenshot_path
            }
        
        except TimeoutException as e:
            logger.error(f"Timeout during booking: {e}")
            screenshot_path = self._save_screenshot(
                driver,
                f"timeout_{user_id}_{booking_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            return {
                'success': False,
                'error': 'Page timeout - please try again',
                'screenshot': screenshot_path
            }
        
        except NoSuchElementException as e:
            logger.error(f"Element not found: {e}")
            screenshot_path = self._save_screenshot(
                driver,
                f"element_error_{user_id}_{booking_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            return {
                'success': False,
                'error': 'Page layout changed - please contact support',
                'screenshot': screenshot_path
            }
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            screenshot_path = self._save_screenshot(
                driver,
                f"error_{user_id}_{booking_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            return {
                'success': False,
                'error': str(e),
                'screenshot': screenshot_path
            }
        
        finally:
            if driver:
                driver.quit()
    
    async def _handle_login(self, driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
        """Handle login process (if required)"""
        try:
            # Check if login credentials are provided
            if self.config.get('auto_login') and self.config.get('username'):
                logger.info("Attempting automatic login...")
                
                # Wait for login form
                username_field = wait.until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                password_field = driver.find_element(By.ID, "password")
                
                username_field.send_keys(self.config['username'])
                password_field.send_keys(self.config['password'])
                
                login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
                login_button.click()
                
                # Wait for login to complete
                await asyncio.sleep(3)
                
                logger.info("Login successful")
            else:
                logger.info("Proceeding without login (guest mode)")
            
            return True
        
        except Exception as e:
            logger.warning(f"Login handling: {e}")
            # If no login form, we're probably already logged in or it's guest mode
            return True
    
    async def _navigate_to_tennis(self, driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
        """Navigate to tennis court booking section"""
        try:
            logger.info("Navigating to tennis courts...")
            
            # Look for tennis/sports amenity link
            tennis_link = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//a[contains(text(), 'Tennis') or contains(text(), 'Sports')]"
                ))
            )
            tennis_link.click()
            
            await asyncio.sleep(2)
            return True
        
        except Exception as e:
            logger.error(f"Navigation to tennis courts failed: {e}")
            return False
    
    async def _select_date(self, driver: webdriver.Chrome, wait: WebDriverWait, date: str) -> bool:
        """Select booking date from calendar"""
        try:
            logger.info(f"Selecting date: {date}")
            
            # Click on date picker
            date_picker = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".date-picker, input[type='date']"))
            )
            date_picker.click()
            
            await asyncio.sleep(1)
            
            # Find and click the specific date
            date_element = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    f"//td[@data-date='{date}' or contains(@aria-label, '{date}')]"
                ))
            )
            date_element.click()
            
            await asyncio.sleep(1)
            return True
        
        except Exception as e:
            logger.error(f"Date selection failed: {e}")
            return False
    
    async def _select_time(self, driver: webdriver.Chrome, wait: WebDriverWait, time: str) -> bool:
        """Select time slot"""
        try:
            logger.info(f"Selecting time: {time}")
            
            # Find time slot button/element
            time_slot = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    f"//button[contains(text(), '{time}') or @data-time='{time}']"
                ))
            )
            
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView(true);", time_slot)
            await asyncio.sleep(0.5)
            
            time_slot.click()
            await asyncio.sleep(1)
            return True
        
        except Exception as e:
            logger.error(f"Time selection failed: {e}")
            return False
    
    async def _select_court(self, driver: webdriver.Chrome, wait: WebDriverWait, court: Optional[str]) -> bool:
        """Select specific court or first available"""
        try:
            if court and court.lower() != 'any':
                logger.info(f"Selecting court: {court}")
                
                court_element = wait.until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        f"//div[contains(@class, 'court') and contains(text(), '{court}')]"
                    ))
                )
                court_element.click()
            else:
                logger.info("Selecting first available court")
                
                # Select first available court
                available_court = wait.until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        ".court.available, .court:not(.booked)"
                    ))
                )
                available_court.click()
            
            await asyncio.sleep(1)
            return True
        
        except Exception as e:
            logger.error(f"Court selection failed: {e}")
            return False
    
    async def _confirm_booking(self, driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
        """Confirm the booking"""
        try:
            logger.info("Confirming booking...")
            
            # Click confirm/book button
            confirm_button = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(text(), 'Confirm') or contains(text(), 'Book')]"
                ))
            )
            confirm_button.click()
            
            await asyncio.sleep(3)
            
            # Handle any confirmation dialogs
            try:
                final_confirm = driver.find_element(
                    By.XPATH,
                    "//button[contains(text(), 'Yes') or contains(text(), 'Proceed')]"
                )
                final_confirm.click()
                await asyncio.sleep(2)
            except NoSuchElementException:
                pass  # No additional confirmation needed
            
            return True
        
        except Exception as e:
            logger.error(f"Booking confirmation failed: {e}")
            return False
    
    async def _get_booking_reference(self, driver: webdriver.Chrome, wait: WebDriverWait) -> str:
        """Extract booking reference number from confirmation page"""
        try:
            # Look for booking reference in success message
            ref_element = wait.until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//*[contains(text(), 'Booking') or contains(text(), 'Reference')]"
                ))
            )
            
            # Extract reference number (implementation depends on actual page structure)
            ref_text = ref_element.text
            
            # Try to extract a number/code from the text
            import re
            match = re.search(r'[A-Z0-9]{6,}', ref_text)
            if match:
                return match.group(0)
            
            return ref_text
        
        except Exception as e:
            logger.warning(f"Could not extract booking reference: {e}")
            return "N/A"
    
    def _save_screenshot(self, driver: webdriver.Chrome, filename: str) -> Optional[str]:
        """Save screenshot of current page"""
        try:
            if driver:
                filepath = self.screenshot_dir / f"{filename}.png"
                driver.save_screenshot(str(filepath))
                logger.info(f"Screenshot saved: {filepath}")
                return str(filepath)
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
        
        return None
    
    async def check_availability(self, date: str, time: str) -> Dict:
        """Check court availability without booking"""
        driver = None
        
        try:
            driver = self._create_driver()
            wait = WebDriverWait(driver, self.element_timeout)
            
            driver.get(self.base_url)
            await asyncio.sleep(2)
            
            # Navigate to availability view
            await self._navigate_to_tennis(driver, wait)
            await self._select_date(driver, wait, date)
            await self._select_time(driver, wait, time)
            
            # Check available courts
            available_courts = driver.find_elements(
                By.CSS_SELECTOR,
                ".court.available, .court:not(.booked)"
            )
            
            court_list = [court.text for court in available_courts]
            
            return {
                'available': len(court_list) > 0,
                'courts': court_list,
                'total': len(court_list)
            }
        
        except Exception as e:
            logger.error(f"Availability check failed: {e}")
            return {
                'available': None,
                'error': str(e)
            }
        
        finally:
            if driver:
                driver.quit()
