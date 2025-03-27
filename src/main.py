"""
LinkedIn Job Scraper - Main entry point for the Apify Actor.
This script integrates the LinkedIn job scraper with the Apify platform.
"""

from __future__ import annotations

import os
import json
import logging
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
        
        # Configure output paths for Apify dataset
        dataset_dir = os.path.join(os.environ.get('APIFY_LOCAL_STORAGE_DIR', ''), 'datasets', 'default')
        os.makedirs(dataset_dir, exist_ok=True)
        
        json_output = os.path.join(dataset_dir, 'linkedin_jobs_output.json')
        csv_output = os.path.join(dataset_dir, 'linkedin_jobs_output.csv')
        
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
        
        # After the crawler is done, push all collected data to Apify dataset
        if os.path.exists(json_output):
            try:
                # Read the collected data from the JSON file
                with open(json_output, 'r', encoding='utf-8') as f:
                    jobs_data = json.load(f)
                
                # Count the actual jobs (excluding the summary)
                job_count = len([item for item in jobs_data if item.get('type') != 'summary'])
                Actor.log.info(f"Successfully scraped {job_count} LinkedIn jobs")
                
                # Push all data to Apify dataset at once
                for item in jobs_data:
                    await Actor.push_data(item)
                
                # Store CSV and JSON as named keys in the default key-value store
                # This makes them available for download from the Apify UI
                default_key_value_store = await Actor.open_key_value_store()
                
                # Store the JSON file
                with open(json_output, 'rb') as f:
                    await default_key_value_store.set_value(
                        'linkedin_jobs.json', 
                        f.read(), 
                        content_type='application/json'
                    )
                Actor.log.info("Saved JSON output for download")
                
                # Store the CSV file if it exists
                if os.path.exists(csv_output):
                    with open(csv_output, 'rb') as f:
                        await default_key_value_store.set_value(
                            'linkedin_jobs.csv', 
                            f.read(), 
                            content_type='text/csv'
                        )
                    Actor.log.info("Saved CSV output for download")
                
                # Add a record with download links
                await Actor.push_data({
                    "type": "download_links",
                    "jobCount": job_count,
                    "downloadLinks": {
                        "json": "https://api.apify.com/v2/key-value-stores/{STORE_ID}/records/linkedin_jobs.json",
                        "csv": "https://api.apify.com/v2/key-value-stores/{STORE_ID}/records/linkedin_jobs.csv"
                    },
                    "note": "Replace {STORE_ID} with your actual store ID from the Apify console"
                })
                
            except Exception as e:
                Actor.log.error(f"Error processing output files: {e}")
        else:
            Actor.log.warning("No output files were created. The scraper may have failed to find any jobs.")