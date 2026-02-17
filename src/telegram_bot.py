"""
Telegram Bot for Tennis Court Booking Automation
Handles user interactions, commands, and booking requests
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from booking_engine import BookingEngine
from database import Database
from scheduler import BookingScheduler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
(SELECTING_DATE, SELECTING_TIME, SELECTING_COURT, 
 CONFIRMING_BOOKING, SETTING_PREFERENCES, ASKING_EMAIL, ASKING_PASSWORD) = range(7)


class TennisBookingBot:
    """Main bot class handling Telegram interactions"""
    
    # Available court names
    AVAILABLE_COURTS = [
        "Amaranta B",
        "Amaranta 3",
        "La Rosa 4",
        "Paddle Court 1",
        "Paddle Court 2"
    ]
    
    def __init__(self, token: str, config: Dict):
        self.token = token
        self.config = config
        self.db = Database()
        self.application = Application.builder().token(token).build()
        self._setup_handlers()
        self.current_booking_context = {}

        # Scheduler: fires saved bookings the moment the 7-day window opens
        def _engine_factory(user_credentials):
            return BookingEngine(
                config=self.config,
                telegram_callback=None,   # scheduler sends its own messages
                user_credentials=user_credentials,
            )

        self.scheduler = BookingScheduler(
            database=self.db,
            booking_engine_factory=_engine_factory,
            telegram_app=self.application,
        )
    
    async def _send_booking_update(self, message: str):
        """Send real-time booking updates to the user"""
        if 'chat_id' in self.current_booking_context:
            try:
                await self.application.bot.send_message(
                    chat_id=self.current_booking_context['chat_id'],
                    text=message
                )
            except Exception as e:
                logger.error(f"Could not send booking update: {e}")
    
    def _setup_handlers(self):
        """Setup all command and callback handlers"""
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("book", self.book_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("history", self.history_command))
        self.application.add_handler(CommandHandler("preferences", self.preferences_command))
        self.application.add_handler(CommandHandler("login", self.login_command))
        self.application.add_handler(CommandHandler("logout", self.logout_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))
        self.application.add_handler(CommandHandler("scheduled", self.scheduled_command))
        
        # Message handler for credential input
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_credential_input))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message when /start is issued"""
        user = update.effective_user
        user_id = user.id
        
        # Register user in database
        self.db.add_user(user_id, user.username or user.first_name)
        
        # Check if credentials are set
        creds = self.db.get_user_credentials(user_id)
        
        welcome_msg = f"👋 Welcome {user.first_name}!\n\n"
        welcome_msg += "🎾 I'm your Tennis Court Booking Assistant for Dubai Properties.\n\n"
        
        if creds:
            welcome_msg += (
                "✅ Your login is set up and ready!\n\n"
                "I can help you:\n"
                "• Book tennis courts automatically\n"
                "• Track your booking history\n"
                "• Save your preferences for quick bookings\n"
                "• Monitor booking status\n\n"
                "Use /book to start a new booking\n"
                "Use /help to see all available commands"
            )
        else:
            welcome_msg += (
                "⚠️ *First Time Setup Required*\n\n"
                "Before you can book courts, you need to add your Dubai Properties account credentials.\n\n"
                "👉 Use /login to set up your account\n\n"
                "After setup, you'll be able to:\n"
                "• Book courts automatically\n"
                "• Save booking preferences\n"
                "• Track your history\n\n"
                "Use /help to see all commands"
            )
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
        logger.info(f"User {user_id} started the bot (credentials: {'yes' if creds else 'no'})")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display help information"""
        user_id = update.effective_user.id
        creds = self.db.get_user_credentials(user_id)
        
        help_text = "📖 *Available Commands:*\n\n"
        
        if creds:
            help_text += (
                "*Booking:*\n"
                "/book - Start a new court booking\n"
                "/status - Check ongoing booking status\n"
                "/history - View your booking history\n"
                "/preferences - Set default preferences\n\n"
                "*Account:*\n"
                f"/logout - Remove credentials\n\n"
                "*Other:*\n"
                "/cancel - Cancel current operation\n"
                "/help - Show this help message\n\n"
                "💡 *Quick Tips:*\n"
                "• Set preferences to speed up bookings\n"
                "• The bot will retry automatically on failures\n"
                "• You'll receive screenshots of each booking attempt\n"
                "• Bookings are available 7 days in advance\n\n"
                f"✅ Logged in as: `{creds['email']}`"
            )
        else:
            help_text += (
                "*Setup:*\n"
                "/login - Add your Dubai Properties credentials\n\n"
                "*Other:*\n"
                "/help - Show this help message\n\n"
                "⚠️ You need to use /login before you can book courts.\n\n"
                "After login, you'll have access to:\n"
                "• /book - Automated booking\n"
                "• /preferences - Save favorites\n"
                "• /history - View past bookings"
            )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def book_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the booking process"""
        user_id = update.effective_user.id
        prefs = self.db.get_user_preferences(user_id)
        
        text, keyboard = self._build_booking_menu(prefs)
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    def _build_booking_menu(self, prefs=None):
        """Build the booking date selection menu (used by both command and callbacks)"""
        keyboard = []
        
        # Add "Use Saved Preferences" button if available
        if prefs:
            keyboard.append([InlineKeyboardButton(
                "⚡ Use Saved Preferences",
                callback_data="use_preferences"
            )])
        
        # Add date selection buttons (next 7 days)
        today = datetime.now()
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            display_date = date.strftime("%a, %b %d")
            
            if i == 0:
                display_date = f"Today ({display_date})"
            elif i == 1:
                display_date = f"Tomorrow ({display_date})"
            
            keyboard.append([InlineKeyboardButton(
                display_date,
                callback_data=f"date_{date_str}_normal"
            )])
        
        # Separator + future scheduling option
        keyboard.append([InlineKeyboardButton(
            "─────────────────",
            callback_data="separator"
        )])
        keyboard.append([InlineKeyboardButton(
            "⏰ Schedule a Future Booking (8+ days)",
            callback_data="schedule_booking"
        )])
        
        text = (
            "📅 *Select Booking Date:*\n\n"
            "Standard: Next 7 days (books immediately)\n"
            "⏰ Schedule: 8+ days ahead (fires at midnight automatically)"
        )
        
        return text, keyboard
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # Date selection
        if data.startswith("date_"):
            if data == "date_advanced":
                await self._show_advanced_booking_dates(query)
            else:
                parts = data.replace("date_", "").split("_")
                selected_date = parts[0]
                booking_mode  = parts[1] if len(parts) > 1 else "normal"
                context.user_data['booking_date']       = selected_date
                context.user_data['scheduled_booking']  = False
                await self._show_time_selection(query, selected_date)

        elif data == "schedule_booking":
            await self._show_schedule_dates(query)

        elif data.startswith("sched_date_"):
            selected_date = data.replace("sched_date_", "")
            context.user_data['booking_date']      = selected_date
            context.user_data['scheduled_booking'] = True
            await self._show_time_selection(query, selected_date)

        elif data.startswith("sched_cancel_"):
            sched_id = int(data.replace("sched_cancel_", ""))
            cancelled = self.db.cancel_scheduled_booking(sched_id, user_id)
            if cancelled:
                self.scheduler.remove_job(sched_id)
                await query.edit_message_text(f"✅ Scheduled booking #{sched_id} cancelled.")
            else:
                await query.edit_message_text(f"❌ Could not cancel booking #{sched_id}.")
        
        # Separator (do nothing)
        elif data == "separator":
            await query.answer("─────────", show_alert=False)
        
        # Time selection
        elif data.startswith("time_"):
            selected_time = data.replace("time_", "")
            context.user_data['booking_time'] = selected_time
            await self._show_court_selection(query)
        
        # Court selection
        elif data.startswith("court_"):
            court_number = data.replace("court_", "")
            context.user_data['court_number'] = court_number
            await self._show_booking_confirmation(query, context.user_data)
        
        # Confirm booking
        elif data == "confirm_booking":
            await self._execute_booking(query, context.user_data, user_id)
        
        # Use saved preferences
        elif data == "use_preferences":
            await self._book_with_preferences(query, user_id)
        
        # Preferences - View current
        elif data == "pref_view":
            await self._show_current_preferences(query, user_id)
        
        # Preferences - Set time
        elif data == "pref_time":
            await self._set_preferred_time(query, user_id)
        
        # Preferences - Set court
        elif data == "pref_court":
            await self._set_preferred_court(query, user_id)
        
        # Preferences - Save time selection
        elif data.startswith("savetime_"):
            selected_time = data.replace("savetime_", "")
            await self._save_time_preference(query, user_id, selected_time)
        
        # Preferences - Save court selection
        elif data.startswith("savecourt_"):
            court_number = data.replace("savecourt_", "")
            await self._save_court_preference(query, user_id, court_number)
        
        # Back to preferences menu
        elif data == "back_to_prefs":
            keyboard = [
                [InlineKeyboardButton("Set Preferred Time", callback_data="pref_time")],
                [InlineKeyboardButton("Set Preferred Court", callback_data="pref_court")],
                [InlineKeyboardButton("View Current Preferences", callback_data="pref_view")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "⚙️ *Booking Preferences*\n\n"
                "Set your default preferences for faster bookings:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        # Cancel booking
        elif data == "cancel_booking":
            context.user_data.clear()
            await query.edit_message_text("❌ Booking cancelled.")
        
        # Back navigation
        elif data == "back_to_booking":
            prefs = self.db.get_user_preferences(user_id)
            text, keyboard = self._build_booking_menu(prefs)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "back_to_date":
            prefs = self.db.get_user_preferences(user_id)
            text, keyboard = self._build_booking_menu(prefs)
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "back_to_time":
            if 'booking_date' in context.user_data:
                await self._show_time_selection(query, context.user_data['booking_date'])
            else:
                prefs = self.db.get_user_preferences(user_id)
                text, keyboard = self._build_booking_menu(prefs)
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        
        elif data == "back_to_court":
            if 'booking_time' in context.user_data:
                await self._show_court_selection(query)
            else:
                prefs = self.db.get_user_preferences(user_id)
                text, keyboard = self._build_booking_menu(prefs)
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
    
    async def _show_time_selection(self, query, date: str):
        """Show available time slots"""
        keyboard = []
        
        # Available time slots (6 AM to 10 PM)
        time_slots = [
            "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
            "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
            "18:00", "19:00", "20:00", "21:00", "22:00"
        ]
        
        # Create buttons in rows of 3
        for i in range(0, len(time_slots), 3):
            row = []
            for time_slot in time_slots[i:i+3]:
                row.append(InlineKeyboardButton(
                    time_slot,
                    callback_data=f"time_{time_slot}"
                ))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_date")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🕐 *Select Time Slot:*\n📅 Date: {date}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_court_selection(self, query):
        """Show available courts"""
        keyboard = []
        
        # Use class constant for court names
        for court in self.AVAILABLE_COURTS:
            keyboard.append([InlineKeyboardButton(
                f"🎾 {court}",
                callback_data=f"court_{court}"
            )])
        
        keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_time")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎾 *Select Court:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_booking_confirmation(self, query, booking_data: Dict):
        """Show booking confirmation screen"""
        date  = booking_data.get('booking_date')
        time  = booking_data.get('booking_time')
        court = booking_data.get('court_number', 'Any')
        is_scheduled = booking_data.get('scheduled_booking', False)

        from scheduler import BookingScheduler
        if is_scheduled:
            fire_at  = BookingScheduler.compute_fire_at(date)
            fire_dt  = datetime.strptime(fire_at, "%Y-%m-%d %H:%M:%S")
            fire_str = fire_dt.strftime("%a %b %d at 00:01")
            mode_txt = (
                f"\n\n⏰ *Scheduled Mode*\n"
                f"Will book automatically on {fire_str}\n"
                f"when the 7-day window opens."
            )
            confirm_label = "⏰ Schedule It"
        else:
            mode_txt      = ""
            confirm_label = "✅ Confirm"

        confirmation_text = (
            f"{'⏰ Confirm Scheduled Booking' if is_scheduled else '✅ Confirm Your Booking'}:\n\n"
            f"📅 Date:  {date}\n"
            f"🕐 Time:  {time}\n"
            f"🎾 Court: {court}"
            f"{mode_txt}\n\n"
            f"Proceed?"
        )

        keyboard = [
            [
                InlineKeyboardButton(confirm_label, callback_data="confirm_booking"),
                InlineKeyboardButton("❌ Cancel",    callback_data="cancel_booking"),
            ],
            [InlineKeyboardButton("« Back", callback_data="back_to_court")],
        ]

        await query.edit_message_text(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _show_advanced_booking_dates(self, query):
        """Show dates 8-14 days in the future (kept for backward compat)"""
        await self._show_schedule_dates(query)

    async def _show_schedule_dates(self, query):
        """Show dates 8-21 days ahead for scheduled bookings"""
        today    = datetime.now()
        keyboard = []

        for i in range(8, 22):
            date        = today + timedelta(days=i)
            date_str    = date.strftime("%Y-%m-%d")
            display     = date.strftime("%a, %b %d")
            fire        = date - timedelta(days=7)
            fire_str    = fire.strftime("%b %d 00:01")
            keyboard.append([InlineKeyboardButton(
                f"📅 {display}  (fires {fire_str})",
                callback_data=f"sched_date_{date_str}"
            )])

        keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_booking")])

        await query.edit_message_text(
            "⏰ *Schedule a Future Booking*\n\n"
            "Pick a date. The bot will automatically book it\n"
            "at 00:01 on the day the window opens.\n\n"
            "You'll get a Telegram notification when it's done.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def _execute_booking(self, query, booking_data: Dict, user_id: int):
        """Execute an immediate booking OR save a scheduled one."""

        user_creds = self.db.get_user_credentials(user_id)
        if not user_creds:
            await query.edit_message_text(
                "⚠️ *No Login Credentials Found*\n\n"
                "Use /login to add your Dubai Properties credentials first.",
                parse_mode='Markdown'
            )
            return

        # ── Scheduled booking path ────────────────────────────────────────────
        if booking_data.get('scheduled_booking'):
            from scheduler import BookingScheduler
            date   = booking_data['booking_date']
            time   = booking_data['booking_time']
            court  = booking_data.get('court_number', 'Any')
            fire_at = BookingScheduler.compute_fire_at(date)
            fire_dt = datetime.strptime(fire_at, "%Y-%m-%d %H:%M:%S")

            sched_id = self.db.add_scheduled_booking(
                user_id=user_id,
                booking_date=date,
                booking_time=time,
                court=court,
                fire_at=fire_at,
            )

            if sched_id:
                # Add to APScheduler immediately
                self.scheduler.add_job({
                    'id': sched_id,
                    'user_id': user_id,
                    'booking_date': date,
                    'booking_time': time,
                    'court': court,
                    'fire_at': fire_at,
                })

                await query.edit_message_text(
                    f"⏰ *Booking Scheduled!*\n\n"
                    f"📅 {date}  🕐 {time}  🎾 {court}\n\n"
                    f"I'll automatically book this on\n"
                    f"*{fire_dt.strftime('%A, %B %d at 00:01')}*\n"
                    f"the moment the 7-day window opens.\n\n"
                    f"You'll get a Telegram notification when it's done.\n"
                    f"Use /scheduled to view or cancel pending bookings.",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("❌ Failed to save scheduled booking. Try again.")
            return

        # ── Immediate booking path ────────────────────────────────────────────
        self.current_booking_context['chat_id'] = query.message.chat_id

        await query.edit_message_text(
            "⏳ *Processing your booking…*\n\nI'll send updates as I progress.",
            parse_mode='Markdown'
        )

        booking_id = self.db.add_booking_attempt(
            user_id,
            booking_data['booking_date'],
            booking_data['booking_time'],
            booking_data.get('court_number', 'Any')
        )

        try:
            booking_engine = BookingEngine(
                self.config,
                telegram_callback=self._send_booking_update,
                user_credentials=user_creds,
            )

            result = await booking_engine.book_court(
                date=booking_data['booking_date'],
                time=booking_data['booking_time'],
                court=booking_data.get('court_number'),
                user_id=user_id,
                booking_id=booking_id,
                enable_time_travel=False,
            )

            if result['success']:
                self.db.update_booking_status(booking_id, 'success', result.get('message'))
                success_msg = f"🎉 *Booking Successful!*\n\n{result.get('message', '')}"
                if result.get('screenshot'):
                    try:
                        with open(result['screenshot'], 'rb') as photo:
                            await self.application.bot.send_photo(
                                chat_id=query.message.chat_id, photo=photo,
                                caption=success_msg, parse_mode='Markdown'
                            )
                    except Exception:
                        await self.application.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=success_msg, parse_mode='Markdown'
                        )
                else:
                    await self.application.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=success_msg, parse_mode='Markdown'
                    )
            else:
                self.db.update_booking_status(booking_id, 'failed', result.get('message'))
                await self.application.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"❌ *Booking Failed*\n\n{result.get('message', 'Unknown error')}",
                    parse_mode='Markdown'
                )
                if result.get('screenshot'):
                    try:
                        with open(result['screenshot'], 'rb') as photo:
                            await self.application.bot.send_photo(
                                chat_id=query.message.chat_id, photo=photo
                            )
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Booking execution error: {e}")
            self.db.update_booking_status(booking_id, 'error', str(e))
            await self.application.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"❌ *Booking Error*\n\n{str(e)}",
                parse_mode='Markdown'
            )
            
    async def _book_with_preferences(self, query, user_id: int):
        """Book using saved user preferences"""
        prefs = self.db.get_user_preferences(user_id)
        
        if not prefs:
            await query.edit_message_text("❌ No saved preferences found.")
            return
        
        booking_data = {
            'booking_date': prefs['preferred_date'],
            'booking_time': prefs['preferred_time'],
            'court_number': prefs['preferred_court']
        }
        
        await self._execute_booking(query, booking_data, user_id)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current booking status"""
        user_id = update.effective_user.id
        
        # Get latest booking
        latest = self.db.get_latest_booking(user_id)
        
        if not latest:
            await update.message.reply_text("No active bookings found.")
            return
        
        status_emoji = {
            'pending': '⏳',
            'success': '✅',
            'failed': '❌',
            'error': '⚠️'
        }
        
        status_msg = (
            f"{status_emoji.get(latest['status'], '❓')} *Booking Status*\n\n"
            f"📅 Date: {latest['booking_date']}\n"
            f"🕐 Time: {latest['booking_time']}\n"
            f"🎾 Court: {latest['court_number']}\n"
            f"Status: {latest['status'].upper()}\n"
            f"Created: {latest['created_at']}\n\n"
        )
        
        if latest.get('message'):
            status_msg += f"Message: {latest['message']}"
        
        await update.message.reply_text(status_msg, parse_mode='Markdown')
    
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show booking history"""
        user_id = update.effective_user.id
        
        history = self.db.get_booking_history(user_id, limit=10)
        
        if not history:
            await update.message.reply_text("No booking history found.")
            return
        
        history_msg = "📜 *Your Booking History* (Last 10)\n\n"
        
        for booking in history:
            status_emoji = {
                'success': '✅',
                'failed': '❌',
                'error': '⚠️',
                'pending': '⏳'
            }
            
            history_msg += (
                f"{status_emoji.get(booking['status'], '❓')} "
                f"{booking['booking_date']} @ {booking['booking_time']}\n"
                f"   Court: {booking['court_number']} | "
                f"Status: {booking['status']}\n\n"
            )
        
        await update.message.reply_text(history_msg, parse_mode='Markdown')
    
    async def preferences_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set user preferences for quick booking"""
        keyboard = [
            [InlineKeyboardButton("Set Preferred Time", callback_data="pref_time")],
            [InlineKeyboardButton("Set Preferred Court", callback_data="pref_court")],
            [InlineKeyboardButton("View Current Preferences", callback_data="pref_view")],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚙️ *Booking Preferences*\n\n"
            "Set your default preferences for faster bookings:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current operation"""
        context.user_data.clear()
        await update.message.reply_text("Operation cancelled. Use /book to start again.")
    
    async def _show_current_preferences(self, query, user_id: int):
        """Show user's current preferences"""
        prefs = self.db.get_user_preferences(user_id)
        
        if not prefs:
            await query.edit_message_text(
                "❌ No preferences saved yet.\n\n"
                "Use the buttons above to set your preferences."
            )
            return
        
        pref_msg = (
            "⚙️ *Current Preferences*\n\n"
            f"🕐 Preferred Time: {prefs.get('preferred_time', 'Not set')}\n"
            f"🎾 Preferred Court: {prefs.get('preferred_court', 'Not set')}\n\n"
            "Use /preferences to update these settings."
        )
        
        await query.edit_message_text(pref_msg, parse_mode='Markdown')
    
    async def _set_preferred_time(self, query, user_id: int):
        """Show time selection for preferences"""
        keyboard = []
        
        # Available time slots
        time_slots = [
            "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
            "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
            "18:00", "19:00", "20:00", "21:00", "22:00"
        ]
        
        # Create buttons in rows of 3
        for i in range(0, len(time_slots), 3):
            row = []
            for time_slot in time_slots[i:i+3]:
                row.append(InlineKeyboardButton(
                    time_slot,
                    callback_data=f"savetime_{time_slot}"
                ))
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_prefs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🕐 *Select Your Preferred Time:*\n\n"
            "This will be used for quick bookings.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _set_preferred_court(self, query, user_id: int):
        """Show court selection for preferences"""
        keyboard = []
        
        # Use class constant for court names
        for court in self.AVAILABLE_COURTS:
            keyboard.append([InlineKeyboardButton(
                f"🎾 {court}",
                callback_data=f"savecourt_{court}"
            )])
        
        keyboard.append([InlineKeyboardButton("« Back", callback_data="back_to_prefs")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎾 *Select Your Preferred Court:*\n\n"
            "This will be used for quick bookings.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _save_time_preference(self, query, user_id: int, time: str):
        """Save the preferred time"""
        success = self.db.set_user_preferences(
            user_id,
            preferred_time=time
        )
        
        if success:
            await query.edit_message_text(
                f"✅ *Preference Saved!*\n\n"
                f"🕐 Preferred Time: {time}\n\n"
                f"You can now use 'Use Saved Preferences' when booking.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ Failed to save preference. Please try again."
            )
    
    async def _save_court_preference(self, query, user_id: int, court: str):
        """Save the preferred court"""
        success = self.db.set_user_preferences(
            user_id,
            preferred_court=court
        )
        
        if success:
            await query.edit_message_text(
                f"✅ *Preference Saved!*\n\n"
                f"🎾 Preferred Court: {court}\n\n"
                f"You can now use 'Use Saved Preferences' when booking.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ Failed to save preference. Please try again."
            )
    
    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start credential setup process"""
        user_id = update.effective_user.id
        
        # Check if credentials already exist
        creds = self.db.get_user_credentials(user_id)
        
        if creds:
            await update.message.reply_text(
                "🔐 *Credentials Already Saved*\n\n"
                "You already have login credentials stored.\n\n"
                "If you want to update them:\n"
                "1. Use /logout to remove current credentials\n"
                "2. Then use /login again to add new ones",
                parse_mode='Markdown'
            )
            return
        
        # Start credential setup
        context.user_data['awaiting_credential'] = 'email'
        
        await update.message.reply_text(
            "🔐 *Login Setup*\n\n"
            "Let's set up your Dubai Properties account for automated bookings.\n\n"
            "Please enter your Dubai Properties account *email address*:",
            parse_mode='Markdown'
        )
        
        logger.info(f"User {user_id} started login setup")
    
    async def handle_credential_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle email/password input during login setup"""
        user_id = update.effective_user.id
        
        # Check if we're waiting for credentials
        if 'awaiting_credential' not in context.user_data:
            return  # Ignore if not in credential setup mode
        
        if context.user_data['awaiting_credential'] == 'email':
            # User sent email
            email = update.message.text.strip()
            context.user_data['temp_email'] = email
            context.user_data['awaiting_credential'] = 'password'
            
            await update.message.reply_text(
                f"✅ Email saved: `{email}`\n\n"
                f"Now please enter your Dubai Properties account *password*:\n\n"
                f"⚠️ Your password will be stored securely in the database.",
                parse_mode='Markdown'
            )
            logger.info(f"User {user_id} provided email for login")
        
        elif context.user_data['awaiting_credential'] == 'password':
            # User sent password
            password = update.message.text.strip()
            email = context.user_data.get('temp_email')
            
            if not email:
                await update.message.reply_text(
                    "❌ Error: Email not found. Please start over with /login"
                )
                context.user_data.pop('awaiting_credential', None)
                context.user_data.pop('temp_email', None)
                return
            
            # Save credentials
            success = self.db.save_user_credentials(user_id, email, password)
            
            if success:
                await update.message.reply_text(
                    "✅ *Credentials Saved Successfully!*\n\n"
                    "Your Dubai Properties login details are now stored securely.\n\n"
                    "You can now use:\n"
                    "/book - Start automated booking\n"
                    "/preferences - Set favorite court/time\n"
                    "/logout - Remove credentials anytime\n\n"
                    "🎾 Ready to book your court!",
                    parse_mode='Markdown'
                )
                logger.info(f"User {user_id} credentials saved successfully")
            else:
                await update.message.reply_text(
                    "❌ *Failed to Save Credentials*\n\n"
                    "There was an error saving your login details.\n\n"
                    "Please try /login again.",
                    parse_mode='Markdown'
                )
                logger.error(f"Failed to save credentials for user {user_id}")
            
            # Clean up
            context.user_data.pop('awaiting_credential', None)
            context.user_data.pop('temp_email', None)
    
    async def logout_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove saved credentials"""
        user_id = update.effective_user.id
        
        # Check if credentials exist
        creds = self.db.get_user_credentials(user_id)
        
        if not creds:
            await update.message.reply_text(
                "ℹ️ *No Credentials Found*\n\n"
                "You don't have any saved login credentials.\n\n"
                "Use /login to set up your account.",
                parse_mode='Markdown'
            )
            return
        
        # Delete credentials
        success = self.db.delete_user_credentials(user_id)
        
        if success:
            await update.message.reply_text(
                "✅ *Credentials Removed*\n\n"
                f"Your login details (email: `{creds['email']}`) have been deleted from the database.\n\n"
                f"Your booking history and preferences are still saved.\n\n"
                f"Use /login to add credentials again when ready.",
                parse_mode='Markdown'
            )
            logger.info(f"User {user_id} logged out (credentials removed)")
        else:
            await update.message.reply_text(
                "❌ *Failed to Remove Credentials*\n\n"
                "There was an error removing your login details.\n\n"
                "Please try /logout again.",
                parse_mode='Markdown'
            )
            logger.error(f"Failed to delete credentials for user {user_id}")
    
    async def scheduled_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show and manage pending scheduled bookings."""
        user_id = update.effective_user.id
        jobs    = self.db.get_scheduled_bookings_for_user(user_id)

        if not jobs:
            await update.message.reply_text(
                "📭 *No Scheduled Bookings*\n\n"
                "Use /book → ⏰ Schedule a Future Booking to set one up.",
                parse_mode='Markdown'
            )
            return

        text = "⏰ *Your Scheduled Bookings:*\n\n"
        keyboard = []
        for job in jobs:
            fire_dt  = datetime.strptime(job['fire_at'], "%Y-%m-%d %H:%M:%S")
            fire_str = fire_dt.strftime("%a %b %d at 00:01")
            attempts = job.get('attempt_count', 0)
            attempts_str = f" (tried {attempts}x)" if attempts > 0 else ""
            text += (
                f"*#{job['id']}* — 📅 {job['booking_date']}  "
                f"🕐 {job['booking_time']}  🎾 {job['court']}{attempts_str}\n"
                f"  ⏰ Fires: {fire_str}\n\n"
            )
            keyboard.append([InlineKeyboardButton(
                f"❌ Cancel #{job['id']} ({job['booking_date']})",
                callback_data=f"sched_cancel_{job['id']}"
            )])

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    def run(self):
        """Start the bot and the background scheduler."""
        import asyncio
        import signal

        async def _run():
            # Initialize app
            await self.application.initialize()
            await self.application.start()
            
            # Start scheduler as background task
            asyncio.create_task(self.scheduler.start())
            logger.info("✅ Scheduler started")
            
            # Start polling
            await self.application.updater.start_polling(allowed_updates=["message", "callback_query"])
            logger.info("✅ Bot started and polling")
            
            # Keep running until signal
            stop_event = asyncio.Event()
            
            def signal_handler(sig, frame):
                logger.info(f"Received signal {sig}, initiating graceful shutdown…")
                stop_event.set()
            
            # Register signal handlers
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            await stop_event.wait()
            
            # Graceful shutdown
            logger.info("⏸️  Stopping bot…")
            await self.application.updater.stop()
            await self.application.stop()
            
            logger.info("⏸️  Stopping scheduler (waiting for jobs to complete)…")
            self.scheduler.stop(wait_for_jobs=True)
            
            await self.application.shutdown()
            logger.info("✅ Shutdown complete")

        logger.info("Starting Tennis Booking Bot…")
        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            logger.info("Bot interrupted")
        except Exception as e:
            logger.error(f"Bot error: {e}", exc_info=True)


if __name__ == "__main__":
    # Load configuration
    with open('config/config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize and run bot
    bot = TennisBookingBot(
        token=config['telegram_token'],
        config=config
    )
    bot.run()
