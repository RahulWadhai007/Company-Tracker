import os
import glob
import re
from datetime import datetime

from .database import (
    init_db,
    upsert_application,
    purge_mock_data,
    get_all_communications,
    delete_communications_by_ids,
    communication_exists,
)
from .ai_processor import get_job_info_from_email
from .email_reader import fetch_unread_emails

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
MOCK_EMAIL_GLOB = os.path.join(PROJECT_ROOT, 'data', 'mock_emails', 'test_email_*.txt')

PRIMARY_PATTERNS = (
    r"\bintern(ship)?\b",
    r"\binterview\b",
    r"\bassessment\b",
    r"\brecruit(er|ment)\b",
    r"\bhiring\b",
    r"\boffer letter\b",
    r"\bhackerrank\b",
    r"\bcoding challenge\b",
    r"\btake[- ]home\b",
    r"\b(job|intern(ship)?)\b.*\bapplication\b",
    r"\bapplication\b.*\b(job|intern(ship)?)\b",
)

SECONDARY_PATTERNS = (
    r"\bjob\b",
    r"\bapplication\b",
    r"\brole\b",
    r"\bresume\b",
    r"\bcv\b",
)

PLATFORM_JOB_SUBJECT_PATTERN = (
    r"\b(job|intern(ship)?|application|assessment|interview|hiring|recruit(er|ment)|"
    r"position|opportunity|shortlisted|offer|status|participation|challenge|test)\b"
)

MICROSOFT_SUBJECT_PATTERN = (
    r"\b(job|intern(ship)?|application|assessment|interview|hiring|recruit(er|ment)|"
    r"position|offer|career)\b"
)

def _is_job_related_email(subject, sender, body):
    subject_sender = f"{subject}\n{sender}".lower()
    sender_lower = (sender or "").lower()
    subject_lower = (subject or "").lower()

    # Explicitly allow major job platforms requested by user.
    if any(hint in sender_lower for hint in ("indeed", "@indeed", "indeedmail", "alerts.indeed")):
        if re.search(PLATFORM_JOB_SUBJECT_PATTERN, subject_lower):
            return True

    if any(hint in sender_lower for hint in ("unstop", "team unstop")):
        if re.search(PLATFORM_JOB_SUBJECT_PATTERN, subject_lower):
            return True

    if any(hint in sender_lower for hint in ("wellfound", "angel.co")):
        if re.search(PLATFORM_JOB_SUBJECT_PATTERN, subject_lower):
            return True

    if any(hint in sender_lower for hint in ("careers.microsoft", "microsoft careers", "microsoft")):
        if re.search(MICROSOFT_SUBJECT_PATTERN, subject_lower):
            return True

    # Platform-specific checks to avoid generic social/community updates.
    if "linkedin" in sender_lower and re.search(
        r"\b(job|intern(ship)?|application|assessment|interview|hiring|recruit(er|ment))\b",
        subject_lower,
    ):
        return True

    if "internshala" in sender_lower and re.search(
        r"\b(application|intern(ship)?|job|shortlisted|accepted|rejected|assessment|interview|status)\b",
        subject_lower,
    ):
        return True

    if any(re.search(pattern, subject_sender) for pattern in PRIMARY_PATTERNS):
        return True

    secondary_hits = sum(1 for pattern in SECONDARY_PATTERNS if re.search(pattern, subject_sender))
    if secondary_hits >= 2:
        return True

    return False


def _cleanup_non_job_history():
    all_comms = get_all_communications()
    to_delete = [
        comm["id"]
        for comm in all_comms
        if not _is_job_related_email(
            comm.get("subject", ""),
            comm.get("sender", ""),
            comm.get("body", ""),
        )
    ]

    if not to_delete:
        return {"deleted_communications": 0, "deleted_applications": 0}

    return delete_communications_by_ids(to_delete)


def run_gmail_ingestion():
    """Ingest unread Gmail emails and keep only job/intern related messages."""
    init_db()
    cleanup_enabled = os.getenv("CLEANUP_MOCK_ON_GMAIL", "1").strip().lower() in {"1", "true", "yes", "y"}
    if cleanup_enabled:
        cleanup_result = purge_mock_data()
        if cleanup_result["deleted_communications"] or cleanup_result["deleted_applications"]:
            print(
                "Removed mock data -> "
                f"communications: {cleanup_result['deleted_communications']}, "
                f"applications: {cleanup_result['deleted_applications']}"
            )

    cleanup_non_job = os.getenv("CLEANUP_NON_JOB_HISTORY", "1").strip().lower() in {"1", "true", "yes", "y"}
    if cleanup_non_job:
        cleanup_non_job_result = _cleanup_non_job_history()
        if cleanup_non_job_result["deleted_communications"] or cleanup_non_job_result["deleted_applications"]:
            print(
                "Removed non-job history -> "
                f"communications: {cleanup_non_job_result['deleted_communications']}, "
                f"applications: {cleanup_non_job_result['deleted_applications']}"
            )

    max_unread = max(int(os.getenv("INGEST_MAX_UNREAD", "30")), 1)
    unread_emails = fetch_unread_emails(max_messages=max_unread)

    if not unread_emails:
        print("No unread Gmail emails found.")
        return

    matched = [
        item
        for item in unread_emails
        if _is_job_related_email(item.get("subject", ""), item.get("sender", ""), item.get("body", ""))
    ]

    if not matched:
        print("No unread job/intern related Gmail emails found.")
        return

    max_matched = max(int(os.getenv("INGEST_MAX_MATCHED", "20")), 1)
    matched = matched[:max_matched]

    processed = 0
    skipped_existing = 0

    for index, email_item in enumerate(matched, start=1):
        message_id = email_item.get("message_id")
        if communication_exists(message_id):
            skipped_existing += 1
            continue

        content = "\n".join([
            email_item.get("subject", ""),
            email_item.get("body", ""),
        ]).strip()

        if not content:
            continue

        print(f"[{index}/{len(matched)}] Processing Gmail email: {email_item.get('subject', 'No Subject')}")
        parsed_data = get_job_info_from_email(content)

        app_id = upsert_application(
            parsed_data=parsed_data,
            email_body=email_item.get("body", ""),
            sender=email_item.get("sender", "Unknown Sender"),
            subject=email_item.get("subject", "No Subject"),
            message_id=message_id,
            received_at=email_item.get("received_at") or datetime.now().isoformat(),
        )
        print(f" -> Database Updated. App ID: {app_id}")
        processed += 1

    print(
        "Ingestion complete. "
        f"Processed {processed} new job/intern related unread Gmail emails, "
        f"skipped {skipped_existing} already-ingested messages."
    )

def run_mock_ingestion():
    init_db()
    
    # Simulate picking up emails from Gmail integration
    # by reading the local test files.
    email_files = sorted(glob.glob(MOCK_EMAIL_GLOB))
    
    if not email_files:
        print("No test emails found to ingest.")
        return
        
    for index, file_path in enumerate(email_files):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"[{index+1}/{len(email_files)}] Processing {file_path}")
        
        # 1. Use Language Model to categorize email
        parsed_data = get_job_info_from_email(content)
        
        # Provide dummy meta-data for simulation
        subject = f"Mock Subject from {file_path}"
        sender = "Mock Sender <mock@example.com>"
        msg_id = f"MOCK_GMAIL_ID_{os.path.basename(file_path)}"
        
        # 2. Database Deduplication & Insertion
        app_id = upsert_application(
            parsed_data=parsed_data,
            email_body=content,
            sender=sender,
            subject=subject,
            message_id=msg_id,
            received_at=datetime.now().isoformat()
        )
        print(f" -> Database Updated. App ID: {app_id}")

def setup_gmail_api():
    """
    Placeholder for actual Gmail API setup.
    You will need `google-auth-oauthlib`, `google-auth-httplib2`, `google-api-python-client`.
    """
    print("Gmail API integration not yet enabled. Using mock files instead.")
    pass


def run_ingestion():
    """
    Default behavior: use live Gmail ingestion.
    Set USE_MOCK_INGESTION=1 to use local test_email_*.txt files instead.
    """
    use_mock = os.getenv("USE_MOCK_INGESTION", "0").strip().lower() in {"1", "true", "yes", "y"}
    if use_mock:
        print("USE_MOCK_INGESTION enabled. Using local mock email files.")
        run_mock_ingestion()
        return

    run_gmail_ingestion()

if __name__ == "__main__":
    run_ingestion()
