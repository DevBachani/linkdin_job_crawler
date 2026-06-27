import json
import os
import time
import threading
import schedule
import redis
from http.server import BaseHTTPRequestHandler, HTTPServer

from crawler import fetch_jobs
from telegram_notifire import send_telegram_message, listen_for_commands
from config import (
    KEYWORDS, LOCATIONS, MAX_JOBS,
    PRIORITY_KEYWORDS, COMPANY_BLOCKLIST, MIN_SCORE,
    CHECK_INTERVAL_MINUTES, MAX_NOTIFICATIONS_PER_RUN,
)

# ─────────────────────────────────────────────────────────────────────────────
# Redis client  (falls back to a local JSON file if REDIS_URL is not set)
# Set REDIS_URL in your Render environment variables.
# Free tier: https://upstash.com  →  create a Redis DB → copy the URL
# ─────────────────────────────────────────────────────────────────────────────
REDIS_URL  = os.getenv("REDIS_URL")
REDIS_KEY  = "job_notifier:seen_links"
SEEN_FILE  = "jobs.json"   # local fallback only

_redis_client = None
if REDIS_URL:
    try:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        print("✅  Redis connected")
    except Exception as e:
        print(f"⚠️  Redis connection failed, using local file fallback: {e}")
        _redis_client = None
else:
    print("ℹ️  REDIS_URL not set — using local jobs.json (state resets on redeploy)")


def load_seen() -> set:
    if _redis_client:
        try:
            raw = _redis_client.get(REDIS_KEY)
            return set(json.loads(raw)) if raw else set()
        except Exception as e:
            print(f"⚠️  Redis read error: {e}")

    # Local file fallback
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE) as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            return {j.get("link") for j in data if isinstance(j, dict)}
        except json.JSONDecodeError:
            return set()


def save_seen(links: set) -> None:
    if _redis_client:
        try:
            _redis_client.set(REDIS_KEY, json.dumps(list(links)))
            return
        except Exception as e:
            print(f"⚠️  Redis write error: {e}")

    # Local file fallback
    with open(SEEN_FILE, "w") as f:
        json.dump(list(links), f)


# ─────────────────────────────────────────────────────────────────────────────
# Relevance scoring
# ─────────────────────────────────────────────────────────────────────────────
def score_job(job: dict) -> int:
    text = (job["title"] + " " + job["company"] + " " + job["location"]).lower()
    score = 0

    for phrase, weight in PRIORITY_KEYWORDS.items():
        if phrase in text:
            score += weight

    for bad in COMPANY_BLOCKLIST:
        if bad in text:
            score -= 5

    return score


# ─────────────────────────────────────────────────────────────────────────────
# Recency filter
# ─────────────────────────────────────────────────────────────────────────────
def is_recent(posted_text: str) -> bool:
    t = posted_text.lower()
    if "just now" in t or "minute" in t:
        return True
    if "hour" in t:
        # Accept "1 hour ago" … "5 hours ago", reject "20 hours ago"
        for n in range(1, 7):
            if str(n) in t:
                return True
    # Naukri uses "X days ago" or "Today" / "1 day ago"
    if "today" in t or "1 day" in t:
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# URL sanitiser
# ─────────────────────────────────────────────────────────────────────────────
def clean_url(url: str) -> str:
    if not url:
        return url
    return url.split("?")[0].replace("in.linkedin.com", "www.linkedin.com")


# ─────────────────────────────────────────────────────────────────────────────
# Core job-check loop
# ─────────────────────────────────────────────────────────────────────────────
def check_new_jobs() -> None:
    print("\n🔍  Checking for new jobs …\n")

    seen_links = load_seen()

    raw_jobs  = fetch_jobs(KEYWORDS, LOCATIONS, MAX_JOBS)
    print(f"📦  Total jobs fetched: {len(raw_jobs)}")

    # Keep only unseen + recent posts
    fresh = [
        j for j in raw_jobs
        if j["link"] not in seen_links and is_recent(j["posted"])
    ]

    # Score and rank
    fresh.sort(key=score_job, reverse=True)

    # Drop irrelevant jobs
    fresh = [j for j in fresh if score_job(j) >= MIN_SCORE]

    # Cap notifications per run to avoid Telegram flood
    to_notify = fresh[:MAX_NOTIFICATIONS_PER_RUN]

    if to_notify:
        print(f"✨  {len(to_notify)} new relevant job(s) — notifying …")
        for job in to_notify:
            seen_links.add(job["link"])
            job_url = clean_url(job["link"])
            score   = score_job(job)
            stars   = "⭐" * min(score, 5) if score > 0 else ""

            msg = (
                f"🚀 <b>{job['title']}</b> {stars}\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"🕒 {job['posted']}\n"
                f"🌐 {job.get('source', 'LinkedIn')}"
            )
            send_telegram_message(msg, job_url)
            time.sleep(1)  # small delay between Telegram messages
    else:
        print("😴  No new jobs found this cycle.")

    # Mark skipped fresh jobs as seen too (avoid re-checking stale ones)
    for j in fresh[MAX_NOTIFICATIONS_PER_RUN:]:
        seen_links.add(j["link"])

    save_seen(seen_links)
    print(f"🕒  Next check in {CHECK_INTERVAL_MINUTES} minutes …\n")


# ─────────────────────────────────────────────────────────────────────────────
# Health-check server (keeps Render web service alive)
# ─────────────────────────────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        body = b"LinkedIn Job Notifier is running."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence noisy access logs


def _start_health_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthHandler)
    print("🌐  Health-check server on port 10000")
    server.serve_forever()


threading.Thread(target=_start_health_server, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Telegram command listener (runs in background thread)
# Lets you type /addkeyword <phrase> or /status in Telegram
# ─────────────────────────────────────────────────────────────────────────────
threading.Thread(target=listen_for_commands, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────────────────────────────────────
schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_new_jobs)

print("🤖  LinkedIn Job Notifier started")
check_new_jobs()   # run immediately on startup

while True:
    schedule.run_pending()
    time.sleep(30)