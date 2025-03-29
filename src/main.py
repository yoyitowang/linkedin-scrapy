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
    search_mode: str = "keyword_location",
    keyword: str = "software developer",
    location: str = "United States",
    company: Optional[str] = None,
    max_pages: int = 1,
    max_jobs: int = 10,
    linkedin_session_id: Optional[str] = None,
    linkedin_jsessionid: Optional[str] = None,
    debug: bool = False,
    start_urls: Optional[List[str]] = None
) -> str:
    """Run the LinkedIn scraper as a standalone script."""
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
    
    # Log parameters based on search mode
    if search_mode == "keyword_location":
        print(f"Search mode: Keyword & Location")
        print(f"Using parameters: keyword={keyword}, location={location}, max_pages={max_pages}, max_jobs={max_jobs}")
    elif search_mode == "company":
        print(f"Search mode: Company")
        print(f"Using parameters: company={company}, max_pages={max_pages}, max_jobs={max_jobs}")
    elif search_mode == "specific_urls":
        print(f"Search mode: Specific URLs")
        print(f"Using {len(start_urls) if start_urls else 0} specific job URLs")
    
    if linkedin_session_id:
        print("LinkedIn session ID provided for authentication")
        if linkedin_jsessionid:
            print("LinkedIn JSESSIONID also provided")
    else:
        print("No LinkedIn session cookies provided. Some job details may not be accessible.")
    
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
    
    # Configure spider parameters based on search mode
    spider_kwargs = {
        'max_pages': max_pages,
        'max_jobs': max_jobs,
        'linkedin_session_id': linkedin_session_id,
        'linkedin_jsessionid': linkedin_jsessionid,
        'debug': debug,
        'start_urls': start_urls,
    }
    
    # Add parameters based on search mode
    if search_mode == "keyword_location":
        spider_kwargs['keyword'] = keyword
        spider_kwargs['location'] = location
    elif search_mode == "company":
        spider_kwargs['company'] = company
    
    # Start the crawler
    print(f"Starting LinkedIn Jobs Spider at {datetime.datetime.now().isoformat()}...")
    process.crawl(LinkedinJobsSpider, **spider_kwargs)
    process.start()  # This will block until the crawling is finished
    print(f"Spider finished at {datetime.datetime.now().isoformat()}.")
    
    return json_output


def read_input_from_file() -> Dict[str, Any]:
    """Read input parameters from various possible input file locations."""
    # Default values
    input_data = {
        "search_mode": "keyword_location",
        "keyword": "software developer",
        "location": "United States",
        "company": None,
        "max_pages": 1,
        "max_jobs": 10,
        "linkedin_session_id": None,
        "linkedin_jsessionid": None,
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
                    
                    # Check for LinkedIn session cookies under different possible names
                    if 'linkedin_session_id' in file_data:
                        input_data['linkedin_session_id'] = file_data['linkedin_session_id']
                        print(f"Found LinkedIn session ID")
                    
                    if 'linkedin_jsessionid' in file_data:
                        input_data['linkedin_jsessionid'] = file_data['linkedin_jsessionid']
                        print(f"Found LinkedIn JSESSIONID")
                    
                    # Handle legacy session_cookies field
                    if 'session_cookies' in file_data and file_data['session_cookies']:
                        print("Warning: 'session_cookies' is deprecated. Please use 'linkedin_session_id' and 'linkedin_jsessionid' instead.")
                    
                    # Log based on search mode
                    search_mode = input_data.get('search_mode', 'keyword_location')
                    if search_mode == "keyword_location":
                        print(f"Read input from {input_file}: keyword={input_data['keyword']}, location={input_data['location']}")
                    elif search_mode == "company":
                        print(f"Read input from {input_file}: company={input_data['company']}")
                    elif search_mode == "specific_urls":
                        start_urls = file_data.get('start_urls', [])
                        print(f"Read input from {input_file}: {len(start_urls)} specific URLs")
                break
        except Exception as e:
            print(f"Error reading input file {input_file}: {e}")
    
    return input_data


async def process_apify_items():
    """Process items collected in memory and push them to the Apify dataset."""
    if not APIFY_AVAILABLE:
        return
        
    global SCRAPED_ITEMS
    
    # Clean and validate items before pushing to dataset
    cleaned_items = []
    
    for item in SCRAPED_ITEMS:
        try:
            # Ensure all values are of valid types for JSON serialization
            cleaned_item = {}
            
            for key, value in item.items():
                # Handle None values
                if value is None:
                    cleaned_item[key] = None
                    continue
                    
                # Convert all string-like objects to strings
                if hasattr(value, '__str__'):
                    cleaned_item[key] = str(value)
                # Convert datetime objects to ISO format strings
                elif hasattr(value, 'isoformat'):
                    cleaned_item[key] = value.isoformat()
                # Handle lists and dictionaries recursively
                elif isinstance(value, (list, dict)):
                    # For simplicity, just convert to string
                    # In a full solution, you'd want to recursively clean these
                    cleaned_item[key] = json.dumps(value)
                else:
                    # For other types, convert to string as fallback
                    cleaned_item[key] = str(value)
            
            # Ensure required fields exist
            if 'id' not in cleaned_item or not cleaned_item['id']:
                cleaned_item['id'] = f"job_{len(cleaned_items)}"
                
            if 'title' not in cleaned_item or not cleaned_item['title']:
                cleaned_item['title'] = "Unknown Title"
                
            if 'companyName' not in cleaned_item or not cleaned_item['companyName']:
                cleaned_item['companyName'] = "Unknown Company"
            
            # Add to cleaned items
            cleaned_items.append(cleaned_item)
            
        except Exception as e:
            Actor.log.error(f"Error cleaning item: {e}")
            # Skip this item if it can't be cleaned
            continue
    
    # Push all cleaned items to the default dataset
    if cleaned_items:
        Actor.log.info(f"Pushing {len(cleaned_items)} cleaned items to the default dataset")
        await Actor.push_data(cleaned_items)
    else:
        Actor.log.warning("No valid items were found to push to the dataset")


class MemoryStoragePipeline:
    """Pipeline that stores items in memory for later processing by Apify."""
    
    def process_item(self, item, spider):
        """Store the item in memory."""
        global SCRAPED_ITEMS
        
        try:
            # Convert item to dict
            item_dict = dict(item)
            
            # Ensure all values are of valid types for JSON serialization
            cleaned_item = {}
            
            for key, value in item_dict.items():
                # Handle None values
                if value is None:
                    cleaned_item[key] = None
                    continue
                    
                # Convert all string-like objects to strings
                if hasattr(value, '__str__'):
                    cleaned_item[key] = str(value)
                # Convert datetime objects to ISO format strings
                elif hasattr(value, 'isoformat'):
                    cleaned_item[key] = value.isoformat()
                else:
                    # For other types, convert to string as fallback
                    cleaned_item[key] = str(value)
            
            # Add to global items list
            SCRAPED_ITEMS.append(cleaned_item)
            
            # Log the count
            if hasattr(spider, 'logger'):
                spider.logger.info(f"Added job to memory storage. Total: {len(SCRAPED_ITEMS)}")
                
        except Exception as e:
            if hasattr(spider, 'logger'):
                spider.logger.error(f"Error storing item in memory: {e}")
        
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
        
        # Extract search mode
        search_mode = actor_input.get('search_mode', 'keyword_location')
        
        # Extract parameters based on search mode
        keyword = actor_input.get('keyword')
        location = actor_input.get('location')
        company = actor_input.get('company')
        
        # Extract LinkedIn session cookies
        linkedin_session_id = actor_input.get('linkedin_session_id')
        linkedin_jsessionid = actor_input.get('linkedin_jsessionid')
        
        # Log warning for deprecated session_cookies field
        if 'session_cookies' in actor_input and actor_input['session_cookies']:
            Actor.log.warning("'session_cookies' is deprecated. Please use 'linkedin_session_id' and 'linkedin_jsessionid' instead.")
        
        max_pages = actor_input.get('max_pages', 5)
        max_jobs = actor_input.get('max_jobs', 0)
        start_urls = [url.get('url') for url in actor_input.get('start_urls', [])]
        debug = actor_input.get('debug', False)
        
        # Validate required parameters based on search mode
        if search_mode == "keyword_location" and (not keyword or not location):
            Actor.log.error("For 'keyword_location' search mode, both 'keyword' and 'location' must be provided")
            await Actor.fail("Missing required parameters")
            return
        elif search_mode == "company" and not company:
            Actor.log.error("For 'company' search mode, 'company' name must be provided")
            await Actor.fail("Missing required parameters")
            return
        elif search_mode == "specific_urls" and not start_urls:
            Actor.log.error("For 'specific_urls' search mode, 'start_urls' must be provided")
            await Actor.fail("Missing required parameters")
            return
        
        # Log startup information based on search mode
        if search_mode == "keyword_location":
            Actor.log.info(f"Starting LinkedIn job search for '{keyword}' in '{location}'")
        elif search_mode == "company":
            Actor.log.info(f"Starting LinkedIn job search for company: '{company}'")
        elif search_mode == "specific_urls":
            Actor.log.info(f"Starting LinkedIn job scraping for {len(start_urls)} specific URLs")
            
        Actor.log.info(f"Debug mode: {'enabled' if debug else 'disabled'}")
        
        # Log authentication status
        if linkedin_session_id:
            Actor.log.info("LinkedIn session ID provided for authentication")
            if linkedin_jsessionid:
                Actor.log.info("LinkedIn JSESSIONID also provided")
        else:
            Actor.log.warning("No LinkedIn session cookies provided. Some job details may not be accessible.")
        
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
        
        # Configure spider parameters based on search mode
        spider_kwargs = {
            'max_pages': max_pages,
            'max_jobs': max_jobs,
            'linkedin_session_id': linkedin_session_id,
            'linkedin_jsessionid': linkedin_jsessionid,
            'start_urls': start_urls,
            'debug': debug
        }
        
        # Add parameters based on search mode
        if search_mode == "keyword_location":
            spider_kwargs['keyword'] = keyword
            spider_kwargs['location'] = location
        elif search_mode == "company":
            spider_kwargs['company'] = company
        
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


def main() -> None:
    """Main entry point for the LinkedIn Job Scraper."""
    print("LinkedIn Job Scraper starting...")
    
    try:
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
                search_mode=input_data.get('search_mode', 'keyword_location'),
                keyword=input_data.get('keyword'),
                location=input_data.get('location'),
                company=input_data.get('company'),
                max_pages=int(input_data.get('max_pages', 1)),
                max_jobs=int(input_data.get('max_jobs', 10)),
                linkedin_session_id=input_data.get('linkedin_session_id'),
                linkedin_jsessionid=input_data.get('linkedin_jsessionid'),
                debug=bool(input_data.get('debug', False)),
                start_urls=input_data.get('start_urls')
            )
        
        print("LinkedIn Job Scraper finished.")
    except Exception as e:
        print(f"Error in LinkedIn Job Scraper: {e}")
        traceback.print_exc()
        sys.exit(1)


# This is executed when the script is run directly
if __name__ == "__main__":
    main()