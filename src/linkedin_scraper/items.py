"""
LinkedIn Job Scraper - Item definitions
"""
import scrapy

class LinkedinJobItem(scrapy.Item):
    """Item for LinkedIn job details"""
    # Basic job info
    id = scrapy.Field()
    title = scrapy.Field()
    companyName = scrapy.Field()
    location = scrapy.Field()
    link = scrapy.Field()
    
    # Job details
    descriptionText = scrapy.Field()
    employment_type = scrapy.Field()
    seniority_level = scrapy.Field()
    postedAt = scrapy.Field()
    scraped_at = scrapy.Field()
    
    # Company info
    companyLinkedinUrl = scrapy.Field()
    companyLogo = scrapy.Field()
    
    # Additional fields
    industries = scrapy.Field()
    functions = scrapy.Field()
    applicants = scrapy.Field()
    skills = scrapy.Field()
    
    # Metadata
    source = scrapy.Field(serializer=str)
    sourceId = scrapy.Field(serializer=str)

class LinkedinJobUrlItem(scrapy.Item):
    """Item for LinkedIn job URLs (used in URL collection mode)"""
    url = scrapy.Field()
    id = scrapy.Field()