import os
import random
import subprocess

# ── Playwright browser path (Render-compatible) ──────────────────────────────
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/opt/render/project/src/.cache/ms-playwright"

try:
    print("🔧 Installing Playwright Chromium …")
    subprocess.run(
        ["python", "-m", "playwright", "install", "chromium"],
        check=True,
        env=os.environ,
    )
except Exception as e:
    print("⚠️  Browser install skipped or failed:", e)

from playwright.sync_api import sync_playwright

# Rotate user-agents so LinkedIn is less likely to serve a CAPTCHA wall
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def _new_browser_page(playwright):
    """Launch a stealth-ish headless browser page."""
    browser = playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=random.choice(_USER_AGENTS),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    # Hide webdriver flag
    context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return browser, context.new_page()


# ─────────────────────────────────────────────────────────────────────────────
# LinkedIn scraper
# ─────────────────────────────────────────────────────────────────────────────
def fetch_linkedin_jobs(keywords, locations, max_jobs=20):
    jobs = []

    with sync_playwright() as p:
        browser, page = _new_browser_page(p)

        for keyword in keywords:
            for location in locations:
                print(f"🔎  LinkedIn: '{keyword}' in '{location}'")

                enc_kw  = keyword.replace(" ", "%20")
                enc_loc = location.replace(" ", "%20")
                # f_TPR=r86400 → last 24 h  |  f_E=2 → full-time
                url = (
                    f"https://www.linkedin.com/jobs/search/"
                    f"?keywords={enc_kw}&location={enc_loc}"
                    f"&f_TPR=r86400&f_E=2"
                )

                try:
                    page.goto(url, timeout=60_000)
                    page.wait_for_timeout(random.randint(3000, 5000))  # human-like delay

                    listings = page.query_selector_all("div.base-card")
                    print(f"   Found {len(listings)} listings")

                    for job in listings[:max_jobs]:
                        try:
                            title    = job.query_selector("h3").inner_text().strip()
                            company  = job.query_selector("h4").inner_text().strip()
                            loc_text = job.query_selector("span.job-search-card__location").inner_text().strip()
                            posted   = job.query_selector("time").inner_text().strip()
                            link_el  = job.query_selector("a.base-card__full-link")
                            link     = link_el.get_attribute("href").split("?")[0].strip()

                            jobs.append({
                                "title":   title,
                                "company": company,
                                "location": loc_text,
                                "posted":  posted,
                                "link":    link,
                                "source":  "LinkedIn",
                            })
                        except Exception:
                            continue

                except Exception as e:
                    print(f"   ⚠️  Failed for {keyword}/{location}: {e}")
                    continue

        browser.close()

    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# Naukri scraper  (fresher-friendly, India-focused, less aggressive blocking)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_naukri_jobs(keywords, max_jobs=20):
    jobs = []

    with sync_playwright() as p:
        browser, page = _new_browser_page(p)

        for keyword in keywords:
            print(f"🔎  Naukri: '{keyword}'")

            slug = keyword.replace(" ", "-")
            url  = f"https://www.naukri.com/{slug}-jobs?jobAge=1"  # last 24 h

            try:
                page.goto(url, timeout=60_000)
                page.wait_for_timeout(random.randint(3000, 5000))

                listings = page.query_selector_all("article.jobTuple")
                print(f"   Found {len(listings)} listings")

                for job in listings[:max_jobs]:
                    try:
                        title   = job.query_selector("a.title").inner_text().strip()
                        company = job.query_selector("a.subTitle").inner_text().strip()
                        loc_els = job.query_selector_all("li.location span")
                        loc_text = ", ".join(el.inner_text().strip() for el in loc_els) or "India"
                        posted  = job.query_selector("span.jobAge").inner_text().strip()
                        link    = job.query_selector("a.title").get_attribute("href").split("?")[0]

                        jobs.append({
                            "title":    title,
                            "company":  company,
                            "location": loc_text,
                            "posted":   posted,
                            "link":     link,
                            "source":   "Naukri",
                        })
                    except Exception:
                        continue

            except Exception as e:
                print(f"   ⚠️  Naukri failed for '{keyword}': {e}")
                continue

        browser.close()

    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# Public API — combined fetch
# ─────────────────────────────────────────────────────────────────────────────
def fetch_jobs(keywords, locations, max_jobs=20):
    """Fetch from LinkedIn + Naukri and return a deduplicated combined list."""
    all_jobs = []

    # LinkedIn
    try:
        li_jobs = fetch_linkedin_jobs(keywords, locations, max_jobs)
        print(f"📦  LinkedIn returned {len(li_jobs)} jobs")
        all_jobs.extend(li_jobs)
    except Exception as e:
        print(f"❌  LinkedIn scraper error: {e}")

    # Naukri (keywords only — location baked into slug is unreliable)
    try:
        nk_jobs = fetch_naukri_jobs(keywords, max_jobs)
        print(f"📦  Naukri returned {len(nk_jobs)} jobs")
        all_jobs.extend(nk_jobs)
    except Exception as e:
        print(f"❌  Naukri scraper error: {e}")

    # Deduplicate by link
    seen, unique = set(), []
    for j in all_jobs:
        if j["link"] not in seen:
            seen.add(j["link"])
            unique.append(j)

    return unique