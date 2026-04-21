"""
Example: Fetch paginated JSON REST API data and export to multiple formats.

Uses the public JSONPlaceholder API — no auth required.

Run:
    python examples/api_scraper.py
"""

from __future__ import annotations

import requests

from scrapekit.exporters import CSVExporter, JSONExporter, ExcelExporter


BASE_URL = "https://jsonplaceholder.typicode.com"


def fetch_all_posts() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/posts", timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_all_users() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/users", timeout=15)
    resp.raise_for_status()
    return resp.json()


def enrich_posts(posts: list[dict], users: list[dict]) -> list[dict]:
    """Join posts with user data by userId."""
    user_map = {u["id"]: u["name"] for u in users}
    for post in posts:
        post["author"] = user_map.get(post["userId"], "Unknown")
    return posts


if __name__ == "__main__":
    print("Fetching posts and users from JSONPlaceholder API…")
    posts = fetch_all_posts()
    users = fetch_all_users()
    enriched = enrich_posts(posts, users)

    print(f"  {len(enriched)} posts fetched.")

    output_dir = "./output"
    filename = "api_posts"

    csv_path  = CSVExporter(output_dir).export(enriched, filename)
    json_path = JSONExporter(output_dir).export(enriched, filename)
    xlsx_path = ExcelExporter(output_dir).export(enriched, filename)

    print(f"CSV   : {csv_path}")
    print(f"JSON  : {json_path}")
    print(f"Excel : {xlsx_path}")
