#!/usr/bin/env python3
"""
Enhanced eBay scraper with improvements to handle:
1. Rate limiting and request failures
2. Pagination issues
3. Memory efficiency
4. Data validation
5. Error handling
6. Proper JSON formatting
7. LLM-friendly summary output
Plus support for Prusa Core One model
"""

import json
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional, Iterator
import time
from contextlib import contextmanager
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Approx. official kit prices from Prusa3D.com (USD) for reference:
OFFICIAL_PRICES = {
    "MK3S": 799.0,  # kit price
    "MK4": 799.0,   # kit price (fully assembled is often ~1099)
    "MINI": 379.0,  # kit price
    "CORE": 399.0   # Core One price
}

class EbayScraperConfig:
    """Configuration class to manage scraper settings"""
    REQUEST_DELAY = 1.0  # Delay between requests in seconds
    MAX_RETRIES = 3
    TIMEOUT = 10
    BATCH_SIZE = 100  # Number of listings to process before writing to file

    @staticmethod
    def get_output_filename() -> str:
        """Generate timestamped output filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"ebay_listings_{timestamp}.json"

class RequestRateLimiter:
    """Handle rate limiting for requests"""
    def __init__(self, delay: float):
        self.delay = delay
        self.last_request_time = 0

    @contextmanager
    def limit_rate(self):
        """Context manager to ensure minimum delay between requests"""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        try:
            yield
        finally:
            self.last_request_time = time.time()

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

def detect_model(title: str) -> str:
    """Detect printer model from listing title with improved accuracy"""
    title_lower = title.lower()

    # Model detection patterns
    model_patterns = {
        "MK3S": [
            r'\bmk3\s*s\+?\b',  # matches mk3s, mk3s+
            r'\bmk3\s+s\+?\b',  # matches mk3 s, mk3 s+
            r'\bi3\s*mk3s\+?\b',  # matches i3 mk3s, i3 mk3s+
            r'prusa\s+mk3s\+?\b'  # matches prusa mk3s, prusa mk3s+
        ],
        "MK4": [
            r'\bmk4\b',  # matches mk4
            r'\bmk\s*4\b',  # matches mk4, mk 4
            r'\bi3\s*mk4\b',  # matches i3 mk4
            r'prusa\s+mk4\b'  # matches prusa mk4
        ],
        "MINI": [
            r'\bmini\+?\b',  # matches mini, mini+
            r'prusa\s+mini\+?\b',  # matches prusa mini, prusa mini+
            r'mini\s*\+\b'  # matches mini+, mini +
        ],
        "CORE": [
            r'\bcore\s*one\b',  # matches core one
            r'\bcore\s*1\b',  # matches core 1
            r'\bcore1\b',  # matches core1
            r'original\s+core\b',  # matches original core
            r'prusa\s+core'  # matches prusa core
        ]
    }

    # Check each model's patterns
    for model, patterns in model_patterns.items():
        if any(re.search(pattern, title_lower) for pattern in patterns):
            # Additional validation to prevent false positives
            if "upgrade" not in title_lower and "part" not in title_lower:
                return model

    return "Unknown"

def is_valid_price_for_model(model: str, price: float) -> bool:
    """Validate if a price is reasonable for a given model"""
    # Price thresholds by model (min, max)
    PRICE_THRESHOLDS = {
        "MK3S": (400, 1200),   # Kit $799, Assembled $1099
        "MK4": (500, 1300),    # Kit $799, Assembled $1099
        "MINI": (250, 500),    # Kit $379, Assembled $459
        "CORE": (300, 500)     # $399 standard price
    }

    if model not in PRICE_THRESHOLDS:
        return False

    min_price, max_price = PRICE_THRESHOLDS[model]
    return min_price <= price <= max_price

def parse_price(price_str: str) -> float:
    """Convert a price string to float, handling various formats"""
    try:
        # Remove currency symbols, commas, and whitespace
        clean_str = re.sub(r'[^\d.]', '', price_str)
        return float(clean_str)
    except (ValueError, AttributeError):
        logging.warning(f"Failed to parse price: {price_str}")
        return 0.0

def parse_shipping_cost(shipping_str: str) -> Optional[float]:
    """Parse shipping cost from various formats"""
    try:
        s = shipping_str.lower()
        if "free" in s:
            return 0.0
        if any(x in s for x in ["varies", "not specified", "see details"]):
            return None
        return parse_price(shipping_str)
    except (ValueError, AttributeError):
        return None

def parse_feedback_count(seller_info: str) -> Optional[int]:
    """Extract seller feedback count from seller info string"""
    try:
        match = re.search(r'\((\d+)\)', seller_info)
        return int(match.group(1)) if match else None
    except (AttributeError, ValueError):
        return None

def parse_rating_percent(seller_info: str) -> Optional[float]:
    """Extract seller rating percentage from seller info string"""
    try:
        match = re.search(r'(\d+(\.\d+)?)%', seller_info)
        return float(match.group(1)) if match else None
    except (AttributeError, ValueError):
        return None

def classify_listing(title: str, price_val: float) -> str:
    """Classify listing as printer or upgrade with improved accuracy"""
    title_lower = title.lower()

    # Definitive upgrade indicators
    upgrade_keywords = [
        "hotend", "frame", "bear upgrade", "nozzle", "extruder",
        "thermistor", "misumi", "sheet", "fan shroud", "bondtech",
        "thermistor sensor", "pinda", "sensor", "bobbin holder",
        "spool holder", "upgrade", "part", "spare", "component"
    ]

    # Definitive printer indicators
    printer_keywords = [
        "3d printer", "assembled", "complete kit", "full kit",
        "working printer", "printing", "fully built"
    ]

    # Check for upgrade keywords first
    if any(kw in title_lower for kw in upgrade_keywords):
        return "upgrade"

    # Check for printer keywords
    is_printer = any(kw in title_lower for kw in printer_keywords)

    # Price validation
    model = detect_model(title)
    if model in OFFICIAL_PRICES:
        if is_valid_price_for_model(model, price_val):
            return "printer"
        elif price_val < OFFICIAL_PRICES[model] * 0.3:  # If price is less than 30% of MSRP
            return "upgrade"  # Likely a part if price is too low

    # If we have explicit printer keywords, classify as printer
    if is_printer:
        return "printer"

    # Default to upgrade for ambiguous cases
    return "upgrade"

def track_model_shipping(model_info: Dict[str, Any], listing: Dict[str, Any]) -> None:
    """Track shipping information for a model"""
    shipping_cost = listing.get("shipping_cost")
    if isinstance(shipping_cost, (int, float)) or shipping_cost == 0:
        model_info["listings_with_shipping"] += 1

def create_model_info():
    """Create a fresh model info dictionary with proper initialization"""
    return {
        "count": 0,
        "price_range": {
            "min": float('inf'),
            "max": float('-inf')
        },
        "below_msrp": 0,
        "listings_with_shipping": 0
    }

def parse_listing(item: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """Extract listing information from a BeautifulSoup item element"""
    try:
        # Required fields
        title_tag = item.select_one('.s-item__title')
        price_tag = item.select_one('.s-item__price')
        link_tag = item.select_one('.s-item__link')
        shipping_tag = item.select_one('.s-item__logisticsCost')
        seller_info_tag = item.select_one('.s-item__seller-info-text')

        if not all([title_tag, price_tag, link_tag]):
            return None

        title = title_tag.get_text(strip=True)
        # Skip dummy "Shop on eBay" listings
        if title.lower().startswith("shop on ebay"):
            return None

        price_str = price_tag.get_text(strip=True)
        link = link_tag.get('href', '')
        shipping_str = shipping_tag.get_text(strip=True) if shipping_tag else "Varies"
        seller_info_str = seller_info_tag.get_text(strip=True) if seller_info_tag else ""

        # Parse all components
        price_val = parse_price(price_str)
        shipping_val = parse_shipping_cost(shipping_str)
        feedback_count = parse_feedback_count(seller_info_str)
        rating_percent = parse_rating_percent(seller_info_str)

        # Classify listing and detect model
        category = classify_listing(title, price_val)
        model = detect_model(title)

        listing_data = {
            "platform": "eBay",
            "title": title,
            "price": price_val,
            "shipping_cost": shipping_val if shipping_val is not None else "Varies/Unknown",
            "total_cost": None,
            "price_vs_official": None,
            "seller_info": seller_info_str,
            "feedback_count": feedback_count,
            "rating_percent": rating_percent,
            "link": link,
            "category": category,
            "model": model
        }

        # Calculate total cost and price comparison if possible
        if isinstance(shipping_val, (int, float)):
            total_cost = round(price_val + shipping_val, 2)
            listing_data["total_cost"] = total_cost
            if model in OFFICIAL_PRICES and is_valid_price_for_model(model, total_cost):
                delta = total_cost - OFFICIAL_PRICES[model]
                listing_data["price_vs_official"] = round(delta, 2)

        return listing_data

    except Exception as e:
        logging.error(f"Error parsing listing: {str(e)}")
        return None

def get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total number of pages from search results"""
    try:
        pagination = soup.select_one('.pagination__items')
        if not pagination:
            return 1

        links = pagination.select("li a")
        max_page = 1

        for link in links:
            try:
                page_num = int(link.get_text(strip=True))
                if page_num > max_page:
                    max_page = page_num
            except ValueError:
                continue

        return max_page
    except Exception as e:
        logging.warning(f"Error getting total pages: {str(e)}")
        return 1

def scrape_ebay_listings(
    keyword: str,
    zip_code: str = "73120",
    max_pages: int = 1
) -> Iterator[Dict[str, Any]]:
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

def write_batch_to_file(batch: List[Dict[str, Any]], filename: str, is_first: bool):
    """Write a batch of listings to a JSON file with proper formatting"""
    mode = 'w' if is_first else 'a'
    with open(filename, mode, encoding='utf-8') as f:
        if is_first:
            # Write header with proper JSON formatting
            instructions = {
                "instructions": {
                    "summary": "Group by category (printer/upgrade) and analyze pricing vs MSRP",
                    "key_metrics": [
                        "Compare total_cost (price + shipping) to official_price",
                        "Flag listings below MSRP",
                        "Note any missing shipping costs"
                    ],
                    "models": {
                        "MK3S": "Original i3 MK3S/+ ($799 MSRP)",
                        "MK4": "Next-gen i3 MK4 ($799 MSRP)",
                        "MINI": "MINI/+ ($379 MSRP)",
                        "CORE": "Core One ($399 MSRP)"
                    }
                }
            }
            f.write(json.dumps(instructions, indent=2))
            f.write(',\n"listings": [\n')

        # Write batch with proper JSON formatting
        json_str = json.dumps(batch, indent=2)
        if not is_first:
            f.write(',\n')
        # Remove the outer array brackets since we're building the array incrementally
        json_str = json_str[1:-1].strip()
        f.write(json_str)

def create_summary_json(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a condensed summary with improved accuracy"""
    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_listings": len(listings),
        "models": {
            "MK3S": create_model_info(),
            "MK4": create_model_info(),
            "MINI": create_model_info(),
            "CORE": create_model_info(),
            "Unknown": {"count": 0}  # Unknown model doesn't track prices
        },
        "categories": {
            "printer": {
                "count": 0,
                "avg_price": 0,
                "listings_with_shipping": 0,
                "listings_below_msrp": 0
            },
            "upgrade": {
                "count": 0,
                "popular_types": {},
                "avg_price": 0,
                "price_range": {
                    "min": float('inf'),
                    "max": float('-inf')
                }
            }
        }
    }

    total_printer_price = 0
    total_upgrade_price = 0
    valid_printer_prices = 0
    valid_upgrade_prices = 0

    for listing in listings:
        category = listing["category"]
        model = listing["model"]
        price = listing.get("price", 0)
        total_cost = listing.get("total_cost")

        if category == "printer":
            summary["categories"]["printer"]["count"] += 1

            if isinstance(price, (int, float)) and price > 0:
                # Only count prices that are within reasonable ranges
                if model != "Unknown" and is_valid_price_for_model(model, price):
                    total_printer_price += price
                    valid_printer_prices += 1

            # Track shipping at category level
            if isinstance(listing.get("shipping_cost"), (int, float)):
                summary["categories"]["printer"]["listings_with_shipping"] += 1

            if model in summary["models"]:
                model_info = summary["models"][model]
                model_info["count"] += 1

                # Track shipping at model level
                track_model_shipping(model_info, listing)

                # Only update price range if total cost is valid for the model
                if isinstance(total_cost, (int, float)) and total_cost > 0:
                    if model != "Unknown" and is_valid_price_for_model(model, total_cost):
                        model_info["price_range"]["min"] = min(model_info["price_range"]["min"], total_cost)
                        model_info["price_range"]["max"] = max(model_info["price_range"]["max"], total_cost)

                price_vs_official = listing.get("price_vs_official")
                if (isinstance(price_vs_official, (int, float)) and
                    price_vs_official < 0 and
                    model in OFFICIAL_PRICES and
                    is_valid_price_for_model(model, listing.get("total_cost", float('inf')))):
                    model_info["below_msrp"] += 1
                    summary["categories"]["printer"]["listings_below_msrp"] += 1

        else:  # upgrade
            summary["categories"]["upgrade"]["count"] += 1

            # Validate upgrade prices (exclude unreasonably high prices that might be printers)
            UPGRADE_MAX_PRICE = 300  # Most upgrades should be under this
            if isinstance(price, (int, float)) and 0 < price <= UPGRADE_MAX_PRICE:
                total_upgrade_price += price
                valid_upgrade_prices += 1
                summary["categories"]["upgrade"]["price_range"]["min"] = min(
                    summary["categories"]["upgrade"]["price_range"]["min"],
                    price
                )
                summary["categories"]["upgrade"]["price_range"]["max"] = max(
                    summary["categories"]["upgrade"]["price_range"]["max"],
                    price
                )

            # Track upgrade types
            title_lower = listing["title"].lower()
            for keyword in ["hotend", "frame", "nozzle", "extruder", "sheet", "bondtech", "bear", "pinda"]:
                if keyword in title_lower:
                    summary["categories"]["upgrade"]["popular_types"][keyword] = \
                        summary["categories"]["upgrade"]["popular_types"].get(keyword, 0) + 1

    # Calculate averages using only valid prices
    if valid_printer_prices > 0:
        summary["categories"]["printer"]["avg_price"] = round(total_printer_price / valid_printer_prices, 2)

    if valid_upgrade_prices > 0:
        summary["categories"]["upgrade"]["avg_price"] = round(total_upgrade_price / valid_upgrade_prices, 2)
    else:
        summary["categories"]["upgrade"]["price_range"] = None

    # Clean up price ranges that have no data
    for model in ["MK3S", "MK4", "MINI", "CORE"]:
        price_range = summary["models"][model]["price_range"]
        if price_range["min"] == float('inf') or price_range["max"] == float('-inf'):
            summary["models"][model]["price_range"] = None

    # Sort popular upgrade types by frequency
    if summary["categories"]["upgrade"]["popular_types"]:
        summary["categories"]["upgrade"]["popular_types"] = dict(
            sorted(
                summary["categories"]["upgrade"]["popular_types"].items(),
                key=lambda x: x[1],
                reverse=True
            )
        )

    return summary

def main():
    """Enhanced main function with better JSON handling"""
    keywords = ["Prusa MK3S", "Prusa MK4", "Prusa MINI", "Prusa Core One"]
    zip_code = "73120"
    max_pages = 2

    output_file = EbayScraperConfig.get_output_filename()
    summary_file = output_file.replace('.json', '_summary.json')
    is_first_batch = True
    all_listings = []

    try:
        # Scrape all listings
        for keyword in keywords:
            logging.info(f"Starting scrape for keyword: {keyword}")
            for batch in scrape_ebay_listings(keyword, zip_code, max_pages):
                write_batch_to_file(batch, output_file, is_first_batch)
                all_listings.extend(batch)
                is_first_batch = False

        # Close the main JSON file properly
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write('\n]}\n')

        # Create summary
        summary = create_summary_json(all_listings)

        # Write summary to file
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logging.info(f"Scraping completed. Results written to: {output_file}")
        logging.info(f"Summary written to: {summary_file}")

    except Exception as e:
        logging.error(f"Fatal error during scraping: {str(e)}")
        raise

if __name__ == "__main__":
    main()