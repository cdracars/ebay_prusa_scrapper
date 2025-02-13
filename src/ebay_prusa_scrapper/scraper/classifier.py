# src/scraper/classifier.py
"""Classification functions for eBay listings"""
import re
from ..config.constants import (
    MODEL_PATTERNS,
    UPGRADE_KEYWORDS,
    PRINTER_KEYWORDS,
    OFFICIAL_PRICES,
    PRICE_THRESHOLDS
)

def detect_model(title: str) -> str:
    """
    Detect printer model from listing title with improved accuracy
    Returns model name or "Unknown" if unclear
    """
    title_lower = title.lower()
    
    # Check each model's patterns
    for model, patterns in MODEL_PATTERNS.items():
        if any(re.search(pattern, title_lower) for pattern in patterns):
            # Additional validation to prevent false positives
            if "upgrade" not in title_lower and "part" not in title_lower:
                return model
            
    return "Unknown"

def is_valid_price_for_model(model: str, price: float) -> bool:
    """Validate if a price is reasonable for a given model"""
    if model not in PRICE_THRESHOLDS:
        return False
    min_price, max_price = PRICE_THRESHOLDS[model]
    return min_price <= price <= max_price

def classify_listing(title: str, price_val: float) -> str:
    """
    Classify listing as printer or upgrade with improved accuracy
    Returns 'printer' or 'upgrade'
    """
    title_lower = title.lower()
    
    # Check for upgrade keywords first
    if any(kw in title_lower for kw in UPGRADE_KEYWORDS):
        return "upgrade"
        
    # Check for printer keywords
    is_printer = any(kw in title_lower for kw in PRINTER_KEYWORDS)
    
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