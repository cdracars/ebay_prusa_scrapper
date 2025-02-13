# src/scraper/ebay_scraper.py
"""Main eBay scraping functionality"""
import logging
import time
from typing import Dict, Any, Optional, Iterator, List
import requests
from bs4 import BeautifulSoup

from config.settings import EbayScraperConfig
from utils.rate_limiter import RequestRateLimiter
from .parser import parse_listing, get_total_pages

def make_request(url: str, params: Dict[str, Any], rate_limiter: RequestRateLimiter) -> Optional[requests.Response]:
    """Make HTTP request with retry logic and rate limiting"""
    for attempt in range(EbayScraperConfig.MAX_RETRIES):
        try:
            with rate_limiter.limit_rate():
                response = requests.get(
                    url,
                    params=params,
                    timeout=EbayScraperConfig.TIMEOUT
                )
                response.raise_for_status()
                return response
        except requests.RequestException as e:
            logging.warning(f"Request failed (attempt {attempt + 1}/{EbayScraperConfig.MAX_RETRIES}): {str(e)}")
            if attempt == EbayScraperConfig.MAX_RETRIES - 1:
                logging.error(f"Max retries exceeded for URL: {url}")
                return None
            time.sleep(2 ** attempt)  # Exponential backoff
    return None

def scrape_ebay_listings(
    keyword: str,
    zip_code: str = "73120",
    max_pages: int = 1
) -> Iterator[List[Dict[str, Any]]]:
    """
    Generator function to scrape eBay listings, yielding results in batches
    to manage memory usage
    """
    base_url = "https://www.ebay.com/sch/i.html"
    rate_limiter = RequestRateLimiter(EbayScraperConfig.REQUEST_DELAY)

    params = {
        "_nkw": keyword,
        "_stpos": zip_code,
        "_ipg": 50,
        "LH_PrefLoc": 2,
    }

    # Get total pages
    response = make_request(base_url, params, rate_limiter)
    if not response:
        logging.error("Failed to get initial page")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    total_pages = min(get_total_pages(soup), max_pages)

    seen = set()
    current_batch = []

    for page_num in range(1, total_pages + 1):
        params["_pgn"] = page_num
        logging.info(f"Scraping page {page_num}/{total_pages} for keyword: {keyword}")

        response = make_request(base_url, params, rate_limiter)
        if not response:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(".s-item")

        for item in items:
            try:
                listing = parse_listing(item)
                if not listing:
                    continue

                dedupe_key = (listing["title"], listing["link"])
                if dedupe_key in seen:
                    continue

                seen.add(dedupe_key)
                current_batch.append(listing)

                # Yield batch when it reaches the configured size
                if len(current_batch) >= EbayScraperConfig.BATCH_SIZE:
                    yield current_batch
                    current_batch = []

            except Exception as e:
                logging.error(f"Error processing listing: {str(e)}")
                continue

    # Yield any remaining listings in the final batch
    if current_batch:
        yield current_batch