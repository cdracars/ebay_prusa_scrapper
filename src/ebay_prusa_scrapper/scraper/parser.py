# src/scraper/parser.py
"""HTML parsing functions for eBay listings"""
import re
import logging
from typing import Optional, Dict, Any, Union
from bs4 import BeautifulSoup
from models.listing import Listing
from .classifier import detect_model, classify_listing
from datetime import datetime, timedelta

def detect_auction_type(item: BeautifulSoup) -> str:
    """
    Detect the auction type based on eBay's HTML structure

    Possible return values:
    - "Buy It Now": Fixed price listing
    - "Auction": Traditional bidding listing
    - "Hybrid": Listings with both Buy It Now and bidding options
    """
    # Look for specific indicators of auction type
    buy_now_tag = item.select_one('.s-item__purchase-options-with-icon')
    bid_tag = item.select_one('.s-item__bidCount')

    # Check for bidding indicators
    has_bids = bid_tag is not None and bid_tag.get_text(strip=True)

    # Check for Buy It Now
    buy_now_text = buy_now_tag.get_text(strip=True).lower() if buy_now_tag else ""
    is_buy_now = "buy it now" in buy_now_text

    # Determine auction type
    if has_bids and is_buy_now:
        return "Hybrid"
    elif has_bids:
        return "Auction"
    elif is_buy_now:
        return "Buy It Now"

    # Default fallback
    return "Buy It Now"

def parse_auction_time(item: BeautifulSoup) -> Optional[Dict[str, Union[str, int]]]:
    """
    Extract auction time information from eBay listing

    Returns a dictionary with:
    - time_remaining: String representation of time left (e.g., "2d 6h")
    - seconds_remaining: Total seconds remaining
    - end_time: Estimated end time of the auction
    """
    try:
        # Look for time remaining tags
        time_tag = item.select_one('.s-item__time-left')

        if not time_tag:
            return None

        time_str = time_tag.get_text(strip=True)

        # Parsing time remaining (e.g., "2d 6h", "12h 30m", "6m left")
        def parse_time_str(time_str: str) -> Optional[Dict[str, Union[str, int]]]:
            # Remove 'left' if present
            time_str = time_str.replace('left', '').strip()

            # Days parsing
            days_match = re.search(r'(\d+)d', time_str)
            hours_match = re.search(r'(\d+)h', time_str)
            mins_match = re.search(r'(\d+)m', time_str)

            days = int(days_match.group(1)) if days_match else 0
            hours = int(hours_match.group(1)) if hours_match else 0
            mins = int(mins_match.group(1)) if mins_match else 0

            # Calculate total seconds
            total_seconds = days * 86400 + hours * 3600 + mins * 60

            # Calculate end time
            end_time = datetime.now() + timedelta(
                days=days,
                hours=hours,
                minutes=mins
            )

            return {
                "time_remaining": time_str,
                "seconds_remaining": total_seconds,
                "end_time": end_time.isoformat()
            }

        return parse_time_str(time_str)

    except Exception as e:
        logging.warning(f"Error parsing auction time: {str(e)}")
        return None

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

         # Detect auction type
        auction_type = detect_auction_type(item)

        # Get auction time information if applicable
        auction_time = None
        if auction_type in ["Auction", "Hybrid"]:
            auction_time = parse_auction_time(item)

        # Create listing data
        listing = Listing(
            platform="eBay",
            title=title,
            price=price_val,
            shipping_cost=shipping_val,
            total_cost=None,
            price_vs_official=None,
            seller_info=seller_info_str,
            feedback_count=feedback_count,
            rating_percent=rating_percent,
            link=link,
            category=category,
            model=model,
            auction_type=auction_type
        )

        # Calculate price comparisons
        listing.calculate_price_comparison()

        # Convert to dictionary and add auction time if exists
        listing_dict = listing.to_dict()
        if auction_time:
            listing_dict['auction_time'] = auction_time

        return listing.to_dict()

    except Exception as e:
        logging.error(f"Error parsing listing: {str(e)}")
        return None