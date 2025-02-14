# src/main.py
"""Entry point for the eBay Prusa scraper"""
import logging
from ebay_prusa_scrapper.config.settings import EbayScraperConfig
from ebay_prusa_scrapper.scraper.ebay_scraper import scrape_ebay_listings
from ebay_prusa_scrapper.utils.file_saving import save_listings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    """Scrape eBay listings and save to files"""
    keywords = ["Prusa MK3S", "Prusa MK4", "Prusa MINI", "Prusa Core One"]
    zip_code = "73120"
    max_pages = 2

    all_listings = []

    try:
        # Scrape all listings
        for keyword in keywords:
            logging.info(f"Starting scrape for keyword: {keyword}")
            for batch in scrape_ebay_listings(keyword, zip_code, max_pages):
                all_listings.extend(batch)

        # Save listings using file saving utility
        save_listings(all_listings)

        logging.info(f"Scraping completed. Total listings: {len(all_listings)}")

    except Exception as e:
        logging.error(f"Fatal error during scraping: {str(e)}")
        raise

if __name__ == "__main__":
    main()