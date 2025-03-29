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
from urllib.parse import urlencode
from scrapy.exceptions import CloseSpider
from scrapy.utils.log import configure_logging
from ..items import LinkedinJobItem

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
    
    def __init__(self, keyword=None, location=None, linkedin_session_id=None, linkedin_jsessionid=None, max_pages=5, max_jobs=0, start_urls=None, debug=False, *args, **kwargs):
        super(LinkedinJobsSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword
        self.location = location
        self.linkedin_session_id = linkedin_session_id
        self.linkedin_jsessionid = linkedin_jsessionid
        self.max_pages = int(max_pages)
        self.max_jobs = int(max_jobs)  # Parameter for job count limit
        self.page_count = 0
        self.job_count = 0  # Counter for scraped jobs
        self.start_urls_list = start_urls or []
        self.debug = debug
        
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
        
        # If LinkedIn session cookies are provided, verify them first
        if self.linkedin_session_id:
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
                cookies=self.cookies
            )
        else:
            self.logger.error("Keyword and location parameters are required for job search")
    
    def check_job_limit(self):
        """Check if we've reached the job limit and close spider if needed"""
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). Stopping the scraper.")
            # Raise CloseSpider exception to immediately stop the crawling process
            raise CloseSpider(f"Reached maximum job count: {self.max_jobs}")
    
    def parse_search_results(self, response):
        """Parse the job search results page"""
        # Check if we've reached the job limit
        self.check_job_limit()
            
        self.page_count += 1
        self.logger.info(f"Parsing search results page {self.page_count} from: {response.url}")
        
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
                    self.logger.info("Saving response HTML for debugging")
                    with open("linkedin_response.html", "w", encoding="utf-8") as f:
                        f.write(response.text)
                    
                    # Try to extract any job-related links as a fallback
                    job_links = response.css("a[href*='/jobs/view/']::attr(href)").getall()
                    if job_links:
                        self.logger.info(f"Found {len(job_links)} job links directly. Attempting to process these.")
                        for job_link in job_links:
                            yield response.follow(
                                job_link,
                                callback=self.parse_job_details,
                                cookies=self.cookies
                            )
        
        self.logger.info(f"Found {len(job_cards)} job cards on page {self.page_count}")
        
        for job_card in job_cards:
            # Check if we've reached the job limit before processing each job
            if self.max_jobs > 0 and self.job_count >= self.max_jobs:
                self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}) while parsing results. Stopping.")
                return
                
            # Try different selectors for job links
            job_link = job_card.css("a.base-card__full-link::attr(href)").get()
            if not job_link:
                job_link = job_card.css("a[href*='/jobs/view/']::attr(href)").get()
            
            if job_link:
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
                
                # Extract job ID from the URL
                job_id = None
                if job_link:
                    match = re.search(r'view/(\d+)', job_link)
                    if match:
                        job_id = match.group(1)
                
                # Only log detailed info in debug mode
                if self.debug:
                    self.logger.debug(f"Found job: {job_title} at {company_name} in {location}")
                else:
                    self.logger.info(f"Found job: {job_title} at {company_name}")
                
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
                        "job_id": job_id
                    }
                )
            else:
                self.logger.warning("Found a job card but couldn't extract the job link")
        
        # Follow pagination if we haven't reached max_pages and haven't hit the job limit
        if self.page_count < self.max_pages and (self.max_jobs == 0 or self.job_count < self.max_jobs):
            next_page = response.css("a.artdeco-pagination__button--next::attr(href)").get()
            if next_page:
                self.logger.info(f"Following pagination to page {self.page_count + 1}")
                yield response.follow(
                    next_page, 
                    callback=self.parse_search_results,
                    cookies=self.cookies
                )
            else:
                self.logger.info("No more pages to follow")
        elif self.page_count >= self.max_pages:
            self.logger.info(f"Reached maximum page limit ({self.max_pages}). Stopping pagination.")
        """Parse the job search results page"""
        # Check if we've reached the job limit
        self.check_job_limit()
            
        self.page_count += 1
        self.logger.info(f"Parsing search results page {self.page_count} from: {response.url}")
        
        # Extract job listings
        job_cards = response.css("div.base-card")
        
        for job_card in job_cards:
            # Check if we've reached the job limit before processing each job
            if self.max_jobs > 0 and self.job_count >= self.max_jobs:
                self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}) while parsing results. Stopping.")
                return
                
            job_link = job_card.css("a.base-card__full-link::attr(href)").get()
            
            if job_link:
                # Extract basic job info from the card
                job_title = job_card.css("h3.base-search-card__title::text").get()
                if job_title:
                    job_title = job_title.strip()
                
                company_name = job_card.css("h4.base-search-card__subtitle a::text").get()
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
                
                # Extract job ID from the URL
                job_id = None
                if job_link:
                    match = re.search(r'view/(\d+)', job_link)
                    if match:
                        job_id = match.group(1)
                
                # Only log detailed info in debug mode
                if self.debug:
                    self.logger.debug(f"Found job: {job_title} at {company_name} in {location}")
                
                yield scrapy.Request(
                    url=job_link,
                    callback=self.parse_job_details,
                    cookies=self.cookies,  # Use the parsed cookies
                    meta={
                        "job_title": job_title,
                        "company_name": company_name,
                        "location": location,
                        "date_posted": date_posted,
                        "relative_time": relative_time,
                        "company_logo": company_logo,
                        "job_id": job_id
                    }
                )
        
        # Follow pagination if we haven't reached max_pages and haven't hit the job limit
        if self.page_count < self.max_pages and (self.max_jobs == 0 or self.job_count < self.max_jobs):
            next_page = response.css("a.artdeco-pagination__button--next::attr(href)").get()
            if next_page:
                yield response.follow(
                    next_page, 
                    callback=self.parse_search_results,
                    cookies=self.cookies  # Use the parsed cookies
                )
   
    def parse_job_details(self, response):
        """Parse the job details page"""
        self.logger.info(f"Parsing job details from: {response.url}")
        
        # Increment job counter
        self.job_count += 1
        
        # Extract job ID from URL if not already in meta
        job_id = response.meta.get('job_id')
        if not job_id:
            match = re.search(r'view/(\d+)', response.url)
            if match:
                job_id = match.group(1)
        
        # Get job details from meta or extract from page
        job_title = response.meta.get('job_title')
        if not job_title:
            job_title = response.css("h1.job-details-jobs-unified-top-card__job-title::text").get()
            if job_title:
                job_title = job_title.strip()
        
        company_name = response.meta.get('company_name')
        if not company_name:
            company_name = response.css("a.job-details-jobs-unified-top-card__company-name::text").get()
            if company_name:
                company_name = company_name.strip()
        
        location = response.meta.get('location')
        if not location:
            location = response.css("span.job-details-jobs-unified-top-card__bullet::text").get()
            if location:
                location = location.strip()
        
        # Extract job description
        description_container = response.css("div.job-details-jobs-unified-description__container")
        description_text = ""
        if description_container:
            # Extract all text from the description container
            description_text = " ".join(description_container.css("::text").getall())
            description_text = description_text.strip()
        
        # Extract other job details
        employment_type = None
        seniority_level = None
        
        criteria_items = response.css("li.job-details-jobs-unified-top-card__job-insight")
        for item in criteria_items:
            text = " ".join(item.css("::text").getall()).strip()
            if "Employment type" in text:
                employment_type = text.replace("Employment type", "").strip()
            elif "Seniority level" in text:
                seniority_level = text.replace("Seniority level", "").strip()
        
        # Create job item
        job_item = LinkedinJobItem()
        job_item['id'] = job_id
        job_item['title'] = job_title
        job_item['companyName'] = company_name
        job_item['location'] = location
        job_item['link'] = response.url
        job_item['descriptionText'] = description_text
        job_item['employment_type'] = employment_type
        job_item['seniority_level'] = seniority_level
        job_item['postedAt'] = response.meta.get('date_posted')
        job_item['scraped_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Log success
        self.logger.info(f"Successfully scraped job {self.job_count}: {job_title} at {company_name}")
        
        # Check if we've reached the job limit
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). Stopping the scraper.")
            raise CloseSpider(f"Reached maximum job count: {self.max_jobs}")
        
        yield job_item
        """Parse the job details page with enhanced data extraction"""
        # Check if we've reached the job limit
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). Skipping job.")
            return
            
        # Increment job counter
        self.job_count += 1
        
        # Create job item - We'll populate fields in the desired order
        job_item = LinkedinJobItem()
        
        # Try to extract structured data from the page
        json_data = self._extract_json_data(response)
        
        # Extract job ID using multiple methods
        job_id = self._extract_job_id(response)
        
        # Extract basic job information
        job_info = self._extract_basic_job_info(response)
        
        # Extract company information
        company_info = self._extract_company_info(response)
        
        # Extract job details
        job_details = self._extract_job_details(response)
        
        # Extract posting time information
        posting_info = self._extract_posting_info(response)
        
        # Extract additional data from JSON if available
        additional_data = self._extract_additional_data(json_data)
        
        # Record the scrape time
        scraped_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Now populate the job item in the desired order
        # 1. ID first
        job_item["id"] = job_id
        # 2. Company name second
        job_item["companyName"] = job_info.get("company_name")
        # 3. Job title third
        job_item["title"] = job_info.get("job_title")
        # 4. Posted time fourth
        job_item["postedAt"] = posting_info.get("posted_at")
        # 5. Location fifth
        job_item["location"] = job_info.get("location")
        # 6. Employment type
        if job_details.get("employment_type"):
            job_item["employment_type"] = job_details.get("employment_type")
        # 7. Seniority level
        if job_details.get("seniority_level"):
            job_item["seniority_level"] = job_details.get("seniority_level")
        # 8. Easy apply flag
        job_item["easyApply"] = job_details.get("easy_apply", False)
        # 9. Job link
        job_item["link"] = response.url
        # 10. Company LinkedIn URL
        if company_info.get("company_linkedin_url"):
            job_item["companyLinkedinUrl"] = company_info.get("company_linkedin_url")
        # 11. Skills
        if job_details.get("skills"):
            job_item["skills"] = job_details.get("skills")
        # 12. Description text
        job_item["descriptionText"] = job_details.get("job_description_text", "")
        # 13. Scraping timestamp
        job_item["scraped_at"] = scraped_at
        
        # Add any workplace types
        if job_details.get("workplace_types"):
            job_item["jobWorkplaceTypes"] = job_details.get("workplace_types")
        
        # Add insights if available
        if job_details.get("insights"):
            job_item["insights"] = job_details.get("insights")
        
        # Add company logo if available
        if company_info.get("company_logo"):
            job_item["companyLogo"] = company_info.get("company_logo")
        
        # Add application URL if available
        if job_details.get("apply_url"):
            job_item["applyUrl"] = job_details.get("apply_url")
        
        # Add company description if available
        if company_info.get("company_description"):
            job_item["companyDescription"] = company_info.get("company_description")
        
        # Add any additional data extracted from JSON
        for key, value in additional_data.items():
            if key not in job_item:
                job_item[key] = value
        
        # In non-debug mode, only log minimal information
        if not self.debug:
            self.logger.info(f"Scraped job {self.job_count}: {job_item['title']} at {job_item['companyName']} (ID: {job_item['id']})")
        else:
            # In debug mode, log detailed information
            self.logger.debug(f"Scraped job {self.job_count} details: {job_item['title']} at {job_item['companyName']} (ID: {job_item['id']})")
            self.logger.debug(f"Full job data: {json.dumps({k: v for k, v in dict(job_item).items() if k != 'descriptionText'}, ensure_ascii=False)}")
            self.logger.debug(f"Job description length: {len(job_item.get('descriptionText', ''))}")
        
        # Check if we've reached the job limit after processing this job
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). This is the final job.")
        
        yield job_item
        
        # Check job limit after yielding the item
        self.check_job_limit()
    
    def _extract_job_id(self, response):
        """Extract job ID using multiple methods to ensure we get a value"""
        job_id = None
        
        # Method 1: Try to get from meta data
        job_id = response.meta.get("job_id")
        
        # Method 2: Try different regex patterns on the URL
        if not job_id:
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
                match = re.search(pattern, response.url)
                if match:
                    job_id = match.group(1)
                    if self.debug:
                        self.logger.debug(f"Extracted job ID {job_id} using pattern: {pattern}")
                    break
        
        # Method 3: Try to extract from JSON data
        if not job_id and hasattr(response, 'json_data') and response.json_data:
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
                current = response.json_data
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
                        job_id = current.split(':')[-1]
                    else:
                        job_id = str(current)
                    
                    if self.debug:
                        self.logger.debug(f"Extracted job ID {job_id} from JSON field: {field_path}")
                    break
        
        # Final fallback: Generate a pseudo-ID if we still don't have one
        if not job_id:
            # Create a deterministic hash from the URL as a last resort
            import hashlib
            job_id = f"gen-{hashlib.md5(response.url.encode()).hexdigest()[:10]}"
            if self.debug:
                self.logger.warning(f"Could not extract real job ID, generated fallback ID: {job_id}")
        
        return job_id
    
    def _extract_basic_job_info(self, response):
        """Extract basic job information from the response"""
        # Extract data from meta or directly from the page if not available
        job_title = response.meta.get("job_title") or response.css("h1.top-card-layout__title::text").get()
        if job_title:
            job_title = job_title.strip()
            
        company_name = response.meta.get("company_name") or response.css("a.topcard__org-name-link::text").get()
        if company_name:
            company_name = company_name.strip()
            
        location = response.meta.get("location") or response.css("span.topcard__flavor--bullet::text").get()
        if location:
            location = location.strip()
            
        return {
            "job_title": job_title,
            "company_name": company_name,
            "location": location
        }
    
    def _extract_company_info(self, response):
        """Extract company information from the response"""
        # Extract company logo
        company_logo = response.meta.get("company_logo") or response.css("img.artdeco-entity-image::attr(src)").get()
        
        # Extract company LinkedIn URL
        company_url = response.css("a.topcard__org-name-link::attr(href)").get()
        if company_url:
            company_linkedin_url = response.urljoin(company_url)
        else:
            company_linkedin_url = None
        
        # Extract company description
        company_description = response.css("div.company-description__text::text").get()
        if company_description:
            company_description = company_description.strip()
            
        return {
            "company_logo": company_logo,
            "company_linkedin_url": company_linkedin_url,
            "company_description": company_description
        }
    
    def _extract_job_details(self, response):
        """Extract detailed job information from the response"""
        # Extract application URL
        apply_url = response.css("a.apply-button::attr(href)").get()
        
        # Check if this is an Easy Apply job
        easy_apply_button = response.css("button.jobs-apply-button").get()
        easy_apply = bool(easy_apply_button)
        
        # Extract workplace type
        workplace_types = []
        workplace_type_elements = response.css("li.job-details-jobs-unified-top-card__workplace-type")
        for element in workplace_type_elements:
            workplace_type = element.css("::text").get()
            if workplace_type:
                workplace_types.append({"localizedName": workplace_type.strip()})
        
        # Extract job criteria (employment type, seniority level, etc.)
        employment_type = None
        seniority_level = None
        job_criteria = response.css("li.description__job-criteria-item")
        for criteria in job_criteria:
            criteria_type = criteria.css("h3.description__job-criteria-subheader::text").get()
            if criteria_type:
                criteria_type = criteria_type.strip()
                criteria_value = criteria.css("span.description__job-criteria-text::text").get()
                if criteria_value:
                    criteria_value = criteria_value.strip()
                    if "Seniority" in criteria_type:
                        seniority_level = criteria_value
                    elif "Employment" in criteria_type:
                        employment_type = criteria_value
        
        # Extract insights about connections
        insights = []
        insights_elements = response.css("span.jobs-unified-top-card__subtitle-secondary-grouping span.jobs-unified-top-card__bullet::text").getall()
        if insights_elements:
            insights = [insight.strip() for insight in insights_elements if "connection" in insight.lower()]
        
        # Extract skills from the job description
        skills = []
        skills_section = response.css("div.description__text ul li::text").getall()
        for skill in skills_section:
            if len(skill.strip()) > 0 and len(skill.strip()) < 50:  # Simple heuristic for skill-like text
                skills.append(skill.strip())
        
        if skills:
            skills = skills[:10]  # Limit to top 10 skills
        
        # Extract job description
        job_description = response.css("div.description__text").get()
        if job_description:
            job_description_text = self._clean_html(job_description)
        else:
            job_description_text = ""
            
        return {
            "apply_url": apply_url,
            "easy_apply": easy_apply,
            "workplace_types": workplace_types,
            "employment_type": employment_type,
            "seniority_level": seniority_level,
            "insights": insights,
            "skills": skills,
            "job_description_text": job_description_text
        }
    
    def _extract_posting_info(self, response):
        """Extract job posting time information"""
        # Handle the posted date - try to get the actual job posting time
        # Try multiple sources to get the most accurate posting time
        posted_at = None
        
        # 1. Try to get the posting time from the specific CSS selector
        relative_time_text = response.css("div.job-details-jobs-unified-top-card__primary-description-container div span.tvm__text::text").get()
        if not relative_time_text:
            # Try alternative selectors
            relative_time_text = response.css("span.posted-time-ago__text::text").get()
            
        if not relative_time_text and response.meta.get("relative_time"):
            relative_time_text = response.meta.get("relative_time")
            
        if relative_time_text:
            # Parse the relative time text to get an estimated datetime
            posted_datetime = self._parse_relative_time(relative_time_text)
            if posted_datetime:
                posted_at = self._format_datetime(posted_datetime)
        
        # If we still don't have a posting time, try the meta data from the search results page
        if not posted_at and response.meta.get("date_posted"):
            posted_at = self._format_datetime(response.meta.get("date_posted"))
            
        return {
            "posted_at": posted_at
        }
    
    def _extract_additional_data(self, json_data):
        """Extract additional data from JSON if available"""
        additional_data = {}
        if json_data:
            try:
                # Navigate through the JSON structure to find job data
                job_data = None
                
                # Check different possible paths in the JSON structure
                if 'data' in json_data and 'jobPostingInfo' in json_data['data']:
                    job_data = json_data['data']['jobPostingInfo']
                elif 'jobPostingInfo' in json_data:
                    job_data = json_data['jobPostingInfo']
                elif 'data' in json_data and 'jobData' in json_data['data']:
                    job_data = json_data['data']['jobData']
                
                if job_data:
                    # Extract job data fields
                    fields_to_extract = [
                        'isReposted', 'posterId', 'easyApply', 'isPromoted', 
                        'jobState', 'contentSource', 'companyWebsite', 'companySlogan',
                        'companyEmployeesCount'
                    ]
                    
                    for field in fields_to_extract:
                        if field in job_data:
                            additional_data[field] = job_data[field]
                    
                    # Extract applicant insights
                    if 'jobApplicantInsights' in job_data:
                        additional_data['jobApplicantInsights'] = job_data['jobApplicantInsights']
                    
                    # Extract company data
                    if 'company' in job_data:
                        additional_data['company'] = job_data['company']
                    
                    # Extract salary data
                    if 'salary' in job_data:
                        additional_data['salary'] = job_data['salary']
                    
                    # Extract recruiter data
                    if 'recruiter' in job_data:
                        additional_data['recruiter'] = job_data['recruiter']
                    
                    # If we have a timestamp in the JSON data, use it for postedAt
                    if 'listedAt' in job_data and not additional_data.get('postedAt'):
                        additional_data['postedAt'] = self._format_datetime(job_data['listedAt'])
                    
                    # Extract skills if we don't have them yet
                    if 'skills' in job_data and not additional_data.get('skills'):
                        additional_data['skills'] = job_data['skills']
                
            except Exception as e:
                if self.debug:
                    self.logger.warning(f"Error extracting additional data from JSON: {e}")
        
        return additional_data
    
    def _extract_json_data(self, response):
        """Extract structured JSON data from the page source"""
        # Try to find job data in script tags
        script_data = response.xpath('//script[contains(text(), "jobPostingInfo") or contains(text(), "companyInfo") or contains(text(), "jobData")]/text()').getall()
        
        job_data = {}
        
        for script in script_data:
            # Look for different data patterns
            patterns = [
                r'(\{"data":\{"jobPostingInfo":.*?\})(?=;)',
                r'(\{"data":\{"companyInfo":.*?\})(?=;)',
                r'(\{"data":\{"jobData":.*?\})(?=;)',
                r'(window\.INITIAL_STATE\s*=\s*\{.*?\})(?=;)',
                r'(\{.*?"jobPostingId":.*?\})(?=;)',
                r'(\{.*?"companyId":.*?\})(?=;)'
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
                            pass  # Would log warning in real implementation
        
        return job_data
    
    def _clean_html(self, html_text):
        """Clean HTML content and extract readable text without external dependencies"""
        if not html_text:
            return ""
        
        try:
            # First, extract just the main content section which contains the job description
            main_content_match = re.search(r'<div class="description__text[^>]*>(.*?)</div>\s*</section>', html_text, re.DOTALL)
            if main_content_match:
                html_text = main_content_match.group(1)
            
            # Remove all buttons and UI elements
            html_text = re.sub(r'<button.*?</button>', '', html_text, flags=re.DOTALL)
            html_text = re.sub(r'<icon.*?</icon>', '', html_text, flags=re.DOTALL)
            
            # Remove script and style elements
            html_text = re.sub(r'<script.*?>.*?</script>', '', html_text, flags=re.DOTALL)
            html_text = re.sub(r'<style.*?>.*?</style>', '', html_text, flags=re.DOTALL)
            
            # Replace common HTML elements with text formatting
            html_text = re.sub(r'<br\s*/?>|<br\s*/?>', '\n', html_text)
            html_text = re.sub(r'<li.*?>', '• ', html_text)
            html_text = re.sub(r'</li>', '\n', html_text)
            html_text = re.sub(r'</(p|div|h\d|ul|ol)>', '\n', html_text)
            html_text = re.sub(r'<(p|div|h\d|ul|ol)[^>]*>', '', html_text)
            
            # Remove any remaining HTML tags
            html_text = re.sub(r'<[^>]*>', '', html_text)
            
            # Handle special HTML entities
            html_text = html_text.replace('&amp;', '&')
            html_text = html_text.replace('&lt;', '<')
            html_text = html_text.replace('&gt;', '>')
            html_text = html_text.replace('&quot;', '"')
            html_text = html_text.replace('&nbsp;', ' ')
            
            # Fix multiple consecutive newlines
            html_text = re.sub(r'\n{3,}', '\n\n', html_text)
            
            # Fix multiple spaces
            html_text = re.sub(r' {2,}', ' ', html_text)
            
            return html_text.strip()
        except Exception:
            # If all else fails, just return the original with tags stripped
            return re.sub(r'<[^>]*>', '', html_text).strip()
    
    def _clean_text(self, text):
        """Clean text by removing extra whitespace"""
        if not text:
            return ""
        return ' '.join(text.split())
    
    def _parse_relative_time(self, relative_time_text):
        """Parse relative time text (like "5 hours ago", "2 days ago") and return an estimated datetime"""
        if not relative_time_text:
            return None
            
        now = datetime.now()
        relative_time_text = relative_time_text.lower().strip()
        
        # Match patterns like "5 hours ago", "2 days ago", "1 week ago", etc.
        minutes_match = re.search(r'(\d+)\s+minute', relative_time_text)
        hours_match = re.search(r'(\d+)\s+hour', relative_time_text)
        days_match = re.search(r'(\d+)\s+day', relative_time_text)
        weeks_match = re.search(r'(\d+)\s+week', relative_time_text)
        months_match = re.search(r'(\d+)\s+month', relative_time_text)
        
        if minutes_match:
            minutes = int(minutes_match.group(1))
            return now - timedelta(minutes=minutes)
        elif hours_match:
            hours = int(hours_match.group(1))
            return now - timedelta(hours=hours)
        elif days_match:
            days = int(days_match.group(1))
            return now - timedelta(days=days)
        elif weeks_match:
            weeks = int(weeks_match.group(1))
            return now - timedelta(weeks=weeks)
        elif months_match:
            months = int(months_match.group(1))
            # Approximate a month as 30 days
            return now - timedelta(days=30*months)
        elif "just now" in relative_time_text or "just posted" in relative_time_text:
            return now
        elif "yesterday" in relative_time_text:
            return now - timedelta(days=1)
        
        # If we can't parse the relative time, return None
        return None
    
    def _format_datetime(self, date_value):
        """Format date to ISO format (YYYY-MM-DDTHH:MM:SS)"""
        if not date_value:
            return None
            
        try:
            from datetime import datetime, timedelta
            
            # If it's already a datetime object
            if isinstance(date_value, datetime):
                return date_value.strftime('%Y-%m-%dT%H:%M:%S')
                
            # If it's already in ISO format
            if isinstance(date_value, str) and 'T' in date_value:
                # Ensure it's properly formatted
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%dT%H:%M:%S')
            
            # If it's a timestamp (integer)
            if isinstance(date_value, (int, float)):
                dt = datetime.fromtimestamp(date_value / 1000)  # Convert milliseconds to seconds
                return dt.strftime('%Y-%m-%dT%H:%M:%S')
                
            # If it's a relative date string, use current date
            return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            return None