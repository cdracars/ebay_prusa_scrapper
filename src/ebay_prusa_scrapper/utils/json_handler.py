# src/ebay_prusa_scrapper/utils/json_handler.py
"""JSON handling utilities"""
import json
from typing import List, Dict, Any
from datetime import datetime

from ..config.constants import OFFICIAL_PRICES, UPGRADE_MAX_PRICE
from ..models.listing import Listing
from ..models.types import ModelStats, UnknownModelStats

def create_model_stats() -> ModelStats:
    """Create model statistics with proper initialization"""
    return {
        "count": 0,
        "price_range": {
            "min": float('inf'),
            "max": float('-inf')
        },
        "below_msrp": 0,
        "listings_with_shipping": 0
    }

def write_batch_to_file(batch: List[Dict[str, Any]], filename: str, is_first: bool):
    """Write a batch of listings to a JSON file with proper formatting"""
    mode = 'w' if is_first else 'a'
    with open(filename, mode, encoding='utf-8') as f:
        if is_first:
            # Start the JSON array directly
            f.write('{\n"listings": [\n')

        # Write batch with proper JSON formatting
        json_str = json.dumps(batch, indent=2)
        if not is_first:
            f.write(',\n')
        # Remove the outer array brackets since we're building the array incrementally
        json_str = json_str[1:-1].strip()
        f.write(json_str)

def create_unknown_stats() -> UnknownModelStats:
    """Create statistics for unknown model"""
    return {"count": 0}

def create_summary_json(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a condensed summary with improved accuracy"""
    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_listings": len(listings),
        "models": {
            "MK3S": create_model_stats(),
            "MK4": create_model_stats(),
            "MINI": create_model_stats(),
            "CORE": create_model_stats(),
            "Unknown": create_unknown_stats()
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
        },
        # New section for auction type tracking
        "auction_types": {
            "Buy It Now": 0,
            "Auction": 0,
            "Hybrid": 0
        }
    }

    total_printer_price = 0
    total_upgrade_price = 0
    valid_printer_prices = 0
    valid_upgrade_prices = 0

    for listing_dict in listings:
        listing = Listing.from_dict(listing_dict)
        category = listing.category
        model = listing.model
        price = listing.price
        total_cost = listing.total_cost

        auction_type = listing_dict.get('auction_type', 'Buy It Now')
        summary["auction_types"][auction_type] += 1

        if category == "printer":
            summary["categories"]["printer"]["count"] += 1

            if isinstance(price, (int, float)) and price > 0:
                if model != "Unknown" and listing.is_valid_price():
                    total_printer_price += price
                    valid_printer_prices += 1

            if listing.has_shipping_info():
                summary["categories"]["printer"]["listings_with_shipping"] += 1

            model_info = summary["models"][model]
            if model != "Unknown":
                model_info["count"] += 1
                model_info = model_info  # type: ModelStats  # Tell mypy this is ModelStats

                # Track shipping at model level
                if listing.has_shipping_info():
                    model_info["listings_with_shipping"] += 1

                # Only update price range if total cost is valid for the model
                if isinstance(total_cost, (int, float)) and total_cost > 0:
                    if listing.is_valid_price():
                        model_info["price_range"]["min"] = min(model_info["price_range"]["min"], total_cost)
                        model_info["price_range"]["max"] = max(model_info["price_range"]["max"], total_cost)

                if (isinstance(listing.price_vs_official, (int, float)) and
                    listing.price_vs_official < 0 and
                    model in OFFICIAL_PRICES and
                    listing.is_valid_price()):
                    model_info["below_msrp"] += 1
                    summary["categories"]["printer"]["listings_below_msrp"] += 1
            else:
                # Handle Unknown model case
                model_info["count"] += 1  # type: UnknownModelStats

        else:  # upgrade
            summary["categories"]["upgrade"]["count"] += 1

            # Validate upgrade prices
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
            title_lower = listing.title.lower()
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
        model_info = summary["models"][model]  # type: ModelStats
        price_range = model_info["price_range"]
        if price_range["min"] == float('inf') or price_range["max"] == float('-inf'):
            model_info["price_range"] = None

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