import json
import os
import time
import schedule
from crawler import fetch_jobs
from telegram_notifire import send_telegram_message
from config import KEYWORDS, LOCATIONS, MAX_JOBS
import threading
from http.server import SimpleHTTPRequestHandler


import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        message = "✅ LinkedIn Job Notifier is alive and running on Render!"
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))  # <-- FIXED (encode to bytes)

def keep_alive():
    server = HTTPServer(("0.0.0.0", 10000), HealthHandler)
    print("🌐 Health check server running on port 10000 for Render")
    server.serve_forever()

# Start server thread
threading.Thread(target=keep_alive, daemon=True).start()



SEEN_FILE = "jobs.json"

# -------------------------------------------
# Safe LinkedIn URL (browser-friendly)
# -------------------------------------------
def safe_linkedin_url(url: str) -> str:
    if not url:
        return url
    clean_url = url.split("?")[0].replace("in.linkedin.com", "www.linkedin.com")
    return clean_url  # send directly, button will open browser


# -------------------------------------------
# Initialize seen jobs storage
# -------------------------------------------
if not os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "w") as f:
        json.dump([], f)


# -------------------------------------------
# Helper: only recent posts
# -------------------------------------------
def is_recent_post(posted_text: str) -> bool:
    posted_text = posted_text.lower()
    return any(word in posted_text for word in ["minute", "hour", "just now"])


# -------------------------------------------
# Job checker
# -------------------------------------------
def check_new_jobs():
    print("\n🔍 Checking for new jobs...\n")

    with open(SEEN_FILE) as f:
        try:
            seen_jobs = json.load(f)
            if isinstance(seen_jobs, list) and all(isinstance(j, str) for j in seen_jobs):
                seen_links = set(seen_jobs)
            else:
                seen_links = {job.get("link") for job in seen_jobs if isinstance(job, dict)}
        except json.JSONDecodeError:
            seen_links = set()

    enhanced_locations = LOCATIONS + ["Work from home"]
    new_jobs = fetch_jobs(KEYWORDS, enhanced_locations, MAX_JOBS)
    print(f"📦 Total jobs fetched: {len(new_jobs)}")

    fresh_jobs = [
        job for job in new_jobs
        if job["link"] not in seen_links and is_recent_post(job["posted"])
    ]

    if fresh_jobs:
        print(f"✨ Found {len(fresh_jobs)} NEW jobs!")
        for job in fresh_jobs:
            seen_links.add(job["link"])
            job_url = safe_linkedin_url(job["link"])
            msg = (
                f"🚀 <b>{job['title']}</b>\n"
                f"🏢 {job['company']}\n"
                f"📍 {job['location']}\n"
                f"🕒 {job['posted']}"
            )
            send_telegram_message(msg, job_url)
    else:
        print("😴 No new jobs found this cycle.")

    # Save seen jobs
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_links), f)

    print("🕒 Next check in 5 minutes...\n")

def keep_alive():
    server = HTTPServer(("0.0.0.0", 10000), SimpleHTTPRequestHandler)
    print("🌐 Dummy server running on port 10000 for Render")
    server.serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()

# -------------------------------------------
# Schedule job every 5 minutes
# -------------------------------------------
schedule.every(5).minutes.do(check_new_jobs)

print("🤖 LinkedIn Job Notifier is running...")

# Run once on startup
check_new_jobs()

while True:
    schedule.run_pending()
    time.sleep(60)
