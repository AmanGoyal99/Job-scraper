import requests
import json
import csv
from datetime import datetime
from html.parser import HTMLParser
import sys

class HTMLStripper(HTMLParser):
    """Simple HTML tag stripper"""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ' '.join(self.text)

def strip_html(html_text):
    """Remove HTML tags from text"""
    if not html_text:
        return ""
    stripper = HTMLStripper()
    stripper.feed(html_text)
    return stripper.get_text()

def fetch_microsoft_jobs(page=1, page_size=20):
    """
    Fetches job listings from Microsoft careers API
    Filters: US locations, specific professions and disciplines, Individual Contributor, Full-Time
    """
    # Updated URL with specific filters
    base_url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
    params = (
        f"?lc=United%20States"
        f"&p=Software%20Engineering"
        f"&p=Research%2C%20Applied%2C%20%26%20Data%20Sciences"
        f"&p=Program%20Management"
        f"&p=Product%20Management"
        f"&d=Technical%20Program%20Management"
        f"&d=Software%20Engineering"
        f"&d=Research%20Sciences"
        f"&d=Product%20Management"
        f"&d=Applied%20Sciences"
        f"&d=Data%20Science"
        f"&rt=Individual%20Contributor"
        f"&et=Full-Time"
        f"&l=en_us"
        f"&pg={page}"
        f"&pgSz={page_size}"
        f"&o=Recent"
        f"&flt=true"
    )
    url = base_url + params

    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'authorization': 'Bearer undefined',
        'cache-control': 'no-cache',
        'origin': 'https://jobs.careers.microsoft.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://jobs.careers.microsoft.com/',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def parse_job_data(data):
    """
    Parses the job data from API response
    """
    jobs = []

    if not data:
        return jobs

    # Navigate through the JSON structure
    if 'operationResult' in data:
        result = data['operationResult'].get('result', {})
        job_listings = result.get('jobs', [])

        for job in job_listings:
            properties = job.get('properties', {})

            # Clean description by removing HTML tags
            description_html = properties.get('description', '')
            clean_description = strip_html(description_html)[:500]  # First 500 chars

            # Extract locations (handle both list and string)
            locations = properties.get('locations', [])
            if isinstance(locations, list):
                locations_str = ', '.join(locations)
            else:
                locations_str = str(locations)

            job_info = {
                'job_id': job.get('jobId', ''),
                'title': job.get('title', ''),
                'posting_date': job.get('postingDate', ''),
                'locations': locations_str,
                'primary_location': properties.get('primaryLocation', ''),
                'work_flexibility': properties.get('workSiteFlexibility', ''),
                'profession': properties.get('profession', ''),
                'discipline': properties.get('discipline', ''),
                'role_type': properties.get('roleType', ''),
                'employment_type': properties.get('employmentType', ''),
                'education_level': str(properties.get('educationLevel', '') or ''),
                'description': clean_description.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
            }
            jobs.append(job_info)

    return jobs

def save_to_csv(jobs, filename='microsoft_jobs.csv'):
    """
    Saves job data to a CSV file
    """
    if not jobs:
        print("No jobs to save")
        return

    # Define CSV headers
    headers = ['job_id', 'title', 'posting_date', 'locations', 'primary_location',
               'work_flexibility', 'profession', 'discipline', 'role_type',
               'employment_type', 'education_level', 'description']

    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"Successfully saved {len(jobs)} jobs to {filename}")

def process_json_file(filename):
    """
    Process a JSON file containing job data
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"File {filename} not found")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return None

def main():
    """
    Main function to orchestrate the scraping process
    Usage:
        python scrape.py                    # Fetch page 1 (default)
        python scrape.py 3                  # Fetch pages 1-3
        python scrape.py 2 5                # Fetch pages 2-5
        python scrape.py file.json          # Process a JSON file
    """
    print("Microsoft Job Scraper")
    print(f"Timestamp: {datetime.now()}")
    print("-" * 50)

    all_jobs = []

    # Parse command line arguments
    if len(sys.argv) == 1:
        # No arguments - fetch page 1
        start_page, end_page = 1, 1
        fetch_mode = True
    elif len(sys.argv) == 2:
        # One argument - either a file or end page
        arg = sys.argv[1]
        if arg.endswith('.json'):
            # Process JSON file
            print(f"Processing JSON file: {arg}")
            data = process_json_file(arg)
            fetch_mode = False
        else:
            # Fetch pages 1 to n
            try:
                end_page = int(arg)
                start_page = 1
                fetch_mode = True
            except ValueError:
                print(f"Invalid argument: {arg}")
                print("Usage: python scrape.py [end_page] or python scrape.py [start_page] [end_page] or python scrape.py file.json")
                return
    elif len(sys.argv) == 3:
        # Two arguments - start and end page
        try:
            start_page = int(sys.argv[1])
            end_page = int(sys.argv[2])
            fetch_mode = True
        except ValueError:
            print("Invalid page numbers")
            print("Usage: python scrape.py [start_page] [end_page]")
            return
    else:
        print("Too many arguments")
        print("Usage: python scrape.py [end_page] or python scrape.py [start_page] [end_page] or python scrape.py file.json")
        return

    if fetch_mode:
        # Fetch from API
        print(f"Fetching job listings from Microsoft API (pages {start_page}-{end_page})...")

        for page in range(start_page, end_page + 1):
            print(f"Fetching page {page}...")
            data = fetch_microsoft_jobs(page=page, page_size=20)

            if data:
                jobs = parse_job_data(data)
                all_jobs.extend(jobs)
                print(f"  Found {len(jobs)} jobs on page {page}")
            else:
                print(f"  Failed to fetch page {page}")

        jobs = all_jobs
    else:
        # Process single JSON file
        if data:
            print("Parsing job data...")
            jobs = parse_job_data(data)
        else:
            jobs = []

    if jobs:
        print(f"\nTotal jobs found: {len(jobs)}")

        # Save to CSV
        save_to_csv(jobs)

        # Display first few jobs
        print("\nFirst 5 job listings:")
        print("-" * 50)
        for i, job in enumerate(jobs[:5], 1):
            print(f"\n{i}. {job['title']}")
            print(f"   Job ID: {job['job_id']}")
            print(f"   Location: {job['primary_location']}")
            print(f"   Work Flexibility: {job['work_flexibility']}")
            print(f"   Employment Type: {job['employment_type']}")
            print(f"   Profession: {job['profession']}")
    else:
        print("No jobs found in the data")

if __name__ == "__main__":
    main()
