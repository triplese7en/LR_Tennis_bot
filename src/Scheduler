"""
Booking Scheduler
Runs as a background asyncio task inside the Telegram bot process.
Every 60 seconds it checks for scheduled bookings whose fire_at time has passed
and executes them automatically, notifying the user via Telegram.

Schedule logic
──────────────
The booking window opens 7 days ahead.  To guarantee we fire the moment
the slot becomes available we schedule at:

    fire_at = (target_date - 7 days) @ 00:01:00 local server time

e.g. to book Feb 26 → fire_at = Feb 19 00:01:00
"""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BookingScheduler:
    """
    Lightweight scheduler that lives inside the bot process.
    Call start() once; it loops forever until the process exits.
    """

    POLL_INTERVAL = 60          # seconds between checks
    MAX_RETRIES   = 5           # attempts per scheduled booking

    def __init__(self, database, booking_engine_factory, telegram_app):
        """
        database              – Database instance
        booking_engine_factory – callable(user_credentials) → BookingEngine
        telegram_app          – python-telegram-bot Application (for sending messages)
        """
        self.db       = database
        self._factory = booking_engine_factory
        self._app     = telegram_app
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def compute_fire_at(booking_date: str) -> str:
        """
        Return the ISO datetime string at which the scheduler should fire.
        = booking_date - 7 days, at 00:01:00
        """
        target = datetime.strptime(booking_date, "%Y-%m-%d")
        fire   = target - timedelta(days=7)
        return fire.strftime("%Y-%m-%d 00:01:00")

    async def start(self):
        """Start the polling loop (call with asyncio.create_task)."""
        self._running = True
        logger.info("📅 Booking scheduler started")
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")
            await asyncio.sleep(self.POLL_INTERVAL)

    def stop(self):
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _tick(self):
        """Check for due bookings and execute them."""
        due = self.db.get_due_scheduled_bookings()
        if not due:
            return

        logger.info(f"⏰ Scheduler: {len(due)} booking(s) due")

        for job in due:
            # Mark as executing immediately so concurrent ticks don't double-fire
            self.db.update_scheduled_booking_status(job['id'], 'executing')
            asyncio.create_task(self._execute(job))

    async def _execute(self, job: dict):
        """Execute a single scheduled booking and notify the user."""
        job_id   = job['id']
        user_id  = job['user_id']
        date     = job['booking_date']
        time     = job['booking_time']
        court    = job['court']

        logger.info(f"🚀 Executing scheduled booking {job_id}: {date} {time} {court} for user {user_id}")

        await self._notify(user_id,
            f"⏰ *Scheduled booking firing now!*\n"
            f"📅 {date}  ⏰ {time}  🎾 {court}\n"
            f"Booking in progress…"
        )

        # Fetch credentials
        creds = self.db.get_user_credentials(user_id)
        if not creds:
            msg = "❌ Scheduled booking failed: no credentials found. Use /login."
            self.db.update_scheduled_booking_status(job_id, 'failed', msg)
            await self._notify(user_id, msg)
            return

        # Build engine and run
        try:
            engine = self._factory(creds)
            result = await engine.book_court(
                date=date,
                time=time,
                court=court,
                enable_time_travel=False,   # window is now open, no tricks needed
            )
        except Exception as e:
            msg = f"❌ Scheduled booking error: {e}"
            logger.error(msg)
            self.db.update_scheduled_booking_status(job_id, 'failed', msg)
            await self._notify(user_id, msg)
            return

        if result.get('success'):
            status = 'success'
            msg    = (
                f"🎉 *Scheduled booking confirmed!*\n"
                f"📅 {date}  ⏰ {time}  🎾 {court}\n"
                f"📧 Check your email for confirmation."
            )
        else:
            status = 'failed'
            msg    = (
                f"❌ *Scheduled booking failed* after {self.MAX_RETRIES} attempts.\n"
                f"📅 {date}  ⏰ {time}  🎾 {court}\n"
                f"{result.get('message', '')}"
            )

        self.db.update_scheduled_booking_status(job_id, status, msg)
        await self._notify(user_id, msg, screenshot=result.get('screenshot'))
        logger.info(f"Scheduled booking {job_id} → {status}")

    async def _notify(self, user_id: int, text: str, screenshot: str = None):
        """Send a Telegram message (and optional screenshot) to the user."""
        try:
            await self._app.bot.send_message(
                chat_id    = user_id,
                text       = text,
                parse_mode = 'Markdown',
            )
            if screenshot:
                try:
                    with open(screenshot, 'rb') as f:
                        await self._app.bot.send_photo(chat_id=user_id, photo=f)
                except Exception as e:
                    logger.warning(f"Could not send screenshot: {e}")
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
