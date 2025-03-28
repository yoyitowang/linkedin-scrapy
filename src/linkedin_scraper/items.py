import scrapy


class LinkedinJobItem(scrapy.Item):
    """
    Enhanced item class for LinkedIn job listings (v2.0.0)
    Supports comprehensive data extraction including company details,
    applicant insights, recruiter information, and more.
    """
    # Core job information (original fields with some renamed for consistency)
    id = scrapy.Field()  # LinkedIn job ID
    title = scrapy.Field()  # Job title
    companyName = scrapy.Field()  # Company name
    location = scrapy.Field()  # Job location (now structured)
    link = scrapy.Field()  # Job URL
    descriptionText = scrapy.Field()  # Job description text
    postedAt = scrapy.Field()  # Posted date ISO format
    postedAtTimestamp = scrapy.Field()  # Posted date timestamp
    
    # Enhanced job details
    isReposted = scrapy.Field()  # Whether the job is reposted
    posterId = scrapy.Field()  # ID of the job poster
    insights = scrapy.Field()  # Network insights (e.g., "4 connections work here")
    insightsV2 = scrapy.Field()  # Enhanced network insights
    easyApply = scrapy.Field()  # Whether the job supports Easy Apply
    isPromoted = scrapy.Field()  # Whether the job is promoted
    applyUrl = scrapy.Field()  # Direct application URL
    jobState = scrapy.Field()  # Job state (e.g., LISTED)
    contentSource = scrapy.Field()  # Source of the job posting
    
    # Company information
    companyLinkedinUrl = scrapy.Field()  # Company LinkedIn URL
    companyLogo = scrapy.Field()  # Company logo URL
    companyDescription = scrapy.Field()  # Company description
    companyAddress = scrapy.Field()  # Structured company address
    companyWebsite = scrapy.Field()  # Company website
    companySlogan = scrapy.Field()  # Company slogan/tagline
    companyEmployeesCount = scrapy.Field()  # Company employee count
    
    # Detailed company information (structured)
    company = scrapy.Field()  # Comprehensive company data
    
    # Job workplace types
    jobWorkplaceTypes = scrapy.Field()  # Workplace types (e.g., remote, on-site)
    
    # Recruiter information
    recruiter = scrapy.Field()  # Information about the job poster/recruiter
    
    # Applicant insights
    jobApplicantInsights = scrapy.Field()  # Insights about job applicants
    
    # Salary information
    salary = scrapy.Field()  # Salary details
    
    # Skills required
    skills = scrapy.Field()  # Required skills for the job
    
    # Metadata
    scraped_at = scrapy.Field()  # When the job was scraped
    
    # Backward compatibility fields (will be populated from new fields)
    job_id = scrapy.Field()
    job_title = scrapy.Field()
    company_name = scrapy.Field()
    job_url = scrapy.Field()
    job_description = scrapy.Field()
    date_posted = scrapy.Field()
    employment_type = scrapy.Field()
    seniority_level = scrapy.Field()