import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ─────────────────────────────────────────────────────────────────────────────
# Send a job notification
# ─────────────────────────────────────────────────────────────────────────────
def send_telegram_message(text: str, url: str) -> None:
    """Send a job notification with an inline 'Open in Browser' button."""
    payload = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[{"text": "🔗 Open in Browser", "url": url}]]
        },
    }
    _post("sendMessage", payload)


def send_plain_message(text: str) -> None:
    """Send a plain text message (used for command replies)."""
    payload = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    _post("sendMessage", payload)


def _post(method: str, payload: dict) -> dict | None:
    try:
        resp = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        print(f"⚠️  Telegram {method} error {resp.status_code}: {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌  Telegram request failed: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Command listener  (long-polling, runs in a background daemon thread)
#
# Supported commands (send from your Telegram chat):
#   /status              → tells you the bot is running
#   /addkeyword <phrase> → adds a keyword to the live search list
#   /removekeyword <phrase> → removes a keyword
#   /listkeywords        → shows active keywords
# ─────────────────────────────────────────────────────────────────────────────

# Import here to avoid a circular import — config is loaded after this module
def _get_keywords():
    from config import KEYWORDS
    return KEYWORDS


_last_update_id = 0   # tracks processed Telegram updates


def listen_for_commands() -> None:
    """Polls Telegram for commands forever. Call in a daemon thread."""
    global _last_update_id
    print("📡  Telegram command listener started")

    while True:
        try:
            resp = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={"offset": _last_update_id + 1, "timeout": 30},
                timeout=40,
            )
            if resp.status_code != 200:
                time.sleep(5)
                continue

            updates = resp.json().get("result", [])

            for update in updates:
                _last_update_id = update["update_id"]
                message = update.get("message", {})
                text    = message.get("text", "").strip()

                if not text.startswith("/"):
                    continue

                # Only respond to your own chat
                chat_id = str(message.get("chat", {}).get("id", ""))
                if chat_id != str(CHAT_ID):
                    continue

                _handle_command(text)

        except Exception as e:
            print(f"⚠️  Command listener error: {e}")
            time.sleep(10)


def _handle_command(text: str) -> None:
    from config import KEYWORDS  # live reference

    parts   = text.split(None, 1)
    command = parts[0].lower()
    arg     = parts[1].strip() if len(parts) > 1 else ""

    if command == "/status":
        send_plain_message(
            f"✅ Bot is running\n"
            f"🔍 Watching {len(KEYWORDS)} keyword(s):\n"
            + "\n".join(f"  • {k}" for k in KEYWORDS)
        )

    elif command == "/addkeyword":
        if not arg:
            send_plain_message("Usage: /addkeyword machine learning intern")
            return
        if arg in KEYWORDS:
            send_plain_message(f"ℹ️ Already watching: <b>{arg}</b>")
        else:
            KEYWORDS.append(arg)
            send_plain_message(f"✅ Added keyword: <b>{arg}</b>")

    elif command == "/removekeyword":
        if not arg:
            send_plain_message("Usage: /removekeyword machine learning intern")
            return
        if arg in KEYWORDS:
            KEYWORDS.remove(arg)
            send_plain_message(f"🗑 Removed keyword: <b>{arg}</b>")
        else:
            send_plain_message(f"❓ Keyword not found: <b>{arg}</b>")

    elif command == "/listkeywords":
        send_plain_message(
            "📋 Active keywords:\n" + "\n".join(f"  • {k}" for k in KEYWORDS)
        )

    else:
        send_plain_message(
            "🤖 Available commands:\n"
            "/status — bot health\n"
            "/addkeyword &lt;phrase&gt; — add a keyword\n"
            "/removekeyword &lt;phrase&gt; — remove a keyword\n"
            "/listkeywords — list all keywords"
        )