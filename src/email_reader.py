import imaplib
import email
import os
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
DOTENV_PATH = os.path.join(PROJECT_ROOT, '.env')

load_dotenv(dotenv_path=DOTENV_PATH, override=True)

# ------------------------
# Configurable credentials
# ------------------------
IMAP_HOST = "imap.gmail.com"
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT").strip()
APP_PASSWORD = (os.getenv("EMAIL_PASS") or "").replace(" ", "").strip()  # Accept spaced or plain app-password format
MAILBOX = "INBOX"
MAX_UNREAD_FETCH = max(int(os.getenv("EMAIL_MAX_UNREAD_FETCH", "75")), 1)


def _decode_mime_header(value):
    if not value:
        return ""

    decoded_parts = decode_header(value)
    output = []

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                output.append(part.decode(encoding or "utf-8", errors="replace"))
            except LookupError:
                output.append(part.decode("utf-8", errors="replace"))
        else:
            output.append(part)

    return "".join(output).strip()


def _extract_plain_text(msg):
    if not msg.is_multipart():
        payload = msg.get_payload(decode=True)
        if payload is None:
            return ""
        charset = msg.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace").strip()
        except LookupError:
            return payload.decode("utf-8", errors="replace").strip()

    body_chunks = []
    for part in msg.walk():
        if part.get_content_type() != "text/plain":
            continue

        disposition = (part.get("Content-Disposition") or "").lower()
        if "attachment" in disposition:
            continue

        payload = part.get_payload(decode=True)
        if payload is None:
            continue

        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")

        text = text.strip()
        if text:
            body_chunks.append(text)

    return "\n".join(body_chunks).strip()


def _normalize_received_at(date_header):
    if not date_header:
        return datetime.now().isoformat()

    try:
        parsed = parsedate_to_datetime(date_header)
        if parsed is None:
            return datetime.now().isoformat()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    except Exception:
        return datetime.now().isoformat()


def fetch_unread_emails(max_messages=None):
    """Fetch unread emails from Gmail and return normalized email payloads."""
    if not EMAIL_ACCOUNT or not APP_PASSWORD:
        raise RuntimeError("Missing EMAIL_ACCOUNT or EMAIL_PASS in .env")

    limit = MAX_UNREAD_FETCH if max_messages is None else max(int(max_messages), 1)
    mail = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=30)
    extracted = []

    try:
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)

        status, _ = mail.select(MAILBOX)
        if status != "OK":
            raise RuntimeError(f"Unable to select mailbox: {MAILBOX}")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError("Failed to search unread emails.")

        email_ids = messages[0].split() if messages and messages[0] else []
        if len(email_ids) > limit:
            email_ids = email_ids[-limit:]

        for email_id in reversed(email_ids):
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status != "OK":
                continue

            for response_part in msg_data:
                if not isinstance(response_part, tuple):
                    continue

                msg = email.message_from_bytes(response_part[1])
                message_id = _decode_mime_header(msg.get("Message-ID", ""))
                if not message_id:
                    message_id = f"imap_uid_{email_id.decode(errors='ignore')}"

                extracted.append(
                    {
                        "message_id": message_id,
                        "subject": _decode_mime_header(msg.get("Subject", "")),
                        "sender": _decode_mime_header(msg.get("From", "")),
                        "body": _extract_plain_text(msg),
                        "received_at": _normalize_received_at(msg.get("Date")),
                    }
                )
                break

    finally:
        try:
            mail.close()
        except imaplib.IMAP4.error:
            pass

        mail.logout()

    return extracted


def check_unread_email_count():
    """Quick IMAP connectivity check that only counts unread emails."""
    if not EMAIL_ACCOUNT or not APP_PASSWORD:
        raise RuntimeError("Missing EMAIL_ACCOUNT or EMAIL_PASS in .env")

    mail = None
    try:
        print("1. Attempting to connect to Gmail...")
        mail = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=30)
        print("[OK] Connected successfully!")

        print("2. Attempting to log in...")
        mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
        print("[OK] Logged in successfully!")

        print("3. Selecting the inbox...")
        status, _ = mail.select(MAILBOX)
        if status != "OK":
            raise RuntimeError(f"Unable to select mailbox: {MAILBOX}")
        print("[OK] Inbox selected!")

        print("4. Searching for unread emails...")
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError("Failed to search unread emails.")

        email_ids = messages[0].split() if messages and messages[0] else []
        print(f"[OK] Found {len(email_ids)} unread emails.")

    finally:
        if mail is not None:
            try:
                mail.close()
            except imaplib.IMAP4.error:
                pass

            mail.logout()


if __name__ == "__main__":
    try:
        check_unread_email_count()
        print("Script finished!")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
