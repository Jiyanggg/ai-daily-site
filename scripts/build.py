#!/usr/bin/env python3
"""
build.py - Copies markdown reports into site/data/ and generates reports-index.json.
Run after generating a new daily report to update the website.
"""
import json
import os
import re
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
SITE_DATA_DIR = PROJECT_ROOT / "site" / "data"


def extract_title(md_text: str) -> str:
    """Extract first H1 from markdown."""
    match = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    return match.group(1).strip() if match else "AI 日报"


def build():
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    reports = []

    for md_file in sorted(REPORTS_DIR.glob("*.md"), reverse=True):
        date_str = md_file.stem  # e.g. "2026-03-18"
        if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
            continue

        content = md_file.read_text(encoding="utf-8")
        title = extract_title(content)

        # Copy to site/data/
        dest = SITE_DATA_DIR / md_file.name
        shutil.copy2(md_file, dest)

        reports.append({"date": date_str, "title": title})

    # Write index
    index = {"reports": reports, "lastUpdated": reports[0]["date"] if reports else None}
    index_path = SITE_DATA_DIR / "reports-index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Built {len(reports)} report(s) into {SITE_DATA_DIR}")
    for r in reports:
        print(f"  - {r['date']}: {r['title']}")


if __name__ == "__main__":
    build()
