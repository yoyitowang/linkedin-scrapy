# LinkedIn Job Scraper (v2.0.0)

This Apify actor scrapes job listings from LinkedIn based on keywords and location. It supports authentication for accessing detailed job information and now features an enhanced data model with comprehensive job details.

## Features

- Search for jobs by keyword and location
- Authenticate with LinkedIn credentials for better results
- Scrape specific LinkedIn job URLs directly
- Extract comprehensive job information including:
  - Job title, company name, and location
  - Complete job description
  - Employment type and seniority level
  - Salary information (when available)
  - Application links and posting dates
  - Company details and logo
  - Recruiter information
  - Applicant insights
  - Workplace types (remote, hybrid, on-site)
  - Required skills
- Limit the number of pages or jobs to scrape
- Backward compatibility with v1.0.0 data structure

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `keyword` | String | Yes* | - | Job search keyword (e.g., "python developer") |
| `location` | String | Yes* | - | Job location (e.g., "San Francisco, CA") |
| `linkedin_username` | String | No | - | LinkedIn username/email for authentication |
| `linkedin_password` | String | No | - | LinkedIn password for authentication |
| `max_pages` | Integer | No | 5 | Maximum number of search result pages to scrape |
| `max_jobs` | Integer | No | 0 | Maximum number of jobs to scrape (0 = no limit) |
| `start_urls` | Array | No | [] | Specific LinkedIn job URLs to scrape directly |
| `debug` | Boolean | No | false | Enable debug mode for detailed logging |

\* Either `keyword`+`location` or `start_urls` must be provided

## Output

The actor outputs a dataset with the following enhanced structure for each job listing:

```json
{
  "id": "3956051081",
  "title": "Marketing Manager",
  "companyName": "Intuit",
  "companyLinkedinUrl": "https://www.linkedin.com/company/intuit/life",
  "location": {
    "abbreviatedLocalizedName": "San Diego, CA",
    "entityUrn": "urn:li:fsd_geo:101784816",
    "defaultLocalizedName": "San Diego, California, United States",
    "countryISOCode": "US"
  },
  "isReposted": true,
  "posterId": "29404392",
  "insights": ["4 connections work here"],
  "companyLogo": "https://media.licdn.com/dms/image/C560BAQFTpF8uneqScw/company-logo_200_200/0/1661446146222/intuit_logo?e=1729123200&v=beta&t=kB5lu-AelQ6j7eYK_HeJwM5Tves-4ncVEi3KMvOlvdo",
  "easyApply": false,
  "isPromoted": false,
  "link": "https://www.linkedin.com/jobs/view/3956051081",
  "applyUrl": "https://dsp.prng.co/hqS7Qwb",
  "insightsV2": [
    "10,001+ employees · Software Development",
    "4 connections work here"
  ],
  "descriptionText": "Overview\n\nIntuit's Consumer Group (CG), a team serving the needs of over 20+ million US consumers...",
  "postedAt": "2024-06-21T15:40:12",
  "companyDescription": "Intuit is a global technology platform that helps our customers and communities...",
  "companyAddress": {
    "type": "PostalAddress",
    "streetAddress": "2700 Coast Ave",
    "addressLocality": "Mountain View",
    "addressRegion": "California",
    "postalCode": "94043",
    "addressCountry": "US"
  },
  "companyWebsite": "https://www.intuit.com/",
  "companySlogan": "The global financial technology platform that powers prosperity...",
  "companyEmployeesCount": 16051,
  "jobApplicantInsights": {
    "applicantCount": 74,
    "degreeDetails": [...],
    "skillDetails": [],
    "seniorityDetails": [...]
  },
  "jobWorkplaceTypes": [
    {
      "localizedName": "On-site",
      "localizedDescription": "Employees come to work in-person.",
      "entityUrn": "urn:li:fsd_workplaceType:1",
      "workplaceTypeEnum": "ON_SITE"
    }
  ],
  "jobState": "LISTED",
  "contentSource": "JOBS_PREMIUM_OFFLINE",
  "recruiter": {
    "profileUrl": "https://www.linkedin.com/in/epoytress",
    "name": "Emily Poytress",
    "connectionType": "2nd",
    "headline": "Group Manager, Digital Media and X-Channel Strategy",
    "isPremium": true,
    "profilePictureUrl": "https://media.licdn.com/dms/image/..."
  },
  "company": {
    "industry": ["Software Development"],
    "employeeCountRange": {
      "start": 10001,
      "end": null
    },
    "followingState": {...},
    "name": "Intuit",
    "description": "Intuit is a global technology platform...",
    "universalName": "intuit",
    "employeeCount": 16050
  },
  "salary": {
    "compensationSource": "JOB_POSTER_PROVIDED",
    "entityUrn": "urn:li:fsd_salaryInsights:3956051081",
    "location": "San Diego, CA"
  },
  "skills": [
    "Campaign Effectiveness",
    "Campaigns",
    "Channel Strategy",
    "Client Relations",
    "Competitive Analysis",
    "Customer Acquisition",
    "Emerging Trends",
    "Marketing Strategy",
    "Mobile Applications",
    "Storytelling"
  ],
  
  // Backward compatibility fields
  "job_id": "3956051081",
  "job_title": "Marketing Manager",
  "company_name": "Intuit",
  "location": "San Diego, CA",
  "job_url": "https://www.linkedin.com/jobs/view/3956051081",
  "job_description": "<div>Overview\n\nIntuit's Consumer Group (CG), a team serving the needs...</div>",
  "date_posted": "2024-06-21T15:40:12",
  "employment_type": "Full-time",
  "seniority_level": "Mid-Senior level",
  "scraped_at": "2025-03-27T15:30:45"
}
```

## Usage

1. Create a new task for the LinkedIn Job Scraper actor in Apify
2. Set the required input parameters (`keyword` and `location` or `start_urls`)
3. Optionally provide LinkedIn credentials for better results
4. Run the actor and wait for the results

## Data Availability

Not all fields will be available for every job listing. The availability depends on:
- Whether the job poster provided the information
- Whether you're authenticated with LinkedIn
- The type and age of the job listing

## Limitations

- LinkedIn may block excessive requests, so use reasonable rate limits
- Some job details may not be accessible without authentication
- The structure of LinkedIn pages may change, which could affect the scraper

## Version History

- **v2.0.0** - Enhanced data model with comprehensive job details
- **v1.0.0** - Initial release with basic job information extraction

## License

This project is licensed under the Apache License 2.0.