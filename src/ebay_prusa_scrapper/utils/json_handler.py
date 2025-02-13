
"""JSON handling utilities"""
import json
from typing import List, Dict, Any
from datetime import datetime

from ebay_prusa_scrapper.scraper.classifier import is_valid_price_for_model
from config.constants import OFFICIAL_PRICES, UPGRADE_MAX_PRICE
from models.listing import Listing

def create_model_info() -> Dict[str, Any]:
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

    for listing_dict in listings:
        listing = Listing.from_dict(listing_dict)
        category = listing.category
        model = listing.model
        price = listing.price
        total_cost = listing.total_cost

        if category == "printer":
            summary["categories"]["printer"]["count"] += 1

            if isinstance(price, (int, float)) and price > 0:
                if model != "Unknown" and listing.is_valid_price():
                    total_printer_price += price
                    valid_printer_prices += 1

            if listing.has_shipping_info():
                summary["categories"]["printer"]["listings_with_shipping"] += 1

            if model in summary["models"]:
                model_info = summary["models"][model]
                model_info["count"] += 1

                # Track shipping at model level
                Listing.track_model_shipping(model_info, listing_dict)

                # Only update price range if total cost is valid for the model
                if isinstance(total_cost, (int, float)) and total_cost > 0:
                    if model != "Unknown" and listing.is_valid_price():
                        model_info["price_range"]["min"] = min(model_info["price_range"]["min"], total_cost)
                        model_info["price_range"]["max"] = max(model_info["price_range"]["max"], total_cost)

                if (isinstance(listing.price_vs_official, (int, float)) and
                    listing.price_vs_official < 0 and
                    model in OFFICIAL_PRICES and
                    listing.is_valid_price()):
                    model_info["below_msrp"] += 1
                    summary["categories"]["printer"]["listings_below_msrp"] += 1

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