from typing import TypedDict, Optional, Union, List

class PriceRange(TypedDict):
    min: float
    max: float

class AuctionInfo(TypedDict):
    title: str
    current_bid: float
    time_remaining: str
    end_time: str
    link: str
    model: str

class AuctionSection(TypedDict):
    active: List[AuctionInfo]
    ending_soon: List[AuctionInfo]

class ModelStats(TypedDict):
    count: int
    price_range: Optional[PriceRange]
    below_msrp: int
    listings_with_shipping: int

class UnknownModelStats(TypedDict):
    count: int

class CategoryAuctions(TypedDict):
    count: int
    ending_soon: int
    avg_current_bid: float

class CategoryBase(TypedDict):
    count: int
    avg_price: float
    listings_with_shipping: int
    auctions: AuctionSection

class PrinterCategory(CategoryBase):
    listings_below_msrp: int

class UpgradeCategory(CategoryBase):
    popular_types: dict
    price_range: Optional[PriceRange]

ModelInfo = Union[ModelStats, UnknownModelStats]