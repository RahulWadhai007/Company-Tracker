import sqlite3
import os

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_FILE = os.path.join(DATA_DIR, 'jobs.db')

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    print("Connecting to data/jobs.db (creates it if it doesn't exist)...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("Creating the applications table schema...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT,
            status TEXT,
            deadline TEXT,
            action_required INTEGER
        )
    ''')

    # Optional: Clear out preexisting test data to prevent duplicates on rerun
    cursor.execute('DELETE FROM applications')

    print("Seeding a realistic test record...")
    cursor.execute('''
        INSERT INTO applications (company, role, status, deadline, action_required)
        VALUES (?, ?, ?, ?, ?)
    ''', ('OpenAI', 'ML Ops Intern', 'Applied', '2026-04-20T12:00:00', 0))

    # Explicitly commit the transaction to save changes permanently to disk
    conn.commit()
    # Safely close the database connection
    conn.close()
    
    print("Database initialization and seeding completed successfully.")

if __name__ == '__main__':
    init_db()