"""Configuration settings for the eBay scraper"""
from datetime import datetime

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