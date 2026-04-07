import sqlite3
import os
import re
from datetime import datetime

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_FILE = os.path.join(DATA_DIR, 'job_tracker.db')


def _infer_company_from_sender(sender):
    if not sender:
        return None

    name_part = sender.split("<")[0].strip().strip('"')
    if name_part and "no-reply" not in name_part.lower() and "noreply" not in name_part.lower():
        return name_part[:80]

    match = re.search(r"<([^>]+)>", sender)
    address = match.group(1) if match else sender
    if "@" not in address:
        return None

    domain = address.split("@")[-1].lower()
    parts = [p for p in domain.split(".") if p]
    if len(parts) < 2:
        return None

    base = parts[-2]
    if base in {"gmail", "yahoo", "outlook", "hotmail", "live", "mail", "email", "accounts"}:
        return None

    return base.replace("-", " ").title()


def _infer_role_from_subject(subject):
    if not subject:
        return None

    subject_lower = subject.lower()
    if "intern" in subject_lower:
        return "Intern"
    if "interview" in subject_lower:
        return "Interview"
    if "assessment" in subject_lower or "challenge" in subject_lower or "test" in subject_lower:
        return "Assessment"
    if "application" in subject_lower:
        return "Application"

    return None

def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Applications table
    c.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT,
            status TEXT,
            deadline TEXT,
            action_required BOOLEAN,
            link TEXT,
            last_updated TEXT
        )
    ''')
    
    # Communications table (links emails to an application)
    c.execute('''
        CREATE TABLE IF NOT EXISTS communications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER,
            message_id TEXT,
            sender TEXT,
            subject TEXT,
            body TEXT,
            received_at TEXT,
            FOREIGN KEY(app_id) REFERENCES applications(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def upsert_application(parsed_data, email_body, sender="Unknown", subject="No Subject", message_id=None, received_at=None):
    """
    Inserts or updates an application based on Company Name and Role.
    Also logs the communication that triggered this update.
    """
    conn = get_connection()
    c = conn.cursor()
    
    company = parsed_data.get('company', 'Unknown')
    role = parsed_data.get('role', 'Unknown')
    status = parsed_data.get('status', 'Applied')
    deadline = parsed_data.get('deadline')
    raw_action_required = parsed_data.get('action_required', parsed_data.get('action required', False))
    if isinstance(raw_action_required, str):
        action_required = raw_action_required.strip().lower() in {'true', '1', 'yes', 'y'}
    else:
        action_required = bool(raw_action_required)
    link = parsed_data.get('link')
    now = datetime.now().isoformat()
    
    if not received_at:
        received_at = now
        
    if not message_id:
        message_id = f"msg_{int(datetime.now().timestamp() * 1000)}"

    if company in {"", "Unknown", "Parse Error / Rate Limit Hit", None}:
        inferred_company = _infer_company_from_sender(sender)
        if inferred_company:
            company = inferred_company

    if role in {"", "Unknown", None}:
        inferred_role = _infer_role_from_subject(subject)
        if inferred_role:
            role = inferred_role

    if not company:
        company = "Unknown"
    if not role:
        role = "Unknown"

    # Check for existing application
    c.execute("SELECT id FROM applications WHERE company = ? AND role = ?", (company, role))
    row = c.fetchone()
    
    if row:
        app_id = row[0]
        # Update existing
        c.execute('''
            UPDATE applications
            SET status = ?, deadline = ?, action_required = ?, link = ?, last_updated = ?
            WHERE id = ?
        ''', (status, deadline, action_required, link, now, app_id))
    else:
        # Create new
        c.execute('''
            INSERT INTO applications (company, role, status, deadline, action_required, link, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (company, role, status, deadline, action_required, link, now))
        app_id = c.lastrowid
        
    # Append communication history only if this message hasn't been logged already.
    c.execute("SELECT id FROM communications WHERE message_id = ?", (message_id,))
    existing_comm = c.fetchone()
    if not existing_comm:
        c.execute('''
            INSERT INTO communications (app_id, message_id, sender, subject, body, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (app_id, message_id, sender, subject, email_body, received_at))
    
    conn.commit()
    conn.close()
    return app_id

def get_all_applications():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM applications ORDER BY last_updated DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_communications(app_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM communications WHERE app_id = ? ORDER BY received_at DESC", (app_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_communications():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM communications ORDER BY received_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def communication_exists(message_id):
    if not message_id:
        return False

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM communications WHERE message_id = ? LIMIT 1", (message_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def delete_communications_by_ids(comm_ids):
    if not comm_ids:
        return {"deleted_communications": 0, "deleted_applications": 0}

    conn = get_connection()
    c = conn.cursor()
    deleted_communications = 0

    # Chunk deletes to stay under SQLite variable limits.
    chunk_size = 500
    for start in range(0, len(comm_ids), chunk_size):
        chunk = comm_ids[start:start + chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        c.execute(f"DELETE FROM communications WHERE id IN ({placeholders})", chunk)
        deleted_communications += c.rowcount if c.rowcount is not None else 0

    c.execute(
        """
        DELETE FROM applications
        WHERE id NOT IN (
            SELECT DISTINCT app_id
            FROM communications
            WHERE app_id IS NOT NULL
        )
        """
    )
    deleted_applications = c.rowcount if c.rowcount is not None else 0

    conn.commit()
    conn.close()

    return {
        "deleted_communications": deleted_communications,
        "deleted_applications": deleted_applications,
    }


def purge_mock_data():
    """Remove seeded/mock communication rows and any orphan applications left behind."""
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """
        DELETE FROM communications
        WHERE message_id LIKE 'MOCK_GMAIL_ID_%'
           OR sender LIKE 'Mock Sender%'
        """
    )
    deleted_communications = c.rowcount if c.rowcount is not None else 0

    c.execute(
        """
        DELETE FROM applications
        WHERE id NOT IN (
            SELECT DISTINCT app_id
            FROM communications
            WHERE app_id IS NOT NULL
        )
        """
    )
    deleted_applications = c.rowcount if c.rowcount is not None else 0

    conn.commit()
    conn.close()

    return {
        "deleted_communications": deleted_communications,
        "deleted_applications": deleted_applications,
    }

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
