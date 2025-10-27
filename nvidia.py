import requests
import csv
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
import os
import argparse
import time
import re
from typing import List, Dict

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

def parse_posting_time(posted_on: str) -> float:
    """
    Parse NVIDIA's posting time format and return hours ago
    Examples: "Posted Today", "Posted Yesterday", "Posted 2 days ago"
    """
    if not posted_on:
        return 0

    posted_on = posted_on.lower()

    if "today" in posted_on:
        return 6  # Assume posted today means ~6 hours ago on average
    elif "yesterday" in posted_on:
        return 30  # Assume posted yesterday means ~30 hours ago on average
    elif "days ago" in posted_on:
        # Extract number from "Posted X days ago"
        numbers = re.findall(r'\d+', posted_on)
        if numbers:
            days = int(numbers[0])
            return days * 24

    return 0  # Default to 0 if can't parse

def fetch_nvidia_jobs(offset=0, limit=20):
    """
    Fetches job listings from NVIDIA Workday API
    Filters: Engineering, Program Management, Research, IT, Operations, Finance, Business Development
    """
    url = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"

    payload = {
        "appliedFacets": {
            "locationHierarchy1": [
                "2fcb99c455831013ea52fb338f2932d8"  # United States
            ],
            "timeType": [
                "5509c0b5959810ac0029943377d47364"  # Full time
            ],
            "jobFamilyGroup": [
                "0c40f6bd1d8f10ae43ffaefd46dc7e78",  # Engineering
                "0c40f6bd1d8f10ae43ffc668c6847e8c",  # Program Manager
                "0c40f6bd1d8f10ae43ffc8817cf47e8e",  # Research
                "0c40f6bd1d8f10ae43ffda1e8d447e94",  # University Employment
                "0c40f6bd1d8f10ae43ffc3fc7d8c7e8a",  # Operations
                "0c40f6bd1d8f10ae43ffac5fdfac7e76",  # Business Development
                "0c40f6bd1d8f10ae43ffbd1459047e84",  # IT - Information Technology
                "0c40f6bd1d8f10ae43ffb5dd06f47e7e"   # Finance
            ],
            "workerSubType": [
                "ab40a98049581037a3ada55b087049b7",  # New College Graduate
                "0c40f6bd1d8f10adf6dae161b1844a15"   # Regular Employee
            ]
        },
        "limit": limit,
        "offset": offset,
        "searchText": ""
    }

    headers = {
        'accept': 'application/json',
        'accept-language': 'en-US',
        'content-type': 'application/json',
        'origin': 'https://nvidia.wd5.myworkdayjobs.com',
        'referer': 'https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/jobs',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def parse_job_data(data):
    """
    Parses the job data from NVIDIA Workday API response
    """
    jobs = []

    if not data:
        return jobs

    # Navigate through the JSON structure
    job_postings = data.get('jobPostings', [])

    for job in job_postings:
        # Extract job ID from bulletFields
        bullet_fields = job.get('bulletFields', [])
        job_id = bullet_fields[0] if bullet_fields else ''

        # Parse location - can be "4 Locations", "US, CA, Santa Clara", etc.
        locations_text = job.get('locationsText', '')

        # Extract city and state if available
        city = ''
        state = ''
        if ', ' in locations_text and not 'Locations' in locations_text:
            parts = locations_text.split(', ')
            if len(parts) >= 3:  # Format: "US, CA, Santa Clara"
                state = parts[1] if len(parts) > 1 else ''
                city = parts[2] if len(parts) > 2 else ''

        # Parse posting time
        posted_on = job.get('postedOn', '')
        hours_ago = parse_posting_time(posted_on)

        # Calculate posting date
        if hours_ago > 0:
            posting_datetime = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
            posting_date = posting_datetime.strftime('%b %d, %Y')
        else:
            posting_date = ''

        job_info = {
            'job_id': job_id,
            'title': job.get('title', ''),
            'posting_date': posting_date,
            'location': locations_text,
            'city': city,
            'state': state,
            'company_name': 'NVIDIA Corporation',
            'business_category': 'Technology',
            'job_category': 'Technology',
            'job_family': '',  # NVIDIA doesn't provide this
            'job_schedule_type': 'Full-Time',
            'description': '',  # NVIDIA API doesn't include descriptions in list view
            'job_path': job.get('externalPath', ''),
            'updated_time': posted_on,
            'hours_ago': hours_ago
        }
        jobs.append(job_info)

    return jobs

def filter_recent_jobs(jobs: List[Dict], hours_back: int = 4) -> List[Dict]:
    """
    Filter jobs posted within the last N hours
    """
    recent_jobs = []
    for job in jobs:
        hours_ago = job.get('hours_ago', 0)
        if hours_ago <= hours_back:
            recent_jobs.append(job)

    return recent_jobs

def send_google_webhook(webhook_url: str, jobs: List[Dict], hours_back: int):
    """
    Send formatted jobs to Google Chat webhook (4 jobs per message, sends ALL jobs)
    """
    if not jobs:
        print("No recent jobs to send")
        return False

    # Sort jobs by most recent first
    sorted_jobs = sorted(jobs, key=lambda x: x.get('hours_ago', 999))

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
            title = f"💚 New NVIDIA Jobs Alert"
            subtitle = f"Found {len(jobs)} new positions in the last {hours_back} hours"
        else:
            title = f"💚 NVIDIA Jobs (Part {message_num} of {total_messages_needed})"
            subtitle = f"Jobs {start_idx + 1}-{end_idx} of {len(jobs)} total"

        message = {
            "cards": [{
                "header": {
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": "https://logos-world.net/wp-content/uploads/2020/09/Nvidia-Logo.png"
                },
                "sections": []
            }]
        }

        # Add jobs as individual sections
        for i, job in enumerate(message_jobs, 1):
            job_url = f"https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite{job.get('job_path', '')}" if job.get('job_path') else "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/jobs"

            job_content = (
                f"<b>{job.get('title', 'Unknown Title')}</b><br/>"
                f"📍 {job.get('location', 'N/A')}<br/>"
                f"💼 {job.get('business_category', 'N/A')} | {job.get('job_schedule_type', 'N/A')}<br/>"
                f"🕐 {job.get('updated_time', 'N/A')} • ID: {job.get('job_id', 'N/A')}<br/>"
                f"🏢 {job.get('company_name', 'NVIDIA Corporation')}<br/>"
                f"<a href=\"{job_url}\">Apply Now →</a>"
            )

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
            time.sleep(3)  # 3 seconds between messages

    if all_successful:
        print(f"✅ Successfully sent all {len(jobs)} jobs in {len(messages_to_send)} message(s)")
    else:
        print(f"⚠️  Some messages failed to send")

    return all_successful

def save_to_csv(jobs, filename='nvidia_jobs.csv'):
    """
    Saves job data to a CSV file
    """
    if not jobs:
        print("No jobs to save")
        return

    # Define CSV headers (excluding hours_ago which is for internal use)
    headers = ['job_id', 'title', 'posting_date', 'location', 'city', 'state',
               'company_name', 'business_category', 'job_category', 'job_family',
               'job_schedule_type', 'description', 'job_path', 'updated_time']

    # Remove hours_ago field for CSV export
    csv_jobs = []
    for job in jobs:
        csv_job = {k: v for k, v in job.items() if k != 'hours_ago'}
        csv_jobs.append(csv_job)

    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(csv_jobs)

    print(f"Successfully saved {len(jobs)} jobs to {filename}")

def main():
    """
    Main function to orchestrate the scraping process
    """
    parser = argparse.ArgumentParser(description='NVIDIA Job Scraper - Fetch and filter NVIDIA job listings')

    # Fetch options
    parser.add_argument('--pages', '-p', type=int, default=1,
                      help='Number of pages to fetch (20 jobs per page, default: 1)')

    # Webhook related arguments
    parser.add_argument('--webhook', '-w', action='store_true',
                      help='Enable webhook mode to send notifications for recent jobs')
    parser.add_argument('--hours', type=int, default=4,
                      help='Hours to look back for recent jobs (default: 4, only with --webhook)')
    parser.add_argument('--webhook-url', type=str,
                      help='Google Chat webhook URL (can also be set via WEBHOOK_URL env var)')

    # Output options
    parser.add_argument('--output', '-o', type=str, default='nvidia_jobs.csv',
                      help='Output CSV filename (default: nvidia_jobs.csv)')
    parser.add_argument('--quiet', '-q', action='store_true',
                      help='Minimal output')

    args = parser.parse_args()

    if not args.quiet:
        print("NVIDIA Job Scraper")
        print(f"Timestamp: {datetime.now()}")
        print("-" * 50)

    all_jobs = []

    # Calculate pagination parameters
    jobs_per_page = 20
    total_pages = args.pages

    # Fetch jobs
    if not args.quiet:
        print(f"Fetching {total_pages} page(s) from NVIDIA API...")

    for page in range(total_pages):
        offset = page * jobs_per_page

        if not args.quiet:
            print(f"Fetching page {page + 1} (offset: {offset})...")

        data = fetch_nvidia_jobs(offset=offset, limit=jobs_per_page)

        if data:
            page_jobs = parse_job_data(data)
            all_jobs.extend(page_jobs)
            if not args.quiet:
                print(f"  Found {len(page_jobs)} jobs on page {page + 1}")
        else:
            if not args.quiet:
                print(f"  Failed to fetch page {page + 1}")

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
                print("  python nvidia.py --webhook --hours 24 --pages 5 --webhook-url 'https://...'")
                return

            # Filter recent jobs
            if not args.quiet:
                print(f"\nFiltering jobs posted in the last {args.hours} hours...")
            recent_jobs = filter_recent_jobs(jobs, hours_back=args.hours)

            if recent_jobs:
                if not args.quiet:
                    print(f"Found {len(recent_jobs)} recent jobs")

                    # Display summary
                    print("\nRecent jobs summary:")
                    for i, job in enumerate(recent_jobs[:5], 1):
                        print(f"  {i}. {job['title']} - {job.get('updated_time', 'N/A')}")

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
                    print(f"   Location: {job['location']}")
                    print(f"   Posted: {job.get('updated_time', 'N/A')}")
    else:
        if not args.quiet:
            print("No jobs found in the data")

if __name__ == "__main__":
    main()