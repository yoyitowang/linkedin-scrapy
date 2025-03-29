"""
Command-line script to run the LinkedIn job scraper directly.
"""

import argparse
import os
import sys
from typing import Dict, Any

# Fix import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.main import run_standalone_scraper


def parse_arguments() -> Dict[str, Any]:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='LinkedIn Job Scraper')
    
    # Add search mode argument
    parser.add_argument('--search_mode', type=str, default='keyword_location',
                      choices=['keyword_location', 'company', 'specific_urls'],
                      help='Search mode: keyword_location, company, or specific_urls')
    
    # Add keyword and location arguments (for keyword_location mode)
    parser.add_argument('--keyword', type=str, help='Job search keyword')
    parser.add_argument('--location', type=str, help='Job search location')
    
    # Add company argument (for company mode)
    parser.add_argument('--company', type=str, help='Company name to search for jobs')
    
    # Add URL argument (for specific_urls mode)
    parser.add_argument('--urls', type=str, nargs='+', help='Specific LinkedIn job URLs to scrape')
    
    # Add common arguments
    parser.add_argument('--max_pages', type=int, default=1,
                      help='Maximum number of search result pages to scrape')
    parser.add_argument('--max_jobs', type=int, default=10,
                      help='Maximum number of job listings to scrape (0 for unlimited)')
    parser.add_argument('--linkedin_session_id', type=str,
                      help='LinkedIn session ID cookie (li_at) for authenticated access')
    parser.add_argument('--linkedin_jsessionid', type=str,
                      help='LinkedIn JSESSIONID cookie for authenticated access')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug mode to print detailed output')
    
    args = parser.parse_args()
    
    # Validate arguments based on search mode
    if args.search_mode == 'keyword_location' and (not args.keyword or not args.location):
        parser.error("For 'keyword_location' search mode, both --keyword and --location are required")
    elif args.search_mode == 'company' and not args.company:
        parser.error("For 'company' search mode, --company is required")
    elif args.search_mode == 'specific_urls' and not args.urls:
        parser.error("For 'specific_urls' search mode, --urls is required")
    
    # Convert arguments to dictionary
    return {
        'search_mode': args.search_mode,
        'keyword': args.keyword,
        'location': args.location,
        'company': args.company,
        'max_pages': args.max_pages,
        'max_jobs': args.max_jobs,
        'linkedin_session_id': args.linkedin_session_id,
        'linkedin_jsessionid': args.linkedin_jsessionid,
        'debug': args.debug,
        'start_urls': args.urls
    }


def main() -> None:
    """Main entry point for the command-line script."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Run the scraper
    run_standalone_scraper(
        search_mode=args.get('search_mode'),
        keyword=args.get('keyword'),
        location=args.get('location'),
        company=args.get('company'),
        max_pages=args.get('max_pages'),
        max_jobs=args.get('max_jobs'),
        linkedin_session_id=args.get('linkedin_session_id'),
        linkedin_jsessionid=args.get('linkedin_jsessionid'),
        debug=args.get('debug'),
        start_urls=args.get('start_urls')
    )


if __name__ == "__main__":
    main()