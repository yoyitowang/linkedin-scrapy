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
        # Ensure data is written immediately when items are scraped
        'FEEDS': {
            'apify_storage/datasets/default/linkedin_jobs_output_%(time)s.json': {
                'format': 'json',
                'encoding': 'utf8',
                'indent': 4,
                'overwrite': True,
            },
        },
        # Ensure clean shutdown
        'CLOSESPIDER_TIMEOUT': 0,  # Disable timeout-based shutdown
    }
    
    def __init__(self, keyword=None, location=None, username=None, password=None, max_pages=5, max_jobs=0, start_urls=None, debug=False, *args, **kwargs):
        super(LinkedinJobsSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword
        self.location = location
        self.linkedin_username = username
        self.linkedin_password = password
        self.max_pages = int(max_pages)
        self.max_jobs = int(max_jobs)  # Parameter for job count limit
        self.page_count = 0
        self.job_count = 0  # Counter for scraped jobs
        self.start_urls_list = start_urls or []
        self.debug = debug
        
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
        """Start with either login page or direct URLs"""
        # If specific job URLs are provided, scrape those first
        if self.start_urls_list:
            self.logger.info(f"Starting with {len(self.start_urls_list)} provided job URLs")
            for url in self.start_urls_list:
                if "linkedin.com/jobs/view" in url:
                    yield scrapy.Request(url=url, callback=self.parse_job_details)
        
        # If credentials are provided, start with login
        if self.linkedin_username and self.linkedin_password:
            yield scrapy.Request(
                url="https://www.linkedin.com/login",
                callback=self.login,
                meta={"dont_redirect": True}
            )
        else:
            # If no credentials, try to search without login
            self.logger.warning("No LinkedIn credentials provided. Some job details may not be accessible.")
            yield from self.start_job_search()
    
    def login(self, response):
        """Handle login process"""
        self.logger.info("Logging in to LinkedIn...")
        
        # Extract CSRF token if needed
        csrf_token = response.css('input[name="csrfToken"]::attr(value)').get()
        
        # Submit login form
        yield scrapy.FormRequest.from_response(
            response,
            formdata={
                'session_key': self.linkedin_username,
                'session_password': self.linkedin_password,
                'csrfToken': csrf_token
            },
            callback=self.after_login
        )
    
    def after_login(self, response):
        """Check if login was successful and start job search"""
        # Check if login was successful by looking for error messages
        if "error" in response.url or response.css(".form-error-message").get():
            self.logger.error("Login failed")
            return
        
        self.logger.info("Successfully logged in to LinkedIn")
        yield from self.start_job_search()
    
    def start_job_search(self):
        """Start the job search process"""
        # Construct the search URL
        if self.keyword and self.location:
            params = {
                'keywords': self.keyword,
                'location': self.location,
                'f_TPR': 'r86400',  # Last 24 hours, can be adjusted
                'position': 1,
                'pageNum': 0
            }
            search_url = f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"
            yield scrapy.Request(url=search_url, callback=self.parse_search_results)
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
                yield response.follow(next_page, callback=self.parse_search_results)
    
    def extract_json_data(self, response):
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
                            self.logger.warning("Failed to parse JSON data from script")
        
        return job_data
    
    def clean_html(self, html_text):
        """Clean HTML content"""
        if not html_text:
            return ""
        
        # Remove script and style elements
        html_text = re.sub(r'<script.*?>.*?</script>', '', html_text, flags=re.DOTALL)
        html_text = re.sub(r'<style.*?>.*?</style>', '', html_text, flags=re.DOTALL)
        
        # Convert <br> to newlines for better readability in plain text
        html_text = re.sub(r'<br\s*/?>|<br\s*/?>', '\n', html_text)
        
        return html_text.strip()
    
    def parse_relative_time(self, relative_time_text):
        """
        Parse relative time text (like "5 hours ago", "2 days ago") 
        and return an estimated datetime
        """
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
    
    def format_datetime(self, date_value):
        """Format date to ISO format (YYYY-MM-DDTHH:MM:SS)"""
        if not date_value:
            return None
            
        try:
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
        except Exception as e:
            if self.debug:
                self.logger.warning(f"Error formatting date {date_value}: {e}")
            return None
    
    def parse_job_details(self, response):
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
        json_data = self.extract_json_data(response)
        
        # IMPROVED JOB ID EXTRACTION - START
        # Extract job ID using multiple methods to ensure we get a value
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
        if not job_id and json_data:
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
        
        # IMPROVED JOB ID EXTRACTION - END
        
        # Extract data from meta or directly from the page if not available
        job_title = response.meta.get("job_title") or response.css("h1.top-card-layout__title::text").get().strip()
        company_name = response.meta.get("company_name") or response.css("a.topcard__org-name-link::text").get().strip()
        location = response.meta.get("location") or response.css("span.topcard__flavor--bullet::text").get().strip()
        job_link = response.url
        
        # Extract company logo
        company_logo = response.meta.get("company_logo") or response.css("img.artdeco-entity-image::attr(src)").get()
        
        # Extract company LinkedIn URL
        company_url = response.css("a.topcard__org-name-link::attr(href)").get()
        if company_url:
            company_linkedin_url = response.urljoin(company_url)
        else:
            company_linkedin_url = None
        
        # Extract application URL
        apply_url = response.css("a.apply-button::attr(href)").get()
        
        # Check if this is an Easy Apply job
        easy_apply_button = response.css("button.jobs-apply-button").get()
        easy_apply = bool(easy_apply_button)
        
        # Extract company description
        company_description = response.css("div.company-description__text::text").get()
        if company_description:
            company_description = company_description.strip()
        
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
            criteria_type = criteria.css("h3.description__job-criteria-subheader::text").get().strip()
            criteria_value = criteria.css("span.description__job-criteria-text::text").get().strip()
            
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
            job_description_text = self.clean_html(job_description)
        else:
            job_description_text = ""
        
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
            posted_datetime = self.parse_relative_time(relative_time_text)
            if posted_datetime:
                posted_at = self.format_datetime(posted_datetime)
        
        # If we still don't have a posting time, try the meta data from the search results page
        if not posted_at and response.meta.get("date_posted"):
            posted_at = self.format_datetime(response.meta.get("date_posted"))
        
        # Extract additional data from JSON if available
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
                    if 'listedAt' in job_data and not posted_at:
                        posted_at = self.format_datetime(job_data['listedAt'])
                    
                    # Extract skills if we don't have them yet
                    if 'skills' in job_data and not skills:
                        skills = job_data['skills']
                
            except Exception as e:
                if self.debug:
                    self.logger.warning(f"Error extracting additional data from JSON: {e}")
        
        # Record the scrape time
        scraped_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Now populate the job item in the desired order
        # 1. ID first
        job_item["id"] = job_id
        # 2. Company name second
        job_item["companyName"] = company_name
        # 3. Job title third
        job_item["title"] = job_title
        # 4. Posted time fourth
        job_item["postedAt"] = posted_at
        # 5. Location fifth
        job_item["location"] = location
        # 6. Employment type
        if employment_type:
            job_item["employment_type"] = employment_type
        # 7. Seniority level
        if seniority_level:
            job_item["seniority_level"] = seniority_level
        # 8. Easy apply flag
        job_item["easyApply"] = easy_apply
        # 9. Job link
        job_item["link"] = job_link
        # 10. Company LinkedIn URL
        if company_linkedin_url:
            job_item["companyLinkedinUrl"] = company_linkedin_url
        # 11. Skills
        if skills:
            job_item["skills"] = skills
        # 12. Description text
        job_item["descriptionText"] = job_description_text
        # 13. Scraping timestamp
        job_item["scraped_at"] = scraped_at
        
        # Add any workplace types
        if workplace_types:
            job_item["jobWorkplaceTypes"] = workplace_types
        
        # Add insights if available
        if insights:
            job_item["insights"] = insights
        
        # Add company logo if available
        if company_logo:
            job_item["companyLogo"] = company_logo
        
        # Add application URL if available
        if apply_url:
            job_item["applyUrl"] = apply_url
        
        # Add company description if available
        if company_description:
            job_item["companyDescription"] = company_description
        
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