"""
LinkedIn Job Scraper - Main entry point.
This script provides functionality to run the LinkedIn job scraper either
as a standalone script or as an Apify Actor.
"""

from __future__ import annotations

import os
import sys
import json
import logging
import datetime
import traceback
from typing import Dict, Any, List, Optional
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.utils.log import configure_logging

# Fix import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import our modules
from src.linkedin_scraper.spiders.linkedin_jobs import LinkedinJobsSpider

# Check if Apify is available
try:
    from apify import Actor
    APIFY_AVAILABLE = True
except ImportError:
    APIFY_AVAILABLE = False


# Global variable to store scraped items in memory
SCRAPED_ITEMS = []


def run_standalone_scraper(
    keyword: str = "software developer",
    location: str = "United States",
    max_pages: int = 1,
    max_jobs: int = 10,
    username: Optional[str] = None,
    password: Optional[str] = None,
    debug: bool = False,
    start_urls: Optional[List[str]] = None
) -> str:
    """Run the LinkedIn scraper as a standalone script.
    
    Args:
        keyword: Search keyword
        location: Location to search in
        max_pages: Maximum number of search result pages to scrape
        max_jobs: Maximum number of jobs to scrape
        username: LinkedIn username for authentication
        password: LinkedIn password for authentication
        debug: Whether to enable debug logging
        start_urls: Optional list of specific URLs to scrape
        
    Returns:
        Path to the output JSON file
    """
    # Generate timestamp for unique filenames
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get Apify environment variables
    apify_local_storage = os.environ.get('APIFY_LOCAL_STORAGE_DIR', './apify_storage')
    dataset_id = os.environ.get('APIFY_DEFAULT_DATASET_ID', 'default')
    
    # Define output paths with timestamp
    dataset_dir = os.path.join(apify_local_storage, 'datasets', dataset_id)
    json_output = os.path.join(dataset_dir, f'linkedin_jobs_output_{timestamp}.json')
    
    # Ensure directory exists
    os.makedirs(dataset_dir, exist_ok=True)
    
    print(f"Using parameters: keyword={keyword}, location={location}, max_pages={max_pages}, max_jobs={max_jobs}")
    print(f"Debug mode: {debug}")
    print(f"Output will be written to: {json_output}")
    
    # Configure logging based on debug flag
    log_level = logging.DEBUG if debug else logging.INFO
    configure_logging({"LOG_LEVEL": log_level})
    
    # Get Scrapy project settings
    settings = get_project_settings()
    
    # Override settings based on debug flag
    settings.set('LOG_LEVEL', 'DEBUG' if debug else 'INFO')
    settings.set('LOG_ENABLED', True)
    
    # Configure output with timestamp
    settings.set('FEEDS', {
        json_output: {
            'format': 'json',
            'encoding': 'utf8',
            'indent': 4,
        },
    })
    
    # Configure CLOSESPIDER_ITEMCOUNT to enforce max_jobs
    if max_jobs > 0:
        settings.set('CLOSESPIDER_ITEMCOUNT', max_jobs)
    
    # Create crawler process with our settings
    process = CrawlerProcess(settings)
    
    # Configure spider parameters
    spider_kwargs = {
        'keyword': keyword,
        'location': location,
        'username': username,
        'password': password,
        'max_pages': max_pages,
        'max_jobs': max_jobs,
        'debug': debug,
        'start_urls': start_urls,
    }
    
    # Start the crawler
    print(f"Starting LinkedIn Jobs Spider at {datetime.datetime.now().isoformat()}...")
    process.crawl(LinkedinJobsSpider, **spider_kwargs)
    process.start()
    print(f"Spider finished at {datetime.datetime.now().isoformat()}.")
    
    return json_output


def read_input_from_file() -> Dict[str, Any]:
    """Read input parameters from various possible input file locations.
    
    Returns:
        Dictionary containing input parameters
    """
    # Default values
    input_data = {
        "keyword": "software developer",
        "location": "United States",
        "max_pages": 1,
        "max_jobs": 10,
        "linkedin_username": None,
        "linkedin_password": None,
        "debug": False
    }
    
    # Get Apify environment variables
    apify_local_storage = os.environ.get('APIFY_LOCAL_STORAGE_DIR', './apify_storage')
    input_path = os.environ.get('APIFY_INPUT_KEY', 'INPUT')
    key_value_store_id = os.environ.get('APIFY_DEFAULT_KEY_VALUE_STORE_ID', 'default')
    
    # List of possible input file locations
    input_files = [
        os.path.join(apify_local_storage, 'key_value_stores', key_value_store_id, input_path + '.json'),
        '/usr/src/app/input.json',
        './input.json',
        os.path.join(apify_local_storage, 'key_value_stores', key_value_store_id, 'INPUT')
    ]
    
    # Try each input file
    for input_file in input_files:
        try:
            if os.path.exists(input_file):
                print(f"Found input file at: {input_file}")
                with open(input_file, 'r') as f:
                    file_data = json.load(f)
                    # Update input data with file values
                    for key in input_data:
                        if key in file_data:
                            input_data[key] = file_data[key]
                    # Special case for username/password
                    if 'linkedin_username' in file_data:
                        input_data['linkedin_username'] = file_data['linkedin_username']
                    if 'linkedin_password' in file_data:
                        input_data['linkedin_password'] = file_data['linkedin_password']
                    print(f"Read input from {input_file}: keyword={input_data['keyword']}, location={input_data['location']}")
                break
        except Exception as e:
            print(f"Error reading input file {input_file}: {e}")
    
    return input_data


# Create a custom item pipeline to collect items in memory
class MemoryStoragePipeline:
    def process_item(self, item, spider):
        # Store the item in our global list
        SCRAPED_ITEMS.append(dict(item))
        return item


async def run_apify_actor() -> None:
    """Run the LinkedIn scraper as an Apify Actor."""
    if not APIFY_AVAILABLE:
        print("Error: Apify package is not available. Cannot run in Actor mode.")
        return
    
    global SCRAPED_ITEMS
    SCRAPED_ITEMS = []  # Reset the global items list
    
    # Enter the context of the Actor
    async with Actor:
        # Retrieve the Actor input
        actor_input = await Actor.get_input() or {}
        
        # Extract parameters from input
        keyword = actor_input.get('keyword')
        location = actor_input.get('location')
        linkedin_username = actor_input.get('linkedin_username')
        linkedin_password = actor_input.get('linkedin_password')
        max_pages = actor_input.get('max_pages', 5)
        max_jobs = actor_input.get('max_jobs', 0)  # Parameter for job count limit
        start_urls = [url.get('url') for url in actor_input.get('start_urls', [])]
        debug = actor_input.get('debug', False)
        
        # Validate required parameters
        if not keyword and not location and not start_urls:
            Actor.log.error("Either 'keyword' and 'location' or 'start_urls' must be provided")
            await Actor.fail("Missing required parameters")
            return
        
        # Log startup information
        if keyword and location:
            Actor.log.info(f"Starting LinkedIn job search for '{keyword}' in '{location}'")
        elif start_urls:
            Actor.log.info(f"Starting LinkedIn job scraping for {len(start_urls)} specific URLs")
            
        Actor.log.info(f"Debug mode: {'enabled' if debug else 'disabled'}")
        
        # Log job limit if set
        if max_jobs > 0:
            Actor.log.info(f"Job limit set: Will scrape a maximum of {max_jobs} jobs")
        
        # Get Scrapy project settings
        settings = get_project_settings()
        
        # Configure logging based on debug flag
        if not debug:
            # Set higher log level to suppress detailed output when debug is False
            settings.set('LOG_LEVEL', 'INFO')
            # Disable default Scrapy debug output
            settings.set('LOG_ENABLED', True)
            # Filter out certain loggers
            settings.set('LOG_FORMATTER', 'src.linkedin_scraper.formatters.LinkedInLogFormatter')
            # Disable item printing in logs
            settings.set('LOG_STDOUT', False)
            settings.set('LOG_FORMATTER_KEYS', ['levelname', 'message'])
        else:
            # In debug mode, show all logs
            settings.set('LOG_LEVEL', 'DEBUG')
            settings.set('LOG_ENABLED', True)
        
        # Add debug flag to settings
        settings.set('DEBUG_MODE', debug)
        
        # Add our custom pipeline to collect items in memory
        # Use a completely new pipeline configuration to avoid issues with existing pipelines
        settings.set('ITEM_PIPELINES', {
            'src.main.MemoryStoragePipeline': 300,
        })
        
        # Configure spider parameters
        spider_kwargs = {
            'keyword': keyword,
            'location': location,
            'username': linkedin_username,
            'password': linkedin_password,
            'max_pages': max_pages,
            'max_jobs': max_jobs,
            'start_urls': start_urls,
            'debug': debug
        }
        
        # Create and run the crawler process
        process = CrawlerProcess(settings)
        process.crawl(LinkedinJobsSpider, **spider_kwargs)
        
        # Log start of scraping
        Actor.log.info("Starting LinkedIn job scraper...")
        
        # Run the crawler - this will collect data in our memory pipeline
        process.start()
        
        # Log completion
        Actor.log.info("LinkedIn job scraping completed")
        
        # Process the items collected in memory
        await process_apify_items()


async def process_apify_items() -> None:
    """Process the items collected in memory and push to Apify dataset."""
    global SCRAPED_ITEMS
    
    try:
        # Check if we have any items
        job_count = len(SCRAPED_ITEMS)
        
        if job_count == 0:
            Actor.log.warning("No jobs were found during scraping.")
            Actor.log.info("This could be due to:")
            Actor.log.info("- No matching jobs found for the given criteria")
            Actor.log.info("- LinkedIn might be blocking the scraping attempt")
            Actor.log.info("- There might be an issue with the search parameters")
            return
            
        Actor.log.info(f"Successfully scraped {job_count} LinkedIn jobs")
        
        # Get the default dataset
        default_dataset = await Actor.open_dataset()
        
        # Push data to the dataset in batch mode
        try:
            # Push all data at once for efficiency
            await default_dataset.push_data(SCRAPED_ITEMS)
            Actor.log.info(f"Successfully pushed {job_count} jobs to Apify dataset in batch")
        except Exception as batch_error:
            Actor.log.warning(f"Batch push failed: {batch_error}. Trying individual pushes...")
            
            # Fallback to individual pushes if batch fails
            success_count = 0
            for job in SCRAPED_ITEMS:
                try:
                    await default_dataset.push_data(job)
                    success_count += 1
                except Exception as e:
                    Actor.log.error(f"Failed to push job: {str(e)}")
            
            Actor.log.info(f"Pushed {success_count}/{job_count} jobs to Apify dataset individually")
        
        # Generate CSV from the dataset
        try:
            # Define CSV output path
            csv_output = '/usr/src/app/apify_storage/datasets/default/linkedin_jobs.csv'
            
            # First try using the export_to_csv method
            await default_dataset.export_to_csv(csv_output)
            Actor.log.info(f"Exported dataset to CSV: {csv_output}")
        except Exception as e:
            Actor.log.warning(f"Could not export to CSV using dataset method: {e}")
            # Fallback: Generate CSV manually
            try:
                import csv
                # Get all possible field names from all items
                fieldnames = set()
                for item in SCRAPED_ITEMS:
                    fieldnames.update(item.keys())
                
                # Remove HTML description to make CSV more readable
                if 'job_description' in fieldnames:
                    fieldnames.remove('job_description')
                
                # Write to CSV
                csv_output = '/usr/src/app/apify_storage/datasets/default/linkedin_jobs.csv'
                with open(csv_output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
                    writer.writeheader()
                    
                    for item in SCRAPED_ITEMS:
                        # Create a copy without HTML description for CSV
                        csv_item = {k: v for k, v in item.items() if k != 'job_description'}
                        writer.writerow(csv_item)
                Actor.log.info(f"Manually generated CSV at: {csv_output}")
            except Exception as e2:
                Actor.log.error(f"Could not manually generate CSV: {e2}")
        
        # Store files in key-value store for easy download
        try:
            default_key_value_store = await Actor.open_key_value_store()
            
            # Store the JSON data - pass the Python object directly
            await default_key_value_store.set_value(
                'linkedin_jobs.json', 
                SCRAPED_ITEMS,  # Pass the Python object directly, SDK handles serialization
                content_type='application/json'
            )
            Actor.log.info("Saved JSON output to key-value store")
            
            # Store the CSV file if it exists
            csv_output = '/usr/src/app/apify_storage/datasets/default/linkedin_jobs.csv'
            if os.path.exists(csv_output):
                with open(csv_output, 'rb') as f:
                    await default_key_value_store.set_value(
                        'linkedin_jobs.csv', 
                        f.read(), 
                        content_type='text/csv'
                    )
                Actor.log.info("Saved CSV output to key-value store")
        except Exception as e:
            Actor.log.error(f"Error storing files in key-value store: {e}")
        
    except Exception as e:
        Actor.log.error(f"Error processing scraped items: {e}")
        Actor.log.error(traceback.format_exc())


def main() -> None:
    """Main entry point for the LinkedIn Job Scraper.
    
    This function detects the environment (standalone or Apify) and runs
    the appropriate version of the scraper.
    """
    print("LinkedIn Job Scraper starting...")
    
    # Check if we're running in Apify environment
    if 'APIFY_ACTOR_ID' in os.environ and APIFY_AVAILABLE:
        print("Running in Apify environment. Starting Actor...")
        import asyncio
        asyncio.run(run_apify_actor())
    else:
        print("Running in standalone mode...")
        # Read input from file
        input_data = read_input_from_file()
        
        # Run the standalone scraper
        run_standalone_scraper(
            keyword=input_data.get('keyword'),
            location=input_data.get('location'),
            max_pages=int(input_data.get('max_pages', 1)),
            max_jobs=int(input_data.get('max_jobs', 10)),
            username=input_data.get('linkedin_username'),
            password=input_data.get('linkedin_password'),
            debug=bool(input_data.get('debug', False))
        )
    
    print("LinkedIn Job Scraper finished.")


if __name__ == "__main__":
    main()