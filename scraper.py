import argparse
import csv
import json
import re
import time
from dataclasses import dataclass
from html import unescape
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HREF_RE = re.compile(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
OWNER_HINT_RE = re.compile(
    r"(?:owner|founder|co-founder|ceo|president|managed by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
    re.IGNORECASE,
)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
OG_SITE_NAME_RE = re.compile(
    r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


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
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; BusinessLeadBot/1.0)"})
    with urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def http_post(url: str, body: str, timeout_s: int = 150) -> str:
    data = body.encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def build_overpass_query(state: str, include_amenity: bool, include_shop: bool, include_office: bool, limit: int) -> str:
    filters = []
    if include_amenity:
        filters.append('nwr["amenity"](area.searchArea);')
    if include_shop:
        filters.append('nwr["shop"](area.searchArea);')
    if include_office:
        filters.append('nwr["office"](area.searchArea);')
    if not filters:
        filters = ['nwr["amenity"](area.searchArea);', 'nwr["shop"](area.searchArea);', 'nwr["office"](area.searchArea);']

    return f"""
[out:json][timeout:120];
area["name"="{state}"]["admin_level"="4"]["boundary"="administrative"]->.searchArea;
(
    {' '.join(filters)}
);
out tags {limit};
""".strip()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not urlparse(url).scheme:
        url = "https://" + url
    return url


def strip_html(html: str) -> str:
    return unescape(TAG_RE.sub(" ", html))


def find_contact_links(base_url: str, html: str) -> List[str]:
    found = []
    for href, text in HREF_RE.findall(html):
        txt = strip_html(text).lower()
        href_l = href.lower()
        if any(k in href_l for k in ["contact", "about", "team"]) or any(k in txt for k in ["contact", "about", "team"]):
            found.append(urljoin(base_url, href))
    out, seen = [], set()
    for u in found:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:3]


def extract_owner_name(text: str) -> str:
    m = OWNER_HINT_RE.search(text)
    return m.group(1).strip() if m else ""


def scrape_site_data(url: str, timeout_s: int = 12) -> Dict[str, str]:
    try:
        home_html = http_get(url, timeout_s)
    except Exception:
        return {}

    pages = [home_html]
    for l in find_contact_links(url, home_html):
        try:
            pages.append(http_get(l, timeout_s))
        except Exception:
            pass

    emails: Set[str] = set()
    owner, company_name = "", ""

    for html in pages:
        text = " ".join(strip_html(html).split())
        emails.update(EMAIL_RE.findall(text))
        if not owner:
            owner = extract_owner_name(text)
        if not company_name:
            m1 = TITLE_RE.search(html)
            if m1:
                company_name = strip_html(m1.group(1)).strip()
            m2 = OG_SITE_NAME_RE.search(html)
            if m2:
                company_name = m2.group(1).strip()

    email = sorted(emails, key=lambda x: ("info@" in x.lower(), len(x)))[0] if emails else ""
    return {"email": email, "owner_name": owner, "company_name": company_name}


def get_businesses_for_state(state: str, include_amenity: bool, include_shop: bool, include_office: bool, limit: int) -> List[Lead]:
    raw = http_post(OVERPASS_URL, build_overpass_query(state, include_amenity, include_shop, include_office, limit))
    data = json.loads(raw)
    leads: List[Lead] = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name", "")
        website = normalize_url(tags.get("website", "") or tags.get("contact:website", ""))
        email = tags.get("email", "") or tags.get("contact:email", "")
        owner = tags.get("operator", "")
        if not name and not website and not email:
            continue
        leads.append(
            Lead(
                name=name,
                email=email,
                website=website,
                owner_name=owner,
                company_name=tags.get("brand", "") or name,
                state=state,
                source="OpenStreetMap/Overpass",
            )
        )
    return leads


def enrich_leads(leads: List[Lead], delay_s: float = 0.6) -> List[Lead]:
    for lead in leads:
        if not lead.website:
            continue
        scraped = scrape_site_data(lead.website)
        if not lead.email:
            lead.email = scraped.get("email", "")
        if not lead.owner_name:
            lead.owner_name = scraped.get("owner_name", "")
        if not lead.company_name:
            lead.company_name = scraped.get("company_name", "")
        time.sleep(delay_s)
    return leads


def dedupe(leads: List[Lead]) -> List[Lead]:
    out, seen = [], set()
    for l in leads:
        key = (l.name.lower(), l.website.lower(), l.email.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(l)
    return out


def save_csv(leads: List[Lead], output: str) -> None:
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email", "website", "owner_name", "company_name", "state", "source"])
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead.__dict__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape US business leads (name/email/website/owner/company).")
    p.add_argument("--states", nargs="+", required=True)
    p.add_argument("--limit-per-state", type=int, default=100)
    p.add_argument("--output", default="business_leads.csv")
    p.add_argument("--amenity", action="store_true")
    p.add_argument("--shop", action="store_true")
    p.add_argument("--office", action="store_true")
    p.add_argument("--skip-enrichment", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    all_leads: List[Lead] = []
    for st in args.states:
        print(f"[+] Fetching businesses for {st} ...")
        try:
            leads = get_businesses_for_state(st, args.amenity, args.shop, args.office, args.limit_per_state)
            print(f"    Found {len(leads)} records from OSM")
            all_leads.extend(leads)
        except Exception as e:
            print(f"    Failed for {st}: {e}")

    all_leads = dedupe(all_leads)
    print(f"[+] Total unique leads before enrichment: {len(all_leads)}")
    if not args.skip_enrichment:
        enrich_leads(all_leads)
    save_csv(dedupe(all_leads), args.output)
    print(f"[+] Saved leads to {args.output}")


if __name__ == "__main__":
    main()
