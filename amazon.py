import requests
import json
import csv
import re
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

def fetch_amazon_jobs(offset=0, result_limit=10):
    """
    Fetches job listings from Amazon careers API
    Filters: Software Dev, Program/Product Management, Full-Time, USA, 1-3 years experience
    """
    base_url = "https://www.amazon.jobs/en/search.json"
    params = (
        f"?category%5B%5D=software-development"
        f"&category%5B%5D=project-program-product-management-technical"
        f"&category%5B%5D=project-program-product-management-non-tech"
        f"&schedule_type_id%5B%5D=Full-Time"
        f"&normalized_country_code%5B%5D=USA"
        f"&radius=24km"
        f"&facets%5B%5D=normalized_country_code"
        f"&facets%5B%5D=normalized_state_name"
        f"&facets%5B%5D=normalized_city_name"
        f"&facets%5B%5D=location"
        f"&facets%5B%5D=business_category"
        f"&facets%5B%5D=category"
        f"&facets%5B%5D=schedule_type_id"
        f"&facets%5B%5D=employee_class"
        f"&facets%5B%5D=normalized_location"
        f"&facets%5B%5D=job_function_id"
        f"&facets%5B%5D=is_manager"
        f"&facets%5B%5D=is_intern"
        f"&offset={offset}"
        f"&result_limit={result_limit}"
        f"&sort=recent"
        f"&latitude="
        f"&longitude="
        f"&loc_group_id="
        f"&loc_query="
        f"&base_query="
        f"&city="
        f"&country="
        f"&region="
        f"&county="
        f"&query_options="
    )
    url = base_url + params

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
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
    Parses the job data from Amazon API response
    """
    jobs = []

    if not data:
        return jobs

    # Navigate through the JSON structure
    job_listings = data.get('jobs', [])

    for job in job_listings:
        # Clean description by removing HTML tags
        description_html = job.get('description', '')
        clean_description = strip_html(description_html)[:500]  # First 500 chars

        # Extract location info
        location = job.get('location', 'N/A')
        city = job.get('city', '')
        state = job.get('state', '')

        # Parse posting date
        posted_date = job.get('posted_date', '')

        job_info = {
            'job_id': job.get('id_icims', job.get('id', '')),
            'title': job.get('title', ''),
            'posting_date': posted_date,
            'location': location,
            'city': city,
            'state': state,
            'company_name': job.get('company_name', 'Amazon'),
            'business_category': job.get('business_category', ''),
            'job_category': job.get('job_category', ''),
            'job_family': job.get('job_family', ''),
            'job_schedule_type': job.get('job_schedule_type', ''),
            'description': clean_description.replace('\n', ' ').replace('\r', '').replace('\t', ' '),
            'job_path': job.get('job_path', ''),
            'updated_time': job.get('updated_time', '')
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
        # Parse the posting date string (e.g., "September 26, 2025")
        posting_date_str = job.get('posting_date', '')
        updated_time = job.get('updated_time', '')

        # Try to calculate hours ago from updated_time (e.g., "2 days", "about 13 hours")
        try:
            if updated_time:
                if 'hour' in updated_time:
                    # Extract number from strings like "2 hours", "about 13 hours"
                    numbers = re.findall(r'\d+', updated_time)
                    if numbers:
                        hours = int(numbers[0])
                        job['hours_ago'] = hours
                        if hours <= hours_back:
                            recent_jobs.append(job)
                elif 'day' in updated_time:
                    # Extract number from strings like "2 days", "about 3 days"
                    numbers = re.findall(r'\d+', updated_time)
                    if numbers:
                        days = int(numbers[0])
                        hours = days * 24
                        job['hours_ago'] = hours
                        if hours <= hours_back:
                            recent_jobs.append(job)
                else:
                    # If we can't parse, include it as potentially recent
                    job['hours_ago'] = 0
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
            title = f"🚀 New Amazon Jobs Alert"
            subtitle = f"Found {len(jobs)} new positions in the last {hours_back} hours"
        else:
            title = f"🚀 Amazon Jobs (Part {message_num} of {total_messages_needed})"
            subtitle = f"Jobs {start_idx + 1}-{end_idx} of {len(jobs)} total"

        message = {
            "cards": [{
                "header": {
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Amazon_logo.svg/603px-Amazon_logo.svg.png"
                },
                "sections": []
            }]
        }

        # Add jobs as individual sections
        for i, job in enumerate(message_jobs, 1):
            job_url = f"https://www.amazon.jobs{job.get('job_path', '')}" if job.get('job_path') else "https://www.amazon.jobs"

            job_content = (
                f"<b>{job.get('title', 'Unknown Title')}</b><br/>"
                f"📍 {job.get('location', 'N/A')}<br/>"
                f"💼 {job.get('job_category', 'N/A')} | {job.get('business_category', 'N/A')}<br/>"
                f"🕐 {job.get('hours_ago', 0):.1f}h ago • {job.get('job_schedule_type', 'N/A')}<br/>"
                f"🏢 {job.get('company_name', 'Amazon')}<br/>"
                f"<a href=\"{job_url}\">Apply Now →</a>"
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
            time.sleep(3)  # 3 seconds between messages

    if all_successful:
        print(f"✅ Successfully sent all {len(jobs)} jobs in {len(messages_to_send)} message(s)")
    else:
        print(f"⚠️  Some messages failed to send")

    return all_successful

def save_to_csv(jobs, filename='amazon_jobs.csv'):
    """
    Saves job data to a CSV file
    """
    if not jobs:
        print("No jobs to save")
        return

    # Define CSV headers
    headers = ['job_id', 'title', 'posting_date', 'location', 'city', 'state',
               'company_name', 'business_category', 'job_category', 'job_family',
               'job_schedule_type', 'description', 'job_path', 'updated_time']

    # Write to CSV
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"Successfully saved {len(jobs)} jobs to {filename}")

def main():
    """
    Main function to orchestrate the scraping process
    """
    parser = argparse.ArgumentParser(description='Amazon Job Scraper - Fetch and filter Amazon job listings')

    # Fetch options
    parser.add_argument('--count', '-c', type=int, default=20,
                      help='Number of jobs to fetch (default: 20)')
    parser.add_argument('--pages', '-p', type=int, default=1,
                      help='Number of pages to fetch (10 jobs per page, default: 1)')

    # Webhook related arguments
    parser.add_argument('--webhook', '-w', action='store_true',
                      help='Enable webhook mode to send notifications for recent jobs')
    parser.add_argument('--hours', type=int, default=4,
                      help='Hours to look back for recent jobs (default: 4, only with --webhook)')
    parser.add_argument('--webhook-url', type=str,
                      help='Google Chat webhook URL (can also be set via WEBHOOK_URL env var)')

    # Output options
    parser.add_argument('--output', '-o', type=str, default='amazon_jobs.csv',
                      help='Output CSV filename (default: amazon_jobs.csv)')
    parser.add_argument('--quiet', '-q', action='store_true',
                      help='Minimal output')

    args = parser.parse_args()

    if not args.quiet:
        print("Amazon Job Scraper")
        print(f"Timestamp: {datetime.now()}")
        print("-" * 50)

    all_jobs = []

    # Calculate total jobs to fetch
    jobs_per_page = 10
    total_pages = args.pages

    # Fetch jobs
    if not args.quiet:
        print(f"Fetching {total_pages} page(s) from Amazon API...")

    for page in range(total_pages):
        offset = page * jobs_per_page

        if not args.quiet:
            print(f"Fetching page {page + 1} (offset: {offset})...")

        data = fetch_amazon_jobs(offset=offset, result_limit=jobs_per_page)

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
                print("  python amazon.py --webhook --hours 24 --pages 5 --webhook-url 'https://...'")
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
                        print(f"  {i}. {job['title']} - {job.get('hours_ago', 0):.1f}h ago")

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

                # Send a "no new jobs" notification
                message = {
                    "text": f"📭 No new Amazon jobs found in the last {args.hours} hours.\nLast checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }
                requests.post(webhook_url, json=message)
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
                    print(f"   Category: {job['job_category']}")
                    print(f"   Business: {job['business_category']}")
                    print(f"   Company: {job['company_name']}")
    else:
        if not args.quiet:
            print("No jobs found in the data")

if __name__ == "__main__":
    main()
