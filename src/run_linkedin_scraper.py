#!/usr/bin/env python
"""
LinkedIn Job Scraper - Main script to run the scraper
"""
import os
import sys
import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from linkedin_scraper.spiders.linkedin_jobs import LinkedinJobsSpider


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='LinkedIn Job Scraper')
    
    # Required arguments
    parser.add_argument('--keyword', type=str, required=True,
                        help='Job search keyword (e.g., "python developer")')
    parser.add_argument('--location', type=str, required=True,
                        help='Job location (e.g., "San Francisco, CA")')
    
    # Optional arguments
    parser.add_argument('--linkedin-session-id', type=str,
                        help='LinkedIn session ID cookie (li_at) for authentication')
    parser.add_argument('--linkedin-jsessionid', type=str,
                        help='LinkedIn JSESSIONID cookie for authentication')
    parser.add_argument('--max-pages', type=int, default=5,
                        help='Maximum number of search result pages to scrape (default: 5)')
    parser.add_argument('--max-jobs', type=int, default=10,
                        help='Maximum number of jobs to scrape (default: 10)')
    parser.add_argument('--output', type=str, default='linkedin_jobs_output.json',
                        help='Output file path (default: linkedin_jobs_output.json)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode with verbose logging')
    
    return parser.parse_args()


def main():
    """Main function to run the LinkedIn job scraper"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get Scrapy project settings
    settings = get_project_settings()
    
    # Update settings with command line arguments
    settings.set('FEEDS', {
        args.output: {
            'format': 'json',
            'encoding': 'utf8',
            'indent': 4,
        },
    })
    
    # Configure debug mode
    if args.debug:
        settings.set('LOG_LEVEL', 'DEBUG')
    else:
        settings.set('LOG_LEVEL', 'INFO')
    
    # Create and configure the crawler process
    process = CrawlerProcess(settings)
    
    # Configure spider parameters
    spider_kwargs = {
        'keyword': args.keyword,
        'location': args.location,
        'linkedin_session_id': args.linkedin_session_id,
        'linkedin_jsessionid': args.linkedin_jsessionid,
        'max_pages': args.max_pages,
        'max_jobs': args.max_jobs,
        'debug': args.debug,
    }
    
    # Start the crawler
    process.crawl(LinkedinJobsSpider, **spider_kwargs)
    process.start()


if __name__ == "__main__":
    main()