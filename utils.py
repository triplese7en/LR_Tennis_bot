#!/usr/bin/env python3
"""
Utility script for bot monitoring and maintenance
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import Database


def show_statistics(db: Database, user_id=None):
    """Display booking statistics"""
    stats = db.get_statistics(user_id)
    
    print("\n📊 Booking Statistics")
    print("=" * 50)
    
    if user_id:
        print(f"User ID: {user_id}")
    else:
        print("Global Statistics")
    
    print(f"\nTotal Attempts: {stats.get('total_attempts', 0)}")
    print(f"Successful: {stats.get('successful', 0)} ✅")
    print(f"Failed: {stats.get('failed', 0)} ❌")
    print(f"Errors: {stats.get('errors', 0)} ⚠️")
    print(f"Success Rate: {stats.get('success_rate', 0):.1f}%")
    
    if stats.get('total_users'):
        print(f"\nTotal Users: {stats['total_users']}")
    
    print("=" * 50 + "\n")


def list_recent_bookings(db: Database, limit=10):
    """List recent bookings across all users"""
    print(f"\n📋 Recent Bookings (Last {limit})")
    print("=" * 70)
    
    conn = db._get_connection()
    conn.row_factory = lambda cursor, row: dict(zip([col[0] for col in cursor.description], row))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            b.id,
            b.user_id,
            u.username,
            b.booking_date,
            b.booking_time,
            b.court_number,
            b.status,
            b.created_at
        FROM booking_attempts b
        JOIN users u ON b.user_id = u.user_id
        ORDER BY b.created_at DESC
        LIMIT ?
    """, (limit,))
    
    bookings = cursor.fetchall()
    conn.close()
    
    if not bookings:
        print("No bookings found.")
        return
    
    for booking in bookings:
        status_emoji = {
            'success': '✅',
            'failed': '❌',
            'error': '⚠️',
            'pending': '⏳'
        }
        
        print(f"{status_emoji.get(booking['status'], '❓')} ID: {booking['id']}")
        print(f"   User: {booking['username']} ({booking['user_id']})")
        print(f"   Date: {booking['booking_date']} @ {booking['booking_time']}")
        print(f"   Court: {booking['court_number']}")
        print(f"   Status: {booking['status'].upper()}")
        print(f"   Created: {booking['created_at']}")
        print()
    
    print("=" * 70 + "\n")


def cleanup_database(db: Database, days=30, dry_run=True):
    """Clean up old booking records"""
    print(f"\n🧹 Database Cleanup")
    print("=" * 50)
    print(f"Removing failed bookings older than {days} days")
    
    if dry_run:
        print("DRY RUN - No changes will be made")
        print("Use --execute to actually delete records")
    
    deleted = db.cleanup_old_bookings(days) if not dry_run else 0
    
    print(f"\nRecords {'would be' if dry_run else ''} deleted: {deleted}")
    print("=" * 50 + "\n")


def export_history(db: Database, output_file='bookings_export.csv'):
    """Export booking history to CSV"""
    import csv
    
    print(f"\n📤 Exporting booking history to {output_file}")
    
    conn = db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            b.id,
            b.user_id,
            u.username,
            b.booking_date,
            b.booking_time,
            b.court_number,
            b.status,
            b.message,
            b.retry_count,
            b.created_at,
            b.updated_at
        FROM booking_attempts b
        JOIN users u ON b.user_id = u.user_id
        ORDER BY b.created_at DESC
    """)
    
    rows = cursor.fetchall()
    
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'ID', 'User ID', 'Username', 'Date', 'Time', 'Court',
            'Status', 'Message', 'Retries', 'Created', 'Updated'
        ])
        writer.writerows(rows)
    
    conn.close()
    
    print(f"✅ Exported {len(rows)} records to {output_file}\n")


def check_health(db: Database):
    """Check bot health and database status"""
    print("\n🏥 Health Check")
    print("=" * 50)
    
    # Check database connectivity
    try:
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()
        print(f"✅ Database: Connected ({user_count} users)")
    except Exception as e:
        print(f"❌ Database: Error - {e}")
    
    # Check directories
    dirs = ['logs', 'screenshots', 'data']
    for dir_name in dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"✅ Directory '{dir_name}': Exists")
        else:
            print(f"❌ Directory '{dir_name}': Missing")
    
    # Check config
    config_path = Path('config/config.json')
    if config_path.exists():
        print(f"✅ Config: Found")
        
        import json
        with open(config_path) as f:
            config = json.load(f)
            if config.get('telegram_token') and config['telegram_token'] != 'YOUR_TELEGRAM_BOT_TOKEN':
                print(f"✅ Telegram Token: Configured")
            else:
                print(f"⚠️  Telegram Token: Not configured")
    else:
        print(f"❌ Config: Missing")
    
    # Check recent activity
    try:
        stats = db.get_statistics()
        recent_count = stats.get('total_attempts', 0)
        print(f"✅ Recent Activity: {recent_count} total bookings")
    except Exception as e:
        print(f"⚠️  Activity Check: {e}")
    
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description='Tennis Booking Bot Utilities')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Statistics
    stats_parser = subparsers.add_parser('stats', help='Show booking statistics')
    stats_parser.add_argument('--user', type=int, help='User ID (optional)')
    
    # Recent bookings
    recent_parser = subparsers.add_parser('recent', help='List recent bookings')
    recent_parser.add_argument('--limit', type=int, default=10, help='Number of bookings to show')
    
    # Cleanup
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old bookings')
    cleanup_parser.add_argument('--days', type=int, default=30, help='Delete records older than N days')
    cleanup_parser.add_argument('--execute', action='store_true', help='Actually delete (default is dry-run)')
    
    # Export
    export_parser = subparsers.add_parser('export', help='Export booking history')
    export_parser.add_argument('--output', default='bookings_export.csv', help='Output CSV file')
    
    # Health check
    subparsers.add_parser('health', help='Check bot health')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database
    db = Database()
    
    # Execute command
    if args.command == 'stats':
        show_statistics(db, args.user)
    
    elif args.command == 'recent':
        list_recent_bookings(db, args.limit)
    
    elif args.command == 'cleanup':
        cleanup_database(db, args.days, dry_run=not args.execute)
    
    elif args.command == 'export':
        export_history(db, args.output)
    
    elif args.command == 'health':
        check_health(db)


if __name__ == '__main__':
    main()
