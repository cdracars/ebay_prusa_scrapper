# src/ebay_prusa_scrapper/models/listing.py
"""Data models for eBay listings"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from config.constants import OFFICIAL_PRICES, PRICE_THRESHOLDS

@dataclass
class Listing:
    """Represents an eBay listing with all its attributes"""
    platform: str
    title: str
    price: float
    shipping_cost: Optional[float]
    total_cost: Optional[float]
    price_vs_official: Optional[float]
    seller_info: str
    feedback_count: Optional[int]
    rating_percent: Optional[float]
    link: str
    category: str
    model: str

    @classmethod
    def from_dict(cls, data: dict) -> 'Listing':
        """Create a Listing instance from a dictionary"""
        return cls(**data)

    def to_dict(self) -> dict:
        """Convert listing to dictionary format"""
        return {
            "platform": self.platform,
            "title": self.title,
            "price": self.price,
            "shipping_cost": self.shipping_cost,
            "total_cost": self.total_cost,
            "price_vs_official": self.price_vs_official,
            "seller_info": self.seller_info,
            "feedback_count": self.feedback_count,
            "rating_percent": self.rating_percent,
            "link": self.link,
            "category": self.category,
            "model": self.model
        }

    def calculate_price_comparison(self) -> None:
        """Calculate total cost and price comparison with MSRP"""
        if isinstance(self.shipping_cost, (int, float)):
            self.total_cost = round(self.price + self.shipping_cost, 2)
            if self.model in OFFICIAL_PRICES:
                delta = self.total_cost - OFFICIAL_PRICES[self.model]
                self.price_vs_official = round(delta, 2)

    def is_valid_price(self) -> bool:
        """Check if the listing's price is within valid range for its model"""
        if self.model not in PRICE_THRESHOLDS:
            return False
        min_price, max_price = PRICE_THRESHOLDS[self.model]
        return min_price <= self.price <= max_price

    def has_shipping_info(self) -> bool:
        """Check if listing has valid shipping information"""
        return isinstance(self.shipping_cost, (int, float))

    @staticmethod
    def track_model_shipping(model_info: Dict[str, Any], listing: Dict[str, Any]) -> None:
        """Track shipping information for a model"""
        shipping_cost = listing.get("shipping_cost")
        if isinstance(shipping_cost, (int, float)) or shipping_cost == 0:
            model_info["listings_with_shipping"] += 1