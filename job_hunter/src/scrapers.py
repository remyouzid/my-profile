"""
Job board scrapers — Welcome to the Jungle, Indeed France, France Travail.
Each returns a list of dicts with keys:
  title, company, location, url, description, contract, posted_date, source
"""

import time
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def _get(url: str, params: dict = None) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        print(f"  [!] Erreur requête {url}: {e}")
        return None


# ─── Welcome to the Jungle ───────────────────────────────────────────────────

def scrape_wttj(query: str, location: str = "Paris", max_pages: int = 3) -> list[dict]:
    """Scrape Welcome to the Jungle job listings."""
    jobs = []
    base_url = "https://www.welcometothejungle.com/fr/jobs"

    for page in range(1, max_pages + 1):
        params = {
            "refinementList[contract_type_names][]": "Internship",
            "query": query,
            "page": page,
        }
        resp = _get(base_url, params)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("li[data-testid='search-results-list-item-wrapper']")
        if not cards:
            cards = soup.select("article[class*='sc-']")

        for card in cards:
            title_el = card.select_one("h3, [data-testid='job-card-title']")
            company_el = card.select_one("[data-testid='job-card-company-name'], span[class*='company']")
            link_el = card.select_one("a[href*='/jobs/']")
            location_el = card.select_one("[data-testid='job-card-location']")

            if not title_el or not link_el:
                continue

            job_url = "https://www.welcometothejungle.com" + link_el["href"]
            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else location,
                "url": job_url,
                "description": "",
                "contract": "Stage",
                "posted_date": datetime.today().strftime("%Y-%m-%d"),
                "source": "WTTJ",
            })

        time.sleep(1.5)

    return jobs


# ─── Indeed France ───────────────────────────────────────────────────────────

def scrape_indeed(query: str, location: str = "Paris", max_pages: int = 3) -> list[dict]:
    """Scrape Indeed France job listings."""
    jobs = []
    base_url = "https://fr.indeed.com/jobs"

    for page in range(max_pages):
        params = {"q": query, "l": location, "start": page * 10}
        resp = _get(base_url, params)
        if not resp:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div.job_seen_beacon, div[class*='jobsearch-SerpJobCard']")

        for card in cards:
            title_el = card.select_one("h2.jobTitle span, span[title]")
            company_el = card.select_one("span[data-testid='company-name'], .companyName")
            location_el = card.select_one("[data-testid='text-location'], .companyLocation")
            link_el = card.select_one("a[id^='job_'], a[href*='/rc/clk']")

            if not title_el:
                continue

            href = link_el["href"] if link_el else ""
            job_url = ("https://fr.indeed.com" + href) if href.startswith("/") else href

            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else location,
                "url": job_url,
                "description": "",
                "contract": "Stage",
                "posted_date": datetime.today().strftime("%Y-%m-%d"),
                "source": "Indeed",
            })

        time.sleep(2)

    return jobs


# ─── France Travail (Pôle Emploi) API ────────────────────────────────────────

def scrape_france_travail(query: str, location_code: str = "75", max_results: int = 50) -> list[dict]:
    """
    Search France Travail official API.
    Requires free registration at: https://francetravail.io/data/api/offres-demploi
    Set env vars: FRANCE_TRAVAIL_CLIENT_ID and FRANCE_TRAVAIL_CLIENT_SECRET
    """
    import os

    client_id = os.getenv("FRANCE_TRAVAIL_CLIENT_ID")
    client_secret = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("  [!] France Travail API non configurée (FRANCE_TRAVAIL_CLIENT_ID / SECRET manquants)")
        return []

    # Get OAuth token
    token_resp = requests.post(
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
        params={"realm": "/partenaire"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "api_offresdemploiv2 o2dsoffre",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        print(f"  [!] Erreur authentification France Travail: {token_resp.status_code}")
        return []

    token = token_resp.json().get("access_token", "")

    search_resp = requests.get(
        "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        params={
            "motsCles": query,
            "departement": location_code,
            "typeContrat": "ST",
            "range": f"0-{min(max_results - 1, 149)}",
        },
        timeout=15,
    )

    if search_resp.status_code != 200:
        return []

    data = search_resp.json()
    jobs = []
    for offer in data.get("resultats", []):
        jobs.append({
            "title": offer.get("intitule", ""),
            "company": offer.get("entreprise", {}).get("nom", "N/A"),
            "location": offer.get("lieuTravail", {}).get("libelle", ""),
            "url": offer.get("origineOffre", {}).get("urlOrigine", ""),
            "description": offer.get("description", ""),
            "contract": "Stage",
            "posted_date": offer.get("dateCreation", datetime.today().strftime("%Y-%m-%d"))[:10],
            "source": "France Travail",
        })

    return jobs


# ─── Fetch full job description ───────────────────────────────────────────────

def fetch_description(job: dict) -> str:
    """Fetch and extract the full job description from the job URL."""
    if job.get("description"):
        return job["description"]

    resp = _get(job["url"])
    if not resp:
        return ""

    soup = BeautifulSoup(resp.text, "lxml")

    for selector in [
        "[data-testid='job-section-description']",
        "div.jobsearch-jobDescriptionText",
        "section[class*='description']",
        "div[class*='job-description']",
        "article",
    ]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(separator="\n", strip=True)[:4000]

    return soup.get_text(separator="\n", strip=True)[:4000]
