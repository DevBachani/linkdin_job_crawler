from playwright.sync_api import sync_playwright

def fetch_jobs(keywords, locations, max_jobs=20):
    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for keyword in keywords:
            for location in locations:
                print(f"🔎 Searching: {keyword} in {location}")

                search_keyword = keyword.replace(" ", "%20")
                search_location = location.replace(" ", "%20")

                # LinkedIn search: last 24 hours + remote jobs
                url = f"https://www.linkedin.com/jobs/search/?keywords={search_keyword}&location={search_location}&f_TPR=r86400&f_WT=2"

                page.goto(url, timeout=60000)
                page.wait_for_timeout(4000)

                listings = page.query_selector_all("div.base-card")

                for job in listings[:max_jobs]:
                    try:
                        title = job.query_selector("h3").inner_text().strip()
                        company = job.query_selector("h4").inner_text().strip()
                        location_text = job.query_selector("span.job-search-card__location").inner_text().strip()
                        posted_text = job.query_selector("time").inner_text().strip()
                        job_link = job.query_selector("a.base-card__full-link").get_attribute("href")
                        job_link = job_link.split("?")[0].strip()  # remove tracking query params


                        # Send normal browser link (reliable)
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location_text,
                            "posted": posted_text,
                            "link": job_link  # browser-friendly link
                        })
                    except Exception:
                        continue

        browser.close()

    return jobs
