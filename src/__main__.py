"""
Main entry point for the LinkedIn Job Scraper.
"""

import os
import sys
import json
import logging
import datetime
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.utils.log import configure_logging

# Fix import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now we can import our modules
from src.linkedin_scraper.spiders.linkedin_jobs import LinkedinJobsSpider

def main():
    """Main function for running the scraper in Apify environment"""
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
    
    # Try to read input from Apify
    input_path = os.environ.get('APIFY_INPUT_KEY', 'INPUT')
    key_value_store_id = os.environ.get('APIFY_DEFAULT_KEY_VALUE_STORE_ID', 'default')
    input_file = os.path.join(apify_local_storage, 'key_value_stores', key_value_store_id, input_path + '.json')
    
    # Default values
    keyword = "software developer"
    location = "United States"
    max_pages = 1
    max_jobs = 10  # Default to 10 jobs
    username = None
    password = None
    debug = False  # Default to non-debug mode
    
    # Print debug info
    print(f"Current directory: {os.getcwd()}")
    print(f"Looking for input file at: {input_file}")
    
    # Try to read input file
    try:
        if os.path.exists(input_file):
            with open(input_file, 'r') as f:
                input_data = json.load(f)
                keyword = input_data.get('keyword', keyword)
                location = input_data.get('location', location)
                max_pages = int(input_data.get('max_pages', max_pages))
                max_jobs = int(input_data.get('max_jobs', max_jobs))
                username = input_data.get('linkedin_username')
                password = input_data.get('linkedin_password')
                debug = bool(input_data.get('debug', False))
                print(f"Read input from {input_file}: keyword={keyword}, location={location}")
        else:
            print(f"Input file not found at: {input_file}")
    except Exception as e:
        print(f"Error reading input file: {e}")
    
    # Alternative input file locations
    alt_inputs = [
        '/usr/src/app/input.json',
        './input.json',
        os.path.join(apify_local_storage, 'key_value_stores', key_value_store_id, 'INPUT')
    ]
    
    for alt_input in alt_inputs:
        try:
            if os.path.exists(alt_input):
                print(f"Found alternative input file at: {alt_input}")
                with open(alt_input, 'r') as f:
                    input_data = json.load(f)
                    keyword = input_data.get('keyword', keyword)
                    location = input_data.get('location', location)
                    max_pages = int(input_data.get('max_pages', max_pages))
                    max_jobs = int(input_data.get('max_jobs', max_jobs))
                    username = input_data.get('linkedin_username')
                    password = input_data.get('linkedin_password')
                    debug = bool(input_data.get('debug', False))
                    print(f"Read input from {alt_input}: keyword={keyword}, location={location}")
                break
            else:
                print(f"Alternative input file not found at: {alt_input}")
        except Exception as e:
            print(f"Error reading alternative input file {alt_input}: {e}")
    
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
    }
    
    # Start the crawler
    print(f"Starting LinkedIn Jobs Spider at {datetime.datetime.now().isoformat()}...")
    process.crawl(LinkedinJobsSpider, **spider_kwargs)
    process.start()
    print(f"Spider finished at {datetime.datetime.now().isoformat()}.")
    
    # After crawling is done, create a symlink to the latest output
    try:
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
            if os.path.exists(latest_output):
                os.remove(latest_output)
            # Create symlink
            os.symlink(os.path.basename(json_output), latest_output)
            print(f"Created symlink to latest output at: {latest_output}")
    except Exception as e:
        print(f"Error creating latest output reference: {e}")
    
    # Also copy the output to the standard Apify output location for compatibility
    try:
        standard_output = os.path.join(dataset_dir, 'linkedin_jobs_output.json')
        import shutil
        shutil.copy2(json_output, standard_output)
        print(f"Copied output to standard location: {standard_output}")
    except Exception as e:
        print(f"Error copying to standard output location: {e}")

# Run the main function
if __name__ == "__main__":
    main()