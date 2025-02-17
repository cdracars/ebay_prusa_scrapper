# src/ebay_prusa_scrapper/utils/json_handler.py
"""JSON handling utilities with improved organization and typing"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..config.constants import OFFICIAL_PRICES, UPGRADE_MAX_PRICE
from ..models.listing import Listing
from ..models.types import (
    ModelStats, UnknownModelStats, AuctionInfo,
    PrinterCategory, UpgradeCategory
)

# Constants
ENDING_SOON_THRESHOLD = 3600  # 1 hour in seconds
UPGRADE_KEYWORDS = [
    "hotend", "frame", "nozzle", "extruder", "sheet",
    "bondtech", "bear", "pinda"
]
PRINTER_MODELS = ["MK3S", "MK4", "MINI", "CORE"]
CATEGORIES = ["printer", "upgrade"]

@dataclass
class PricingAccumulator:
    """Track price statistics with proper typing"""
    total_price: float = 0.0
    valid_count: int = 0

    def add_price(self, price: float) -> None:
        """Add a valid price to the accumulator"""
        self.total_price += price
        self.valid_count += 1

    def get_average(self) -> Optional[float]:
        """Calculate the average if there are valid prices"""
        if self.valid_count == 0:
            return None
        return round(self.total_price / self.valid_count, 2)

@dataclass
class AuctionAccumulator:
    """Track auction statistics"""
    total_bids: float = 0.0
    count: int = 0
    ending_soon: int = 0

    def add_auction(self, current_bid: float, seconds_remaining: int) -> None:
        """Add auction data to accumulator"""
        self.total_bids += current_bid
        self.count += 1
        if seconds_remaining < ENDING_SOON_THRESHOLD:
            self.ending_soon += 1

    def get_average_bid(self) -> Optional[float]:
        """Calculate average bid if there are auctions"""
        if self.count == 0:
            return None
        return round(self.total_bids / self.count, 2)

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

def create_unknown_stats() -> UnknownModelStats:
    """Create statistics for unknown model"""
    return {"count": 0}

def initialize_data_structure() -> Dict[str, Any]:
    """Initialize the complete data structure with proper typing"""
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_listings": 0,
        "models": {model: create_model_stats() for model in PRINTER_MODELS} |
                 {"Unknown": create_unknown_stats()},
        "categories": {
            "printer": {
                "count": 0,
                "avg_price": 0,
                "listings_with_shipping": 0,
                "listings_below_msrp": 0,
                "auctions": {
                    "active": [],
                    "ending_soon": []
                }
            },
            "upgrade": {
                "count": 0,
                "popular_types": {},
                "avg_price": 0,
                "price_range": {
                    "min": float('inf'),
                    "max": float('-inf')
                },
                "auctions": {
                    "active": [],
                    "ending_soon": []
                }
            }
        },
        "auction_types": {
            "Buy It Now": 0,
            "Auction": 0,
            "Hybrid": 0
        },
        "active_auctions": {
            "count": 0,
            "ending_soon": 0,
            "avg_current_bid": 0.0
        }
    }

def process_auction_data(
    listing_dict: Dict[str, Any],
    listing: Listing,
    data: Dict[str, Any],
    auction_stats: AuctionAccumulator
) -> None:
    """Process auction-specific data"""
    auction_type = listing_dict.get('auction_type', 'Buy It Now')
    data["auction_types"][auction_type] += 1

    if auction_type in ["Auction", "Hybrid"]:
        # Use the flattened fields instead of nested auction_time
        if listing.seconds_remaining is not None:
            auction_stats.add_auction(listing.price, listing.seconds_remaining)

            auction_info: AuctionInfo = {
                "title": listing.title,
                "current_bid": listing.price,
                "time_remaining": listing.time_remaining,
                "end_time": listing.end_time,
                "link": listing.link,
                "model": listing.model
            }

            category_auctions = data["categories"][listing.category]["auctions"]
            if listing.seconds_remaining < ENDING_SOON_THRESHOLD:
                category_auctions["ending_soon"].append(auction_info)
            else:
                category_auctions["active"].append(auction_info)

def update_price_range(
    price_range: Dict[str, float],
    value: float
) -> None:
    """Update a price range with a new value"""
    price_range["min"] = min(price_range["min"], value)
    price_range["max"] = max(price_range["max"], value)

def process_printer_data(
    listing: Listing,
    data: Dict[str, Any],
    model_info: Dict[str, Any],
    printer_prices: PricingAccumulator
) -> None:
    """Process printer-specific data"""
    if isinstance(listing.price, (int, float)) and listing.price > 0:
        if listing.model != "Unknown" and listing.is_valid_price():
            printer_prices.add_price(listing.price)

    if listing.has_shipping_info():
        data["categories"]["printer"]["listings_with_shipping"] += 1
        if listing.model != "Unknown":
            model_info["listings_with_shipping"] += 1

    if listing.model != "Unknown":
        if isinstance(listing.total_cost, (int, float)) and listing.total_cost > 0:
            if listing.is_valid_price():
                update_price_range(model_info["price_range"], listing.total_cost)

        if (isinstance(listing.price_vs_official, (int, float)) and
            listing.price_vs_official < 0 and
            listing.model in OFFICIAL_PRICES and
            listing.is_valid_price()):
            model_info["below_msrp"] += 1
            data["categories"]["printer"]["listings_below_msrp"] += 1

def process_upgrade_data(
    listing: Listing,
    data: Dict[str, Any],
    upgrade_prices: PricingAccumulator
) -> None:
    """Process upgrade-specific data"""
    if isinstance(listing.price, (int, float)) and 0 < listing.price <= UPGRADE_MAX_PRICE:
        upgrade_prices.add_price(listing.price)
        update_price_range(
            data["categories"]["upgrade"]["price_range"],
            listing.price
        )

    # Track upgrade types
    title_lower = listing.title.lower()
    for keyword in UPGRADE_KEYWORDS:
        if keyword in title_lower:
            data["categories"]["upgrade"]["popular_types"][keyword] = \
                data["categories"]["upgrade"]["popular_types"].get(keyword, 0) + 1

def finalize_data(
    data: Dict[str, Any],
    printer_prices: PricingAccumulator,
    upgrade_prices: PricingAccumulator,
    auction_stats: AuctionAccumulator
) -> None:
    """Finalize data structure with calculated values"""
    # Update auction statistics
    data["active_auctions"].update({
        "count": auction_stats.count,
        "ending_soon": auction_stats.ending_soon,
        "avg_current_bid": auction_stats.get_average_bid() or 0.0
    })

    # Update category averages
    data["categories"]["printer"]["avg_price"] = printer_prices.get_average() or 0.0
    if upgrade_avg := upgrade_prices.get_average():
        data["categories"]["upgrade"]["avg_price"] = upgrade_avg
    else:
        data["categories"]["upgrade"]["price_range"] = None

    # Clean up price ranges
    for model in PRINTER_MODELS:
        model_info = data["models"][model]
        price_range = model_info["price_range"]
        if price_range["min"] == float('inf') or price_range["max"] == float('-inf'):
            model_info["price_range"] = None

    # Sort auctions by end time
    for category in CATEGORIES:
        for auction_type in ["active", "ending_soon"]:
            data["categories"][category]["auctions"][auction_type].sort(
                key=lambda x: x["end_time"]
            )

    # Sort upgrade types by frequency
    if data["categories"]["upgrade"]["popular_types"]:
        data["categories"]["upgrade"]["popular_types"] = dict(
            sorted(
                data["categories"]["upgrade"]["popular_types"].items(),
                key=lambda x: x[1],
                reverse=True
            )
        )

def organize_listing_data(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Organize eBay listing data with detailed auction tracking and statistics"""
    data = initialize_data_structure()
    data["total_listings"] = len(listings)

    printer_prices = PricingAccumulator()
    upgrade_prices = PricingAccumulator()
    auction_stats = AuctionAccumulator()

    for listing_dict in listings:
        listing = Listing.from_dict(listing_dict)
        data["categories"][listing.category]["count"] += 1

        # Process auction data
        process_auction_data(listing_dict, listing, data, auction_stats)

        # Update model counts
        model_info = data["models"][listing.model]
        model_info["count"] += 1

        # Process category-specific data
        if listing.category == "printer":
            process_printer_data(listing, data, model_info, printer_prices)
        else:
            process_upgrade_data(listing, data, upgrade_prices)

    finalize_data(data, printer_prices, upgrade_prices, auction_stats)
    return data