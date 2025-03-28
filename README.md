# LinkedIn Job Scraper

This Apify actor scrapes job listings from LinkedIn based on keywords and location. It supports authentication for accessing detailed job information.

## Features

- Search for jobs by keyword and location
- Authenticate with LinkedIn credentials for better results
- Extract detailed job information including:
  - Job title
  - Company name
  - Location
  - Job description
  - Employment type
  - Seniority level
  - Date posted
- Limit the number of pages to scrape
- Option to provide specific LinkedIn job URLs to scrape

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `keyword` | String | Yes | - | Job search keyword (e.g., "python developer") |
| `location` | String | Yes | - | Job location (e.g., "San Francisco, CA") |
| `linkedin_username` | String | No | - | LinkedIn username/email for authentication |
| `linkedin_password` | String | No | - | LinkedIn password for authentication |
| `max_pages` | Integer | No | 5 | Maximum number of search result pages to scrape |
| `start_urls` | Array | No | [] | Specific LinkedIn job URLs to scrape directly |

## Output

The actor outputs a dataset with the following structure for each job listing:

```json
{
  "job_id": "3123456789",
  "job_title": "Senior Python Developer",
  "company_name": "Example Company",
  "location": "San Francisco, CA",
  "job_url": "https://www.linkedin.com/jobs/view/senior-python-developer-at-example-company-3123456789",
  "job_description": "<div>Full job description HTML...</div>",
  "date_posted": "2025-03-25",
  "employment_type": "Full-time",
  "seniority_level": "Mid-Senior level",
  "scraped_at": "2025-03-27T15:30:45.123Z"
}
```

## Usage

1. Create a new task for the LinkedIn Job Scraper actor in Apify
2. Set the required input parameters (`keyword` and `location`)
3. Optionally provide LinkedIn credentials for better results
4. Run the actor and wait for the results

## Limitations

- LinkedIn may block excessive requests, so use reasonable rate limits
- Some job details may not be accessible without authentication
- The structure of LinkedIn pages may change, which could affect the scraper

## License

This project is licensed under the Apache License 2.0.