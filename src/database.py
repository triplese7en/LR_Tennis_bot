"""
Database module for storing user data, preferences, and booking history
Uses SQLite for simplicity and portability
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """SQLite database handler for the booking bot"""
    
    def __init__(self, db_path: str = "data/bookings.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._create_tables()
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                preferred_time TEXT,
                preferred_court TEXT,
                preferred_date TEXT,
                auto_retry BOOLEAN DEFAULT 1,
                notifications BOOLEAN DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Booking attempts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS booking_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                court_number TEXT,
                status TEXT DEFAULT 'pending',
                message TEXT,
                screenshot_path TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Booking confirmations table (successful bookings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS booking_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_attempt_id INTEGER,
                booking_reference TEXT,
                confirmation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_attempt_id) REFERENCES booking_attempts(id)
            )
        """)
        
        # Create indices for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_bookings 
            ON booking_attempts(user_id, created_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_booking_status 
            ON booking_attempts(status, created_at DESC)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("Database tables created successfully")
    
    def add_user(self, user_id: int, username: str) -> bool:
        """Add or update user in database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (user_id, username, last_active)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    last_active = CURRENT_TIMESTAMP
            """, (user_id, username))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User {user_id} added/updated")
            return True
        
        except Exception as e:
            logger.error(f"Failed to add user: {e}")
            return False
    
    def add_booking_attempt(
        self,
        user_id: int,
        booking_date: str,
        booking_time: str,
        court_number: str = None
    ) -> Optional[int]:
        """Record a new booking attempt"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO booking_attempts 
                (user_id, booking_date, booking_time, court_number, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (user_id, booking_date, booking_time, court_number))
            
            booking_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"Booking attempt {booking_id} created for user {user_id}")
            return booking_id
        
        except Exception as e:
            logger.error(f"Failed to add booking attempt: {e}")
            return None
    
    def update_booking_status(
        self,
        booking_id: int,
        status: str,
        message: str = None,
        screenshot_path: str = None
    ) -> bool:
        """Update booking attempt status"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE booking_attempts
                SET status = ?,
                    message = ?,
                    screenshot_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, message, screenshot_path, booking_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Booking {booking_id} status updated to {status}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update booking status: {e}")
            return False
    
    def add_booking_confirmation(
        self,
        booking_attempt_id: int,
        booking_reference: str
    ) -> bool:
        """Record a successful booking confirmation"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO booking_confirmations (booking_attempt_id, booking_reference)
                VALUES (?, ?)
            """, (booking_attempt_id, booking_reference))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Booking confirmation added for attempt {booking_attempt_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to add booking confirmation: {e}")
            return False
    
    def get_booking_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get booking history for a user"""
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id,
                    booking_date,
                    booking_time,
                    court_number,
                    status,
                    message,
                    screenshot_path,
                    retry_count,
                    created_at,
                    updated_at
                FROM booking_attempts
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Failed to get booking history: {e}")
            return []
    
    def get_latest_booking(self, user_id: int) -> Optional[Dict]:
        """Get the most recent booking attempt for a user"""
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id,
                    booking_date,
                    booking_time,
                    court_number,
                    status,
                    message,
                    screenshot_path,
                    retry_count,
                    created_at,
                    updated_at
                FROM booking_attempts
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        
        except Exception as e:
            logger.error(f"Failed to get latest booking: {e}")
            return None
    
    def set_user_preferences(
        self,
        user_id: int,
        preferred_time: str = None,
        preferred_court: str = None,
        preferred_date: str = None,
        auto_retry: bool = True,
        notifications: bool = True
    ) -> bool:
        """Set or update user preferences"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO user_preferences 
                (user_id, preferred_time, preferred_court, preferred_date, auto_retry, notifications)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    preferred_time = COALESCE(excluded.preferred_time, preferred_time),
                    preferred_court = COALESCE(excluded.preferred_court, preferred_court),
                    preferred_date = COALESCE(excluded.preferred_date, preferred_date),
                    auto_retry = excluded.auto_retry,
                    notifications = excluded.notifications,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, preferred_time, preferred_court, preferred_date, auto_retry, notifications))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Preferences updated for user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to set user preferences: {e}")
            return False
    
    def get_user_preferences(self, user_id: int) -> Optional[Dict]:
        """Get user preferences"""
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    preferred_time,
                    preferred_court,
                    preferred_date,
                    auto_retry,
                    notifications,
                    updated_at
                FROM user_preferences
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        
        except Exception as e:
            logger.error(f"Failed to get user preferences: {e}")
            return None
    
    def get_statistics(self, user_id: int = None) -> Dict:
        """Get booking statistics"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if user_id:
                # User-specific stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_attempts,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                    FROM booking_attempts
                    WHERE user_id = ?
                """, (user_id,))
            else:
                # Global stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_attempts,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                        COUNT(DISTINCT user_id) as total_users
                    FROM booking_attempts
                """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'total_attempts': row[0],
                    'successful': row[1],
                    'failed': row[2],
                    'errors': row[3],
                    'success_rate': (row[1] / row[0] * 100) if row[0] > 0 else 0,
                    'total_users': row[4] if len(row) > 4 else None
                }
            
            return {}
        
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def cleanup_old_bookings(self, days: int = 30) -> int:
        """Delete booking attempts older than specified days"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM booking_attempts
                WHERE created_at < datetime('now', '-' || ? || ' days')
                AND status IN ('failed', 'error')
            """, (days,))
            
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_count} old booking attempts")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Failed to cleanup old bookings: {e}")
            return 0
