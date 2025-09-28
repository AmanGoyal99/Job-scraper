# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Architecture

This is a Microsoft job scraper that fetches job listings from Microsoft's careers API and sends notifications via Google Chat webhooks. The system is designed to run both locally and through automated GitHub Actions.

### Key Components

1. **scrape.py**: Main scraper with webhook notification system
   - Fetches from: `https://gcsservices.careers.microsoft.com/search/api/v1/search`
   - Filters: US-based Software Engineering, Research, Program Management, Product Management roles
   - Webhook batching: Sends 4 jobs per Google Chat message
   - Retry logic: Exponential backoff for failed webhook messages (500 errors common)
   - Rate limiting: 3-second delays between webhook messages

2. **GitHub Actions Workflow**: Automated execution every 2 hours
   - Schedule: `5 */2 * * *` (5 minutes past every 2nd hour)
   - Secret required: `WEBHOOK_URL` in repository secrets

## Essential Commands

```bash
# Install dependencies (use uv for package management)
uv sync

# Fetch jobs and save to CSV
uv run python scrape.py --pages 3

# Send webhook notification for recent jobs
uv run python scrape.py --webhook --hours 4 --pages 3 --webhook-url 'WEBHOOK_URL'

# Test webhook with environment variable
export WEBHOOK_URL='your_webhook_url'
uv run python scrape.py --webhook --hours 2 --pages 3

# Process specific page range
uv run python scrape.py --range 2 5

# Quiet mode for automated runs
uv run python scrape.py --webhook --hours 2 --pages 3 --quiet
```

## Webhook Integration Details

The scraper sends formatted Google Chat cards with specific structure:
- Messages are batched (4 jobs per message) to avoid Google Chat API limits
- Implements retry logic with exponential backoff for 500 errors
- Each job includes: title, location, profession, discipline, hours ago, job ID, apply link
- Message format: Part X of Y for multiple messages

## API Filters

The Microsoft API URL includes these hardcoded filters:
- Location: United States (`lc=United%20States`)
- Professions: Software Engineering, Research/Applied/Data Sciences, Program/Product Management
- Disciplines: Technical Program Management, Software Engineering, Research Sciences, etc.
- Role Type: Individual Contributor (`rt=Individual%20Contributor`)
- Employment Type: Full-Time (`et=Full-Time`)

## Common Issues and Solutions

1. **Webhook 500 Errors**: Google Chat API rate limiting
   - Script includes retry logic with exponential backoff
   - 3-second delays between messages
   - Consider reducing batch size if persistent

2. **GitHub Actions Failures**: Usually webhook-related
   - Verify `WEBHOOK_URL` secret is set correctly
   - Check for rate limiting in action logs
   - Manual retry via Actions tab → Run workflow

## Development Workflow

1. Test locally first with small page counts
2. Verify webhook formatting with test data
3. Push changes and monitor GitHub Actions execution
4. Webhook URL format: `https://chat.googleapis.com/v1/spaces/SPACE_ID/messages?key=KEY&token=TOKEN`