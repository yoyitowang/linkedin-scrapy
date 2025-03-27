import scrapy


class LinkedinJobItem(scrapy.Item):
    """
    Item class for LinkedIn job listings
    """
    job_id = scrapy.Field()
    job_title = scrapy.Field()
    company_name = scrapy.Field()
    location = scrapy.Field()
    job_url = scrapy.Field()
    job_description = scrapy.Field()
    date_posted = scrapy.Field()
    employment_type = scrapy.Field()
    seniority_level = scrapy.Field()
    scraped_at = scrapy.Field()