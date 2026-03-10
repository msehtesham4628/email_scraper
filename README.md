# USA Business Email Scraper

This project provides a Python CLI that builds a lead list of U.S. businesses and attempts to extract:

- Business name
- Email
- Website
- Owner name (best effort)
- Company name

## Important notes

- Scraping "all businesses in the USA" is very large. This tool is designed to run by state and category in batches.
- Data quality depends on public website metadata and page content.
- You must comply with each website's Terms of Service and robots.txt.
- Use responsibly and follow applicable privacy/spam laws (CAN-SPAM, GDPR where applicable, etc.).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Example: scrape businesses in California and Texas.

```bash
python scraper.py --states "California" "Texas" --limit-per-state 150 --output data/business_leads.csv
```

Optional category filters (OpenStreetMap tag based):

```bash
python scraper.py --states "New York" --shop --office --amenity --limit-per-state 100
```

## Output

CSV columns:

- `name`
- `email`
- `website`
- `owner_name`
- `company_name`
- `state`
- `source`

## How it works

1. Queries OpenStreetMap (Overpass API) for businesses in selected state(s).
2. Reads any OSM-provided website/email/operator fields.
3. Crawls homepage + contact/about pages to extract emails and likely owner names.
4. Writes de-duplicated records to CSV.
