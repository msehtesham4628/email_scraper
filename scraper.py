import argparse
import csv
import json
import re
import time
from dataclasses import dataclass, asdict
from html import unescape
from typing import Dict, List, Set, Optional
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HREF_RE = re.compile(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
OWNER_HINT_RE = re.compile(r"(?:owner|founder|co-founder|ceo|president|managed by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", re.IGNORECASE)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

@dataclass
class Lead:
    name: str = ""
    email: str = ""
    website: str = ""
    owner_name: str = ""
    company_name: str = ""
    state: str = ""
    source: str = ""

def http_get(url: str, timeout_s: int = 15) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BusinessLeadBot/1.1"})
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except: return ""

def http_post(url: str, body: str, timeout_s: int = 150) -> str:
    data = body.encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"}, method="POST")
    with urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def build_overpass_query(state: str, amenity: bool, shop: bool, office: bool, limit: int) -> str:
    filters = []
    if amenity: filters.append('nwr["amenity"](area.searchArea);')
    if shop: filters.append('nwr["shop"](area.searchArea);')
    if office: filters.append('nwr["office"](area.searchArea);')
    if not filters: filters = ['nwr["amenity"](area.searchArea);']

    return f'[out:json][timeout:120];area["name"="{state}"]["admin_level"="4"]->.searchArea;({" ".join(filters)});out tags {limit};'

def scrape_site_data(url: str) -> Dict[str, str]:
    html = http_get(url)
    if not html: return {}
    emails = EMAIL_RE.findall(html)
    email = emails[0] if emails else ""
    return {"email": email}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--states", nargs="+", required=True)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--output", default="leads_v2.csv")
    args = p.parse_args()

    all_leads = []
    for st in args.states:
        print(f"[+] Processing {st}...")
        query = build_overpass_query(st, True, True, True, args.limit)
        raw = http_post(OVERPASS_URL, query)
        data = json.loads(raw)
        
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            lead = Lead(name=tags.get("name", "Unknown"), 
                        website=tags.get("website", ""),
                        state=st)
            if lead.website:
                print(f"  - Enriching {lead.name} via {lead.website}")
                scraped = scrape_site_data(lead.website)
                lead.email = scraped.get("email", "")
            all_leads.append(lead)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email", "website", "owner_name", "company_name", "state", "source"])
        writer.writeheader()
        for l in all_leads: writer.writerow(asdict(l))
    print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()