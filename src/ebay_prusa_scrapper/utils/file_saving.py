"""File saving utilities for eBay scraper"""
import os
import json
from datetime import datetime
from typing import List, Dict, Any

def ensure_directory_exists(path: str):
    """Create directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)

def get_listings_save_paths(base_dir: str = 'public/data') -> Dict[str, str]:
    """
    Generate save paths for current and historical listings

    Args:
        base_dir (str): Base directory for saving files

    Returns:
        Dict with paths for current and historical listings
    """
    # Get current date
    now = datetime.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')

    # Construct paths
    current_dir = os.path.join(base_dir, 'current')
    historical_dir = os.path.join(base_dir, 'historical', year, month)

    # Ensure directories exist
    ensure_directory_exists(current_dir)
    ensure_directory_exists(historical_dir)

    # Generate filename
    filename = f'listings_{now.strftime("%Y%m%d")}.json'

    return {
        'current_path': os.path.join(current_dir, 'listings.json'),
        'historical_path': os.path.join(historical_dir, filename)
    }

def save_listings(listings: List[Dict[str, Any]], base_dir: str = 'public/data'):
    """
    Save listings to both current and historical directories

    Args:
        listings (List[Dict]): List of listing dictionaries
        base_dir (str): Base directory for saving files
    """
    # Get save paths
    paths = get_listings_save_paths(base_dir)

    # Prepare data
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_listings": len(listings),
        "listings": listings
    }

    # Save to current directory
    with open(paths['current_path'], 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Save to historical directory
    with open(paths['historical_path'], 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Update metadata
    update_metadata(base_dir)

def update_metadata(base_dir: str = 'public/data'):
    """
    Update or create metadata.json to track historical listings

    Args:
        base_dir (str): Base directory for saving files
    """
    metadata_path = os.path.join(base_dir, 'metadata.json')

    # Read existing metadata or create new
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        metadata = {
            "historical_files": {},
            "last_updated": None
        }

    # Get current date details
    now = datetime.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    filename = f'listings_{now.strftime("%Y%m%d")}.json'

    # Update metadata
    if year not in metadata['historical_files']:
        metadata['historical_files'][year] = {}
    if month not in metadata['historical_files'][year]:
        metadata['historical_files'][year][month] = []

    # Add current file to metadata if not already present
    full_path = os.path.join('historical', year, month, filename)
    if full_path not in metadata['historical_files'][year][month]:
        metadata['historical_files'][year][month].append(full_path)

    # Update last updated timestamp
    metadata['last_updated'] = now.isoformat()

    # Save updated metadata
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)