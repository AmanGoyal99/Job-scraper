# Integrate New Job Portal

Automatically generates a new job scraper from a Python API request file and integrates it into the existing job scraper ecosystem.

## Usage

```
/integrate-new-job-portal <sample_file.py> [company_name]
```

## Parameters

- `sample_file.py`: Path to Python file containing API request (url, payload, headers)
- `company_name` (optional): Override auto-detected company name

## Description

This command takes a Python file containing a raw API request (like `sample.py`) and automatically:

1. **Analyzes the API structure** by parsing the Python file to extract:
   - API endpoint URL
   - Request payload/parameters
   - Required headers
   - Request method (POST/GET)

2. **Tests the API** to understand the response format and data structure

3. **Generates a complete scraper** following the established pattern:
   - Full CLI interface with argparse
   - CSV export functionality
   - Google Chat webhook integration with company branding
   - Message batching (4 jobs per message)
   - Retry logic and error handling
   - Time-based filtering for recent jobs

4. **Updates the GitHub Actions workflow** to include the new scraper:
   - Adds scraper to dropdown options
   - Adds conditional execution logic
   - Creates webhook environment variable reference

5. **Tests the generated scraper** to ensure it works correctly

## Input File Format

The input Python file should contain a raw API request like this:

```python
import requests
import json

url = "https://api.company.com/jobs"

payload = json.dumps({
  "location": "US",
  "jobType": "full-time",
  "limit": 20,
  "offset": 0
})

headers = {
  'accept': 'application/json',
  'content-type': 'application/json',
  'user-agent': 'Mozilla/5.0...'
}

response = requests.request("POST", url, headers=headers, data=payload)
print(response.text)
```

## Examples

```bash
# Generate Google scraper from sample file
/integrate-new-job-portal sample_google.py

# Generate Meta scraper with custom name
/integrate-new-job-portal sample_meta.py Meta

# Generate from any API sample
/integrate-new-job-portal sample_spotify.py
```

## Auto-Detection Features

- **Company Detection**: Automatically detects company name from URL
- **API Structure**: Analyzes response to map fields to standard schema
- **Pagination Style**: Detects offset/page/cursor-based pagination
- **Time Format**: Understands various date/time formats
- **Field Mapping**: Maps API fields to standard CSV columns

## Generated Output

- **`{company}.py`**: Complete job scraper with all functionality
- **Updated workflow**: `.github/workflows/job-scraper.yml` with new scraper
- **Webhook integration**: Company-branded Google Chat notifications
- **CLI interface**: Consistent with existing scrapers

## Post-Generation Steps

After running this command:

1. Add `{COMPANY}_WEBHOOK_URL` secret to GitHub repository
2. Test the scraper: `uv run python {company}.py --help`
3. Test CSV export: `uv run python {company}.py --pages 1`
4. Test webhook: `uv run python {company}.py --webhook --hours 24 --pages 1`

## Supported APIs

Works with any HTTP API that returns job listings in JSON format. Automatically handles:

- REST APIs (GET/POST)
- GraphQL endpoints
- Various authentication methods (headers/tokens)
- Different pagination styles
- Nested JSON responses
- Various date/time formats

The command maintains the same high quality and consistency as the existing Microsoft, Amazon, Apple, and NVIDIA scrapers.