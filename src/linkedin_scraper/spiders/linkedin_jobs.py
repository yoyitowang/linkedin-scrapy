import scrapy
import json
import re
import time
from datetime import datetime
from urllib.parse import urlencode
from scrapy.exceptions import CloseSpider
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
        
        # Configure logging based on debug flag
        if not self.debug:
            # Disable certain types of logging when debug is off
            self.logger.setLevel('INFO')
        else:
            # Log debug status
            self.logger.info("Debug mode is enabled - detailed output will be shown")
            
        # Log job limit if set
        if self.max_jobs > 0:
            self.logger.info(f"Job limit set: Will scrape a maximum of {self.max_jobs} jobs")
    
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
    
    def format_datetime(self, date_value):
        """Format date to ISO format (YYYY-MM-DDTHH:MM:SS)"""
        if not date_value:
            return None
            
        try:
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
            self.logger.warning(f"Error formatting date {date_value}: {e}")
            return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    
    def parse_job_details(self, response):
        """Parse the job details page with enhanced data extraction"""
        # Check if we've reached the job limit
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). Skipping job.")
            return
            
        # Increment job counter
        self.job_count += 1
        
        # Create job item
        job_item = LinkedinJobItem()
        
        # Try to extract structured data from the page
        json_data = self.extract_json_data(response)
        
        # Extract data from meta or directly from the page if not available
        job_item["title"] = response.meta.get("job_title") or response.css("h1.top-card-layout__title::text").get().strip()
        job_item["companyName"] = response.meta.get("company_name") or response.css("a.topcard__org-name-link::text").get().strip()
        job_item["location"] = response.meta.get("location") or response.css("span.topcard__flavor--bullet::text").get().strip()
        job_item["link"] = response.url
        
        # Extract job ID from URL or meta
        job_id = response.meta.get("job_id")
        if not job_id:
            match = re.search(r'view/(\d+)', response.url)
            if match:
                job_id = match.group(1)
        
        job_item["id"] = job_id
        
        # Extract posted date and format consistently
        posted_date = response.meta.get("date_posted") or response.css("span.posted-time-ago__text::text").get()
        if posted_date:
            job_item["postedAt"] = self.format_datetime(posted_date)
        else:
            job_item["postedAt"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Extract job description
        job_description = response.css("div.description__text").get()
        if job_description:
            job_item["descriptionText"] = self.clean_html(job_description)
        
        # Extract company logo
        company_logo = response.meta.get("company_logo") or response.css("img.artdeco-entity-image::attr(src)").get()
        if company_logo:
            job_item["companyLogo"] = company_logo
        
        # Extract company LinkedIn URL
        company_url = response.css("a.topcard__org-name-link::attr(href)").get()
        if company_url:
            job_item["companyLinkedinUrl"] = response.urljoin(company_url)
        
        # Extract application URL
        apply_url = response.css("a.apply-button::attr(href)").get()
        if apply_url:
            job_item["applyUrl"] = apply_url
        
        # Check if this is an Easy Apply job
        easy_apply_button = response.css("button.jobs-apply-button").get()
        job_item["easyApply"] = bool(easy_apply_button)
        
        # Extract company description
        company_description = response.css("div.company-description__text::text").get()
        if company_description:
            job_item["companyDescription"] = company_description.strip()
        
        # Extract workplace type
        workplace_types = []
        workplace_type_elements = response.css("li.job-details-jobs-unified-top-card__workplace-type")
        for element in workplace_type_elements:
            workplace_type = element.css("::text").get()
            if workplace_type:
                workplace_types.append({"localizedName": workplace_type.strip()})
        
        if workplace_types:
            job_item["jobWorkplaceTypes"] = workplace_types
        
        # Extract job criteria (employment type, seniority level, etc.)
        job_criteria = response.css("li.description__job-criteria-item")
        for criteria in job_criteria:
            criteria_type = criteria.css("h3.description__job-criteria-subheader::text").get().strip()
            criteria_value = criteria.css("span.description__job-criteria-text::text").get().strip()
            
            if "Seniority" in criteria_type:
                job_item["seniority_level"] = criteria_value
            elif "Employment" in criteria_type:
                job_item["employment_type"] = criteria_value
        
        # Extract insights about connections
        insights = response.css("span.jobs-unified-top-card__subtitle-secondary-grouping span.jobs-unified-top-card__bullet::text").getall()
        if insights:
            cleaned_insights = [insight.strip() for insight in insights if "connection" in insight.lower()]
            if cleaned_insights:
                job_item["insights"] = cleaned_insights
        
        # Extract skills from the job description
        skills = []
        skills_section = response.css("div.description__text ul li::text").getall()
        for skill in skills_section:
            if len(skill.strip()) > 0 and len(skill.strip()) < 50:  # Simple heuristic for skill-like text
                skills.append(skill.strip())
        
        if skills:
            job_item["skills"] = skills[:10]  # Limit to top 10 skills
        
        # Populate backward compatibility fields
        job_item["job_id"] = job_id
        job_item["job_title"] = job_item["title"]
        job_item["company_name"] = job_item["companyName"]
        job_item["job_url"] = job_item["link"]
        job_item["job_description"] = job_item.get("descriptionText")
        job_item["date_posted"] = job_item.get("postedAt")
        
        # Add timestamp in consistent format
        job_item["scraped_at"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Extract additional data from JSON if available
        if json_data:
            self.extract_additional_data_from_json(job_item, json_data)
        
        # In non-debug mode, only log minimal information
        if not self.debug:
            self.logger.info(f"Scraped job {self.job_count}: {job_item['title']} at {job_item['companyName']}")
        else:
            # In debug mode, log detailed information
            self.logger.debug(f"Scraped job {self.job_count} details: {job_item['title']} at {job_item['companyName']}")
            self.logger.debug(f"Full job data: {json.dumps({k: v for k, v in dict(job_item).items() if k != 'descriptionText'}, ensure_ascii=False)}")
            self.logger.debug(f"Job description length: {len(job_item.get('descriptionText', ''))}")
        
        # Check if we've reached the job limit after processing this job
        if self.max_jobs > 0 and self.job_count >= self.max_jobs:
            self.logger.info(f"✅ Reached the maximum job count limit ({self.max_jobs}). This is the final job.")
        
        yield job_item
        
        # Check job limit after yielding the item
        self.check_job_limit()
    
    def extract_additional_data_from_json(self, job_item, json_data):
        """Extract additional data from JSON structure"""
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
            
            if not job_data:
                return
            
            # Extract job data fields
            fields_to_extract = [
                'isReposted', 'posterId', 'easyApply', 'isPromoted', 
                'jobState', 'contentSource', 'companyWebsite', 'companySlogan',
                'companyEmployeesCount'
            ]
            
            for field in fields_to_extract:
                if field in job_data:
                    job_item[field] = job_data[field]
            
            # Extract applicant insights
            if 'jobApplicantInsights' in job_data:
                job_item['jobApplicantInsights'] = job_data['jobApplicantInsights']
            
            # Extract company data
            if 'company' in job_data:
                job_item['company'] = job_data['company']
            
            # Extract salary data
            if 'salary' in job_data:
                job_item['salary'] = job_data['salary']
            
            # Extract recruiter data
            if 'recruiter' in job_data:
                job_item['recruiter'] = job_data['recruiter']
            
            # Extract skills
            if 'skills' in job_data and not job_item.get('skills'):
                job_item['skills'] = job_data['skills']
            
            # If we have a timestamp in the JSON data, format it consistently
            if 'listedAt' in job_data:
                job_item['postedAt'] = self.format_datetime(job_data['listedAt'])
            
        except Exception as e:
            self.logger.warning(f"Error extracting additional data from JSON: {e}")