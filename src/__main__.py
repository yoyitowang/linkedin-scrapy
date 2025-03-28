"""
Main entry point for the LinkedIn Job Scraper.
"""

import os
import sys
import json
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Fix import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now we can import our modules
from src.linkedin_scraper.spiders.linkedin_jobs import LinkedinJobsSpider

def main():
    """Main function for running the scraper in Apify environment"""
    # Get Apify environment variables
    apify_local_storage = os.environ.get('APIFY_LOCAL_STORAGE_DIR', './apify_storage')
    dataset_id = os.environ.get('APIFY_DEFAULT_DATASET_ID', 'default')
    
    # Define output paths
    dataset_dir = os.path.join(apify_local_storage, 'datasets', dataset_id)
    json_output = os.path.join(dataset_dir, 'linkedin_jobs_output.json')
    
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
    username = None
    password = None
    
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
                max_pages = input_data.get('max_pages', max_pages)
                username = input_data.get('linkedin_username')
                password = input_data.get('linkedin_password')
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
                    max_pages = input_data.get('max_pages', max_pages)
                    username = input_data.get('linkedin_username')
                    password = input_data.get('linkedin_password')
                    print(f"Read input from {alt_input}: keyword={keyword}, location={location}")
                break
            else:
                print(f"Alternative input file not found at: {alt_input}")
        except Exception as e:
            print(f"Error reading alternative input file {alt_input}: {e}")
    
    print(f"Using parameters: keyword={keyword}, location={location}, max_pages={max_pages}")
    print(f"Output will be written to: {json_output}")
    
    # Get Scrapy project settings
    settings = get_project_settings()
    
    # Configure output
    settings.set('FEEDS', {
        json_output: {
            'format': 'json',
            'encoding': 'utf8',
            'indent': 4,
        },
    })
    
    # Create crawler process
    process = CrawlerProcess(settings)
    
    # Configure spider parameters
    spider_kwargs = {
        'keyword': keyword,
        'location': location,
        'username': username,
        'password': password,
        'max_pages': max_pages,
    }
    
    # Start the crawler
    print("Starting LinkedIn Jobs Spider...")
    process.crawl(LinkedinJobsSpider, **spider_kwargs)
    process.start()
    print("Spider finished.")

# Run the main function
if __name__ == "__main__":
    main()