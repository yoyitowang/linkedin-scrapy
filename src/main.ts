/**
 * LinkedIn Job Scraper using Playwright and Crawlee
 */

import { Actor } from 'apify';
import { PlaywrightCrawler, log } from 'crawlee';
import { router } from './routes.js';
import { firefox } from 'playwright';
import { launchOptions as camoufoxLaunchOptions } from 'camoufox-js';

interface Input {
    keyword: string;
    location: string;
    maxRequestsPerCrawl: number;
    startUrls: string[];
}

// Initialize the Apify SDK
await Actor.init();

// Structure of input is defined in input_schema.json
const {
    keyword = 'software engineer',
    location = 'United States',
    startUrls = ['https://www.linkedin.com/jobs/search/'],
    maxRequestsPerCrawl = 50,
} = await Actor.getInput<Input>() ?? {} as Input;

// Set up logging
log.info('Starting LinkedIn job scraper', { keyword, location });

const proxyConfiguration = await Actor.createProxyConfiguration({
    groups: ['RESIDENTIAL'],  // Using residential proxies for better success with LinkedIn
});

if (!proxyConfiguration) {
    log.warning('No proxy configuration provided, LinkedIn might block the requests');
}

// Prepare the crawler
const crawler = new PlaywrightCrawler({
    proxyConfiguration,
    maxRequestsPerCrawl,
    requestHandler: router,
    // Using Firefox with Camoufox for better anti-detection
    launchContext: {
        launcher: firefox,
        launchOptions: await camoufoxLaunchOptions({
            headless: true,
            // Using a common user agent to avoid detection
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            // Additional Camoufox options for better stealth
            fonts: ['Arial', 'Times New Roman', 'Courier New'],
            viewport: { width: 1920, height: 1080 },
        }),
    },
    // Store crawler context with input parameters
    context: {
        input: {
            keyword,
            location
        }
    },
    // Slow down to avoid detection
    navigationTimeoutSecs: 120,
    requestHandlerTimeoutSecs: 180,
    // Add delays between requests to avoid being detected as a bot
    maxRequestRetries: 3,
    preNavigationHooks: [
        async ({ page, request }) => {
            // Random delay between 1-5 seconds before each request
            const delay = Math.floor(Math.random() * 4000) + 1000;
            await new Promise(resolve => setTimeout(resolve, delay));
            
            // Set cookies to appear more like a regular user
            await page.context().addCookies([
                {
                    name: 'li_at',
                    value: '',  // LinkedIn auth token would go here if you had one
                    domain: '.linkedin.com',
                    path: '/',
                },
                {
                    name: 'JSESSIONID',
                    value: `"ajax:${Math.random().toString(36).substring(2, 15)}"`,
                    domain: '.linkedin.com',
                    path: '/',
                },
            ]);
            
            // Add random mouse movements to appear more human-like
            if (Math.random() > 0.7) {
                await page.mouse.move(
                    100 + Math.floor(Math.random() * 500),
                    100 + Math.floor(Math.random() * 500)
                );
            }
        }
    ],
});

// Construct the initial URL with search parameters
const searchUrl = new URL('https://www.linkedin.com/jobs/search/');
searchUrl.searchParams.append('keywords', keyword);
searchUrl.searchParams.append('location', location);
searchUrl.searchParams.append('f_TPR', 'r86400'); // Last 24 hours

log.info(`Starting LinkedIn job scraper for "${keyword}" in "${location}"`);
log.info(`Initial search URL: ${searchUrl.toString()}`);

// Run the crawler
await crawler.run([searchUrl.toString()]);

// Log the results
const dataset = await Dataset.open();
const { itemCount } = await dataset.getInfo();
log.info(`Scraping finished. Extracted ${itemCount} job listings.`);

// Exit successfully
await Actor.exit();