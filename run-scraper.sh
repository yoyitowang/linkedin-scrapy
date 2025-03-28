#!/bin/bash

# LinkedIn Job Scraper Docker Build and Run Script
# This script builds the Docker image and runs the container with the appropriate volumes and environment variables

echo "Building LinkedIn Job Scraper Docker image..."
docker build -t linkedin-jobs-scraper -f .actor/Dockerfile .

if [ $? -eq 0 ]; then
    echo "Docker image built successfully!"
    
    echo "Running LinkedIn Job Scraper container..."
    docker run -it --rm \
    -v $(pwd)/input.json:/usr/src/app/input.json \
    -v $(pwd)/apify_storage:/usr/src/app/apify_storage \
    -e APIFY_LOCAL_STORAGE_DIR=/usr/src/app/apify_storage \
    -e APIFY_DEFAULT_KEY_VALUE_STORE_ID=default \
    -e APIFY_DEFAULT_DATASET_ID=default \
    linkedin-jobs-scraper
    
    echo "Scraper execution completed."
else
    echo "Error: Docker build failed."
    exit 1
fi