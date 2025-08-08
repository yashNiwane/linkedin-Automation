#!/usr/bin/env python3
"""
Database migration script to add missing columns to existing database.
Run this once to fix the schema mismatch.
"""

import sqlite3
import os

def migrate_database():
    db_path = os.path.join('instance', 'app.db')
    
    if not os.path.exists(db_path):
        print("Database doesn't exist yet. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns exist
    cursor.execute("PRAGMA table_info(leads)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Add missing columns
    if 'thread_url' not in columns:
        cursor.execute("ALTER TABLE leads ADD COLUMN thread_url VARCHAR(512)")
        print("Added thread_url column")
    
    if 'last_seen_msg_token' not in columns:
        cursor.execute("ALTER TABLE leads ADD COLUMN last_seen_msg_token VARCHAR(128)")
        print("Added last_seen_msg_token column")
    
    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database()