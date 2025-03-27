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
    parser.add_argument('--username', type=str,
                        help='LinkedIn username/email for authentication')
    parser.add_argument('--password', type=str,
                        help='LinkedIn password for authentication')
    parser.add_argument('--max-pages', type=int, default=5,
                        help='Maximum number of search result pages to scrape (default: 5)')
    parser.add_argument('--output', type=str, default='linkedin_jobs_output.json',
                        help='Output file path (default: linkedin_jobs_output.json)')
    
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
    
    # Create and configure the crawler process
    process = CrawlerProcess(settings)
    
    # Configure spider parameters
    spider_kwargs = {
        'keyword': args.keyword,
        'location': args.location,
        'username': args.username,
        'password': args.password,
        'max_pages': args.max_pages,
    }
    
    # Start the crawler
    process.crawl(LinkedinJobsSpider, **spider_kwargs)
    process.start()


if __name__ == "__main__":
    main()