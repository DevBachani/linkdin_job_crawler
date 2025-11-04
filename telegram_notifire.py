import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram_message(text, url):
    """
    Sends a Telegram message with an inline button that opens the job in a browser.
    """
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "Open in Browser", "url": url}]
            ]
        }
    }

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Telegram message sent successfully")
        else:
            print(f"⚠️ Telegram API error {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send Telegram message: {e}")
