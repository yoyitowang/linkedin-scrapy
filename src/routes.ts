import { Dataset, createPlaywrightRouter } from 'crawlee';

export const router = createPlaywrightRouter();

router.addDefaultHandler(async ({ enqueueLinks, log, request, crawler }) => {
    log.info(`Processing start URL: ${request.url}`);
    
    // Navigate directly to LinkedIn Jobs search page
    await enqueueLinks({
        urls: ['https://www.linkedin.com/jobs/search/'],
        label: 'search',
    });
});

router.addHandler('search', async ({ request, page, log, crawler }) => {
    log.info(`Searching for jobs on LinkedIn`, { url: request.loadedUrl });
    
    // Get the search keyword from input or use a default
    const input = await crawler.getContext().input;
    const keyword = input?.keyword || 'software engineer';
    const location = input?.location || 'United States';
    
    // Check if we need to handle login - LinkedIn sometimes shows login page
    const isLoginPage = await page.evaluate(() => {
        return window.location.href.includes('checkpoint') || 
               window.location.href.includes('login') ||
               document.querySelector('.login-form') !== null;
    });
    
    if (isLoginPage) {
        log.info('Login page detected. Skipping login and trying to access jobs directly.');
        await page.goto(`https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}`, { timeout: 60000 });
    }
    
    // Wait for the page to load
    await page.waitForLoadState('networkidle');
    
    // Check if we're on the search page
    const isSearchPage = await page.evaluate(() => {
        return document.querySelector('.jobs-search__results-list') !== null;
    });
    
    if (!isSearchPage) {
        log.info('Not on search results page. Attempting to search directly.');
        
        // Wait for the search input field to be available
        await page.waitForSelector('input[role="combobox"]', { timeout: 60000 }).catch(() => {
            log.warning('Search input not found');
        });
        
        // Type the job title
        await page.fill('input[role="combobox"]', keyword).catch(() => {
            log.warning('Could not fill job title input');
        });
        
        // Type the location
        const locationInputs = await page.$$('input[aria-controls]');
        if (locationInputs.length >= 2) {
            await locationInputs[1].fill(location).catch(() => {
                log.warning('Could not fill location input');
            });
        }
        
        // Click the search button
        await page.click('button[type="submit"]').catch(() => {
            log.warning('Could not click search button');
        });
        
        // Wait for search results to load
        await page.waitForSelector('.jobs-search__results-list', { timeout: 60000 }).catch(() => {
            log.warning('Search results not found');
        });
    }
    
    // Wait a bit to ensure all jobs are loaded
    await page.waitForTimeout(3000);
    
    // Extract job listings
    const jobs = await page.evaluate(() => {
        const jobCards = document.querySelectorAll('.jobs-search__results-list li');
        return Array.from(jobCards).map(card => {
            // Get job title
            const titleElement = card.querySelector('.base-search-card__title');
            const title = titleElement ? titleElement.textContent.trim() : '';
            
            // Get company name
            const companyElement = card.querySelector('.base-search-card__subtitle');
            const company = companyElement ? companyElement.textContent.trim() : '';
            
            // Get location
            const locationElement = card.querySelector('.job-search-card__location');
            const location = locationElement ? locationElement.textContent.trim() : '';
            
            // Get job link
            const linkElement = card.querySelector('a.base-card__full-link');
            const link = linkElement ? linkElement.href : '';
            
            // Get posted date
            const dateElement = card.querySelector('.job-search-card__listdate');
            const postedDate = dateElement ? dateElement.textContent.trim() : '';
            
            return {
                title,
                company,
                location,
                link,
                postedDate
            };
        });
    });
    
    log.info(`Found ${jobs.length} jobs for "${keyword}" in "${location}"`);
    
    // Save the job listings to the dataset
    await Dataset.pushData({
        searchQuery: {
            keyword,
            location
        },
        jobCount: jobs.length,
        jobs: jobs,
        pageUrl: request.loadedUrl
    });
    
    // Enqueue individual job links for detailed scraping if needed
    for (const job of jobs) {
        if (job.link) {
            await crawler.addRequests([{
                url: job.link,
                label: 'detail',
                userData: {
                    title: job.title,
                    company: job.company
                }
            }]);
        }
    }
    
    // Check if there's a next page and enqueue it
    const hasNextPage = await page.evaluate(() => {
        const nextButton = document.querySelector('button[aria-label="Next"]');
        return nextButton !== null && !nextButton.hasAttribute('disabled');
    });
    
    if (hasNextPage) {
        log.info('Found next page, enqueueing it');
        await page.click('button[aria-label="Next"]').catch(() => {
            log.warning('Could not click next page button');
        });
        
        // Wait for the page to load
        await page.waitForTimeout(3000);
        
        // Get the URL of the next page
        const nextPageUrl = page.url();
        
        // Enqueue the next page
        await crawler.addRequests([{
            url: nextPageUrl,
            label: 'search'
        }]);
    }
});

router.addHandler('detail', async ({ request, page, log }) => {
    const { title, company } = request.userData;
    log.info(`Processing job detail: ${title} at ${company}`, { url: request.loadedUrl });
    
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Extract job details
    const jobDetail = await page.evaluate(() => {
        // Function to safely get text content
        const getText = (selector) => {
            const element = document.querySelector(selector);
            return element ? element.textContent.trim() : null;
        };
        
        // Get job description
        let description = getText('.description__text');
        if (!description) {
            description = getText('.show-more-less-html__markup');
        }
        
        // Get job criteria items
        const criteriaItems = document.querySelectorAll('.description__job-criteria-item');
        const criteria = {};
        
        criteriaItems.forEach(item => {
            const label = item.querySelector('.description__job-criteria-subheader')?.textContent.trim();
            const value = item.querySelector('.description__job-criteria-text')?.textContent.trim();
            
            if (label && value) {
                criteria[label] = value;
            }
        });
        
        // Get company details
        const companyName = getText('.topcard__org-name-link') || 
                           getText('.topcard__org-name');
        
        return {
            description,
            criteria,
            companyName,
            jobTitle: getText('.top-card-layout__title'),
            location: getText('.topcard__flavor--bullet'),
            postedDate: getText('.posted-time-ago__text'),
            applicants: getText('.num-applicants__caption'),
            employmentType: criteria['Employment type'] || null,
            seniorityLevel: criteria['Seniority level'] || null,
            jobFunction: criteria['Job function'] || null,
            industries: criteria['Industries'] || null
        };
    });
    
    // Combine with metadata from the request
    const fullJobDetail = {
        url: request.loadedUrl,
        title: title || jobDetail.jobTitle,
        company: company || jobDetail.companyName,
        ...jobDetail
    };
    
    // Save the detailed job information
    await Dataset.pushData(fullJobDetail);
});

export default router;