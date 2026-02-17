"""
Booking Scheduler — APScheduler-based job dispatcher with collision detection.

Uses APScheduler to fire scheduled bookings at the exact datetime they're due,
rather than polling. Includes collision detection to prevent double-booking the
same user/court/time.

The scheduler runs on Dubai time (UTC+4) to ensure midnight jobs fire correctly.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from threading import Lock

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
import pytz

logger = logging.getLogger(__name__)

# Dubai timezone
DUBAI_TZ = pytz.timezone('Asia/Dubai')


class BookingScheduler:
    """
    APScheduler-based scheduler with collision detection.
    Loads pending jobs from the database and schedules them to fire at their
    exact fire_at datetime. Prevents concurrent execution of overlapping bookings.
    """

    MAX_RETRIES_PER_JOB = 3   # attempts per scheduled booking

    def __init__(self, database, booking_engine_factory, telegram_app):
        """
        database               – Database instance
        booking_engine_factory – callable(user_credentials) → BookingEngine
        telegram_app           – python-telegram-bot Application (for sending messages)
        """
        self.db       = database
        self._factory = booking_engine_factory
        self._app     = telegram_app

        # Collision detection: lock + set of active (user_id, date, time, court) tuples
        self._lock   = Lock()
        self._active = set()

        # APScheduler (asyncio-compatible)
        self._scheduler = AsyncIOScheduler(timezone=DUBAI_TZ)

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def compute_fire_at(booking_date: str) -> str:
        """
        Return the ISO datetime string (Dubai time) at which to fire.
        = booking_date - 7 days, at 00:01:00 Dubai time
        """
        target = datetime.strptime(booking_date, "%Y-%m-%d")
        fire   = target - timedelta(days=7)
        # Localize to Dubai timezone
        fire_dubai = DUBAI_TZ.localize(datetime.combine(fire.date(), datetime.min.time()))
        fire_dubai = fire_dubai.replace(hour=0, minute=1, second=0, microsecond=0)
        # Return ISO string (APScheduler DateTrigger wants a datetime object, but we store ISO)
        return fire_dubai.isoformat()

    async def start(self):
        """Load pending jobs from DB and start the scheduler."""
        logger.info("📅 Booking scheduler starting (APScheduler + Dubai timezone)…")

        # Load all pending scheduled bookings and add them to APScheduler
        pending = self.db.get_due_scheduled_bookings()   # Actually gets ALL pending, not just due
        # Let me check this method name — it should be "get all pending" not "get due"
        # Actually we want a new method. Let me add it:
        pending = self._get_all_pending_jobs()

        for job in pending:
            fire_at_str = job['fire_at']
            try:
                # Parse ISO datetime string → Dubai-aware datetime
                fire_dt = datetime.fromisoformat(fire_at_str)
                if fire_dt.tzinfo is None:
                    fire_dt = DUBAI_TZ.localize(fire_dt)
                
                # Schedule this job
                self._scheduler.add_job(
                    func=self._execute,
                    trigger=DateTrigger(run_date=fire_dt),
                    args=[job],
                    id=f"sched_{job['id']}",
                    replace_existing=True,
                )
                logger.info(
                    f"📅 Scheduled booking #{job['id']} "
                    f"({job['booking_date']} {job['booking_time']}) "
                    f"→ fires at {fire_dt.strftime('%Y-%m-%d %H:%M %Z')}"
                )
            except Exception as e:
                logger.error(f"Could not schedule job {job['id']}: {e}")

        self._scheduler.start()
        logger.info(f"✅ Scheduler started with {len(pending)} pending job(s)")

    def stop(self, wait_for_jobs: bool = True):
        """
        Gracefully shutdown the scheduler.
        
        Args:
            wait_for_jobs: If True, waits for running jobs to complete before shutdown.
                          If False, cancels them immediately (not recommended).
        """
        if wait_for_jobs:
            logger.info("⏸️  Scheduler shutting down gracefully (waiting for jobs to complete)…")
            self._scheduler.shutdown(wait=True)
        else:
            logger.info("⏸️  Scheduler shutting down immediately")
            self._scheduler.shutdown(wait=False)
        logger.info("✅ Scheduler stopped")

    def add_job(self, job: dict):
        """
        Add a newly created scheduled booking to the running scheduler.
        Call this after saving a new scheduled booking to the database.
        """
        fire_at_str = job['fire_at']
        try:
            fire_dt = datetime.fromisoformat(fire_at_str)
            if fire_dt.tzinfo is None:
                fire_dt = DUBAI_TZ.localize(fire_dt)

            self._scheduler.add_job(
                func=self._execute,
                trigger=DateTrigger(run_date=fire_dt),
                args=[job],
                id=f"sched_{job['id']}",
                replace_existing=True,
            )
            logger.info(f"📅 Added job #{job['id']} → fires {fire_dt.strftime('%Y-%m-%d %H:%M %Z')}")
        except Exception as e:
            logger.error(f"Could not add job {job['id']}: {e}")

    def remove_job(self, job_id: int):
        """Remove a scheduled job from APScheduler (e.g. when user cancels)."""
        try:
            self._scheduler.remove_job(f"sched_{job_id}")
            logger.info(f"🗑️  Removed scheduled job #{job_id}")
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_all_pending_jobs(self) -> list:
        """Get all pending scheduled bookings (not just due ones)."""
        try:
            conn = self.db._get_connection()
            conn.row_factory = __import__('sqlite3').Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scheduled_bookings
                WHERE status = 'pending'
                ORDER BY fire_at ASC
            """)
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch all pending jobs: {e}")
            return []

    async def _execute(self, job: dict):
        """Execute a single scheduled booking with collision detection + retry logic."""
        job_id   = job['id']
        user_id  = job['user_id']
        date     = job['booking_date']
        time     = job['booking_time']
        court    = job['court']

        logger.info(f"🚀 Scheduled booking #{job_id} firing: {date} {time} {court} for user {user_id}")

        # ── Collision detection ───────────────────────────────────────────────
        collision_key = (user_id, date, time, court)
        with self._lock:
            if collision_key in self._active:
                logger.warning(
                    f"⚠️  Collision detected: booking #{job_id} already executing for "
                    f"user {user_id}, {date} {time} {court}. Skipping."
                )
                self.db.update_scheduled_booking_status(
                    job_id, 'failed',
                    "⚠️ Collision: Another identical booking was already in progress."
                )
                return
            self._active.add(collision_key)

        try:
            await self._notify(user_id,
                f"⏰ *Scheduled booking firing now!*\n"
                f"📅 {date}  ⏰ {time}  🎾 {court}\n"
                f"Booking in progress…"
            )

            # Fetch credentials
            creds = self.db.get_user_credentials(user_id)
            if not creds:
                msg = "❌ No credentials found. Use /login to add them."
                self.db.update_scheduled_booking_status(job_id, 'failed', msg)
                await self._notify(user_id, msg)
                return

            # ── Retry loop ─────────────────────────────────────────────────────
            result = None
            for attempt in range(1, self.MAX_RETRIES_PER_JOB + 1):
                attempt_count = self.db.increment_scheduled_booking_attempts(job_id)
                logger.info(f"Scheduled booking #{job_id} attempt {attempt}/{self.MAX_RETRIES_PER_JOB}")

                if attempt > 1:
                    await self._notify(user_id, f"⚠️ Retry {attempt}/{self.MAX_RETRIES_PER_JOB}…")

                try:
                    engine = self._factory(creds)
                    result = await engine.book_court(
                        date=date, time=time, court=court, enable_time_travel=False
                    )
                    if result.get('success'):
                        break   # Success — exit retry loop
                except Exception as e:
                    logger.error(f"Scheduled booking #{job_id} attempt {attempt} error: {e}")
                    result = {'success': False, 'message': str(e)}

                if attempt < self.MAX_RETRIES_PER_JOB:
                    await asyncio.sleep(5)   # Wait before retry

            # ── Update status & notify ─────────────────────────────────────────
            if result and result.get('success'):
                status = 'success'
                msg    = (
                    f"🎉 *Scheduled booking confirmed!*\n"
                    f"📅 {date}  ⏰ {time}  🎾 {court}\n"
                    f"📧 Check your email for confirmation."
                )
            else:
                status = 'failed'
                msg    = (
                    f"❌ *Scheduled booking failed* after {self.MAX_RETRIES_PER_JOB} attempts.\n"
                    f"📅 {date}  ⏰ {time}  🎾 {court}\n"
                    f"{result.get('message', 'Unknown error') if result else 'Unknown error'}"
                )

            self.db.update_scheduled_booking_status(job_id, status, msg)
            await self._notify(user_id, msg, screenshot=result.get('screenshot') if result else None)
            logger.info(f"Scheduled booking #{job_id} → {status}")

        finally:
            # Release collision lock
            with self._lock:
                self._active.discard(collision_key)

    async def _notify(self, user_id: int, text: str, screenshot: str = None):
        """Send a Telegram message (and optional screenshot) to the user."""
        try:
            await self._app.bot.send_message(
                chat_id=user_id, text=text, parse_mode='Markdown'
            )
            if screenshot:
                try:
                    with open(screenshot, 'rb') as f:
                        await self._app.bot.send_photo(chat_id=user_id, photo=f)
                except Exception as e:
                    logger.warning(f"Could not send screenshot: {e}")
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
