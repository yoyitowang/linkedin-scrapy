# LinkedIn Job Scraper

A powerful scraper for LinkedIn job listings with multiple search modes.

## Features

- **Multiple Search Modes**:
  - Search by keyword and location
  - Search by company name
  - Scrape specific job URLs directly

- **Comprehensive Data**: Extracts detailed job information including titles, descriptions, company details, and more

- **Authentication Support**: Optional LinkedIn session cookies for accessing more job details

- **Configurable Limits**: Control the number of pages and jobs to scrape

## Usage Options

### 1. Search by Keyword and Location

Search for jobs using a keyword and location:

```bash
python src/run_linkedin_scraper.py --search_mode keyword_location --keyword "python developer" --location "San Francisco" --max_pages 3 --max_jobs 50
```

### 2. Search by Company

Search for jobs at a specific company:

```bash
python src/run_linkedin_scraper.py --search_mode company --company "Microsoft" --max_pages 3 --max_jobs 50
```

### 3. Scrape Specific Job URLs

Scrape specific LinkedIn job listings:

```bash
python src/run_linkedin_scraper.py --search_mode specific_urls --urls "https://www.linkedin.com/jobs/view/12345" "https://www.linkedin.com/jobs/view/67890"
```

### Common Options

- `--max_pages`: Maximum number of search result pages to scrape (default: 1)
- `--max_jobs`: Maximum number of job listings to scrape (default: 10, 0 for unlimited)
- `--linkedin_session_id`: LinkedIn session ID cookie for authenticated access
- `--linkedin_jsessionid`: LinkedIn JSESSIONID cookie for authenticated access
- `--debug`: Enable debug mode for detailed output

## Using with Apify

This scraper can be run as an Apify Actor. Configure the input parameters in the Apify console:

1. Select a search mode (keyword_location, company, or specific_urls)
2. Provide the required parameters for your selected search mode
3. Set limits and authentication options as needed

## Output

The scraper produces JSON output with detailed job information:

```json
[
  {
    "id": "12345",
    "title": "Python Developer",
    "companyName": "Example Corp",
    "location": "San Francisco, CA",
    "link": "https://www.linkedin.com/jobs/view/12345",
    "descriptionText": "We are looking for a Python developer...",
    "employment_type": "Full-time",
    "seniority_level": "Mid-Senior level",
    "postedAt": "2023-04-15T10:30:00",
    "scraped_at": "2023-04-16T14:25:30",
    "companyLinkedinUrl": "https://www.linkedin.com/company/example-corp/"
  },
  ...
]
```

## Authentication

For best results, provide LinkedIn session cookies:

1. Log in to LinkedIn in your browser
2. Open browser developer tools (F12)
3. Go to Application/Storage > Cookies > www.linkedin.com
4. Find the `li_at` cookie (this is your session ID)
5. Optionally, find the `JSESSIONID` cookie
6. Provide these values using the `--linkedin_session_id` and `--linkedin_jsessionid` options