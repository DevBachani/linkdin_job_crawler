# ─────────────────────────────────────────────
# Search targets
# ─────────────────────────────────────────────
KEYWORDS = [
    "machine learning engineer",
    "ai ml fresher",
    "ai ml engineer",
    "data scientist fresher",
    "nlp engineer",
    "deep learning engineer",
]

LOCATIONS = [
    "Ahmedabad",
    "Vadodara",
    "Bengaluru",
    "Mumbai",
    "Pune",
    "Remote",
    "Work from home",
]

MAX_JOBS = 20  # max listings to inspect per keyword × location combo

# ─────────────────────────────────────────────
# Relevance scoring
# Each matching phrase adds its weight to the job score.
# Jobs with score < MIN_SCORE are silently skipped.
# ─────────────────────────────────────────────
PRIORITY_KEYWORDS = {
    "fresher":       3,
    "0-1 year":      3,
    "0-2 year":      3,
    "entry level":   3,
    "entry-level":   3,
    "junior":        2,
    "graduate":      2,
    "trainee":       2,
    "associate":     1,
    "remote":        1,
    "work from home":1,
}

# Jobs from these companies / types are filtered out (score penalty)
COMPANY_BLOCKLIST = [
    "staffing",
    "consultancy",
    "manpower",
    "recruiting",
    "placement",
    "hr solutions",
]

MIN_SCORE = 0   # set to 1 to hide irrelevant listings entirely

# ─────────────────────────────────────────────
# Notification behaviour
# ─────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = 5
MAX_NOTIFICATIONS_PER_RUN = 10  # avoid Telegram flood if many jobs appear