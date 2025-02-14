# src/ebay_prusa_scrapper/models/types.py
from typing import TypedDict, Optional, Union

class PriceRange(TypedDict):
    min: float
    max: float

class ModelStats(TypedDict):
    count: int
    price_range: Optional[PriceRange]
    below_msrp: int
    listings_with_shipping: int

class UnknownModelStats(TypedDict):
    count: int

ModelInfo = Union[ModelStats, UnknownModelStats]