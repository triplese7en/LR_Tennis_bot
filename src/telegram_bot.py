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
 CONFIRMING_BOOKING, SETTING_PREFERENCES) = range(5)


class TennisBookingBot:
    """Main bot class handling Telegram interactions"""
    
    def __init__(self, token: str, config: Dict):
        self.token = token
        self.config = config
        self.db = Database()
        self.booking_engine = BookingEngine(config)
        self.application = Application.builder().token(token).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all command and callback handlers"""
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("book", self.book_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("history", self.history_command))
        self.application.add_handler(CommandHandler("preferences", self.preferences_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message when /start is issued"""
        user = update.effective_user
        
        # Register user in database
        self.db.add_user(user.id, user.username or user.first_name)
        
        welcome_msg = (
            f"👋 Welcome {user.first_name}!\n\n"
            "🎾 I'm your Tennis Court Booking Assistant for Dubai Parks & Resorts.\n\n"
            "I can help you:\n"
            "• Book tennis courts automatically\n"
            "• Track your booking history\n"
            "• Save your preferences for quick bookings\n"
            "• Monitor booking status\n\n"
            "Use /book to start a new booking\n"
            "Use /help to see all available commands"
        )
        
        await update.message.reply_text(welcome_msg)
        logger.info(f"User {user.id} started the bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display help information"""
        help_text = (
            "📖 *Available Commands:*\n\n"
            "/book - Start a new court booking\n"
            "/status - Check ongoing booking status\n"
            "/history - View your booking history\n"
            "/preferences - Set default preferences\n"
            "/cancel - Cancel current operation\n"
            "/help - Show this help message\n\n"
            "💡 *Quick Tips:*\n"
            "• Set preferences to speed up bookings\n"
            "• The bot will retry automatically on failures\n"
            "• You'll receive screenshots of each booking attempt\n"
            "• Bookings are available 7 days in advance"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def book_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the booking process"""
        user_id = update.effective_user.id
        
        # Check for saved preferences
        prefs = self.db.get_user_preferences(user_id)
        
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
                callback_data=f"date_{date_str}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📅 *Select Booking Date:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # Date selection
        if data.startswith("date_"):
            selected_date = data.replace("date_", "")
            context.user_data['booking_date'] = selected_date
            await self._show_time_selection(query, selected_date)
        
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
        
        # Cancel booking
        elif data == "cancel_booking":
            context.user_data.clear()
            await query.edit_message_text("❌ Booking cancelled.")
    
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
        
        # Assuming 4 tennis courts
        for i in range(1, 5):
            keyboard.append([InlineKeyboardButton(
                f"Court {i}",
                callback_data=f"court_{i}"
            )])
        
        keyboard.append([InlineKeyboardButton(
            "🎲 Any Available Court",
            callback_data="court_any"
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
        date = booking_data.get('booking_date')
        time = booking_data.get('booking_time')
        court = booking_data.get('court_number', 'Any')
        
        confirmation_text = (
            "✅ *Confirm Your Booking:*\n\n"
            f"📅 Date: {date}\n"
            f"🕐 Time: {time}\n"
            f"🎾 Court: {court}\n\n"
            "Proceed with this booking?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_booking"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_booking")
            ],
            [InlineKeyboardButton("« Back", callback_data="back_to_court")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _execute_booking(self, query, booking_data: Dict, user_id: int):
        """Execute the actual booking process"""
        await query.edit_message_text(
            "⏳ *Processing your booking...*\n\n"
            "This may take a few moments. I'll notify you when complete.",
            parse_mode='Markdown'
        )
        
        # Record booking attempt
        booking_id = self.db.add_booking_attempt(
            user_id,
            booking_data['booking_date'],
            booking_data['booking_time'],
            booking_data.get('court_number', 'Any')
        )
        
        try:
            # Execute booking
            result = await self.booking_engine.book_court(
                date=booking_data['booking_date'],
                time=booking_data['booking_time'],
                court=booking_data.get('court_number'),
                user_id=user_id,
                booking_id=booking_id
            )
            
            if result['success']:
                # Update database
                self.db.update_booking_status(booking_id, 'success', result.get('message'))
                
                success_msg = (
                    "🎉 *Booking Successful!*\n\n"
                    f"📅 Date: {booking_data['booking_date']}\n"
                    f"🕐 Time: {booking_data['booking_time']}\n"
                    f"🎾 Court: {result.get('court', booking_data.get('court_number', 'N/A'))}\n\n"
                    f"Booking ID: `{result.get('booking_reference', 'N/A')}`\n\n"
                    "Screenshot saved to your booking history."
                )
                
                # Send screenshot if available
                if result.get('screenshot'):
                    await query.message.reply_photo(
                        photo=open(result['screenshot'], 'rb'),
                        caption=success_msg,
                        parse_mode='Markdown'
                    )
                else:
                    await query.message.reply_text(success_msg, parse_mode='Markdown')
            
            else:
                # Update database
                self.db.update_booking_status(booking_id, 'failed', result.get('error'))
                
                error_msg = (
                    "❌ *Booking Failed*\n\n"
                    f"Reason: {result.get('error', 'Unknown error')}\n\n"
                    f"Retry attempts: {result.get('retry_count', 0)}/{self.config.get('max_retries', 3)}\n\n"
                    "Please try again or contact support if the issue persists."
                )
                
                # Send screenshot if available
                if result.get('screenshot'):
                    await query.message.reply_photo(
                        photo=open(result['screenshot'], 'rb'),
                        caption=error_msg,
                        parse_mode='Markdown'
                    )
                else:
                    await query.message.reply_text(error_msg, parse_mode='Markdown')
        
        except Exception as e:
            logger.error(f"Booking execution error: {e}", exc_info=True)
            self.db.update_booking_status(booking_id, 'error', str(e))
            
            await query.message.reply_text(
                f"⚠️ *System Error*\n\n"
                f"An unexpected error occurred: {str(e)}\n\n"
                "Please try again later.",
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
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Tennis Booking Bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


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
