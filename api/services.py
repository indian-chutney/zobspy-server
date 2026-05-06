import requests
import time
from datetime import datetime
import random
import pandas as pd
import re
from bs4 import BeautifulSoup
from .utils import _get_job_details, _parse_date, _parse_experience, _parse_work_type

linkedin_companies = ["ascendum", "infovision", "axi", "13brinda", "balbix", "infocepts", "tcs"]
custom_companies = ["appen", "thomson reuters", "alignerr"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def linkedin_scraper(
    company_name: str,
    max_jobs: int = 10,
    fetch_details: bool = True,          # set False for speed (skips job page)
    delay_between_requests: float = 2.0,
) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update(HEADERS)

    search_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    records = []
    start = 0
    seen_ids = set()

    print(f"🔍 Searching LinkedIn jobs for company: '{company_name}'")

    while len(records) < max_jobs:
        params = {
            "keywords": company_name,   # use company name as keyword
            "start": start,
            "pageSize": 25,
            "sortBy": "DD",             # date descending
        }

        try:
            resp = session.get(search_url, params=params, timeout=10)
        except Exception as e:
            print(f"  Request failed: {e}")
            break

        if resp.status_code == 429:
            print("  Rate limited — sleeping 30s...")
            time.sleep(30)
            continue
        if resp.status_code != 200:
            print(f"  Got status {resp.status_code}, stopping.")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_="base-card")

        if not cards:
            print(f"  No more cards found at offset {start}.")
            break

        page_hits = 0
        for card in cards:
            # ── extract job ID ──
            href_tag = card.find("a", class_="base-card__full-link")
            if not href_tag:
                continue
            href = href_tag.get("href", "")
            job_id = href.split("?")[0].split("-")[-1]
            if not job_id or job_id in seen_ids:
                continue

            # ── basic card fields ──
            title_tag   = card.find("h3", class_="base-search-card__title")
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            location_tag= card.find("span", class_="job-search-card__location")
            time_tag    = card.find("time")

            title    = title_tag.get_text(strip=True)    if title_tag    else "N/A"
            company  = company_tag.get_text(strip=True)  if company_tag  else "N/A"
            location = location_tag.get_text(strip=True) if location_tag else "N/A"
            post_date= _parse_date(time_tag)

            # ── filter by company name (loose match) ──
            if company_name.lower() not in company.lower():
                continue

            seen_ids.add(job_id)
            job_url = href.split("?")[0]

            # ── fetch detail page ──
            description = ""
            apply_url   = job_url
            experience  = None
            work_type   = _parse_work_type(title, location, "")

            if fetch_details:
                time.sleep(delay_between_requests + random.uniform(0, 1))
                details   = _get_job_details(session, job_id)
                description = details.get("description", "")
                apply_url   = details.get("apply_url", job_url)
                experience  = details.get("experience")
                work_type   = _parse_work_type(title, location, description)

            records.append({
                "Job_name":             title,
                "Job_description":      description,
                "Posting_date":         post_date,
                "Experience":           experience,
                "Location":             location,
                "Company_name":         company,
                "Job_application_link": apply_url,
                "Type":                 work_type,
            })

            page_hits += 1
            print(f"  [{len(records)}] {title} @ {company} — {location}")

            if len(records) >= max_jobs:
                break

        start += 25

        # if the whole page had zero matching company cards, stop
        if page_hits == 0 and start > 200:
            print("  No matching company cards for several pages, stopping.")
            break

        # polite delay between pages
        time.sleep(delay_between_requests)

    df = pd.DataFrame(records, columns=[
        "Job_name", "Job_description", "Posting_date",
        "Experience", "Location", "Company_name",
        "Job_application_link", "Type"
    ])

    print(f"\n✅ Done. {len(df)} jobs collected for '{company_name}'.")
    return df

def custom_scraper(name):
    if name.lower() == "appen":

        url = "https://api.lever.co/v0/postings/appen-2?mode=json"
        res = requests.get(url)
        data = res.json()

        jobs_data = []

        for job in data:
            # Basic fields
            title = job.get("text", "N/A")
            location = job.get("categories", {}).get("location", "N/A")
            link = job.get("hostedUrl", "N/A")
            company = "Appen"

            # Posting date
            created = job.get("createdAt")
            if created:
                posting_date = datetime.fromtimestamp(created/1000).strftime("%d_%m_%Y")
            else:
                posting_date = "N/A"

            # 🔥 Fetch FULL Job Description (second request)
            jd_text = "N/A"
            experience = "N/A"
            job_type = "N/A"

            try:
                jd_res = requests.get(link)
                soup = BeautifulSoup(jd_res.text, "html.parser")

                desc_div = soup.find("div", class_="content")
                if desc_div:
                    jd_text = desc_div.get_text(separator=" ", strip=True)

                    # 🔥 Experience extraction (strict numeric)
                    exp_match = re.search(r'(\d+\+?\s*(?:-\s*\d+\+?)?\s*years?)', jd_text, re.IGNORECASE)
                    if exp_match:
                        experience = exp_match.group(1)

                    # 🔥 Job type detection
                    jd_lower = jd_text.lower()
                    if "remote" in jd_lower:
                        job_type = "Remote"
                    elif "hybrid" in jd_lower:
                        job_type = "Hybrid"
                    elif "onsite" in jd_lower or "on-site" in jd_lower:
                        job_type = "Onsite"

            except:
                pass

            jobs_data.append({
                "Job_name": title,
                "Job_description": jd_text,
                "Posting_date": posting_date,
                "Experience": experience,
                "Location": location,
                "Company_name": company,
                "Job_application_link": link,
                "Type": job_type
            })

        df = pd.DataFrame(jobs_data)

        return df
    
    if name.lower() == "thomson reuters":
        max_jobs = 10
        offset = 0
        limit = 10

        jobs_data = []

        base_url = "https://thomsonreuters.wd5.myworkdayjobs.com/wday/cxs/thomsonreuters/External_Career_Site/jobs"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        # ---------------- SCRAPING ----------------
        while len(jobs_data) < max_jobs:

            payload = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": ""
            }

            try:
                res = requests.post(base_url, json=payload, headers=headers, timeout=15)
                data = res.json()
            except Exception as e:
                print("Error fetching API:", e)
                break

            jobs = data.get("jobPostings", [])

            if not jobs:
                break

            for job in jobs:
                if len(jobs_data) >= max_jobs:
                    break

                title = job.get("title", "N/A")
                location = job.get("locationsText", "N/A")

                external_path = job.get("externalPath", "")
                link = f"https://thomsonreuters.wd5.myworkdayjobs.com/en-US/External_Career_Site{external_path}"

                posted = job.get("postedOn", "")
                posting_date = "N/A"

                try:
                    posting_date = datetime.strptime(posted, "%Y-%m-%d").strftime("%d_%m_%Y")
                except:
                    pass

                company = "Thomson Reuters"

                jd_text = "N/A"
                experience = "N/A"
                job_type = "N/A"

                # ---------------- JOB DESCRIPTION SCRAPE ----------------
                try:
                    jd_res = requests.get(link, headers=headers, timeout=15)
                    soup = BeautifulSoup(jd_res.text, "html.parser")

                    desc_div = soup.find("div", {"data-automation-id": "jobPostingDescription"})

                    if desc_div:
                        jd_text = desc_div.get_text(separator=" ", strip=True)
                        jd_lower = jd_text.lower()

                        sentences = re.split(r'(?<=[.!?]) +', jd_text)

                        for sentence in sentences:
                            s = sentence.lower()

                            if "year" in s and "experience" in s:
                                if any(x in s for x in ["about", "company", "founded", "history"]):
                                    continue

                                match = re.search(r'(\d+\+?\s*(?:-\s*\d+\+?)?\s*years?)', sentence, re.IGNORECASE)
                                if match:
                                    experience = match.group(1)
                                    break

                        if "remote" in jd_lower:
                            job_type = "Remote"
                        elif "hybrid" in jd_lower:
                            job_type = "Hybrid"
                        elif "on-site" in jd_lower or "onsite" in jd_lower:
                            job_type = "Onsite"

                except:
                    pass

                jobs_data.append({
                    "Job_name": title,
                    "Job_description": jd_text,
                    "Posting_date": posting_date,
                    "Experience": experience,
                    "Location": location,
                    "Company_name": company,
                    "Job_application_link": link,
                    "Type": job_type
                })

            print(f"Fetched {len(jobs_data)} jobs so far...")

            offset += limit

        df = pd.DataFrame(jobs_data)


        return df
    if name.lower() == "alignerr":
        pass


def scrape(query):
    results = []

    try:
        query = query.lower()

        if query == "all":
            for comp in linkedin_companies:
                df = linkedin_scraper(comp)
                if df is not None:
                    results.append(df)

            for comp in custom_companies:
                df = custom_scraper(comp)
                if df is not None:
                    results.append(df)

        else:
            if query in linkedin_companies:
                df = linkedin_scraper(query)
            elif query in custom_companies:
                df = custom_scraper(query)
            else:
                raise ValueError(f"Unknown company: {query}")

            if df is not None:
                results.append(df)

        if not results:
            raise ValueError("No data collected")

        return pd.concat(results, ignore_index=True)

    except Exception as e:
        # You can log this later
        raise RuntimeError(f"Scraping failed: {str(e)}")

''' 
def scrape(query):
    data = [
        {"name": "Alice", "company": "TCS"},
        {"name": "Bob", "company": "Infosys"},
        {"name": "Charlie", "company": "Google"},
    ]

    df = pd.DataFrame(data)
    return df

'''
