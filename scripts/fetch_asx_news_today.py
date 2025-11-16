#!/usr/bin/env python3
"""
Simple script to fetch all ASX announcements from QuoteAPI
`asx_news_today.json` and print a basic summary to stdout.

This reuses the existing QuoteAPI credentials from `config.Config`.
"""

import requests
from typing import List, Dict, Any

from scripts.asx_healthcare_codes import HEALTHCARE_STOCKS
from scripts.config import Config


NEWS_URL = "https://quoteapi.com/files/stocksdigital/asx_news_today.json"


def fetch_announcements() -> List[Dict[str, Any]]:
    """
    Fetch all announcements from QuoteAPI's asx_news_today.json.

    Returns a list of announcement dictionaries. The function handles both
    the "list" and "{ 'announcements': [...] }" JSON shapes.
    """
    session = requests.Session()
    session.auth = (Config.QUOTEAPI_USERNAME, Config.QUOTEAPI_PASSWORD)
    session.headers.update(
        {
            "User-Agent": Config.USER_AGENT,
            "Accept": "application/json",
        }
    )

    response = session.get(NEWS_URL, timeout=15)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict) and "announcements" in data:
        announcements = data.get("announcements", [])
    elif isinstance(data, list):
        announcements = data
    else:
        announcements = []

    return announcements


def group_healthcare_announcements(
    announcements: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group all announcements by healthcare stock code.

    - Uses HEALTHCARE_STOCKS mapping to determine which codes are healthcare.
    - Ignores announcements whose code is not in HEALTHCARE_STOCKS.
    - Does NOT split or modify individual announcements; it only groups them.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for ann in announcements:
        code = str(ann.get("code", "")).upper()
        if not code:
            continue

        if code not in HEALTHCARE_STOCKS:
            # Ignore non-healthcare announcements
            continue

        if code not in grouped:
            grouped[code] = []
        grouped[code].append(ann)

    return grouped


def main() -> None:
    """Fetch announcements and print a grouped healthcare summary."""
    try:
        announcements = fetch_announcements()
        print(f"Total announcements returned: {len(announcements)}")

        grouped = group_healthcare_announcements(announcements)
        total_healthcare = sum(len(v) for v in grouped.values())

        print(f"Total healthcare announcements: {total_healthcare}")
        print(f"Distinct healthcare codes with announcements: {len(grouped)}")

        # Print a compact summary grouped by healthcare code
        for code in sorted(grouped.keys()):
            company = HEALTHCARE_STOCKS.get(code, "Unknown company")
            count = len(grouped[code])
            print(f"{code} - {company}: {count} announcements")

    except Exception as exc:
        print(f"Error fetching announcements: {exc}")


if __name__ == "__main__":
    main()


