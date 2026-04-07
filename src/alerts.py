import os
import requests
from . import database

def send_telegram_message(message: str):
    """
    Sends a push notification via Telegram Bot API.
    To test: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in environment variables.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("[MOCK PUSH NOTIFICATION]")
        print(message)
        print("-------------------------------------------------")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram push notification sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def run_alerts():
    """
    Scans the database for jobs requiring immediate action and issues a notification.
    """
    database.init_db()
    apps = database.get_all_applications()
    
    actionable = [a for a in apps if a['action_required']]
    
    if not actionable:
        print("No immediate actions required.")
        return
        
    for app in actionable:
        deadline_str = f"🛑 <b>Deadline:</b> {app['deadline']}" if app['deadline'] else "🛑 <b>Deadline:</b> Unknown"
        link_str = f"\n🔗 <a href='{app['link']}'>Action Link</a>" if app['link'] and app['link'] != 'None' else ""
        
        msg = (
            f"⚠️ <b>Action Required:</b> {app['company']}\n"
            f"💼 <b>Role:</b> {app['role']}\n"
            f"📋 <b>Status:</b> {app['status']}\n"
            f"{deadline_str}"
            f"{link_str}"
        )
        
        send_telegram_message(msg)

if __name__ == "__main__":
    print("Running Priority Alert Engine...")
    run_alerts()
