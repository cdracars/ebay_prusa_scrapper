# src/main.py
"""Entry point for the eBay Prusa scraper"""
import json
import logging
from ebay_prusa_scrapper.config.settings import EbayScraperConfig
from ebay_prusa_scrapper.scraper.ebay_scraper import scrape_ebay_listings
from ebay_prusa_scrapper.utils.json_handler import write_batch_to_file, create_summary_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    """Enhanced main function with better JSON handling"""
    keywords = ["Prusa MK3S", "Prusa MK4", "Prusa MINI", "Prusa Core One"]
    zip_code = "73120"
    max_pages = 2

    output_file = EbayScraperConfig.get_output_filename()
    summary_file = output_file.replace('.json', '_summary.json')
    is_first_batch = True
    all_listings = []

    try:
        # Scrape all listings
        for keyword in keywords:
            logging.info(f"Starting scrape for keyword: {keyword}")
            for batch in scrape_ebay_listings(keyword, zip_code, max_pages):
                write_batch_to_file(batch, output_file, is_first_batch)
                all_listings.extend(batch)
                is_first_batch = False

        # Close the main JSON file properly
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write('\n]}\n')

        # Create summary
        summary = create_summary_json(all_listings)

        # Write summary to file
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logging.info(f"Scraping completed. Results written to: {output_file}")
        logging.info(f"Summary written to: {summary_file}")

    except Exception as e:
        logging.error(f"Fatal error during scraping: {str(e)}")
        raise

if __name__ == "__main__":
    main()