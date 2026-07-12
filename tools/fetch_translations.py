#!/usr/bin/env python3
"""
Batch fetch Chinese translations and icons from paldb.cc for PST project.
Usage: python tools/fetch_translations.py [--pals] [--items] [--icons] [--dry-run]
"""

import json
import os
import re
import sys
import time
import argparse
from pathlib import Path
from urllib import request as url_request
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAL_JSON = PROJECT_ROOT / "web" / "src" / "assets" / "pal.json"
ITEMS_JSON = PROJECT_ROOT / "web" / "src" / "assets" / "items.json"
PALS_DIR = PROJECT_ROOT / "web" / "src" / "assets" / "pals"

PALDB_BASE = "https://paldb.cc"
ICON_BASE = "https://cdn.paldb.cc/image/Pal/Texture/PalIcon/Normal/T_{}_icon_normal.webp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def http_get(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = url_request.Request(url, headers=HEADERS)
            with url_request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError) as e:
            if attempt == retries:
                print(f"  FAIL: {url} -> {e}")
                return None
            time.sleep(1)


def fetch_cn_name(pal_id):
    """Fetch Chinese name from paldb.cc/cn/{PalID}."""
    url = f"{PALDB_BASE}/cn/{pal_id}"
    html = http_get(url)
    if not html:
        return None
    # Try to extract from <title> tag: "帕鲁ID 中文名 - PalDB"
    m = re.search(r"<title>\s*(?:[^<]+?\s+)?([^<\s-]+?)\s*-?\s*PalDB\s*</title>", html, re.I)
    if m:
        return m.group(1).strip()
    # Try h1
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I)
    if m:
        return m.group(1).strip()
    return None


def fetch_item_cn_name(item_id):
    """Fetch Chinese item name from paldb.cc/cn/{item_id}."""
    return fetch_cn_name(item_id)


def is_placeholder(name, pal_id=None):
    """Check if a name looks like an untranslated placeholder."""
    if not name:
        return True
    # Common patterns for placeholder translations
    if re.match(r"^[A-Z][a-z]+\(BOSS\)$", name):  # "ElecLion(BOSS)"
        return True
    if re.match(r"^[A-Z_]+$", name):  # ALL_CAPS_UNDERSCORED
        return True
    if name.endswith("_text") or "Text " in name:
        return True
    if name.startswith("en ") or name.startswith("en_text"):
        return True
    # Zh name is the same as the internal ID (PascalCase name) — untranslated
    if pal_id and name == pal_id:
        return True
    return False


def process_pals(dry_run=False):
    print("=" * 50)
    print("Processing pal.json...")
    print("=" * 50)

    with open(PAL_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    en_data = data.get("en", {})
    zh_data = data.get("zh", {})

    missing = []
    already_ok = 0
    for pal_id, en_name in sorted(en_data.items()):
        zh_name = zh_data.get(pal_id, "")
        if not zh_name or is_placeholder(zh_name, pal_id):
            missing.append(pal_id)
        else:
            already_ok += 1

    print(f"Total EN entries: {len(en_data)}")
    print(f"Already translated (zh): {already_ok}")
    print(f"Missing/placeholder: {len(missing)}")
    if missing:
        print("  Samples:", ", ".join(missing[:10]))

    if dry_run:
        print("\n[Dry-run] Would fetch translations for:")
        for pid in missing[:10]:
            print(f"  {pid}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        return

    fixed = 0
    for i, pal_id in enumerate(missing):
        print(f"[{i+1}/{len(missing)}] {pal_id}...", end=" ", flush=True)
        cn_name = fetch_cn_name(pal_id)
        if cn_name:
            # Clean up: remove " (BOSS)" suffix in zh if present for non-boss
            cn_name = cn_name.strip()
            zh_data[pal_id] = cn_name
            fixed += 1
            print(f"-> {cn_name}")
        else:
            print("(not found, keeping placeholder)")
        time.sleep(0.3)  # Rate limit

    # Save
    with open(PAL_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")
    print(f"\nFixed {fixed} translations. File saved.")


def process_items(dry_run=False):
    print("\n" + "=" * 50)
    print("Processing items.json...")
    print("=" * 50)

    with open(ITEMS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    en_items = {item["id"]: item for item in data.get("en", [])}
    zh_items = {item["id"]: item for item in data.get("zh", [])}

    missing = []
    already_ok = 0
    for item_id, en_item in sorted(en_items.items()):
        zh_item = zh_items.get(item_id)
        if not zh_item:
            missing.append(item_id)
            continue
        zh_name = zh_item.get("name", "")
        if not zh_name or is_placeholder(zh_name):
            missing.append(item_id)
        else:
            already_ok += 1

    print(f"Total EN entries: {len(en_items)}")
    print(f"Already translated (zh): {already_ok}")
    print(f"Missing/placeholder: {len(missing)}")

    if dry_run:
        print("\n[Dry-run] Would fetch translations for:")
        for item_id in missing[:10]:
            print(f"  {item_id}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        return

    fixed = 0
    for i, item_id in enumerate(missing):
        print(f"[{i+1}/{len(missing)}] {item_id}...", end=" ", flush=True)
        cn_name = fetch_item_cn_name(item_id)
        if cn_name:
            if item_id in zh_items:
                zh_items[item_id]["name"] = cn_name
            else:
                zh_items[item_id] = {
                    "id": item_id,
                    "name": cn_name,
                    "description": "",
                    "key": en_items[item_id]["key"] if item_id in en_items else item_id,
                }
            fixed += 1
            print(f"-> {cn_name}")
        else:
            print("(not found)")
        time.sleep(0.3)

    # Rebuild zh list preserving original order + new entries
    new_zh_list = []
    seen = set()
    for item in data.get("zh", []):
        item_id = item["id"]
        if item_id in zh_items:
            new_zh_list.append(zh_items[item_id])
            seen.add(item_id)
    for item_id, item in zh_items.items():
        if item_id not in seen:
            new_zh_list.append(item)
    data["zh"] = new_zh_list

    with open(ITEMS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\nFixed {fixed} translations. File saved.")


def fetch_icons(dry_run=False):
    print("\n" + "=" * 50)
    print("Fetching missing pal icons...")
    print("=" * 50)

    PALS_DIR.mkdir(parents=True, exist_ok=True)

    with open(PAL_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    en_data = data.get("en", {})
    existing = {p.stem.lower() for p in PALS_DIR.glob("*.png")}
    existing.update({p.stem.lower() for p in PALS_DIR.glob("*.webp")})

    # Only download for actual pal entries (exclude BOSS_, GYM_, RAID_, Arena_, etc.)
    pal_ids = []
    for pal_id in sorted(en_data.keys()):
        if pal_id.startswith(("BOSS_", "GYM_", "RAID_", "Arena_", "Quest_", "Believer_",
                               "Police_", "Male_", "Female_", "baker_", "baker0")):
            continue
        pal_ids.append(pal_id)

    missing = [pid for pid in pal_ids if pid.lower() not in existing]
    print(f"Total Pals: {len(pal_ids)}")
    print(f"Already have icons: {len(pal_ids) - len(missing)}")
    print(f"Missing icons: {len(missing)}")

    if dry_run:
        for pid in missing[:10]:
            print(f"  {pid}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        return

    downloaded = 0
    for i, pal_id in enumerate(missing):
        icon_url = ICON_BASE.format(pal_id)
        save_path = PALS_DIR / f"{pal_id.lower()}.webp"
        print(f"[{i+1}/{len(missing)}] {pal_id}...", end=" ", flush=True)
        try:
            req = url_request.Request(icon_url, headers=HEADERS)
            with url_request.urlopen(req, timeout=15) as r:
                img_data = r.read()
                if r.status == 200 and len(img_data) > 100:
                    with open(save_path, "wb") as f:
                        f.write(img_data)
                    downloaded += 1
                    print(f"OK ({len(img_data)} bytes)")
                else:
                    print(f"FAIL (empty/bad response)")
        except Exception as e:
            print(f"FAIL ({e})")
        time.sleep(0.2)

    print(f"\nDownloaded {downloaded} icons.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pals", action="store_true", help="Fetch pal translations")
    parser.add_argument("--items", action="store_true", help="Fetch item translations")
    parser.add_argument("--icons", action="store_true", help="Download missing pal icons")
    parser.add_argument("--all", action="store_true", help="Do everything")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    do_all = args.all or (not args.pals and not args.items and not args.icons)

    if do_all or args.pals:
        process_pals(dry_run=args.dry_run)
    if do_all or args.items:
        process_items(dry_run=args.dry_run)
    if do_all or args.icons:
        fetch_icons(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
