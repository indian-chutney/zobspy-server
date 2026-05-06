from datetime import datetime, timedelta
from typing import Optional
import re
import requests
from bs4 import BeautifulSoup

def _parse_date(tag) -> Optional[str]:
    """Extract posting date from a <time> tag and return dd_mm_yyyy string."""
    if not tag:
        return None
    dt_str = tag.get("datetime", "")
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
        try:
            return datetime.strptime(dt_str, fmt).strftime("%d_%m_%Y")
        except ValueError:
            continue
    # fallback: relative text like "2 days ago"
    text = tag.get_text(strip=True).lower()
    today = datetime.now()
    if "today" in text:
        return today.strftime("%d_%m_%Y")
    if "yesterday" in text:
        return (today - timedelta(days=1)).strftime("%d_%m_%Y")
    m = re.search(r"(\d+)\s+day", text)
    if m:
        return (today - timedelta(days=int(m.group(1)))).strftime("%d_%m_%Y")
    m = re.search(r"(\d+)\s+week", text)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).strftime("%d_%m_%Y")
    m = re.search(r"(\d+)\s+month", text)
    if m:
        return (today - timedelta(days=int(m.group(1)) * 30)).strftime("%d_%m_%Y")
    return None


def _parse_work_type(title: str, location: str, description: str) -> str:
    """Infer Remote / Hybrid / Onsite from available text."""
    combined = f"{title} {location} {description}".lower()
    if "remote" in combined:
        return "Remote"
    if "hybrid" in combined:
        return "Hybrid"
    return "Onsite"


def _parse_experience(description: str) -> Optional[str]:
    """Try to pull experience requirement from job description."""
    if not description:
        return None
    patterns = [
        r"(\d+\+?\s*[-–to]*\s*\d*\s+years?)\s+of\s+experience",
        r"(\d+\+?\s+years?)\s+experience",
        r"experience[:\s]+(\d+\+?\s*[-–to]*\s*\d*\s+years?)",
        r"minimum\s+(\d+\+?\s+years?)",
    ]
    for pat in patterns:
        m = re.search(pat, description, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _get_job_details(session: requests.Session, job_id: str) -> dict:
    """
    Fetch individual job page and extract:
    description, experience, work_type clues, apply link.
    """
    url = f"https://www.linkedin.com/jobs/view/{job_id}"
    try:
        resp = session.get(url, timeout=10)
        if resp.status_code != 200:
            return {}
    except Exception:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── description ──
    description = ""
    for cls in ["show-more-less-html__markup", "description__text", "jobs-description"]:
        div = soup.find("div", class_=lambda x: x and cls in x)
        if div:
            description = div.get_text(separator=" ", strip=True)
            break

    # ── direct apply URL ──
    apply_url = None
    code_tag = soup.find("code", id="applyUrl")
    if code_tag:
        raw = str(code_tag)
        m = re.search(r'url=([^"&\s>]+)', raw)
        if m:
            from urllib.parse import unquote
            decoded = unquote(m.group(1)).split("&urlHash=")[0]
            if "linkedin.com" not in decoded.lower():
                apply_url = decoded

    return {
        "description": description,
        "apply_url": apply_url or url,   # fall back to job page itself
        "experience": _parse_experience(description),
        "description_raw": description,
    }