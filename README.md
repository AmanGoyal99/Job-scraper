# Microsoft Job Scraper

A Python script that scrapes Microsoft job listings and sends notifications to Google Chat via webhooks.

## Features

- 🔍 **Smart Filtering**: Filters for Software Engineering, Research, Program Management, and Product Management roles in the US
- 📱 **Webhook Notifications**: Sends job alerts to Google Chat with formatted cards
- ⚡ **Batch Processing**: Sends 4 jobs per message to ensure all jobs are delivered
- 🕐 **Time-based Filtering**: Only shows jobs posted within a specified time window
- 🤖 **Automated Scheduling**: GitHub Actions workflow runs every 2 hours

## Quick Start

### Local Usage

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Basic usage**:
   ```bash
   # Fetch 3 pages and save to CSV
   uv run python scrape.py --pages 3

   # Send webhook for jobs from last 4 hours
   uv run python scrape.py --webhook --hours 4 --pages 3 --webhook-url 'YOUR_WEBHOOK_URL'
   ```

### GitHub Actions Setup

1. **Fork this repository**

2. **Set up webhook URL secret**:
   - Go to your repo Settings → Secrets and variables → Actions
   - Add a new repository secret:
     - Name: `WEBHOOK_URL`
     - Value: Your Google Chat webhook URL

3. **Enable Actions**:
   - Go to Actions tab and enable workflows
   - The scraper will run automatically every 2 hours

4. **Manual trigger**:
   - Go to Actions → Microsoft Job Scraper → Run workflow
   - Customize hours back and pages as needed

## Command Line Options

```bash
usage: scrape.py [-h] [--pages PAGES | --range START END | --file FILE]
                 [--webhook] [--hours HOURS] [--webhook-url WEBHOOK_URL]
                 [--output OUTPUT] [--quiet]

Options:
  --pages PAGES, -p PAGES    Number of pages to fetch (default: 1)
  --range START END, -r      Fetch pages from START to END
  --file FILE, -f FILE       Process a JSON file instead of fetching from API
  --webhook, -w              Enable webhook mode
  --hours HOURS              Hours to look back for recent jobs (default: 4)
  --webhook-url WEBHOOK_URL  Google Chat webhook URL
  --output OUTPUT, -o        Output CSV filename (default: microsoft_jobs.csv)
  --quiet, -q                Minimal output
```

## Examples

```bash
# Fetch 5 pages and save to custom CSV
uv run python scrape.py --pages 5 --output jobs_$(date +%Y%m%d).csv

# Send webhook for jobs from last 6 hours, checking 4 pages
uv run python scrape.py --webhook --hours 6 --pages 4 --webhook-url 'https://...'

# Quiet mode for scheduled runs
uv run python scrape.py --webhook --hours 2 --pages 3 --quiet

# Fetch specific page range
uv run python scrape.py --range 2 5 --output recent_jobs.csv
```

## Webhook Message Format

Each webhook message contains:
- 📋 **Header**: Alert title and job count
- 🔢 **Jobs**: Up to 4 jobs per message with:
  - Job title and ID
  - Location and work flexibility
  - Profession and discipline
  - Time since posting
  - Direct apply link
- 📊 **Footer**: Progress indicator and timestamp

## Scheduling

The GitHub Action runs:
- **Every 2 hours** at 5 minutes past the hour (00:05, 02:05, 04:05, etc.)
- **Checks last 2 hours** for new job postings
- **Fetches 3 pages** (60 jobs) for comprehensive coverage

## Environment Variables

- `WEBHOOK_URL`: Google Chat webhook URL (required for webhook mode)

## Job Filters

The scraper filters for:
- **Location**: United States
- **Professions**: Software Engineering, Research Applied & Data Sciences, Program Management, Product Management
- **Disciplines**: Technical Program Management, Software Engineering, Research Sciences, Product Management, Applied Sciences, Data Science
- **Role Type**: Individual Contributor
- **Employment Type**: Full-Time

## Output

- **CSV File**: Complete job details saved locally
- **Webhook**: Formatted cards sent to Google Chat
- **Console**: Progress and summary information