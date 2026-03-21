import os
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voice_interviews.db")

# Extract SQLite database path from URL
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

def create_tables():
    """Create database tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create interviews table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id TEXT PRIMARY KEY,
        phone_number TEXT,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        transcript TEXT,
        analysis TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create conversation_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_id TEXT,
        speaker TEXT,
        message TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (interview_id) REFERENCES interviews (id)
    )
    """)
    
    conn.commit()
    conn.close()
    
    print("Database tables created")

async def store_interview(interview_id, analysis, phone_number=None):
    """Store interview data in the database."""
    # Run in a separate thread to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _store_interview, interview_id, analysis, phone_number)

def _store_interview(interview_id, analysis, phone_number=None):
    """Synchronous function to store interview data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if interview exists
    cursor.execute("SELECT id FROM interviews WHERE id = ?", (interview_id,))
    result = cursor.fetchone()
    
    if result:
        # Update existing interview
        cursor.execute("""
        UPDATE interviews
        SET end_time = ?, analysis = ?
        WHERE id = ?
        """, (datetime.now(), analysis, interview_id))
    else:
        # Insert new interview
        cursor.execute("""
        INSERT INTO interviews (id, phone_number, start_time, end_time, analysis)
        VALUES (?, ?, ?, ?, ?)
        """, (interview_id, phone_number, datetime.now(), datetime.now(), analysis))
    
    conn.commit()
    conn.close()
    
    print(f"Interview {interview_id} stored in database")

async def store_conversation_log(interview_id, speaker, message):
    """Store conversation log in the database."""
    # Run in a separate thread to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _store_conversation_log, interview_id, speaker, message)

def _store_conversation_log(interview_id, speaker, message):
    """Synchronous function to store conversation log."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Insert conversation log
    cursor.execute("""
    INSERT INTO conversation_logs (interview_id, speaker, message)
    VALUES (?, ?, ?)
    """, (interview_id, speaker, message))
    
    conn.commit()
    conn.close()
    
    print(f"Conversation log stored for interview {interview_id}")

async def get_interview_transcript(interview_id):
    """Get the full transcript of an interview."""
    # Run in a separate thread to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_interview_transcript, interview_id)

def _get_interview_transcript(interview_id):
    """Synchronous function to get interview transcript."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get conversation logs for the interview
    cursor.execute("""
    SELECT speaker, message, timestamp
    FROM conversation_logs
    WHERE interview_id = ?
    ORDER BY timestamp ASC
    """, (interview_id,))
    
    logs = cursor.fetchall()
    conn.close()
    
    # Format transcript
    transcript = ""
    for speaker, message, timestamp in logs:
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime("%H:%M:%S")
        transcript += f"[{time_str}] {speaker.capitalize()}: {message}\n"
    
    return transcript 