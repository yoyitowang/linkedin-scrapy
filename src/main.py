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
    
    # Also define a symlink to the latest output for convenience
    latest_output = os.path.join(dataset_dir, 'linkedin_jobs_output_latest.json')
    
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
    
    # After crawling is done, create a symlink to the latest output
    try:
        # First check if the output file exists and has content
        if not os.path.exists(json_output) or os.path.getsize(json_output) == 0:
            print(f"Warning: Output file {json_output} does not exist or is empty.")
            return json_output
            
        # If on Windows, we need to handle symlinks differently
        if os.name == 'nt':  # Windows
            # On Windows, just copy the file instead of creating a symlink
            import shutil
            if os.path.exists(latest_output):
                os.remove(latest_output)
            shutil.copy2(json_output, latest_output)
            print(f"Created copy of latest output at: {latest_output}")
        else:  # Unix-like systems
            # Remove existing symlink if it exists
            if os.path.exists(latest_output) or os.path.islink(latest_output):
                os.unlink(latest_output)  # Use unlink instead of remove for symlinks
            # Create symlink - use relative path to make it more portable
            os.symlink(os.path.basename(json_output), latest_output)
            print(f"Created symlink to latest output at: {latest_output}")
    except Exception as e:
        print(f"Error creating latest output reference: {e}")
    
    # Also copy the output to the standard Apify output location for compatibility
    try:
        standard_output = os.path.join(dataset_dir, 'linkedin_jobs_output.json')
        import shutil
        if os.path.exists(standard_output):
            os.remove(standard_output)
        shutil.copy2(json_output, standard_output)
        print(f"Copied output to standard location: {standard_output}")
    except Exception as e:
        print(f"Error copying to standard output location: {e}")
    
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


async def run_apify_actor() -> None:
    """Run the LinkedIn scraper as an Apify Actor."""
    if not APIFY_AVAILABLE:
        print("Error: Apify package is not available. Cannot run in Actor mode.")
        return
    
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
        
        # Configure output paths for local files
        local_storage_dir = os.environ.get('APIFY_LOCAL_STORAGE_DIR', './apify_storage')
        dataset_dir = os.path.join(local_storage_dir, 'datasets', 'default')
        os.makedirs(dataset_dir, exist_ok=True)
        
        json_output = os.path.join(dataset_dir, 'linkedin_jobs_output.json')
        csv_output = os.path.join(dataset_dir, 'linkedin_jobs.csv')
        
        # Ensure the output file exists with an empty array
        try:
            with open(json_output, 'w', encoding='utf-8') as f:
                json.dump([], f)
            Actor.log.info(f"Created empty output file: {json_output}")
        except Exception as e:
            Actor.log.warning(f"Could not create empty output file: {e}")
        
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
        
        # Run the crawler - this will collect data in the pipeline
        process.start()
        
        # Log completion
        Actor.log.info("LinkedIn job scraping completed")
        
        # Process the output files
        await process_apify_output(json_output, csv_output)


async def process_apify_output(json_output: str, csv_output: str) -> None:
    """Process the output files for Apify.
    
    Args:
        json_output: Path to the JSON output file
        csv_output: Path to the CSV output file
    """
    # Try to get the data from the JSON file first
    jobs_data = []
    file_found = False
    
    # List of possible file locations to check
    possible_paths = [
        json_output,
        os.path.abspath(json_output),
        '/tmp/linkedin_jobs_output.json',
        '/usr/src/app/apify_storage/datasets/default/linkedin_jobs_output.json',
        './apify_storage/datasets/default/linkedin_jobs_output.json'
    ]
    
    # Try each possible path
    for path in possible_paths:
        try:
            if os.path.exists(path):
                Actor.log.info(f"Found output file at: {path}")
                with open(path, 'r', encoding='utf-8') as f:
                    jobs_data = json.load(f)
                file_found = True
                break
        except Exception as e:
            Actor.log.warning(f"Could not read from {path}: {e}")
    
    # If we have data from the file
    if jobs_data:
        try:
            # Log the count
            job_count = len(jobs_data)
            Actor.log.info(f"Successfully scraped {job_count} LinkedIn jobs")
            
            # Get the default dataset
            default_dataset = await Actor.open_dataset()
            
            # Push data to the dataset in batches to improve performance
            try:
                # Push all data at once - this is more efficient
                await default_dataset.push_data(jobs_data)
                Actor.log.info(f"Successfully pushed {job_count} jobs to Apify dataset in batch")
            except Exception as batch_error:
                Actor.log.warning(f"Batch push failed: {batch_error}. Trying individual pushes...")
                # Fallback to individual pushes if batch fails
                success_count = 0
                for job in jobs_data:
                    try:
                        await default_dataset.push_data(job)
                        success_count += 1
                    except Exception as e:
                        Actor.log.error(f"Failed to push job: {str(e)}")
                
                Actor.log.info(f"Pushed {success_count}/{job_count} jobs to Apify dataset individually")
            
            # Generate CSV from the dataset
            try:
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
                    for item in jobs_data:
                        fieldnames.update(item.keys())
                    
                    # Remove HTML description to make CSV more readable
                    if 'job_description' in fieldnames:
                        fieldnames.remove('job_description')
                    
                    # Write to CSV
                    with open(csv_output, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
                        writer.writeheader()
                        
                        for item in jobs_data:
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
                    jobs_data,  # Pass the Python object directly, SDK handles serialization
                    content_type='application/json'
                )
                Actor.log.info("Saved JSON output to key-value store")
                
                # Store the CSV file if it exists
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
            
            # Print the paths to help users find the files
            Actor.log.info(f"Local JSON file: {os.path.abspath(json_output)}")
            Actor.log.info(f"Local CSV file: {os.path.abspath(csv_output)}")
            
        except Exception as e:
            Actor.log.error(f"Error processing output files: {e}")
            Actor.log.error(traceback.format_exc())
    else:
        # If no data was found in files, check if we have data in the dataset directly
        try:
            # Skip checking the dataset since we know the file is empty
            Actor.log.warning("No jobs were found during scraping. The output file is empty.")
            
            # Optional: You can add a message explaining possible reasons
            Actor.log.info("This could be due to:")
            Actor.log.info("- No matching jobs found for the given criteria")
            Actor.log.info("- LinkedIn might be blocking the scraping attempt")
            Actor.log.info("- There might be an issue with the search parameters")
            
        except Exception as e:
            Actor.log.error(f"Error in final processing: {str(e)}")
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