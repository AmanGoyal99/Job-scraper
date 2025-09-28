import requests
import csv
from datetime import datetime, timezone
from html.parser import HTMLParser
import os
import argparse
import time
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

def fetch_apple_jobs(page=1):
    """
    Fetches job listings from Apple careers API
    Filters: ML/AI and Software Engineering roles in USA
    """
    url = "https://jobs.apple.com/api/v1/search"

    payload = {
        "query": "",
        "filters": {
            "locations": [
                "postLocation-USA"
            ],
            "teams": [
                {
                    "team": "teamsAndSubTeams-MLAI",
                    "subTeam": "subTeam-MLI"
                },
                {
                    "team": "teamsAndSubTeams-MLAI",
                    "subTeam": "subTeam-DLRL"
                },
                {
                    "team": "teamsAndSubTeams-MLAI",
                    "subTeam": "subTeam-NLP"
                },
                {
                    "team": "teamsAndSubTeams-MLAI",
                    "subTeam": "subTeam-CV"
                },
                {
                    "team": "teamsAndSubTeams-MLAI",
                    "subTeam": "subTeam-AR"
                },
                {
                    "team": "teamsAndSubTeams-SFTWR",
                    "subTeam": "subTeam-EPM"
                },
                {
                    "team": "teamsAndSubTeams-SFTWR",
                    "subTeam": "subTeam-MCHLN"
                }
            ]
        },
        "page": page,
        "locale": "en-us",
        "sort": "newest",
        "format": {
            "longDate": "MMMM D, YYYY",
            "mediumDate": "MMM D, YYYY"
        }
    }

    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://jobs.apple.com',
        'referer': 'https://jobs.apple.com/en-us/search',
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
    Parses the job data from Apple API response
    """
    jobs = []

    if not data:
        return jobs

    # Navigate through the JSON structure
    search_results = data.get('res', {}).get('searchResults', [])

    for job in search_results:
        # Clean description by removing HTML tags
        description_html = job.get('jobSummary', '')
        clean_description = strip_html(description_html)[:500]  # First 500 chars

        # Extract location info - Apple has nested location structure
        locations = job.get('locations', [])
        location_name = locations[0].get('name', 'N/A') if locations else 'N/A'
        location_country = locations[0].get('countryName', 'USA') if locations else 'USA'
        location = f"{location_country}, {location_name}" if location_name != 'N/A' else location_country

        # Extract team info
        team_info = job.get('team', {})
        team_name = team_info.get('teamName', '')

        # Parse posting date
        posted_date = job.get('postingDate', '')
        post_date_gmt = job.get('postDateInGMT', '')

        # Calculate time since posting
        hours_ago = 0
        if post_date_gmt:
            try:
                post_datetime = datetime.fromisoformat(post_date_gmt.replace('Z', '+00:00'))
                current_time = datetime.now(timezone.utc)
                time_diff = current_time - post_datetime
                hours_ago = time_diff.total_seconds() / 3600
            except Exception:
                hours_ago = 0

        job_info = {
            'job_id': job.get('positionId', ''),
            'title': job.get('postingTitle', ''),
            'posting_date': posted_date,
            'location': location,
            'city': location_name,
            'state': '',  # Apple doesn't provide state separately
            'company_name': 'Apple Inc.',
            'business_category': team_name,
            'job_category': 'Technology',
            'job_family': team_info.get('teamCode', ''),
            'job_schedule_type': 'Full-Time',
            'description': clean_description.replace('\n', ' ').replace('\r', '').replace('\t', ' '),
            'job_path': f"/en-us/details/{job.get('transformedPostingTitle', '')}/{job.get('reqId', '')}",
            'updated_time': f"{hours_ago:.1f} hours",
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
            title = f"🍎 New Apple Jobs Alert"
            subtitle = f"Found {len(jobs)} new positions in the last {hours_back} hours"
        else:
            title = f"🍎 Apple Jobs (Part {message_num} of {total_messages_needed})"
            subtitle = f"Jobs {start_idx + 1}-{end_idx} of {len(jobs)} total"

        message = {
            "cards": [{
                "header": {
                    "title": title,
                    "subtitle": subtitle,
                    "imageUrl": "https://www.apple.com/ac/structured-data/images/knowledge_graph_logo.png"
                },
                "sections": []
            }]
        }

        # Add jobs as individual sections
        for i, job in enumerate(message_jobs, 1):
            job_url = f"https://jobs.apple.com{job.get('job_path', '')}" if job.get('job_path') else "https://jobs.apple.com"

            job_content = (
                f"<b>{job.get('title', 'Unknown Title')}</b><br/>"
                f"📍 {job.get('location', 'N/A')}<br/>"
                f"💼 {job.get('business_category', 'N/A')} | {job.get('job_family', 'N/A')}<br/>"
                f"🕐 {job.get('hours_ago', 0):.1f}h ago • {job.get('job_schedule_type', 'N/A')}<br/>"
                f"🏢 {job.get('company_name', 'Apple Inc.')}<br/>"
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

def save_to_csv(jobs, filename='apple_jobs.csv'):
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
    parser = argparse.ArgumentParser(description='Apple Job Scraper - Fetch and filter Apple job listings')

    # Fetch options
    parser.add_argument('--pages', '-p', type=int, default=1,
                      help='Number of pages to fetch (default: 1)')

    # Webhook related arguments
    parser.add_argument('--webhook', '-w', action='store_true',
                      help='Enable webhook mode to send notifications for recent jobs')
    parser.add_argument('--hours', type=int, default=4,
                      help='Hours to look back for recent jobs (default: 4, only with --webhook)')
    parser.add_argument('--webhook-url', type=str,
                      help='Google Chat webhook URL (can also be set via WEBHOOK_URL env var)')

    # Output options
    parser.add_argument('--output', '-o', type=str, default='apple_jobs.csv',
                      help='Output CSV filename (default: apple_jobs.csv)')
    parser.add_argument('--quiet', '-q', action='store_true',
                      help='Minimal output')

    args = parser.parse_args()

    if not args.quiet:
        print("Apple Job Scraper")
        print(f"Timestamp: {datetime.now()}")
        print("-" * 50)

    all_jobs = []

    # Fetch jobs
    if not args.quiet:
        print(f"Fetching {args.pages} page(s) from Apple API...")

    for page in range(1, args.pages + 1):
        if not args.quiet:
            print(f"Fetching page {page}...")

        data = fetch_apple_jobs(page=page)

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
                print("  python apple.py --webhook --hours 24 --pages 5 --webhook-url 'https://...'")
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
                    "text": f"📭 No new Apple jobs found in the last {args.hours} hours.\nLast checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
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
                    print(f"   Team: {job['business_category']}")
                    print(f"   Hours ago: {job.get('hours_ago', 0):.1f}")
    else:
        if not args.quiet:
            print("No jobs found in the data")

if __name__ == "__main__":
    main()