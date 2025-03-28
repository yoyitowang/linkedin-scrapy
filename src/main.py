"""
LinkedIn Job Scraper - Main entry point for the Apify Actor.
This script integrates the LinkedIn job scraper with the Apify platform.
"""

from __future__ import annotations

import os
import json
import logging
import traceback
from apify import Actor
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from src.linkedin_scraper.spiders.linkedin_jobs import LinkedinJobsSpider


async def main() -> None:
    """Define the main entry point for the Apify Actor.
    
    This function handles the Actor lifecycle and runs the LinkedIn job scraper
    with the provided input parameters.
    """
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
                
                # Push data to the dataset one by one to ensure each record is properly saved
                for job in jobs_data:
                    await default_dataset.push_data(job)
                
                Actor.log.info(f"Pushed {job_count} jobs to Apify dataset individually")
                
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
                    
                    # Store the JSON data
                    await default_key_value_store.set_value(
                        'linkedin_jobs.json', 
                        json.dumps(jobs_data, ensure_ascii=False, indent=2), 
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