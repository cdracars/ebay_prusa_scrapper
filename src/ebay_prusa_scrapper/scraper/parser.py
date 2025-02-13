# src/scraper/parser.py
"""HTML parsing functions for eBay listings"""
import re
import logging
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from models.listing import Listing
from .classifier import detect_model, classify_listing

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
            model=model
        )

        # Calculate price comparisons
        listing.calculate_price_comparison()

        return listing.to_dict()

    except Exception as e:
        logging.error(f"Error parsing listing: {str(e)}")
        return None