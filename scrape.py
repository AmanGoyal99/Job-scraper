import requests
import json
import csv
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import sys
import os
import argparse
import time
from typing import List, Dict, Any

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

def filter_recent_jobs(jobs: List[Dict], hours_back: int = 4) -> List[Dict]:
    """
    Filter jobs posted within the last N hours
    """
    current_time = datetime.now(timezone.utc)
    cutoff_time = current_time - timedelta(hours=hours_back)

    recent_jobs = []
    for job in jobs:
        # Parse the posting date string
        posting_date_str = job.get('posting_date', '')
        if posting_date_str:
            try:
                # Parse ISO format datetime string
                posting_date = datetime.fromisoformat(posting_date_str.replace('Z', '+00:00'))
                if posting_date >= cutoff_time:
                    # Add time difference for display
                    time_diff = current_time - posting_date
                    hours_ago = time_diff.total_seconds() / 3600
                    job['hours_ago'] = round(hours_ago, 1)
                    recent_jobs.append(job)
            except Exception as e:
                print(f"Error parsing date for job {job.get('job_id')}: {e}")

    return recent_jobs

def send_google_webhook(webhook_url: str, jobs: List[Dict], hours_back: int):
    """
    Send formatted jobs to Google Chat webhook (4 jobs per message, sends ALL jobs)
    """
    if not jobs:
        print("No recent jobs to send")
        return False

    # Sort jobs by posting date (most recent first)
    sorted_jobs = sorted(jobs, key=lambda x: x.get('posting_date', ''), reverse=True)

    # Settings for message batching
    JOBS_PER_MESSAGE = 4
    total_messages_needed = (len(sorted_jobs) + JOBS_PER_MESSAGE - 1) // JOBS_PER_MESSAGE

    # Create messages
    messages_to_send = []

    for message_num in range(1, total_messages_needed + 1):
        # Get jobs for this message
        start_idx = (message_num - 1) * JOBS_PER_MESSAGE
        end_idx = min(start_idx + JOBS_PER_MESSAGE, len(sorted_jobs))
        message_jobs = sorted_jobs[start_idx:end_idx]

        # Determine header
        if total_messages_needed == 1:
            title = f"🚀 New Microsoft Jobs Alert"
            subtitle = f"Found {len(jobs)} new positions in the last {hours_back} hours"
        else:
            title = f"🚀 Microsoft Jobs (Part {message_num} of {total_messages_needed})"
            subtitle = f"Jobs {start_idx + 1}-{end_idx} of {len(jobs)} total"

        message = {
            "cards": [{
                "header": {
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Microsoft_logo.svg/512px-Microsoft_logo.svg.png"
                },
                "sections": []
            }]
        }

        # Add jobs as individual sections
        for i, job in enumerate(message_jobs, 1):
            job_content = (
                f"<b>{job.get('title', 'Unknown Title')}</b><br/>"
                f"📍 {job.get('primary_location', 'N/A')}<br/>"
                f"💼 {job.get('profession', 'N/A')} | {job.get('discipline', 'N/A')}<br/>"
                f"🕐 {job.get('hours_ago', 0):.1f}h ago • {job.get('work_flexibility', 'N/A')}<br/>"
                f"🆔 Job ID: {job.get('job_id', 'N/A')}<br/>"
                f"<a href=\"https://jobs.careers.microsoft.com/global/en/job/{job.get('job_id', '')}\">Apply Now →</a>"
            )

            # Add brief description if available
            description = job.get('description', '')[:100]
            if description:
                job_content += f"<br/><i>{description}...</i>"

            section = {
                "header": f"#{start_idx + i}",
                "widgets": [{
                    "textParagraph": {
                        "text": job_content
                    }
                }]
            }

            message["cards"][0]["sections"].append(section)

        # Add footer
        if message_num == total_messages_needed:
            footer_text = f"<i>✅ All {len(jobs)} jobs sent • {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
        else:
            remaining_jobs = len(jobs) - end_idx
            footer_text = f"<i>➡️ {remaining_jobs} more jobs in next message...</i>"

        message["cards"][0]["sections"].append({
            "widgets": [{
                "textParagraph": {
                    "text": footer_text
                }
            }]
        })

        messages_to_send.append(message)

    # Send all messages with retry logic
    all_successful = True
    total_jobs_sent = 0
    MAX_RETRIES = 2

    for i, message in enumerate(messages_to_send, 1):
        success = False

        for attempt in range(MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    delay = 2 ** attempt  # Exponential backoff: 2, 4 seconds
                    print(f"🔄 Retrying message {i} in {delay} seconds (attempt {attempt + 1}/{MAX_RETRIES + 1})")
                    time.sleep(delay)

                response = requests.post(
                    webhook_url,
                    json=message,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                if response.status_code == 200:
                    jobs_in_this_message = min(JOBS_PER_MESSAGE, len(jobs) - total_jobs_sent)
                    total_jobs_sent += jobs_in_this_message
                    print(f"✅ Sent message {i}/{len(messages_to_send)} ({jobs_in_this_message} jobs)")
                    success = True
                    break
                elif response.status_code == 429:  # Rate limited
                    print(f"⏳ Rate limited on message {i}, waiting longer...")
                    time.sleep(5)
                    continue
                elif response.status_code >= 500:  # Server error, retry
                    print(f"🔄 Server error {response.status_code} on message {i}, will retry...")
                    continue
                else:
                    print(f"❌ Failed to send message {i}: {response.status_code}")
                    print(f"Response: {response.text}")
                    break

            except requests.exceptions.Timeout:
                print(f"⏱️  Timeout on message {i}, will retry...")
                continue
            except Exception as e:
                print(f"❌ Error sending message {i}: {e}")
                break

        if not success:
            all_successful = False

        # Delay between messages to avoid rate limiting
        if i < len(messages_to_send):
            time.sleep(3)  # Increased to 3 seconds between messages

    if all_successful:
        print(f"✅ Successfully sent all {len(jobs)} jobs in {len(messages_to_send)} message(s)")
    else:
        print(f"⚠️  Some messages failed to send")

    return all_successful

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
    """
    parser = argparse.ArgumentParser(description='Microsoft Job Scraper - Fetch and filter Microsoft job listings')

    # Create mutually exclusive group for main operations
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--pages', '-p', type=int, default=1,
                      help='Number of pages to fetch (default: 1)')
    group.add_argument('--range', '-r', nargs=2, type=int, metavar=('START', 'END'),
                      help='Fetch pages from START to END')
    group.add_argument('--file', '-f', type=str,
                      help='Process a JSON file instead of fetching from API')

    # Webhook related arguments
    parser.add_argument('--webhook', '-w', action='store_true',
                      help='Enable webhook mode to send notifications for recent jobs')
    parser.add_argument('--hours', type=int, default=4,
                      help='Hours to look back for recent jobs (default: 4, only with --webhook)')
    parser.add_argument('--webhook-url', type=str,
                      help='Google Chat webhook URL (can also be set via WEBHOOK_URL env var)')

    # Output options
    parser.add_argument('--output', '-o', type=str, default='microsoft_jobs.csv',
                      help='Output CSV filename (default: microsoft_jobs.csv)')
    parser.add_argument('--quiet', '-q', action='store_true',
                      help='Minimal output')

    args = parser.parse_args()

    if not args.quiet:
        print("Microsoft Job Scraper")
        print(f"Timestamp: {datetime.now()}")
        print("-" * 50)

    all_jobs = []

    # Determine fetch mode and page range
    if args.file:
        # Process JSON file
        if not args.quiet:
            print(f"Processing JSON file: {args.file}")
        data = process_json_file(args.file)
        if data:
            jobs = parse_job_data(data)
        else:
            jobs = []
    else:
        # Determine page range
        if args.range:
            start_page, end_page = args.range
        else:
            start_page = 1
            end_page = args.pages

        # Fetch from API
        if not args.quiet:
            print(f"Fetching job listings from Microsoft API (pages {start_page}-{end_page})...")

        for page in range(start_page, end_page + 1):
            if not args.quiet:
                print(f"Fetching page {page}...")
            data = fetch_microsoft_jobs(page=page, page_size=20)

            if data:
                page_jobs = parse_job_data(data)
                all_jobs.extend(page_jobs)
                if not args.quiet:
                    print(f"  Found {len(page_jobs)} jobs on page {page}")
            else:
                if not args.quiet:
                    print(f"  Failed to fetch page {page}")

        jobs = all_jobs

    if jobs:
        if not args.quiet:
            print(f"\nTotal jobs found: {len(jobs)}")

        # Webhook mode: filter recent jobs and send notification
        if args.webhook:
            # Get webhook URL from argument or environment
            webhook_url = args.webhook_url or os.getenv('WEBHOOK_URL', '')

            if not webhook_url:
                print("\n⚠️  No webhook URL provided!")
                print("Provide webhook URL via:")
                print("  1. Command line: --webhook-url 'your_webhook_url'")
                print("  2. Environment: export WEBHOOK_URL='your_webhook_url'")
                print("\nExample:")
                print("  python scrape.py --webhook --hours 6 --pages 5 --webhook-url 'https://...'")
                return

            # Filter recent jobs
            if not args.quiet:
                print(f"\nFiltering jobs posted in the last {args.hours} hours...")
            recent_jobs = filter_recent_jobs(jobs, hours_back=args.hours)

            if recent_jobs:
                if not args.quiet:
                    print(f"Found {len(recent_jobs)} recent jobs")

                    # Sort by posting date (most recent first)
                    recent_jobs.sort(key=lambda x: x.get('posting_date', ''), reverse=True)

                    # Display summary
                    print("\nRecent jobs summary:")
                    for i, job in enumerate(recent_jobs[:5], 1):
                        print(f"  {i}. {job['title']} - {job['hours_ago']:.1f}h ago")

                    if len(recent_jobs) > 5:
                        print(f"  ... and {len(recent_jobs) - 5} more")

                    print(f"\nSending to Google Chat webhook...")

                # Send webhook notification
                success = send_google_webhook(webhook_url, recent_jobs, args.hours)

                if not args.quiet:
                    if success:
                        print("✅ Webhook notification sent successfully!")
                    else:
                        print("❌ Failed to send webhook notification")
            else:
                if not args.quiet:
                    print(f"No jobs found in the last {args.hours} hours")
        else:
            # Normal mode: save to CSV
            save_to_csv(jobs, filename=args.output)

            if not args.quiet:
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
        if not args.quiet:
            print("No jobs found in the data")

if __name__ == "__main__":
    main()
