import scrapy
import json
import time
from datetime import datetime
from urllib.parse import urlencode
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
    }
    
    def __init__(self, keyword=None, location=None, username=None, password=None, max_pages=5, start_urls=None, debug=False, *args, **kwargs):
        super(LinkedinJobsSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword
        self.location = location
        self.linkedin_username = username
        self.linkedin_password = password
        self.max_pages = int(max_pages)
        self.page_count = 0
        self.start_urls_list = start_urls or []
        self.debug = debug
        
        # Log debug status
        if self.debug:
            self.logger.info("Debug mode is enabled - detailed output will be shown")
    
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
    
    def parse_search_results(self, response):
        """Parse the job search results page"""
        self.page_count += 1
        self.logger.info(f"Parsing search results page {self.page_count} from: {response.url}")
        
        # Extract job listings
        job_cards = response.css("div.base-card")
        
        for job_card in job_cards:
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
                
                if self.debug:
                    self.logger.info(f"Found job: {job_title} at {company_name} in {location}")
                
                yield scrapy.Request(
                    url=job_link,
                    callback=self.parse_job_details,
                    meta={
                        "job_title": job_title,
                        "company_name": company_name,
                        "location": location,
                        "date_posted": date_posted
                    }
                )
        
        # Follow pagination if we haven't reached max_pages
        if self.page_count < self.max_pages:
            next_page = response.css("a.artdeco-pagination__button--next::attr(href)").get()
            if next_page:
                yield response.follow(next_page, callback=self.parse_search_results)
    
    def parse_job_details(self, response):
        """Parse the job details page"""
        # Create job item
        job_item = LinkedinJobItem()
        
        # Extract data from meta or directly from the page if not available
        job_item["job_title"] = response.meta.get("job_title") or response.css("h1.top-card-layout__title::text").get().strip()
        job_item["company_name"] = response.meta.get("company_name") or response.css("a.topcard__org-name-link::text").get().strip()
        job_item["location"] = response.meta.get("location") or response.css("span.topcard__flavor--bullet::text").get().strip()
        job_item["job_url"] = response.url
        job_item["date_posted"] = response.meta.get("date_posted")
        
        # Extract job ID from URL
        job_id = response.url.split("?")[0].split("-")[-1]
        job_item["job_id"] = job_id
        
        # Extract job description
        job_description = response.css("div.description__text").get()
        if job_description:
            job_item["job_description"] = job_description
        
        # Extract additional details if available
        job_criteria = response.css("li.description__job-criteria-item")
        for criteria in job_criteria:
            criteria_type = criteria.css("h3.description__job-criteria-subheader::text").get().strip()
            criteria_value = criteria.css("span.description__job-criteria-text::text").get().strip()
            
            if "Seniority" in criteria_type:
                job_item["seniority_level"] = criteria_value
            elif "Employment" in criteria_type:
                job_item["employment_type"] = criteria_value
        
        # Add timestamp
        job_item["scraped_at"] = datetime.now().isoformat()
        
        # Log detailed job information in debug mode
        if self.debug:
            self.logger.info(f"Scraped job details: {job_item['job_title']} at {job_item['company_name']}")
            self.logger.debug(f"Full job data: {json.dumps(dict(job_item), ensure_ascii=False)}")
        else:
            self.logger.info(f"Scraped job: {job_item['job_title']}")
        
        yield job_item