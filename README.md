# USA Business Email Scraper

Simple CLI to collect U.S. business lead data:

- **name**
- **email**
- **website**
- **owner_name** (best effort)
- **company_name**

---

## 1) Super quick install (recommended)

```bash
cd /workspace/email_scraper
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Current version is **stdlib-only** (no external package required), so install is very lightweight.

---

## 2) Get 1000+ leads at a time

Use the new `--target-per-state` option (default is already 1000).

```bash
python scraper.py --states "California" --target-per-state 1200 --limit-per-query 700 --output ca_1200.csv
```

How this works:
- Scraper runs multiple Overpass tag queries (`amenity`, `shop`, `office`, `craft`, `tourism`, `leisure`).
- It keeps deduplicating and stops early once target count is reached.
- If one tag query fails, it continues with the rest.

---

## 3) Common commands

### Multi-state run (large pull)

```bash
python scraper.py --states "California" "Texas" --target-per-state 1000 --limit-per-query 600 --output leads_2states.csv
```

### Faster run (skip website crawling)

```bash
python scraper.py --states "Florida" --target-per-state 1500 --skip-enrichment --output fl_fast.csv
```

### Restrict to specific OSM groups only

```bash
python scraper.py --states "New York" --amenity --shop --office --target-per-state 1000 --limit-per-query 800
```

---

## 4) Output CSV columns

- `name`
- `email`
- `website`
- `owner_name`
- `company_name`
- `state`
- `source`

---

## 5) Troubleshooting

### A) `python: command not found`
Use `python3` instead.

### B) Overpass/network/proxy errors (e.g. `403 Forbidden`)
Usually environment/network policy.

Options:
- Run from a machine/network with outbound HTTPS allowed.
- Configure `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`.
- Retry later (public Overpass can be rate-limited).

### C) Not reaching 1000 leads
- Increase `--limit-per-query` (e.g. 1000).
- Use larger/business-dense states.
- Run multiple states in one command.
- Use default tag set (do not over-filter with flags).

---

## 6) Important notes

- Scraping **all businesses in the USA** is a large batch job; run in chunks by state.
- Respect each site's Terms of Service and robots.txt.
- Follow applicable anti-spam/privacy laws (CAN-SPAM, GDPR where applicable, etc.).
