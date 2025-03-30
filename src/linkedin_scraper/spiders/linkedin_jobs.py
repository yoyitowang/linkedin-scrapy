"""
LinkedIn Jobs Spider - Scrapes job listings from LinkedIn
"""
import scrapy
import json
import re
import time
import logging
import signal
import sys
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, parse_qs
from scrapy.exceptions import CloseSpider
from scrapy.utils.log import configure_logging
from ..items import LinkedinJobItem, LinkedinJobUrlItem

class LinkedinJobsSpider(scrapy.Spider):
    name = "linkedin_jobs"
    allowed_domains = ["linkedin.com"]
    
    # Custom settings for the spider
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 3,  # Add delay to avoid being blocked
        'COOKIES_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'CONCURRENT_REQUESTS': 1,  # Limit concurrent requests
        # Ensure clean shutdown
        'CLOSESPIDER_TIMEOUT': 0,  # Disable timeout-based shutdown
    }
    
    def __init__(self, keyword=None, location=None, company=None, linkedin_session_id=None, linkedin_jsessionid=None, 
                 max_pages=5, max_jobs=0, start_urls=None, debug=False, collect_urls_only=False, 
                 process_job_details_only=False, *args, **kwargs):
        super(LinkedinJobsSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword
        self.location = location
        self.company = company  # Parameter for company search
        self.linkedin_session_id = linkedin_session_id
        self.linkedin_jsessionid = linkedin_jsessionid
        self.max_pages = int(max_pages) if max_pages else 5
        self.max_jobs = int(max_jobs) if max_jobs else 0  # Parameter for job count limit
        self.page_count = 0
        self.job_count = 0  # Counter for scraped jobs
        self.start_urls_list = start_urls or []
        self.debug = debug
        # Flag to track if job limit has been reached
        self.reached_job_limit = False
        # Track processed job IDs to avoid duplicates
        self.processed_job_ids = set()
        # New flags for operation mode
        self.collect_urls_only = collect_urls_only
        self.process_job_details_only = process_job_details_only
        
        # Initialize cookies dictionary
        self.cookies = {}
        
        # Process LinkedIn session cookies if provided
        if self.linkedin_session_id:
            self.cookies['li_at'] = self.linkedin_session_id
            if self.debug:
                self.logger.debug(f"Using LinkedIn session ID: {self.linkedin_session_id[:10]}...")
        
        # Add JSESSIONID if provided
        if self.linkedin_jsessionid:
            self.cookies['JSESSIONID'] = self.linkedin_jsessionid
            if self.debug:
                self.logger.debug(f"Using LinkedIn JSESSIONID: {self.linkedin_jsessionid[:10]}...")
        
        # Register signal handlers for graceful shutdown
        self.register_shutdown_handlers()
        
        # Configure logging based on debug flag
        if not self.debug:
            # Disable Scrapy's default logging when not in debug mode
            self.silence_scrapy_logs()
            # Set our logger to only show INFO and above
            self.logger.setLevel(logging.INFO)
            # Only show minimal, important messages
            self.logger.info("Debug mode is disabled - only essential information will be shown")
        else:
            # In debug mode, show all logs
            self.logger.setLevel(logging.DEBUG)
            # Log debug status
            self.logger.info("Debug mode is enabled - detailed output will be shown")
            
        # Log job limit if set
        if self.max_jobs > 0:
            self.logger.info(f"Job limit set: Will scrape a maximum of {self.max_jobs} jobs")
            
        # Log page limit
        self.logger.info(f"Page limit set: Will scrape a maximum of {self.max_pages} pages")
        
        # Log operation mode
        if self.collect_urls_only:
            self.logger.info("Operating in URL collection mode (collecting job URLs only)")
        elif self.process_job_details_only:
            self.logger.info("Operating in job detail processing mode (processing single job URL)")
    
    def register_shutdown_handlers(self):
        """Register handlers for graceful shutdown on SIGTERM and SIGINT"""
        # For SIGTERM (what Apify sends when aborting)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        # For SIGINT (Ctrl+C)
        signal.signal(signal.SIGINT, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown when receiving termination signals"""
        signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        self.logger.info(f"Received {signal_name} signal - performing graceful shutdown")
        self.logger.info(f"Scraped {self.job_count} jobs before shutdown")
        
        # Set the job limit reached flag to prevent processing new items
        self.reached_job_limit = True
        
        # Force pipeline to write current items
        if hasattr(self, 'crawler') and hasattr(self.crawler, 'engine'):
            # Get the pipeline from the crawler
            try:
                pipeline = next((p for p in self.crawler.engine.scraper.itemproc.middlewares 
                            if hasattr(p, 'items') and hasattr(p, '_write_json_backup')), None)
                if pipeline:
                    self.logger.info("Forcing pipeline to write items before shutdown")
                    pipeline._write_json_backup()
            except Exception as e:
                self.logger.error(f"Error writing items during shutdown: {e}")
        
        # Force the crawler to stop and save data
        # This ensures that all collected items are written to output
        self.crawler.engine.close_spider(self, f"Received {signal_name} signal")
        
        # Exit with success status
        sys.exit(0)
        
    def silence_scrapy_logs(self):
        """Silence Scrapy's default logging when not in debug mode"""
        # Configure Scrapy's logging to be minimal
        configure_logging(settings={
            'LOG_LEVEL': 'ERROR',  # Only show errors
            'LOG_ENABLED': False,  # Disable most logging
            'LOG_STDOUT': False    # Don't log to stdout
        })
        
        # Silence other commonly noisy loggers
        for logger_name in [
            'scrapy', 'scrapy.core.engine', 'scrapy.extensions', 
            'scrapy.core.scraper', 'scrapy.core.downloader',
            'twisted', 'filelock', 'hpack', 'urllib3'
        ]:
            logging.getLogger(logger_name).setLevel(logging.ERROR)
            logging.getLogger(logger_name).propagate = False
        
        # Set our own logger to only show important messages
        self.logger.setLevel(logging.INFO)
        
        # Override the spider's custom settings
        self.custom_settings.update({
            'LOG_LEVEL': 'ERROR',
            'LOG_ENABLED': False,
            'LOG_STDOUT': False,
            'LOGSTATS_INTERVAL': 0  # Disable periodic stats logging
        })
    
    def start_requests(self):
        """Start with either session verification or direct URLs"""
        # If processing job details only, go directly to the job URLs
        if self.process_job_details_only:
            self.logger.info(f"Processing job details for {len(self.start_urls_list)} URLs")
            for url in self.start_urls_list:
                yield scrapy.Request(
                    url=url, 
                    callback=self.parse_job_details,
                    cookies=self.cookies
                )
            return
            
        # If specific job URLs are provided, scrape those first
        if self.start_urls_list:
            self.logger.info(f"Starting with {len(self.start_urls_list)} provided job URLs")
            for url in self.start_urls_list:
                if "linkedin.com/jobs/view" in url:
                    yield scrapy.Request(
                        url=url, 
                        callback=self.parse_job_details,
                        cookies=self.cookies
                    )
                    
        # If company name is provided, search by company
        elif self.company:
            self.logger.info(f"Starting company job search for: {self.company}")
            
            # First, verify authentication if session cookies are provided
            if self.linkedin_session_id:
                self.logger.info("LinkedIn session cookies provided, verifying authentication...")
                yield scrapy.Request(
                    url="https://www.linkedin.com/feed/",
                    cookies=self.cookies,
                    callback=self.verify_session_for_company_search,
                    meta={"dont_redirect": True}
                )
            else:
                # If no session cookies, try to search without authentication
                self.logger.warning("No LinkedIn session cookies provided. Some company jobs may not be accessible.")
                yield from self.start_company_job_search()
        
        # If LinkedIn session cookies are provided, verify them first
        elif self.linkedin_session_id:
            self.logger.info("LinkedIn session cookies provided, verifying authentication...")
            
            # Make a request to LinkedIn with the session cookies to verify
            yield scrapy.Request(
                url="https://www.linkedin.com/feed/",  # LinkedIn feed page to check if logged in
                cookies=self.cookies,
                callback=self.verify_session,
                meta={"dont_redirect": True}
            )
        else:
            # If no session cookies, try to search without authentication
            self.logger.warning("No LinkedIn session cookies provided. Some job details may not be accessible.")
            yield from self.start_job_search()
    
    def verify_session(self, response):
        """Verify the session cookies are valid"""
        # Check if we're logged in by looking for feed content or redirects to login page
        if "login" in response.url or "checkpoint" in response.url:
            self.logger.error("LinkedIn session cookies are invalid or expired. Please provide fresh LinkedIn session cookies.")
            # Try to continue without authentication
            yield from self.start_job_search()
        else:
            self.logger.info("Successfully authenticated using LinkedIn session cookies")
            yield from self.start_job_search()
            
    def verify_session_for_company_search(self, response):
        """Verify the session cookies are valid for company search"""
        # Check if we're logged in by looking for feed content or redirects to login page
        if "login" in response.url or "checkpoint" in response.url:
            self.logger.error("LinkedIn session cookies are invalid or expired. Please provide fresh LinkedIn session cookies.")
            # Try to continue without authentication
            yield from self.start_company_job_search()
        else:
            self.logger.info("Successfully authenticated using LinkedIn session cookies")
            yield from self.start_company_job_search()
    
    def start_job_search(self):
        """Start the job search process"""
        # Construct the search URL
        if self.keyword and self.location:
            self.logger.info(f"Starting job search for '{self.keyword}' in '{self.location}'")
            params = {
                'keywords': self.keyword,
                'location': self.location,
                'f_TPR': 'r86400',  # Last 24 hours, can be adjusted
                'position': 1,
                'pageNum': 0
            }
            search_url = f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"
            self.logger.info(f"Searching jobs at URL: {search_url}")
            yield scrapy.Request(
                url=search_url, 
                callback=self.parse_search_results,
                cookies=self.cookies,
                meta={"page": 1}  # Track the page number
            )
        else:
            self.logger.error("Keyword and location parameters are required for job search")
            
    def start_company_job_search(self):
        """Start the company job search process"""
        if not self.company:
            self.logger.error("Company name is required for company job search")
            return
            
        # First, search for the company to get its LinkedIn page
        self.logger.info(f"Searching for company: {self.company}")
        
        # Try to construct a direct company URL
        company_slug = self.company.lower().replace(' ', '-').replace(',', '').replace('.', '')
        company_url = f"https://www.linkedin.com/company/{company_slug}/"
        
        # First try the direct company URL
        self.logger.info(f"Trying direct company URL: {company_url}")
        yield scrapy.Request(
            url=company_url,
            callback=self.parse_company_page,
            cookies=self.cookies,
            errback=self.handle_company_url_error,
            meta={"company_name": self.company}
        )
    
    def handle_company_url_error(self, failure):
        """Handle errors when direct company URL fails"""
        company_name = failure.request.meta.get("company_name", self.company)
        self.logger.warning(f"Direct company URL failed for {company_name}. Trying search instead.")
        
        # Fall back to search for the company
        search_url = f"https://www.linkedin.com/search/results/companies/?keywords={urlencode({'keywords': company_name})[9:]}"
        return scrapy.Request(
            url=search_url,
            callback=self.parse_company_search_results,
            cookies=self.cookies,
            meta={"company_name": company_name}
        )
    
    def parse_company_search_results(self, response):
        """Parse company search results to find the company page"""
        company_name = response.meta.get("company_name", self.company)
        self.logger.info(f"Parsing company search results for: {company_name}")
        
        # Extract company links from search results
        company_links = response.css("a.app-aware-link[href*='/company/']::attr(href)").getall()
        
        if not company_links:
            self.logger.warning(f"No company results found for: {company_name}")
            return
            
        # Take the first result as the most likely match
        company_url = company_links[0]
        self.logger.info(f"Found company URL: {company_url}")
        
        # Follow the company page
        yield scrapy.Request(
            url=company_url,
            callback=self.parse_company_page,
            cookies=self.cookies,
            meta={"company_name": company_name}
        )
    
    def parse_company_page(self, response):
        """Parse the company page to find the jobs link"""
        company_name = response.meta.get("company_name", self.company)
        self.logger.info(f"Parsing company page for: {company_name}")
        
        # Extract company ID from the page
        company_id = None
        
        # Try to extract from URL
        url_match = re.search(r'/company/([^/]+)', response.url)
        if url_match:
            company_id = url_match.group(1)
        
        # Try to extract from page content if not found in URL
        if not company_id:
            # Try to extract from script tags
            scripts = response.xpath('//script[contains(text(), "companyId") or contains(text(), "entityUrn")]/text()').getall()
            for script in scripts:
                id_match = re.search(r'"companyId":\s*"?(\d+)"?', script)
                if id_match:
                    company_id = id_match.group(1)
                    break
                    
                # Try alternative pattern
                urn_match = re.search(r'"entityUrn":\s*"urn:li:company:(\d+)"', script)
                if urn_match:
                    company_id = urn_match.group(1)
                    break
        
        if not company_id:
            self.logger.error(f"Could not extract company ID for: {company_name}")
            return
            
        self.logger.info(f"Found company ID: {company_id} for {company_name}")
        
        # Construct the jobs URL for this company
        jobs_url = f"https://www.linkedin.com/company/{company_id}/jobs/"
        
        # Follow the jobs page
        self.logger.info(f"Following company jobs URL: {jobs_url}")
        yield scrapy.Request(
            url=jobs_url,
            callback=self.parse_company_jobs_page,
            cookies=self.cookies,
            meta={"company_name": company_name, "company_id": company_id, "page": 1}
        )
    
    def parse_company_jobs_page(self, response):
        """Parse the company jobs page"""
        company_name = response.meta.get("company_name", self.company)
        company_id = response.meta.get("company_id", "")
        page = response.meta.get("page", 1)
        
        # Increment page count to track pagination properly
        if page > self.page_count:
            self.page_count = page
        
        self.logger.info(f"Parsing jobs for company: {company_name} (Page {page} of max {self.max_pages})")
        
        # Check if we've reached the job limit
        if self.check_job_limit():
            return
            
        # Extract job links from the company jobs page
        job_links = response.css("a.job-card-container__link[href*='/jobs/view/']::attr(href), a[href*='/jobs/view/']::attr(href)").getall()
        
        if not job_links:
            self.logger.warning(f"No job links found on company jobs page for: {company_name}")
            
            # Try an alternative approach - search for jobs with the company name
            self.logger.info(f"Trying alternative approach - searching for jobs with company: {company_name}")
            search_url = f"https://www.linkedin.com/jobs/search/?f_C={company_id}"
            yield scrapy.Request(
                url=search_url,
                callback=self.parse_search_results,
                cookies=self.cookies,
                meta={"company_name": company_name, "page": page}
            )
            return
        
        self.logger.info(f"Found {len(job_links)} job links for company: {company_name}")
        
        # Process each job link
        for job_link in job_links:
            # Check if we've reached the job limit before processing each job
            if self.check_job_limit():
                return
                
            # Make sure URL is absolute
            if not job_link.startswith("http"):
                job_link = f"https://www.linkedin.com{job_link}"
                
            # Extract job ID from the URL
            job_id = self._extract_job_id_from_url(job_link)
            
            # Skip if we've already processed this job ID
            if job_id in self.processed_job_ids:
                self.logger.info(f"Skipping already processed job ID: {job_id}")
                continue
                
            # Add to processed IDs
            self.processed_job_ids.add(job_id)
            
            # If in URL collection mode, yield the URL as an item
            if self.collect_urls_only:
                self.job_count += 1
                yield LinkedinJobUrlItem(url=job_link, id=job_id)
            else:
                # Follow the job link
                yield scrapy.Request(
                    url=job_link,
                    callback=self.parse_job_details,
                    cookies=self.cookies,
                    meta={"company_name": company_name, "job_id": job_id}
                )
        
        # Check for pagination and follow next page if available
        if not self.reached_job_limit and page < self.max_pages:
            next_page_link = response.css("a.artdeco-pagination__button--next::attr(href)").get()
            
            if next_page_link:
                self.logger.info(f"Following pagination to page {page + 1} for company: {company_name}")
                yield scrapy.Request(
                    url=next_page_link if next_page_link.startswith("http") else f"https://www.linkedin.com{next_page_link}",
                    callback=self.parse_company_jobs_page,
                    cookies=self.cookies,
                    meta={"company_name": company_name, "company_id": company_id, "page": page + 1}
                )
            else:
                # Try alternative pagination approach
                # Construct a search URL with pagination parameters
                search_url = f"https://www.linkedin.com/jobs/search/?f_C={company_id}&start={page * 25}"
                self.logger.info(f"Trying alternative pagination URL: {search_url}")
                yield scrapy.Request(
                    url=search_url,
                    callback=self.parse_search_results,
                    cookies=self.cookies,
                    meta={"company_name": company_name, "page": page + 1}
                )
        elif page >= self.max_pages:
            self.logger.info(f"Reached maximum page limit ({self.max_pages}) for company: {company_name}")
    
    def check_job_limit(self):
        """Check if we've reached the job limit and close spider if needed"""
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            if not self.reached_job_limit:
                self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). Stopping the scraper.")
                self.reached_job_limit = True
                # Raise CloseSpider exception to immediately stop the crawling process
                raise CloseSpider(f"Reached maximum job count: {self.max_jobs}")
            return True
        return False
    
    def parse_search_results(self, response):
        """Parse the job search results page"""
        # Get current page from meta or default to incrementing the counter
        current_page = response.meta.get("page", self.page_count + 1)
        
        # Update the page count to track pagination properly
        if current_page > self.page_count:
            self.page_count = current_page
            
        self.logger.info(f"Parsing search results page {self.page_count} of max {self.max_pages} from: {response.url}")
        
        # Check if we've reached the job limit before processing
        if self.check_job_limit():
            return
            
        # Debug: Log a sample of the response HTML to see what we're working with
        if self.debug:
            self.logger.debug(f"Response HTML sample: {response.text[:500]}...")
        
        # Try different CSS selectors for job cards
        job_cards = response.css("div.base-card")
        
        if not job_cards:
            self.logger.warning(f"No job cards found with primary selector. Trying alternative selectors...")
            # Try alternative selectors
            job_cards = response.css("li.jobs-search-results__list-item")
            
            if not job_cards:
                job_cards = response.css("div.job-search-card")
                
                if not job_cards:
                    self.logger.warning("No job cards found with any selector. This might indicate:")
                    self.logger.warning("1. LinkedIn has changed their HTML structure")
                    self.logger.warning("2. The search returned no results")
                    self.logger.warning("3. LinkedIn is blocking the scraper")
                    
                    # Log the full HTML for debugging
                    if self.debug:
                        self.logger.info("Saving response HTML for debugging")
                        with open("linkedin_response.html", "w", encoding="utf-8") as f:
                            f.write(response.text)
                    
                    # Try to extract any job-related links as a fallback
                    job_links = response.css("a[href*='/jobs/view/']::attr(href)").getall()
                    if job_links:
                        self.logger.info(f"Found {len(job_links)} job links directly. Attempting to process these.")
                        for job_link in job_links:
                            if self.check_job_limit():
                                return
                                
                            # If in URL collection mode, yield the URL as an item
                            if self.collect_urls_only:
                                # Extract job ID from the URL
                                job_id = self._extract_job_id_from_url(job_link)
                                
                                # Skip if we've already processed this job ID
                                if job_id in self.processed_job_ids:
                                    self.logger.info(f"Skipping already processed job ID: {job_id}")
                                    continue
                                
                                # Add to processed IDs
                                self.processed_job_ids.add(job_id)
                                
                                # Make sure URL is absolute
                                if not job_link.startswith("http"):
                                    job_link = f"https://www.linkedin.com{job_link}"
                                
                                # Yield URL as item
                                self.job_count += 1
                                yield LinkedinJobUrlItem(url=job_link, id=job_id)
                            else:
                                # Process job details
                                yield response.follow(
                                    job_link,
                                    callback=self.parse_job_details,
                                    cookies=self.cookies
                                )
        
        self.logger.info(f"Found {len(job_cards)} job cards on page {self.page_count}")
        
        for job_card in job_cards:
            # Check if we've reached the job limit before processing each job
            if self.check_job_limit():
                return
                
            # Try different selectors for job links
            job_link = job_card.css("a.base-card__full-link::attr(href)").get()
            if not job_link:
                job_link = job_card.css("a[href*='/jobs/view/']::attr(href)").get()
            
            if job_link:
                # Extract job ID from the URL using enhanced extraction
                job_id = self._extract_job_id_from_url(job_link)
                
                # Skip if we've already processed this job ID
                if job_id in self.processed_job_ids:
                    self.logger.info(f"Skipping already processed job ID: {job_id}")
                    continue
                
                # Add to processed IDs
                self.processed_job_ids.add(job_id)
                
                # Extract basic job info from the card
                job_title = job_card.css("h3.base-search-card__title::text, h3.job-search-card__title::text").get()
                if job_title:
                    job_title = job_title.strip()
                
                company_name = job_card.css("h4.base-search-card__subtitle a::text, span.job-search-card__company-name::text").get()
                if company_name:
                    company_name = company_name.strip()
                
                location = job_card.css("span.job-search-card__location::text").get()
                if location:
                    location = location.strip()
                
                # Extract posted date if available
                date_posted = job_card.css("time::attr(datetime)").get()
                
                # Extract the relative time text (e.g., "5 hours ago", "2 days ago")
                relative_time = job_card.css("time::text").get()
                if relative_time:
                    relative_time = relative_time.strip()
                
                # Extract company logo if available
                company_logo = job_card.css("img.artdeco-entity-image::attr(src)").get()
                
                # Extract company link if available on the search results page
                company_link = job_card.css("h4.base-search-card__subtitle a::attr(href), a.job-search-card__company-name::attr(href)").get()
                if company_link and not company_link.startswith("http"):
                    company_link = f"https://www.linkedin.com{company_link}"
                
                # Make sure URL is absolute
                if not job_link.startswith("http"):
                    job_link = f"https://www.linkedin.com{job_link}"
                
                # Only log detailed info in debug mode
                if self.debug:
                    self.logger.debug(f"Found job: {job_title} at {company_name} in {location}")
                    if job_id:
                        self.logger.debug(f"Extracted job ID: {job_id}")
                    if company_link:
                        self.logger.debug(f"Found company link on search page: {company_link}")
                else:
                    self.logger.info(f"Found job: {job_title} at {company_name}")
                
                # If in URL collection mode, yield the URL as an item
                if self.collect_urls_only:
                    self.job_count += 1
                    yield LinkedinJobUrlItem(url=job_link, id=job_id)
                else:
                    # Process job details
                    yield scrapy.Request(
                        url=job_link,
                        callback=self.parse_job_details,
                        cookies=self.cookies,
                        meta={
                            "job_title": job_title,
                            "company_name": company_name,
                            "location": location,
                            "date_posted": date_posted,
                            "relative_time": relative_time,
                            "company_logo": company_logo,
                            "job_id": job_id,
                            "company_link": company_link  # Pass the company link if found
                        }
                    )
            else:
                self.logger.warning("Found a job card but couldn't extract the job link")
        
        # Follow pagination if we haven't reached max_pages and haven't hit the job limit
        if not self.reached_job_limit and self.page_count < self.max_pages:
            next_page = response.css("a.artdeco-pagination__button--next::attr(href)").get()
            if next_page:
                self.logger.info(f"Following pagination to page {self.page_count + 1}")
                yield response.follow(
                    next_page, 
                    callback=self.parse_search_results,
                    cookies=self.cookies,
                    meta={"page": self.page_count + 1}
                )
            else:
                self.logger.info("No more pages to follow")
        elif self.page_count >= self.max_pages:
            self.logger.info(f"Reached maximum page limit ({self.max_pages}). Stopping pagination.")
   
    def parse_job_details(self, response):
        """Parse the job details page with support for both logged-in and non-logged-in views"""
        # Check if we've reached the job limit before processing
        if self.reached_job_limit:
            return
        
        self.logger.info(f"Parsing job details from: {response.url}")
        
        # Extract job ID using multiple methods to ensure we get a valid ID
        job_id = self._extract_job_id_comprehensive(response)
        
        # Skip if we've already processed this job ID
        if job_id in self.processed_job_ids and job_id != response.meta.get("job_id"):
            self.logger.info(f"Skipping already processed job ID: {job_id}")
            return
        
        # Add to processed IDs
        self.processed_job_ids.add(job_id)
        
        # Increment job counter
        self.job_count += 1
        
        if self.debug:
            self.logger.debug(f"Extracted job ID: {job_id}")
        
        # Detect if we're logged in by looking for specific elements
        is_logged_in = "nav__button-secondary" not in response.text
        self.logger.debug(f"Detected authentication status: {'Logged in' if is_logged_in else 'Not logged in'}")
        
        # Extract JSON data from the page
        json_data = self._extract_json_data(response)
        
        # Initialize variables
        job_title = None
        company_name = None
        location = None
        description_text = None
        employment_type = None
        seniority_level = None
        company_link = None  # Initialize company link variable
        
        # Try to get job details based on authentication status
        if is_logged_in:
            # Logged-in view selectors
            job_title = response.css("h1.job-details-jobs-unified-top-card__job-title::text, h1.topcard__title::text").get()
            company_name = response.css("a.job-details-jobs-unified-top-card__company-name::text, a.topcard__org-name-link::text").get()
            location = response.css("span.job-details-jobs-unified-top-card__bullet::text, span.topcard__flavor--bullet::text").get()
            
            # Extract company link for logged-in view
            company_link_element = response.css("a.job-details-jobs-unified-top-card__company-name::attr(href), a.topcard__org-name-link::attr(href)").get()
            if company_link_element:
                company_link = self._normalize_company_url(company_link_element)
            
            # Description for logged-in view
            description_container = response.css("div.job-details-jobs-unified-description__container, div.description__text")
            if description_container:
                description_text = " ".join(description_container.css("::text").getall())
            
            # Job criteria for logged-in view
            criteria_items = response.css("li.job-details-jobs-unified-top-card__job-insight, li.job-criteria__item")
            for item in criteria_items:
                text = " ".join(item.css("::text").getall()).strip()
                if "Employment type" in text or "Employment Type" in text:
                    employment_type = text.replace("Employment type", "").replace("Employment Type", "").strip()
                elif "Seniority level" in text or "Seniority Level" in text:
                    seniority_level = text.replace("Seniority level", "").replace("Seniority Level", "").strip()
        else:
            # Non-logged-in view selectors
            job_title = response.css("h1.top-card-layout__title::text").get()
            company_name = response.css("a.topcard__org-name-link::text").get()
            location = response.css("span.topcard__flavor--bullet::text").get()
            
            # Extract company link for non-logged-in view
            company_link_element = response.css("a.topcard__org-name-link::attr(href)").get()
            if company_link_element:
                company_link = self._normalize_company_url(company_link_element)
            
            # Description for non-logged-in view
            description_container = response.css("div.description__text")
            if description_container:
                description_text = " ".join(description_container.css("::text").getall())
            
            # Job criteria for non-logged-in view
            criteria_items = response.css("li.description__job-criteria-item")
            for item in criteria_items:
                item_title = item.css("h3.description__job-criteria-subheader::text").get()
                item_value = item.css("span.description__job-criteria-text::text").get()
                
                if item_title and item_value:
                    item_title = item_title.strip()
                    item_value = item_value.strip()
                    
                    if "Employment type" in item_title or "Employment Type" in item_title:
                        employment_type = item_value
                    elif "Seniority level" in item_title or "Seniority Level" in item_title:
                        seniority_level = item_value
        
        # Fall back to meta data if we couldn't extract from the page
        if not job_title:
            job_title = response.meta.get('job_title')
        if not company_name:
            company_name = response.meta.get('company_name')
        if not location:
            location = response.meta.get('location')
        if not company_link:
            company_link = response.meta.get('company_link')
        
        # Try additional methods to extract company link if still not found
        if not company_link:
            # Try to extract from "About the company" section
            about_company_links = response.css("a.jobs-company__link::attr(href), a.jobs-company-link::attr(href)").getall()
            for link in about_company_links:
                if "/company/" in link:
                    company_link = self._normalize_company_url(link)
                    break
        
        # Try to extract company link from JSON data if available
        if not company_link and json_data:
            company_link = self._extract_company_url_from_json(json_data)
        
        # If we still don't have a company link, try to construct one from the company name
        if not company_link and company_name:
            # Try to construct a URL from company name (this is a fallback and may not be accurate)
            company_slug = company_name.lower().replace(' ', '-').replace(',', '').replace('.', '')
            company_link = f"https://www.linkedin.com/company/{company_slug}/"
            
            # Log that this is a constructed URL
            if self.debug:
                self.logger.debug(f"Constructed company URL from name: {company_link}")
        
        # Clean up extracted data
        if job_title:
            job_title = job_title.strip()
        if company_name:
            company_name = company_name.strip()
        if location:
            location = location.strip()
        if description_text:
            description_text = description_text.strip()
        
        # Log company link if found
        if company_link and self.debug:
            self.logger.debug(f"Company LinkedIn URL: {company_link}")
        
        # Create job item with proper data types
        job_item = LinkedinJobItem()
        job_item['id'] = str(job_id) if job_id else f"job_{self.job_count}"
        job_item['title'] = str(job_title) if job_title else "Unknown Title"
        job_item['companyName'] = str(company_name) if company_name else "Unknown Company"
        job_item['location'] = str(location) if location else "Unknown Location"
        job_item['link'] = str(response.url)
        job_item['descriptionText'] = str(description_text) if description_text else ""
        job_item['employment_type'] = str(employment_type) if employment_type else None
        job_item['seniority_level'] = str(seniority_level) if seniority_level else None
        job_item['postedAt'] = response.meta.get('date_posted')
        job_item['scraped_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Add company LinkedIn URL to the item
        job_item['companyLinkedinUrl'] = str(company_link) if company_link else None
        
        # Extract additional data from JSON if available
        if json_data:
            additional_data = self._extract_additional_data(json_data)
            for key, value in additional_data.items():
                if key in job_item.fields and value is not None:
                    job_item[key] = value
        
        # Log success
        self.logger.info(f"Successfully scraped job {self.job_count}: {job_title} at {company_name} (ID: {job_id})")
        
        # Check if we've reached the job limit
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            self.reached_job_limit = True
            self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). Stopping the scraper.")
        
        yield job_item
    
    def _normalize_company_url(self, url):
        """Normalize company URL to standard format"""
        if not url:
            return None
            
        # If URL is relative, make it absolute
        if url.startswith('/'):
            url = f"https://www.linkedin.com{url}"
            
        # Ensure URL is for company page
        if '/company/' in url:
            # Remove query parameters and fragments
            url = url.split('?')[0].split('#')[0]
            
            # Ensure URL ends with trailing slash for consistency
            if not url.endswith('/'):
                url += '/'
                
            return url
        
        return None
    
    def _extract_company_url_from_json(self, json_data):
        """Extract company URL from JSON data"""
        if not json_data:
            return None
            
        # Try different possible paths to company URL
        possible_paths = [
            # Path for newer LinkedIn job pages
            ('data', 'companyInfo', 'companyPageUrl'),
            ('data', 'jobPostingInfo', 'companyInfo', 'companyPageUrl'),
            ('data', 'jobData', 'companyInfo', 'companyPageUrl'),
            # Path for company data
            ('data', 'companyInfo', 'companyPageUrl'),
            ('companyInfo', 'companyPageUrl'),
            # Alternative paths
            ('company', 'companyPageUrl'),
            ('company', 'url'),
        ]
        
        for path in possible_paths:
            try:
                current = json_data
                for key in path:
                    if key in current:
                        current = current[key]
                    else:
                        current = None
                        break
                
                if current and isinstance(current, str) and 'linkedin.com/company/' in current:
                    return self._normalize_company_url(current)
            except:
                continue
                
        # Look for company ID and construct URL
        company_id = None
        try:
            if 'data' in json_data and 'companyInfo' in json_data['data']:
                company_id = json_data['data']['companyInfo'].get('companyId')
            elif 'companyInfo' in json_data:
                company_id = json_data['companyInfo'].get('companyId')
                
            if company_id:
                return f"https://www.linkedin.com/company/{company_id}/"
        except:
            pass
            
        return None
    
    def _extract_job_id_comprehensive(self, response):
        """Extract job ID using multiple methods to ensure we get a value"""
        job_id = None
        
        # Method 1: Try to get from meta data
        job_id = response.meta.get("job_id")
        if job_id and self.debug:
            self.logger.debug(f"Found job ID in meta: {job_id}")
        
        # Method 2: Try different regex patterns on the URL
        if not job_id:
            job_id = self._extract_job_id_from_url(response.url)
            if job_id and self.debug:
                self.logger.debug(f"Extracted job ID from URL: {job_id}")
        
        # Method 3: Try to extract from HTML content
        if not job_id:
            # Look for job ID in data attributes
            data_job_id_elements = response.css('[data-job-id]::attr(data-job-id)').get()
            if data_job_id_elements:
                job_id = data_job_id_elements
                if self.debug:
                    self.logger.debug(f"Extracted job ID from data attribute: {job_id}")
        
        # Method 4: Try to extract from canonical URL
        if not job_id:
            canonical_url = response.css('link[rel="canonical"]::attr(href)').get()
            if canonical_url:
                job_id = self._extract_job_id_from_url(canonical_url)
                if job_id and self.debug:
                    self.logger.debug(f"Extracted job ID from canonical URL: {job_id}")
        
        # Method 5: Try to extract from JSON data
        if not job_id:
            json_data = self._extract_json_data(response)
            if json_data:
                job_id = self._extract_job_id_from_json(json_data)
                if job_id and self.debug:
                    self.logger.debug(f"Extracted job ID from JSON data: {job_id}")
        
        # Method 6: Try to extract from script tags
        if not job_id:
            script_tags = response.xpath('//script[contains(text(), "jobId") or contains(text(), "jobPosting")]/text()').getall()
            for script in script_tags:
                # Try different regex patterns
                patterns = [
                    r'jobId["\s:=]+["\']?(\d+)["\']?',
                    r'jobPosting[Ii]d["\s:=]+["\']?(\d+)["\']?',
                    r'job[Ii]d["\s:=]+["\']?(\d+)["\']?'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, script)
                    if match:
                        job_id = match.group(1)
                        if self.debug:
                            self.logger.debug(f"Extracted job ID from script: {job_id}")
                        break
                
                if job_id:
                    break
        
        # Final fallback: Generate a pseudo-ID if we still don't have one
        if not job_id:
            # Create a deterministic hash from the URL as a last resort
            import hashlib
            job_id = f"gen-{hashlib.md5(response.url.encode()).hexdigest()[:10]}"
            if self.debug:
                self.logger.warning(f"Could not extract real job ID, generated fallback ID: {job_id}")
        
        return job_id
    
    def _extract_job_id_from_url(self, url):
        """Extract job ID from URL using multiple patterns"""
        if not url:
            return None
            
        # Try multiple URL patterns
        url_patterns = [
            r'view/(\d+)',                  # Standard format: /jobs/view/12345
            r'currentJobId=(\d+)',          # Query param format
            r'jobId=(\d+)',                 # Another query param format
            r'jobs/(\d+)',                  # Alternative format
            r'-(\d{10,})',                  # Long ID at the end of slug
            r'linkedin\.com/jobs/search/.*?(?:viewJob=|jobId=)(\d+)'  # Search results format
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Try to extract from query parameters
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            # Check common parameter names
            for param in ['jobId', 'currentJobId', 'viewJob', 'id']:
                if param in query_params and query_params[param]:
                    return query_params[param][0]
        except:
            pass
            
        return None
    
    def _extract_job_id_from_json(self, json_data):
        """Extract job ID from JSON data"""
        if not json_data:
            return None
            
        # Look for job ID in different possible JSON locations
        possible_id_fields = [
            'data.jobPostingInfo.jobPostingId',
            'jobPostingInfo.jobPostingId',
            'data.jobPostingId',
            'jobPostingId',
            'data.jobData.jobPostingId',
            'jobData.jobPostingId',
            'entityUrn'
        ]
        
        for field_path in possible_id_fields:
            # Navigate through nested JSON using the field path
            current = json_data
            path_parts = field_path.split('.')
            
            for part in path_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    current = None
                    break
            
            # If we found a value and it looks like a job ID
            if current and (isinstance(current, int) or 
                           (isinstance(current, str) and re.search(r'\d+', current))):
                # If it's a string with format like "urn:li:jobPosting:12345", extract just the ID
                if isinstance(current, str) and ':' in current:
                    return current.split(':')[-1]
                else:
                    return str(current)
                    
        return None
    
    def _extract_json_data(self, response):
        """Extract structured JSON data from the page source"""
        # Try to find job data in script tags
        script_data = response.xpath('//script[contains(text(), "jobPostingInfo") or contains(text(), "companyInfo") or contains(text(), "jobData")]/text()').getall()
        
        job_data = {}
        
        for script in script_data:
            # Look for different data patterns
            patterns = [
                r'(\{"data":\{"jobPostingInfo":.+?\})\s*;',
                r'(\{"jobData":.+?\})\s*;',
                r'(\{"data":.+?\})\s*;',
                r'window\.initialData\s*=\s*(\{.+?\})\s*;',
                r'_initialData\s*=\s*(\{.+?\})\s*;',
                r'(\{"companyInfo":.+?\})\s*;'
            ]
            
            for pattern in patterns:
                matches = re.search(pattern, script, re.DOTALL)
                if matches:
                    try:
                        data = json.loads(matches.group(1))
                        # Merge with existing data
                        job_data.update(data)
                    except json.JSONDecodeError:
                        if self.debug:
                            self.logger.debug(f"Failed to parse JSON data from script")
                    except Exception as e:
                        if self.debug:
                            self.logger.debug(f"Error extracting JSON data: {str(e)}")
        
        return job_data
    
    def _extract_additional_data(self, json_data):
        """Extract additional job data from JSON"""
        additional_data = {}
        
        if not json_data:
            return additional_data
            
        try:
            # Navigate through different possible JSON structures
            job_posting_info = None
            
            # Try different paths to job posting info
            if 'data' in json_data and 'jobPostingInfo' in json_data['data']:
                job_posting_info = json_data['data']['jobPostingInfo']
            elif 'jobPostingInfo' in json_data:
                job_posting_info = json_data['jobPostingInfo']
            elif 'data' in json_data and 'jobData' in json_data['data']:
                job_posting_info = json_data['data']['jobData']
            elif 'jobData' in json_data:
                job_posting_info = json_data['jobData']
                
            if job_posting_info:
                # Extract job details
                if 'title' in job_posting_info:
                    additional_data['title'] = job_posting_info['title']
                    
                if 'description' in job_posting_info:
                    additional_data['descriptionText'] = job_posting_info['description']
                    
                if 'formattedLocation' in job_posting_info:
                    additional_data['location'] = job_posting_info['formattedLocation']
                    
                # Extract employment type
                if 'employmentType' in job_posting_info:
                    additional_data['employment_type'] = job_posting_info['employmentType']
                    
                # Extract seniority level
                if 'seniority' in job_posting_info:
                    additional_data['seniority_level'] = job_posting_info['seniority']
                elif 'seniorityLevel' in job_posting_info:
                    additional_data['seniority_level'] = job_posting_info['seniorityLevel']
                    
                # Extract posted date
                if 'listedAt' in job_posting_info:
                    try:
                        # Convert timestamp to ISO format
                        timestamp = int(job_posting_info['listedAt']) / 1000  # Convert from milliseconds
                        posted_date = datetime.fromtimestamp(timestamp).isoformat()
                        additional_data['postedAt'] = posted_date
                    except:
                        pass
                        
            # Try to extract company info
            company_info = None
            
            if 'data' in json_data and 'companyInfo' in json_data['data']:
                company_info = json_data['data']['companyInfo']
            elif 'companyInfo' in json_data:
                company_info = json_data['companyInfo']
                
            if company_info:
                # Extract company name
                if 'name' in company_info:
                    additional_data['companyName'] = company_info['name']
                    
                # Extract company URL
                if 'companyPageUrl' in company_info:
                    additional_data['companyLinkedinUrl'] = company_info['companyPageUrl']
                    
                # Extract company logo
                if 'logo' in company_info:
                    additional_data['companyLogo'] = company_info['logo']
                elif 'logoUrl' in company_info:
                    additional_data['companyLogo'] = company_info['logoUrl']
                    
        except Exception as e:
            if self.debug:
                self.logger.debug(f"Error extracting additional data: {str(e)}")
                
        return additional_data