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
        # Initialize booking engine with Telegram callback for real-time updates
        self.booking_engine = BookingEngine(config, telegram_callback=self._send_booking_update)
        self.application = Application.builder().token(token).build()
        self._setup_handlers()
        # Store current booking context for updates
        self.current_booking_context = {}
    
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
            "🎾 I'm your Tennis/Paddel Court Booking Assistant for Villanova.\n\n"
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
        """Execute the actual booking process with smart availability checking"""
        # Store context for real-time updates
        self.current_booking_context['chat_id'] = query.message.chat_id
        
        await query.edit_message_text(
            "⏳ *Processing your booking...*\n\n"
            "This may take a few moments. I'll send updates as I progress.",
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
            # Execute booking with smart availability checking
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
                    f"{result.get('message', '')}\n\n"
                )
                
                if result.get('reference'):
                    success_msg += f"📝 Reference: `{result['reference']}`\n\n"
                
                success_msg += "Screenshot saved to your booking history."
                
                # Send screenshot if available
                if result.get('screenshot'):
                    try:
                        await query.message.reply_photo(
                            photo=open(result['screenshot'], 'rb'),
                            caption=success_msg,
                            parse_mode='Markdown'
                        )
                    except:
                        await query.message.reply_text(success_msg, parse_mode='Markdown')
                else:
                    await query.message.reply_text(success_msg, parse_mode='Markdown')
            
            else:
                # Booking failed - show detailed availability info
                self.db.update_booking_status(booking_id, 'failed', result.get('message'))
                
                error_msg = f"❌ *Booking Not Completed*\n\n{result.get('message', 'Unknown error')}\n\n"
                
                # Show available alternatives if provided
                if result.get('available_times'):
                    error_msg += "⏰ *Available Times:*\n"
                    for i, time_slot in enumerate(result['available_times'][:5], 1):
                        error_msg += f"  {i}. {time_slot}\n"
                    
                    if len(result['available_times']) > 5:
                        error_msg += f"  ... and {len(result['available_times']) - 5} more\n"
                    error_msg += "\n"
                
                if result.get('available_dates'):
                    error_msg += "📅 *Available Dates (Day Numbers):*\n"
                    dates_str = ", ".join(result['available_dates'][:10])
                    error_msg += f"  {dates_str}\n\n"
                
                error_msg += "💡 *Tip:* Try booking a different time or date."
                
                # Send screenshot if available
                if result.get('screenshot'):
                    try:
                        await query.message.reply_photo(
                            photo=open(result['screenshot'], 'rb'),
                            caption=error_msg,
                            parse_mode='Markdown'
                        )
                    except:
                        await query.message.reply_text(error_msg, parse_mode='Markdown')
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
        
        finally:
            # Clear booking context
            self.current_booking_context = {}
    
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
        token=config['8587310793:AAFRMgSmP-j602x6WunMl_4UCY0v_mZhpXU'],
        config=config
    )
    bot.run()
